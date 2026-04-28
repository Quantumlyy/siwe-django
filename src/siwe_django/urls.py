from django.urls import path

from . import views

app_name = "siwe_django"

urlpatterns = [
    path("nonce/", views.nonce, name="nonce"),
    path("verify/", views.verify, name="verify"),
    path("reauth/", views.reauth, name="reauth"),
    path("me/", views.me, name="me"),
    path("logout/", views.logout, name="logout"),
    path("link/", views.link, name="link"),
    path("wallets/", views.wallets, name="wallets"),
    path("wallets/<int:wallet_id>/", views.wallet_detail, name="wallet_detail"),
    path("profile/<str:address_or_name>/", views.profile, name="profile"),
]
