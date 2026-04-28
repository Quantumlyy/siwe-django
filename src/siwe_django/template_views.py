from __future__ import annotations

from collections.abc import Iterable

from django.urls import NoReverseMatch, reverse
from django.views.generic.edit import FormView

from .forms import SiweVerifyForm


class SiweLoginView(FormView):
    """Starter SIWE login view.

    The vanilla URL namespace is preferred, with DRF URL names accepted as a
    fallback for projects that mount ``siwe_django.drf.urls``.
    """

    template_name = "siwe_django/siwe_login.html"
    form_class = SiweVerifyForm
    nonce_url_name = "siwe_django:nonce"
    verify_url_name = "siwe_django:verify"
    nonce_url_fallback_names = ("siwe_django_drf:nonce",)
    verify_url_fallback_names = ("siwe_django_drf:verify",)

    def _reverse_first(self, primary: str, fallbacks: Iterable[str]) -> str:
        error = None
        for url_name in (primary, *fallbacks):
            try:
                return reverse(url_name)
            except NoReverseMatch as exc:
                error = exc
        if error is not None:
            raise error
        raise NoReverseMatch("No SIWE URL names configured.")

    def get_nonce_url(self) -> str:
        return self._reverse_first(self.nonce_url_name, self.nonce_url_fallback_names)

    def get_verify_url(self) -> str:
        return self._reverse_first(
            self.verify_url_name,
            self.verify_url_fallback_names,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "nonce_url" not in context:
            context["nonce_url"] = self.get_nonce_url()
        if "verify_url" not in context:
            context["verify_url"] = self.get_verify_url()
        return context
