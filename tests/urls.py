from django.urls import include, path

from siwe_django.template_views import SiweLoginView

urlpatterns = [
    path("siwe/", include("siwe_django.urls")),
    path("siwe-drf/", include("siwe_django.drf.urls")),
    path("login/siwe/", SiweLoginView.as_view(), name="siwe-login"),
]
