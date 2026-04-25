from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from siwe import SiweMessage, VerificationError, generate_nonce
from web3 import HTTPProvider

from .ens import resolve_ens_profile
from .gates import sync_wallet_groups
from .models import SiweNonce, SiweWallet, caip10_subject, checksum_address
from .settings import allowed_chain_ids, get_setting


class SiweAuthError(Exception):
    status_code = 400
    code = "siwe_error"

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class InvalidNonce(SiweAuthError):
    status_code = 401
    code = "invalid_nonce"


class InvalidSignature(SiweAuthError):
    status_code = 401
    code = "invalid_signature"


class WalletConflict(SiweAuthError):
    status_code = 409
    code = "wallet_conflict"


class UserCreationDisabled(SiweAuthError):
    status_code = 403
    code = "user_creation_disabled"


class InactiveUser(SiweAuthError):
    status_code = 401
    code = "inactive_user"


@dataclass(frozen=True)
class SiweIdentity:
    address: str
    chain_id: int
    caip10: str
    ens_name: str = ""
    ens_avatar: str = ""


@dataclass(frozen=True)
class SiweAuthResult:
    user: Any
    wallet: SiweWallet
    identity: SiweIdentity


def _ensure_session_key(request) -> str:
    if request.session.session_key is None:
        request.session.create()
    return request.session.session_key


def request_domain(request) -> str:
    return get_setting("DOMAIN") or request.get_host()


def request_uri(request) -> str:
    configured = get_setting("URI")
    if configured:
        return configured
    return request.build_absolute_uri("/")


def issue_nonce(request=None) -> SiweNonce:
    ttl = int(get_setting("NONCE_TTL_SECONDS"))
    session_key = _ensure_session_key(request) if request is not None else ""
    domain = (
        request_domain(request)
        if request is not None
        else (get_setting("DOMAIN") or "")
    )
    uri = request_uri(request) if request is not None else (get_setting("URI") or "")
    return SiweNonce.objects.create(
        nonce=generate_nonce(),
        session_key=session_key or "",
        domain=domain,
        uri=uri,
        expires_at=timezone.now() + timezone.timedelta(seconds=ttl),
    )


def _provider_for_chain(chain_id: int) -> HTTPProvider | None:
    rpc_urls = get_setting("RPC_URLS") or {}
    rpc_url = None
    if isinstance(rpc_urls, dict):
        rpc_url = rpc_urls.get(chain_id) or rpc_urls.get(str(chain_id))
    return HTTPProvider(rpc_url) if rpc_url else None


def _session_key(request) -> str:
    if request is None:
        return ""
    return request.session.session_key or ""


def _load_nonce(message_nonce: str, request=None) -> SiweNonce:
    try:
        nonce = SiweNonce.objects.get(nonce=message_nonce)
    except SiweNonce.DoesNotExist as exc:
        raise InvalidNonce("Invalid or expired SIWE nonce.") from exc
    if not nonce.is_usable_for_session(_session_key(request)):
        raise InvalidNonce("Invalid or expired SIWE nonce.")
    return nonce


def _consume_nonce(nonce: SiweNonce) -> None:
    updated = SiweNonce.objects.filter(
        nonce=nonce.nonce,
        consumed_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).update(consumed_at=timezone.now())
    if updated != 1:
        raise InvalidNonce("SIWE nonce has already been used.")


def verify_siwe_message(message: str, signature: str, request=None) -> SiweIdentity:
    try:
        siwe_message = SiweMessage.from_message(message)
    except Exception as exc:
        raise InvalidSignature("Invalid SIWE message.") from exc

    chain_id = int(siwe_message.chain_id)
    allowed = allowed_chain_ids()
    if allowed is not None and chain_id not in allowed:
        raise InvalidSignature("SIWE chain is not allowed.")

    nonce = _load_nonce(str(siwe_message.nonce), request)
    expected_domain = nonce.domain or (request_domain(request) if request else None)
    expected_uri = nonce.uri or (request_uri(request) if request else None)

    try:
        siwe_message.verify(
            signature,
            domain=expected_domain,
            uri=expected_uri,
            chain_id=chain_id,
            nonce=nonce.nonce,
            provider=_provider_for_chain(chain_id),
            strict=True,
        )
    except VerificationError as exc:
        raise InvalidSignature("Invalid SIWE signature or message.") from exc

    _consume_nonce(nonce)
    address = checksum_address(siwe_message.address)
    ens_profile = resolve_ens_profile(address)
    return SiweIdentity(
        address=address,
        chain_id=chain_id,
        caip10=caip10_subject(chain_id, address),
        ens_name=ens_profile.name,
        ens_avatar=ens_profile.avatar,
    )


def default_user_factory(identity: SiweIdentity, request=None):
    UserModel = get_user_model()
    username_field = UserModel.USERNAME_FIELD
    manager = UserModel._default_manager

    if username_field == "ethereum_address":
        existing = manager.filter(ethereum_address=identity.address).first()
        if existing:
            return existing
        return manager.create_user(ethereum_address=identity.address)

    if username_field == "email":
        value = f"{identity.address.lower()}@ethereum.local"
    else:
        value = f"siwe_{identity.chain_id}_{identity.address[2:].lower()}"

    field = UserModel._meta.get_field(username_field)
    max_length = getattr(field, "max_length", None)
    if max_length:
        value = value[:max_length]

    existing = manager.filter(**{username_field: value}).first()
    if existing:
        return existing
    return manager.create_user(**{username_field: value})


def _user_factory():
    return import_string(get_setting("USER_FACTORY"))


def _update_user_identity_fields(user, identity: SiweIdentity) -> None:
    changed = []
    for field, value in (
        ("ethereum_address", identity.address),
        ("chain_id", identity.chain_id),
        ("ens_name", identity.ens_name),
        ("ens_avatar", identity.ens_avatar),
    ):
        if hasattr(user, field) and value and getattr(user, field) != value:
            setattr(user, field, value)
            changed.append(field)
    if changed:
        user.save(update_fields=changed)


def _create_wallet(user, identity: SiweIdentity) -> SiweWallet:
    is_primary = not SiweWallet.objects.filter(user=user).exists()
    return SiweWallet.objects.create(
        user=user,
        address=identity.address,
        chain_id=identity.chain_id,
        ens_name=identity.ens_name,
        ens_avatar=identity.ens_avatar,
        is_primary=is_primary,
        last_login=timezone.now(),
    )


def _update_wallet(wallet: SiweWallet, identity: SiweIdentity) -> SiweWallet:
    wallet.last_login = timezone.now()
    wallet.ens_name = identity.ens_name or wallet.ens_name
    wallet.ens_avatar = identity.ens_avatar or wallet.ens_avatar
    wallet.save(update_fields=["last_login", "ens_name", "ens_avatar", "updated_at"])
    return wallet


def authenticate_siwe(message: str, signature: str, request=None) -> SiweAuthResult:
    identity = verify_siwe_message(message, signature, request)
    wallet = (
        SiweWallet.objects.filter(
            address=identity.address,
            chain_id=identity.chain_id,
        )
        .select_related("user")
        .first()
    )

    if wallet is None:
        if not get_setting("AUTO_CREATE_USERS"):
            raise UserCreationDisabled("No user is linked to this wallet.")
        user = _user_factory()(identity=identity, request=request)
        wallet = _create_wallet(user, identity)
    else:
        user = wallet.user
        wallet = _update_wallet(wallet, identity)

    if not getattr(user, "is_active", True):
        raise InactiveUser("User is inactive.")

    _update_user_identity_fields(user, identity)
    if get_setting("SYNC_TOKEN_GATES_ON_LOGIN"):
        sync_wallet_groups(wallet)
    return SiweAuthResult(user=user, wallet=wallet, identity=identity)


def link_siwe_wallet(user, message: str, signature: str, request=None) -> SiweWallet:
    identity = verify_siwe_message(message, signature, request)
    with transaction.atomic():
        existing = (
            SiweWallet.objects.select_for_update()
            .filter(address=identity.address, chain_id=identity.chain_id)
            .first()
        )
        if existing and existing.user_id != user.pk:
            raise WalletConflict("Wallet is already linked to another user.")
        if existing:
            return _update_wallet(existing, identity)
        try:
            wallet = _create_wallet(user, identity)
        except IntegrityError as exc:
            raise WalletConflict("Wallet is already linked.") from exc
    if get_setting("SYNC_TOKEN_GATES_ON_LOGIN"):
        sync_wallet_groups(wallet)
    return wallet


def unlink_wallet(user, wallet_id: int) -> None:
    try:
        wallet = SiweWallet.objects.get(pk=wallet_id, user=user)
    except ObjectDoesNotExist as exc:
        raise SiweAuthError("Wallet not found.", status_code=404) from exc
    was_primary = wallet.is_primary
    wallet.delete()
    if was_primary:
        next_wallet = SiweWallet.objects.filter(user=user).first()
        if next_wallet:
            next_wallet.is_primary = True
            next_wallet.save(update_fields=["is_primary"])


def serialize_user(user) -> dict[str, Any]:
    return {
        "id": str(user.pk),
        "isAuthenticated": bool(getattr(user, "is_authenticated", False)),
        "username": getattr(user, "get_username", lambda: "")(),
    }


def serialize_wallet(wallet: SiweWallet) -> dict[str, Any]:
    return {
        "id": wallet.pk,
        "address": wallet.address,
        "chainId": wallet.chain_id,
        "caip10": wallet.caip10,
        "ensName": wallet.ens_name,
        "ensAvatar": wallet.ens_avatar,
        "isPrimary": wallet.is_primary,
        "lastLogin": wallet.last_login.isoformat() if wallet.last_login else None,
    }


def primary_wallet_for_user(user) -> SiweWallet | None:
    return SiweWallet.objects.filter(user=user, is_primary=True).first()
