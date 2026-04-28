from __future__ import annotations

from django.urls import include, path, re_path

from . import views

urlpatterns = [
    path("auth/siwe/", include("siwe_django.urls")),
    path("api/showcase/session/", views.session, name="showcase-session"),
    re_path(r"^(?P<path>.*)$", views.spa, name="showcase-spa"),
]
