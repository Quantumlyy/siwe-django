from django.urls import include, path

urlpatterns = [
    path("siwe/", include("siwe_django.urls")),
    path("siwe-drf/", include("siwe_django.drf.urls")),
]
