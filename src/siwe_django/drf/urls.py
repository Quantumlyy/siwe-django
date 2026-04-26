from django.urls import path

from . import views

app_name = "siwe_django_drf"

urlpatterns = [
    path("nonce/", views.NonceView.as_view(), name="nonce"),
    path("verify/", views.VerifyView.as_view(), name="verify"),
    path("me/", views.MeView.as_view(), name="me"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("link/", views.LinkView.as_view(), name="link"),
    path("wallets/", views.WalletsView.as_view(), name="wallets"),
    path(
        "wallets/<int:wallet_id>/",
        views.WalletDetailView.as_view(),
        name="wallet_detail",
    ),
]
