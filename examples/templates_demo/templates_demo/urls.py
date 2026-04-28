from __future__ import annotations

from django.urls import include, path

from siwe_django.template_views import SiweLoginView

urlpatterns = [
    path("auth/siwe/", include("siwe_django.urls")),
    path("", SiweLoginView.as_view(), name="signin"),
]
