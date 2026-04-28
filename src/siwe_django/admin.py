from django.contrib import admin

from .models import EthereumUser, SiweNonce, SiweWallet


@admin.register(EthereumUser)
class EthereumUserAdmin(admin.ModelAdmin):
    list_display = (
        "ethereum_address",
        "chain_id",
        "identity_display_name",
        "ens_name",
        "followers_count",
        "following_count",
        "is_active",
        "is_staff",
    )
    search_fields = ("ethereum_address", "identity_display_name", "ens_name")
    list_filter = ("is_active", "is_staff", "chain_id")


@admin.register(SiweWallet)
class SiweWalletAdmin(admin.ModelAdmin):
    list_display = (
        "address",
        "chain_id",
        "user",
        "is_primary",
        "identity_display_name",
        "ens_name",
        "followers_count",
        "following_count",
        "last_login",
    )
    search_fields = (
        "address",
        "caip10",
        "identity_display_name",
        "ens_name",
        "user__pk",
    )
    list_filter = ("chain_id", "is_primary")
    readonly_fields = ("caip10", "created_at", "updated_at", "last_login")


@admin.register(SiweNonce)
class SiweNonceAdmin(admin.ModelAdmin):
    list_display = ("nonce", "session_key", "expires_at", "consumed_at", "created_at")
    search_fields = ("nonce", "session_key")
    list_filter = ("expires_at", "consumed_at")
    readonly_fields = ("nonce", "created_at")
