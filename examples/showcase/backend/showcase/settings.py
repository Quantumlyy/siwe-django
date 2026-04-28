from __future__ import annotations

import os
from pathlib import Path

from .gates import demo_holder_addresses

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parents[2]

SECRET_KEY = os.getenv("SIWE_DEMO_SECRET_KEY", "siwe-django-showcase-dev-key")
DEBUG = os.getenv("SIWE_DEMO_DEBUG", "true").lower() in {"1", "true", "yes"}

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "siwe_django",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "showcase.urls"
WSGI_APPLICATION = "showcase.wsgi.application"
ASGI_APPLICATION = "showcase.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTHENTICATION_BACKENDS = [
    "siwe_django.backend.SiweBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


def _rpc_urls() -> dict[int, str]:
    urls: dict[int, str] = {}
    for chain_id in (1, 11155111, 31337):
        value = os.getenv(f"SIWE_DEMO_RPC_URL_{chain_id}")
        if value:
            urls[chain_id] = value
    return urls


SIWE_DJANGO = {
    "DOMAIN": "localhost:5173",
    "URI": "http://localhost:5173/",
    "STATEMENT": "Sign in to the siwe-django showcase.",
    "ALLOWED_CHAIN_IDS": [1, 11155111, 31337],
    "AUTO_CREATE_USERS": True,
    "USER_FACTORY": "showcase.auth.demo_user_factory",
    "ENS_ENABLED": bool(os.getenv("SIWE_DEMO_ENS_RPC_URL")),
    "ENS_RPC_URL": os.getenv("SIWE_DEMO_ENS_RPC_URL"),
    "ETHID_ENABLED": os.getenv("SIWE_DEMO_ETHID_ENABLED", "true").lower()
    in {"1", "true", "yes"},
    "ETHID_PROFILE_PROXY_ENABLED": True,
    "RPC_URLS": _rpc_urls(),
    "TOKEN_GATES": [
        {
            "name": "demo-holders",
            "label": "Demo holders",
            "description": "Local allow-list gate for testing group sync.",
            "type": "custom",
            "checker": "showcase.gates.demo_holder_gate",
            "group": "demo-holders",
            "addresses": demo_holder_addresses(),
        }
    ],
    "SYNC_TOKEN_GATES_ON_LOGIN": True,
}
