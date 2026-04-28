from __future__ import annotations

import os
from pathlib import Path

from .gates import demo_holder_addresses

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parents[2]


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes"}


def _csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.getenv("SIWE_DEMO_SECRET_KEY", "siwe-django-showcase-dev-key")
DEBUG = _bool("SIWE_DEMO_DEBUG", "true")

ALLOWED_HOSTS = _csv(
    "SIWE_DEMO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
)
CSRF_TRUSTED_ORIGINS = _csv(
    "SIWE_DEMO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "siwe_django",
]

try:
    import whitenoise  # noqa: F401

    _HAS_WHITENOISE = True
except ImportError:
    _HAS_WHITENOISE = False

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    *(
        ["whitenoise.middleware.WhiteNoiseMiddleware"]
        if _HAS_WHITENOISE
        else []
    ),
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "showcase.urls"
WSGI_APPLICATION = "showcase.wsgi.application"
ASGI_APPLICATION = "showcase.asgi.application"

_FRONTEND_DIST = BASE_DIR / "showcase" / "static_frontend"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [_FRONTEND_DIST] if _FRONTEND_DIST.exists() else [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(
            os.getenv("SIWE_DEMO_DATABASE_PATH", str(BASE_DIR / "db.sqlite3"))
        ),
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

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [_FRONTEND_DIST] if _FRONTEND_DIST.exists() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if (_HAS_WHITENOISE and not DEBUG)
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = _bool("SIWE_DEMO_SECURE_COOKIES")
CSRF_COOKIE_SECURE = _bool("SIWE_DEMO_SECURE_COOKIES")
if _bool("SIWE_DEMO_USE_X_FORWARDED_PROTO"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
    "DOMAIN": os.getenv("SIWE_DEMO_DOMAIN", "localhost:5173"),
    "URI": os.getenv("SIWE_DEMO_URI", "http://localhost:5173/"),
    "STATEMENT": "Sign in to the siwe-django showcase.",
    "ALLOWED_CHAIN_IDS": [1, 11155111, 31337],
    "AUTO_CREATE_USERS": True,
    "USER_FACTORY": "showcase.auth.demo_user_factory",
    "ENS_ENABLED": bool(os.getenv("SIWE_DEMO_ENS_RPC_URL")),
    "ENS_RPC_URL": os.getenv("SIWE_DEMO_ENS_RPC_URL"),
    "ETHID_ENABLED": _bool("SIWE_DEMO_ETHID_ENABLED", "true"),
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
