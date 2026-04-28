from __future__ import annotations

from django.urls import reverse
from django.views.generic.edit import FormView

from .forms import SiweVerifyForm


class SiweLoginView(FormView):
    template_name = "siwe_django/siwe_login.html"
    form_class = SiweVerifyForm
    nonce_url_name = "siwe_django:nonce"
    verify_url_name = "siwe_django:verify"

    def get_nonce_url(self) -> str:
        return reverse(self.nonce_url_name)

    def get_verify_url(self) -> str:
        return reverse(self.verify_url_name)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("nonce_url", self.get_nonce_url())
        context.setdefault("verify_url", self.get_verify_url())
        return context
