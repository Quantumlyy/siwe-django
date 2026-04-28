from __future__ import annotations

import pytest
from django.test import RequestFactory, override_settings

from siwe_django.audit import record_event
from siwe_django.models import SiweAuthEvent

from .helpers import post_json, signed_payload


def _request(*, ip: str = "203.0.113.1", ua: str = "test-ua/1.0"):
    factory = RequestFactory()
    return factory.get("/", REMOTE_ADDR=ip, HTTP_USER_AGENT=ua)


@pytest.mark.django_db
def test_record_event_persists_request_metadata():
    request = _request()

    event = record_event(
        request,
        SiweAuthEvent.EVENT_NONCE_ISSUED,
        metadata={"key": "value"},
    )

    assert event is not None
    assert event.event == SiweAuthEvent.EVENT_NONCE_ISSUED
    assert event.ip == "203.0.113.1"
    assert event.user_agent == "test-ua/1.0"
    assert event.success is True
    assert event.metadata == {"key": "value"}


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "AUDIT_ENABLED": False,
    }
)
def test_record_event_skipped_when_audit_disabled():
    assert record_event(_request(), SiweAuthEvent.EVENT_NONCE_ISSUED) is None
    assert SiweAuthEvent.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "RATE_LIMIT_TRUST_X_FORWARDED_FOR": True,
    }
)
def test_record_event_uses_x_forwarded_for_when_trusted():
    factory = RequestFactory()
    request = factory.get(
        "/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_FORWARDED_FOR="198.51.100.7, 10.0.0.1",
    )

    event = record_event(request, SiweAuthEvent.EVENT_NONCE_ISSUED)

    assert event is not None
    assert event.ip == "198.51.100.7"


@pytest.mark.django_db
def test_record_event_ignores_invalid_remote_addr():
    event = record_event(
        _request(ip="not-an-ip"),
        SiweAuthEvent.EVENT_NONCE_ISSUED,
    )

    assert event is not None
    assert event.ip is None


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "RATE_LIMIT_TRUST_X_FORWARDED_FOR": True,
    }
)
def test_record_event_ignores_invalid_x_forwarded_for():
    factory = RequestFactory()
    request = factory.get(
        "/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_FORWARDED_FOR="definitely-not-an-ip, 198.51.100.7",
    )

    event = record_event(request, SiweAuthEvent.EVENT_NONCE_ISSUED)

    assert event is not None
    assert event.ip is None


@pytest.mark.django_db
def test_nonce_endpoint_records_event(client):
    response = client.get("/siwe/nonce/")

    assert response.status_code == 200
    events = list(SiweAuthEvent.objects.all())
    assert len(events) == 1
    assert events[0].event == SiweAuthEvent.EVENT_NONCE_ISSUED


@pytest.mark.django_db
def test_verify_success_creates_audit_event(client, django_user_model):
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 200
    success_events = SiweAuthEvent.objects.filter(
        event=SiweAuthEvent.EVENT_VERIFY_SUCCESS
    )
    assert success_events.count() == 1
    event = success_events.get()
    assert event.address == payload["account"].address
    assert event.user is not None
    assert event.success is True


@pytest.mark.django_db
def test_verify_failure_creates_audit_event(client):
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": "garbage", "signature": "0x00"},
    )

    assert response.status_code != 200
    failure = SiweAuthEvent.objects.filter(
        event=SiweAuthEvent.EVENT_VERIFY_FAILURE
    ).get()
    assert failure.success is False
    assert failure.error_code  # any non-empty error code


@pytest.mark.django_db
def test_logout_records_event(client):
    payload = signed_payload(client)
    post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )
    SiweAuthEvent.objects.all().delete()

    response = client.post(
        "/siwe/logout/", content_type="application/json", data="{}"
    )

    assert response.status_code == 200
    assert SiweAuthEvent.objects.filter(event=SiweAuthEvent.EVENT_LOGOUT).exists()
