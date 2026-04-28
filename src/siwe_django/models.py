from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    Group,
    Permission,
    PermissionsMixin,
)
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from web3 import Web3


def checksum_address(address: str) -> str:
    if not Web3.is_address(address):
        raise ValidationError("Enter a valid Ethereum address.")
    return Web3.to_checksum_address(address)


def caip10_subject(chain_id: int, address: str) -> str:
    return f"eip155:{int(chain_id)}:{checksum_address(address)}"


def validate_ethereum_address(value: str) -> None:
    checksum_address(value)


class EthereumUserManager(BaseUserManager):
    def create_user(self, ethereum_address: str, password: str | None = None, **extra):
        if not ethereum_address:
            raise ValueError("Ethereum users require an ethereum_address.")
        user = self.model(ethereum_address=checksum_address(ethereum_address), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self, ethereum_address: str, password: str | None = None, **extra
    ):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(ethereum_address, password, **extra)


class AbstractEthereumUser(AbstractBaseUser, PermissionsMixin):
    ethereum_address = models.CharField(
        max_length=42,
        unique=True,
        validators=[validate_ethereum_address],
    )
    chain_id = models.PositiveIntegerField(default=1)
    ens_name = models.CharField(max_length=255, blank=True)
    ens_avatar = models.URLField(max_length=1024, blank=True)
    ens_description = models.TextField(blank=True)
    ens_header = models.URLField(max_length=1024, blank=True)
    ens_records = models.JSONField(default=dict, blank=True)
    identity_display_name = models.CharField(max_length=255, blank=True)
    identity_avatar = models.URLField(max_length=1024, blank=True)
    identity_url = models.URLField(max_length=1024, blank=True)
    identity_profile = models.JSONField(default=dict, blank=True)
    followers_count = models.PositiveIntegerField(default=0)
    following_count = models.PositiveIntegerField(default=0)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="siwe_ethereum_users",
        related_query_name="siwe_ethereum_user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="siwe_ethereum_users",
        related_query_name="siwe_ethereum_user",
    )

    USERNAME_FIELD = "ethereum_address"
    REQUIRED_FIELDS: list[str] = []

    objects = EthereumUserManager()

    class Meta:
        abstract = True

    @property
    def caip10_subject(self) -> str:
        return caip10_subject(self.chain_id, self.ethereum_address)

    def clean(self) -> None:
        super().clean()
        self.ethereum_address = checksum_address(self.ethereum_address)

    def save(self, *args, **kwargs):
        self.ethereum_address = checksum_address(self.ethereum_address)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.ethereum_address


class EthereumUser(AbstractEthereumUser):
    class Meta:
        verbose_name = "Ethereum user"
        verbose_name_plural = "Ethereum users"


class SiweWallet(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="siwe_wallets",
    )
    address = models.CharField(max_length=42, validators=[validate_ethereum_address])
    chain_id = models.PositiveIntegerField()
    caip10 = models.CharField(max_length=128, editable=False)
    ens_name = models.CharField(max_length=255, blank=True)
    ens_avatar = models.URLField(max_length=1024, blank=True)
    ens_description = models.TextField(blank=True)
    ens_header = models.URLField(max_length=1024, blank=True)
    ens_records = models.JSONField(default=dict, blank=True)
    identity_display_name = models.CharField(max_length=255, blank=True)
    identity_avatar = models.URLField(max_length=1024, blank=True)
    identity_url = models.URLField(max_length=1024, blank=True)
    identity_profile = models.JSONField(default=dict, blank=True)
    followers_count = models.PositiveIntegerField(default=0)
    following_count = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-is_primary", "chain_id", "address"]
        constraints = [
            models.UniqueConstraint(
                fields=["chain_id", "address"],
                name="siwe_wallet_unique_chain_address",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_primary=True),
                name="siwe_wallet_one_primary_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "chain_id"]),
            models.Index(fields=["caip10"]),
        ]

    def clean(self) -> None:
        super().clean()
        self.address = checksum_address(self.address)
        self.caip10 = caip10_subject(self.chain_id, self.address)

    def save(self, *args, **kwargs):
        self.address = checksum_address(self.address)
        self.caip10 = caip10_subject(self.chain_id, self.address)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.caip10


class SiweNonce(models.Model):
    nonce = models.CharField(max_length=128, primary_key=True)
    session_key = models.CharField(max_length=64, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    uri = models.URLField(max_length=2048, blank=True)
    expires_at = models.DateTimeField()
    not_before = models.DateTimeField(blank=True, null=True)
    request_id = models.CharField(max_length=255, blank=True)
    resources = models.JSONField(default=list, blank=True)
    consumed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["expires_at"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["consumed_at"]),
        ]

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

    def consume(self) -> None:
        if self.consumed_at is None:
            self.consumed_at = timezone.now()
            self.save(update_fields=["consumed_at"])

    def __str__(self) -> str:
        return self.nonce
