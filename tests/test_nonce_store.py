from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.test import override_settings

from siwe_django.nonce_store import (
    DjangoOrmNonceStore,
    NonceRecord,
    RedisNonceStore,
    get_nonce_store,
)


def _future(seconds: int = 300) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(seconds=seconds)


# -----------------------------------------------------------------------------
# DjangoOrmNonceStore
# -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_orm_store_round_trips_record():
    store = DjangoOrmNonceStore()

    record = store.save(
        nonce="abc123",
        expires_at=_future(),
        domain="example.com",
        request_id="req-1",
        resources=["https://example.com/scope"],
    )
    loaded = store.load("abc123")

    assert isinstance(record, NonceRecord)
    assert loaded == record


@pytest.mark.django_db
def test_orm_store_load_missing_returns_none():
    store = DjangoOrmNonceStore()

    assert store.load("does-not-exist") is None


@pytest.mark.django_db
def test_orm_store_consume_is_atomic_single_use():
    store = DjangoOrmNonceStore()
    store.save(nonce="once", expires_at=_future())

    assert store.consume("once") is True
    assert store.consume("once") is False


@pytest.mark.django_db
def test_orm_store_consume_rejects_expired():
    store = DjangoOrmNonceStore()
    store.save(
        nonce="expired", expires_at=datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    )

    assert store.consume("expired") is False


# -----------------------------------------------------------------------------
# RedisNonceStore
# -----------------------------------------------------------------------------


class _FakeRedisClient:
    """Minimal in-memory stand-in supporting the subset of redis-py we use."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    def get(self, key):
        return self._store.get(key)

    def delete(self, key):
        existed = key in self._store
        self._store.pop(key, None)
        return 1 if existed else 0


def test_redis_store_round_trips_record():
    client = _FakeRedisClient()
    store = RedisNonceStore(client=client)

    saved = store.save(
        nonce="r-1",
        expires_at=_future(),
        domain="example.com",
        not_before=datetime(2026, 4, 28, tzinfo=timezone.utc),
        request_id="req-2",
        resources=["https://example.com"],
    )
    loaded = store.load("r-1")

    assert loaded is not None
    assert loaded.nonce == saved.nonce
    assert loaded.domain == saved.domain
    assert loaded.not_before == saved.not_before
    assert loaded.request_id == saved.request_id
    assert loaded.resources == saved.resources


def test_redis_store_load_missing_returns_none():
    store = RedisNonceStore(client=_FakeRedisClient())
    assert store.load("missing") is None


def test_redis_store_consume_is_single_use():
    client = _FakeRedisClient()
    store = RedisNonceStore(client=client)
    store.save(nonce="single", expires_at=_future())

    assert store.consume("single") is True
    assert store.consume("single") is False


def test_redis_store_save_uses_nx_to_prevent_overwrite():
    client = _FakeRedisClient()
    store = RedisNonceStore(client=client)
    store.save(nonce="nx", expires_at=_future(), domain="first.example.com")
    store.save(nonce="nx", expires_at=_future(), domain="second.example.com")

    loaded = store.load("nx")
    assert loaded is not None
    assert loaded.domain == "first.example.com"


# -----------------------------------------------------------------------------
# get_nonce_store resolution
# -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_nonce_store_default_is_orm():
    store = get_nonce_store()

    assert isinstance(store, DjangoOrmNonceStore)


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "NONCE_STORE": "tests.test_nonce_store.RedisStoreFactory",
    }
)
def test_get_nonce_store_honours_dotted_path():
    store = get_nonce_store()

    assert isinstance(store, RedisNonceStore)


def RedisStoreFactory() -> RedisNonceStore:
    return RedisNonceStore(client=_FakeRedisClient())
