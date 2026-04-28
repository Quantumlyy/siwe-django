from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from django.test import override_settings

from siwe_django.webhooks import (
    SIGNATURE_HEADER,
    deliver,
    dispatch,
    event_payload,
    matching_subscriptions,
    sign_payload,
)


def test_sign_payload_uses_hmac_sha256():
    body = b'{"event":"verify_succeeded"}'
    secret = "shh"

    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert sign_payload(secret, body) == expected


@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "WEBHOOKS": [
            {"event": "verify_succeeded", "url": "https://a", "secret": "x"},
            {"event": "*", "url": "https://b", "secret": "y"},
            {"event": "verify_failed", "url": "https://c", "secret": "z"},
        ],
    }
)
def test_matching_subscriptions_includes_wildcards():
    matched = matching_subscriptions("verify_succeeded")

    urls = [m["url"] for m in matched]
    assert "https://a" in urls
    assert "https://b" in urls
    assert "https://c" not in urls


def test_event_payload_shape():
    payload = event_payload(
        "verify_succeeded",
        address="0xabc",
        user_id="42",
        metadata={"chain_id": 1},
    )

    assert payload == {
        "event": "verify_succeeded",
        "address": "0xabc",
        "user_id": "42",
        "success": True,
        "error_code": "",
        "metadata": {"chain_id": 1},
    }


def test_deliver_signs_body_and_posts(mocker):
    captured = {}

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["data"] = request.data
        captured["timeout"] = timeout
        return _Response()

    mocker.patch("siwe_django.webhooks.urlrequest.urlopen", side_effect=_urlopen)

    payload = event_payload("verify_succeeded", address="0xabc")
    ok = deliver({"url": "https://example.com", "secret": "xyz"}, payload)

    assert ok is True
    assert captured["url"] == "https://example.com"
    expected_body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    assert captured["data"] == expected_body
    expected_sig = sign_payload("xyz", expected_body)
    sig_value = next(
        v
        for k, v in captured["headers"].items()
        if k.lower() == SIGNATURE_HEADER.lower()
    )
    assert sig_value == expected_sig


def test_deliver_returns_false_when_url_or_secret_missing():
    assert deliver({"url": "", "secret": "x"}, {}) is False
    assert deliver({"url": "https://x", "secret": ""}, {}) is False


def test_deliver_returns_false_on_network_error(mocker):
    mocker.patch(
        "siwe_django.webhooks.urlrequest.urlopen",
        side_effect=OSError("boom"),
    )

    assert (
        deliver({"url": "https://x", "secret": "y"}, event_payload("e")) is False
    )


def test_deliver_returns_false_when_payload_not_json_serialisable(mocker):
    urlopen = mocker.patch("siwe_django.webhooks.urlrequest.urlopen")

    class _NotSerialisable:
        pass

    payload = {"event": "verify_succeeded", "metadata": {"obj": _NotSerialisable()}}

    assert deliver({"url": "https://x", "secret": "y"}, payload) is False
    assert urlopen.called is False


@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "WEBHOOKS": [
            {"event": "verify_succeeded", "url": "https://hook", "secret": "s"}
        ],
    }
)
def test_dispatch_calls_deliver_for_matching_subscriptions(mocker):
    mock_deliver = mocker.patch("siwe_django.webhooks.deliver", return_value=True)

    delivered = dispatch("verify_succeeded", event_payload("verify_succeeded"))

    assert delivered == 1
    assert mock_deliver.call_count == 1


@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "WEBHOOKS": [
            {"event": "verify_succeeded", "url": "https://hook", "secret": "s"}
        ],
        "WEBHOOK_DISPATCHER": "tests.test_webhooks.fake_dispatcher",
    }
)
def test_dispatch_respects_custom_dispatcher():
    fake_dispatcher.calls = []  # type: ignore[attr-defined]

    delivered = dispatch("verify_succeeded", event_payload("verify_succeeded"))

    assert delivered == 1
    assert len(fake_dispatcher.calls) == 1  # type: ignore[attr-defined]


def fake_dispatcher(event, payload, subscriptions):
    fake_dispatcher.calls.append((event, payload, subscriptions))


fake_dispatcher.calls = []  # type: ignore[attr-defined]


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "WEBHOOKS": [{"event": "*", "url": "https://hook", "secret": "s"}],
    }
)
def test_record_event_dispatches_webhook(mocker, django_user_model):
    mock_deliver = mocker.patch("siwe_django.webhooks.deliver", return_value=True)
    from django.test import RequestFactory

    from siwe_django.audit import record_event
    from siwe_django.models import SiweAuthEvent

    request = RequestFactory().get("/", REMOTE_ADDR="203.0.113.1")
    record_event(
        request,
        SiweAuthEvent.EVENT_VERIFY_SUCCESS,
        address="0xabc",
    )

    assert mock_deliver.called
    payload = mock_deliver.call_args.args[1]
    assert payload["event"] == SiweAuthEvent.EVENT_VERIFY_SUCCESS
    assert payload["address"] == "0xabc"
