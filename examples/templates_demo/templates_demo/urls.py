from __future__ import annotations

from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("auth/siwe/", include("siwe_django.urls")),
    path(
        "",
        TemplateView.as_view(
            template_name="siwe_django/siwe_login.html",
            extra_context={
                "nonce_url": "/auth/siwe/nonce/",
                "verify_url": "/auth/siwe/verify/",
            },
        ),
        name="signin",
    ),
]
