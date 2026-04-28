from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from siwe_django.models import SiweAuthEvent
from siwe_django.stepup import (
    SESSION_KEY,
    has_recent_siwe,
    mark_recent_siwe,
    require_recent_siwe,
)

from .helpers import post_json, signed_payload


def _request_with_session():
    request = RequestFactory().get("/")
    from django.contrib.sessions.backends.db import SessionStore

    session = SessionStore()
    session.create()
    request.session = session
    return request


@pytest.mark.django_db
def test_mark_and_has_recent_siwe():
    request = _request_with_session()

    assert has_recent_siwe(request, seconds=300) is False
    mark_recent_siwe(request)
    assert has_recent_siwe(request, seconds=300) is True


@pytest.mark.django_db
def test_has_recent_siwe_returns_false_when_stale():
    request = _request_with_session()
    stale = datetime.now(tz=timezone.utc) - timedelta(seconds=600)
    request.session[SESSION_KEY] = stale.isoformat()

    assert has_recent_siwe(request, seconds=300) is False


@pytest.mark.django_db
def test_has_recent_siwe_handles_garbage():
    request = _request_with_session()
    request.session[SESSION_KEY] = "not-a-date"

    assert has_recent_siwe(request, seconds=300) is False


@pytest.mark.django_db
def test_require_recent_siwe_blocks_when_missing():
    @require_recent_siwe(seconds=300)
    def view(request):
        return HttpResponse("ok")

    response = view(_request_with_session())

    assert response.status_code == 403
    assert b"stepup_required" in response.content


@pytest.mark.django_db
def test_require_recent_siwe_allows_when_fresh():
    @require_recent_siwe(seconds=300)
    def view(request):
        return HttpResponse("ok")

    request = _request_with_session()
    mark_recent_siwe(request)

    response = view(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_verify_endpoint_marks_recent_siwe(client):
    payload = signed_payload(client)
    post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert SESSION_KEY in client.session


@pytest.mark.django_db
def test_reauth_endpoint_requires_authenticated_user(client):
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/reauth/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_reauth_endpoint_succeeds_for_linked_wallet(client):
    payload = signed_payload(client)
    post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )
    session = client.session
    session[SESSION_KEY] = (
        datetime.now(tz=timezone.utc) - timedelta(seconds=600)
    ).isoformat()
    session.save()
    fresh = signed_payload(client, account=payload["account"])

    response = post_json(
        client,
        "/siwe/reauth/",
        {"message": fresh["message"], "signature": fresh["signature"]},
    )

    assert response.status_code == 200, response.content
    assert response.json()["address"] == payload["account"].address
    assert SESSION_KEY in client.session


@pytest.mark.django_db
def test_reauth_endpoint_rejects_other_wallet(client):
    payload = signed_payload(client)
    post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )
    other = signed_payload(client)

    response = post_json(
        client,
        "/siwe/reauth/",
        {"message": other["message"], "signature": other["signature"]},
    )

    assert response.status_code == 403
    assert response.json()["error"] == "wallet_not_linked"
    failure = SiweAuthEvent.objects.filter(
        event=SiweAuthEvent.EVENT_VERIFY_FAILURE,
        error_code="wallet_not_linked",
    ).get()
    assert failure.address == other["account"].address
    assert failure.success is False
    assert failure.metadata == {"stepup": True}
