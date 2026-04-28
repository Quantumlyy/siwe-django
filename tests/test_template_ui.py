import pytest
from django.forms.widgets import HiddenInput
from django.test import override_settings
from django.urls import path

from siwe_django.forms import SiweVerifyForm
from siwe_django.template_views import SiweLoginView

TEMPLATE_OVERRIDES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "tests/custom_button.html": (
                            '<button id="siwe-submit" type="button" '
                            "data-custom-button>Custom wallet</button>"
                        ),
                        "tests/custom_status.html": (
                            '<output id="siwe-status" role="status" '
                            "data-custom-status></output>"
                        ),
                    },
                ),
                "django.template.loaders.app_directories.Loader",
            ]
        },
    }
]


class CustomButtonSiweLoginView(SiweLoginView):
    button_template_name = "tests/custom_button.html"

    def get_nonce_url(self) -> str:
        return "/custom/nonce/"

    def get_verify_url(self) -> str:
        return "/custom/verify/"


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
    assert (
        response.context["siwe_form_template_name"]
        == "siwe_django/partials/form.html"
    )
    assert (
        response.context["siwe_button_template_name"]
        == "siwe_django/partials/button.html"
    )
    assert (
        response.context["siwe_status_template_name"]
        == "siwe_django/partials/status.html"
    )
    assert (
        response.context["siwe_result_template_name"]
        == "siwe_django/partials/result.html"
    )
    assert (
        response.context["siwe_script_template_name"]
        == "siwe_django/partials/script.html"
    )
    content = response.content.decode()
    assert 'name="message"' in content
    assert 'name="signature"' in content
    assert 'data-siwe-form' in content
    assert 'data-siwe-submit' in content
    assert 'data-siwe-status' in content
    assert 'data-siwe-result' in content
    assert "buildSiweMessage" in content
    assert "<style" not in content
    assert "class=" not in content


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
    path(
        "subclass-partial-login/",
        CustomButtonSiweLoginView.as_view(),
        name="subclass-partial-siwe-login",
    ),
    path(
        "context-partial-login/",
        SiweLoginView.as_view(
            extra_context={
                "nonce_url": "/custom/nonce/",
                "verify_url": "/custom/verify/",
                "siwe_status_template_name": "tests/custom_status.html",
            }
        ),
        name="context-partial-siwe-login",
    ),
]


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__)
def test_siwe_login_view_respects_explicit_context_urls(client):
    response = client.get("/custom-login/")

    assert response.status_code == 200
    assert response.context["nonce_url"] == "/custom/nonce/"
    assert response.context["verify_url"] == "/custom/verify/"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__, TEMPLATES=TEMPLATE_OVERRIDES)
def test_siwe_login_view_uses_subclass_partial_template(client):
    response = client.get("/subclass-partial-login/")

    assert response.status_code == 200
    assert response.context["siwe_button_template_name"] == "tests/custom_button.html"
    content = response.content.decode()
    assert "Custom wallet" in content
    assert "data-custom-button" in content


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__, TEMPLATES=TEMPLATE_OVERRIDES)
def test_siwe_login_view_uses_extra_context_partial_template(client):
    response = client.get("/context-partial-login/")

    assert response.status_code == 200
    assert response.context["nonce_url"] == "/custom/nonce/"
    assert response.context["verify_url"] == "/custom/verify/"
    assert response.context["siwe_status_template_name"] == "tests/custom_status.html"
    content = response.content.decode()
    assert "data-custom-status" in content
