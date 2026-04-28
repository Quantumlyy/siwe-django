from __future__ import annotations

from rest_framework import serializers


class SiweVerifySerializer(serializers.Serializer):
    message = serializers.CharField()
    signature = serializers.CharField()


class WalletSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    address = serializers.CharField()
    chainId = serializers.IntegerField()
    caip10 = serializers.CharField()
    ensName = serializers.CharField(allow_blank=True)
    ensAvatar = serializers.CharField(allow_blank=True)
    displayName = serializers.CharField(allow_blank=True)
    avatar = serializers.CharField(allow_blank=True)
    profile = serializers.DictField()
    ethereumIdentityKit = serializers.DictField()
    isPrimary = serializers.BooleanField()
    lastLogin = serializers.CharField(allow_null=True)
