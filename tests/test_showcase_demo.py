from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings

from siwe_django.models import SiweWallet

DEMO_BACKEND = Path(__file__).resolve().parents[1] / "examples" / "showcase" / "backend"
if str(DEMO_BACKEND) not in sys.path:
    sys.path.insert(0, str(DEMO_BACKEND))

from showcase import settings as demo_settings  # noqa: E402


@pytest.fixture
def demo_urls_settings():
    with override_settings(
        ROOT_URLCONF="showcase.urls",
        SIWE_DJANGO=deepcopy(demo_settings.SIWE_DJANGO),
    ):
        yield


def test_showcase_settings_import():
    assert demo_settings.SIWE_DJANGO["DOMAIN"] == "localhost:5173"
    assert demo_settings.SIWE_DJANGO["URI"] == "http://localhost:5173"
    assert demo_settings.SIWE_DJANGO["TOKEN_GATES"][0]["group"] == "demo-holders"


def test_showcase_settings_derive_fly_defaults(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "siwe-django-showcase")

    assert demo_settings._default_public_host() == "siwe-django-showcase.fly.dev"
    assert (
        demo_settings._default_public_origin()
        == "https://siwe-django-showcase.fly.dev"
    )
    assert "siwe-django-showcase.fly.dev" in demo_settings._default_allowed_hosts()
    assert (
        "https://siwe-django-showcase.fly.dev"
        in demo_settings._default_csrf_trusted_origins()
    )


@pytest.mark.django_db
def test_showcase_urls_issue_nonce(client, demo_urls_settings):
    response = client.get("/auth/siwe/nonce/")

    assert response.status_code == 200
    assert response.json()["domain"] == "localhost:5173"


@pytest.mark.django_db
def test_showcase_session_unauthenticated(client, demo_urls_settings):
    response = client.get("/api/showcase/session/")

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["wallets"] == []
    assert body["gates"][0]["name"] == "demo-holders"
    assert body["gates"][0]["active"] is False


@pytest.mark.django_db
def test_showcase_session_authenticated_syncs_demo_gate(
    client,
    django_user_model,
    settings,
    demo_urls_settings,
):
    user = django_user_model.objects.create_user(username="demo")
    wallet = SiweWallet.objects.create(
        user=user,
        address="0x0000000000000000000000000000000000000001",
        chain_id=1,
        is_primary=True,
    )
    settings.SIWE_DJANGO["TOKEN_GATES"][0]["addresses"] = [wallet.address]
    client.force_login(user)

    response = client.get("/api/showcase/session/")

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["wallet"]["address"] == wallet.address
    assert body["groups"] == ["demo-holders"]
    assert body["gates"][0]["active"] is True
    assert Group.objects.filter(name="demo-holders").exists()
    assert user.groups.filter(name="demo-holders").exists()
