"""Pluggable nonce storage.

The default backend is the existing :class:`siwe_django.models.SiweNonce`
table. Apps that want sub-millisecond reads or that want nonces to live
outside the primary DB can swap in :class:`RedisNonceStore` (or anything
else implementing :class:`NonceStore`) by setting
``SIWE_DJANGO["NONCE_STORE"]``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from django.utils import timezone
from django.utils.module_loading import import_string

from .settings import get_setting

if TYPE_CHECKING:
    from .models import SiweNonce


@dataclass(frozen=True)
class NonceRecord:
    nonce: str
    expires_at: datetime
    session_key: str = ""
    domain: str = ""
    uri: str = ""
    not_before: datetime | None = None
    request_id: str = ""
    resources: list[str] = field(default_factory=list)
    consumed_at: datetime | None = None

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_usable_for_session(self, session_key: str | None) -> bool:
        if self.is_consumed or self.is_expired:
            return False
        return not (self.session_key and self.session_key != (session_key or ""))


class NonceStore(Protocol):
    def save(
        self,
        *,
        nonce: str,
        expires_at: datetime,
        session_key: str = "",
        domain: str = "",
        uri: str = "",
        not_before: datetime | None = None,
        request_id: str = "",
        resources: Iterable[str] = (),
    ) -> NonceRecord: ...

    def load(self, nonce: str) -> NonceRecord | None: ...

    def consume(self, nonce: str) -> bool: ...


# -----------------------------------------------------------------------------
# Django ORM backend (default)
# -----------------------------------------------------------------------------


class DjangoOrmNonceStore:
    """Default backend backed by the :class:`SiweNonce` model."""

    @staticmethod
    def _to_record(model: SiweNonce) -> NonceRecord:
        return NonceRecord(
            nonce=model.nonce,
            session_key=model.session_key,
            domain=model.domain,
            uri=model.uri,
            expires_at=model.expires_at,
            not_before=model.not_before,
            request_id=model.request_id,
            resources=list(model.resources or []),
            consumed_at=model.consumed_at,
        )

    def save(
        self,
        *,
        nonce: str,
        expires_at: datetime,
        session_key: str = "",
        domain: str = "",
        uri: str = "",
        not_before: datetime | None = None,
        request_id: str = "",
        resources: Iterable[str] = (),
    ) -> NonceRecord:
        from .models import SiweNonce

        model = SiweNonce.objects.create(
            nonce=nonce,
            session_key=session_key,
            domain=domain,
            uri=uri,
            expires_at=expires_at,
            not_before=not_before,
            request_id=request_id,
            resources=list(resources),
        )
        return self._to_record(model)

    def load(self, nonce: str) -> NonceRecord | None:
        from .models import SiweNonce

        model = SiweNonce.objects.filter(nonce=nonce).first()
        return self._to_record(model) if model else None

    def consume(self, nonce: str) -> bool:
        from .models import SiweNonce

        return (
            SiweNonce.objects.filter(
                nonce=nonce,
                consumed_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).update(consumed_at=timezone.now())
            == 1
        )


# -----------------------------------------------------------------------------
# Redis backend (optional)
# -----------------------------------------------------------------------------


class RedisNonceStore:
    """Redis-backed store. Uses ``SET NX EX`` for save and atomic delete for
    consume; replay protection is enforced because the second consumer's
    delete returns 0.

    The ``client`` argument can be a ``redis.Redis`` instance or any object
    matching the ``set`` / ``get`` / ``delete`` shape. If unset, the store
    instantiates one from ``REDIS_URL`` in settings.
    """

    def __init__(self, client: Any | None = None, *, key_prefix: str = "siwe-nonce:"):
        self.key_prefix = key_prefix
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import redis  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "RedisNonceStore requires `redis-py`. Install via the "
                "`siwe-django[redis]` extra."
            ) from exc
        url = get_setting("REDIS_URL") or "redis://localhost:6379/0"
        self._client = redis.Redis.from_url(url, decode_responses=True)
        return self._client

    def _key(self, nonce: str) -> str:
        return f"{self.key_prefix}{nonce}"

    def _payload(self, record: NonceRecord) -> str:
        data = asdict(record)
        data["expires_at"] = record.expires_at.isoformat()
        data["not_before"] = (
            record.not_before.isoformat() if record.not_before else None
        )
        return json.dumps(data)

    def _from_payload(self, raw: str) -> NonceRecord:
        data = json.loads(raw)
        expires_at = datetime.fromisoformat(data["expires_at"])
        not_before = (
            datetime.fromisoformat(data["not_before"])
            if data.get("not_before")
            else None
        )
        consumed_at_raw = data.get("consumed_at")
        consumed_at = (
            datetime.fromisoformat(consumed_at_raw) if consumed_at_raw else None
        )
        return NonceRecord(
            nonce=data["nonce"],
            session_key=data.get("session_key", ""),
            domain=data.get("domain", ""),
            uri=data.get("uri", ""),
            expires_at=expires_at,
            not_before=not_before,
            request_id=data.get("request_id", ""),
            resources=list(data.get("resources") or []),
            consumed_at=consumed_at,
        )

    def save(
        self,
        *,
        nonce: str,
        expires_at: datetime,
        session_key: str = "",
        domain: str = "",
        uri: str = "",
        not_before: datetime | None = None,
        request_id: str = "",
        resources: Iterable[str] = (),
    ) -> NonceRecord:
        record = NonceRecord(
            nonce=nonce,
            expires_at=expires_at,
            session_key=session_key,
            domain=domain,
            uri=uri,
            not_before=not_before,
            request_id=request_id,
            resources=list(resources),
        )
        ttl = max(int((expires_at - timezone.now()).total_seconds()), 1)
        self.client.set(self._key(nonce), self._payload(record), ex=ttl, nx=True)
        return record

    def load(self, nonce: str) -> NonceRecord | None:
        raw = self.client.get(self._key(nonce))
        if not raw:
            return None
        return self._from_payload(raw)

    def consume(self, nonce: str) -> bool:
        deleted = self.client.delete(self._key(nonce))
        try:
            return int(deleted) == 1
        except (TypeError, ValueError):
            return bool(deleted)


# -----------------------------------------------------------------------------
# Resolver
# -----------------------------------------------------------------------------


def get_nonce_store() -> NonceStore:
    """Resolve the configured nonce store. Caches nothing — apps that pin a
    store instance should do so via Django's app config or an LRU cache.
    """
    dotted = get_setting("NONCE_STORE")
    if not dotted:
        return DjangoOrmNonceStore()
    cls_or_factory = import_string(dotted)
    return cls_or_factory()
