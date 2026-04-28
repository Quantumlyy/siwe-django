import pytest
from django.forms.widgets import HiddenInput
from django.test import override_settings
from django.urls import path

from siwe_django.forms import SiweVerifyForm
from siwe_django.template_views import SiweLoginView


def test_siwe_verify_form_accepts_message_and_signature():
    form = SiweVerifyForm(data={"message": "message", "signature": "0xsig"})

    assert form.is_valid()
    assert form.cleaned_data == {"message": "message", "signature": "0xsig"}


def test_siwe_verify_form_uses_hidden_fields():
    form = SiweVerifyForm()

    assert isinstance(form.fields["message"].widget, HiddenInput)
    assert isinstance(form.fields["signature"].widget, HiddenInput)


@pytest.mark.django_db
def test_siwe_login_view_exposes_form_and_endpoint_urls(client):
    response = client.get("/login/siwe/")

    assert response.status_code == 200
    assert isinstance(response.context["form"], SiweVerifyForm)
    assert response.context["nonce_url"] == "/siwe/nonce/"
    assert response.context["verify_url"] == "/siwe/verify/"
    content = response.content.decode()
    assert 'name="message"' in content
    assert 'name="signature"' in content


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_drf_only")
def test_siwe_login_view_falls_back_to_drf_endpoint_urls(client):
    response = client.get("/login/siwe/")

    assert response.status_code == 200
    assert response.context["nonce_url"] == "/siwe-drf/nonce/"
    assert response.context["verify_url"] == "/siwe-drf/verify/"


urlpatterns = [
    path(
        "custom-login/",
        SiweLoginView.as_view(
            extra_context={
                "nonce_url": "/custom/nonce/",
                "verify_url": "/custom/verify/",
            }
        ),
        name="custom-siwe-login",
    ),
]


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__)
def test_siwe_login_view_respects_explicit_context_urls(client):
    response = client.get("/custom-login/")

    assert response.status_code == 200
    assert response.context["nonce_url"] == "/custom/nonce/"
    assert response.context["verify_url"] == "/custom/verify/"
