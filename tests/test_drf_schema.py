from __future__ import annotations

from siwe_django.drf import schema


def test_extend_schema_returns_passthrough_when_spectacular_missing():
    if schema.SPECTACULAR_INSTALLED:
        # When drf-spectacular is installed the decorator returns a real
        # spectacular wrapper. The passthrough behaviour we want to assert
        # only matters in the optional-extra path; nothing to test here.
        return

    @schema.extend_schema(tags=[schema.SIWE_TAG], summary="x")
    def view():
        return "ok"

    assert view() == "ok"


def test_drf_views_import_without_spectacular():
    from siwe_django.drf import views as drf_views

    assert drf_views.NonceView is not None
    assert drf_views.VerifyView is not None
    assert drf_views.ReauthView is not None
