"""Minimal Django settings for the siwe-django templates demo."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "templates-demo-secret")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "siwe_django",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "templates_demo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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
        "NAME": BASE_DIR / "templates_demo.sqlite3",
    },
}

AUTHENTICATION_BACKENDS = [
    "siwe_django.backend.SiweBackend",
    "django.contrib.auth.backends.ModelBackend",
]

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

SIWE_DJANGO = {
    "DOMAIN": os.environ.get("SIWE_DOMAIN", "localhost:8000"),
    "URI": os.environ.get("SIWE_URI", "http://localhost:8000/"),
    "STATEMENT": "Sign in with Ethereum to the templates demo.",
    "ALLOWED_CHAIN_IDS": [1, 11155111],
}
