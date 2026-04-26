# siwe-django

Reusable Django authentication for Sign-In with Ethereum (SIWE / EIP-4361).

`siwe-django` provides a nonce-based SIWE login flow, session login, wallet
linking for existing Django users, an optional Ethereum-native user model,
optional Django REST Framework views, ENS profile enrichment, and token-gated
Django group sync.

## Install

```bash
pip install siwe-django
```

For the optional DRF views:

```bash
pip install "siwe-django[drf]"
```

## Configure

```python
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "siwe_django",
]

AUTHENTICATION_BACKENDS = [
    "siwe_django.backend.SiweBackend",
    "django.contrib.auth.backends.ModelBackend",
]

SIWE_DJANGO = {
    "DOMAIN": "example.com",
    "URI": "https://example.com/",
    "STATEMENT": "Sign in with Ethereum.",
    "ALLOWED_CHAIN_IDS": [1, 11155111],
    "RPC_URLS": {
        1: "https://mainnet.infura.io/v3/...",
        11155111: "https://sepolia.infura.io/v3/...",
    },
}
```

Add the vanilla Django routes:

```python
from django.urls import include, path

urlpatterns = [
    path("auth/siwe/", include("siwe_django.urls")),
]
```

Or the optional DRF routes:

```python
urlpatterns = [
    path("api/auth/siwe/", include("siwe_django.drf.urls")),
]
```

Run migrations:

```bash
python manage.py migrate
```

## Endpoints

- `GET /nonce/`: returns `{ nonce, expiresAt, domain, uri, statement }` and
  binds the nonce to the current Django session.
- `POST /verify/`: accepts `{ message, signature }`, verifies the SIWE message
  with strict domain, URI, chain, and nonce checks, logs in the user, and returns
  user and wallet data.
- `GET /me/`: returns the current authenticated SIWE identity.
- `POST /logout/`: destroys the Django session.
- `POST /link/`: links another verified wallet to the current user.
- `GET /wallets/`: lists the current user's wallets.
- `DELETE /wallets/<id>/`: unlinks a wallet.

## Frontend Flow

1. Fetch `GET /auth/siwe/nonce/`.
2. Create an EIP-4361 SIWE message with the returned nonce, domain, URI, and
   statement.
3. Ask the wallet to sign the prepared SIWE message.
4. Submit `{ message, signature }` to `POST /auth/siwe/verify/`.

The server consumes each nonce after the first successful verification, so replay
attempts fail.

## Existing Users and Wallet-Native Users

By default, `SiweWallet` links Ethereum wallets to `settings.AUTH_USER_MODEL`.
This is the best fit for existing Django applications.

Projects that want wallets to be the primary user identity can set:

```python
AUTH_USER_MODEL = "siwe_django.EthereumUser"
```

Set this before the first migration, as with any Django custom user model.

## Settings

All settings live under `SIWE_DJANGO`.

| Setting | Default | Purpose |
| --- | --- | --- |
| `DOMAIN` | request host | Expected SIWE domain. Set explicitly behind proxies. |
| `URI` | request root URI | Expected SIWE URI. |
| `STATEMENT` | `"Sign in with Ethereum."` | Human-readable statement for clients. |
| `NONCE_TTL_SECONDS` | `300` | Nonce lifetime. |
| `ALLOWED_CHAIN_IDS` | `None` | Optional allow-list for message chain IDs. |
| `RPC_URLS` | `{}` | Chain ID to RPC URL map for contract wallet and token checks. |
| `ENS_ENABLED` | `False` | Enable ENS name/avatar lookup. |
| `ENS_RPC_URL` | `None` | RPC URL used for ENS lookup. |
| `AUTO_CREATE_USERS` | `True` | Create a user when a new wallet signs in. |
| `USER_FACTORY` | built-in | Dotted path for custom user creation. |
| `RATE_LIMITS` | `{}` | Optional per-view limits like `{ "verify": "5/m" }`. |
| `TOKEN_GATES` | `[]` | Optional group sync gates. |
| `SYNC_TOKEN_GATES_ON_LOGIN` | `True` | Sync token gates after login/linking. |

## Token Gates

Token gates sync Django `Group` membership and fail closed when an RPC URL is
missing or a check errors.

```python
SIWE_DJANGO = {
    "RPC_URLS": {1: "https://mainnet.infura.io/v3/..."},
    "TOKEN_GATES": [
        {
            "type": "erc721",
            "chain_id": 1,
            "contract": "0x...",
            "group": "nft-holders",
        },
        {
            "type": "custom",
            "checker": "myapp.siwe_gates.is_member",
            "group": "members",
        },
    ],
}
```

Custom checkers receive `wallet` and `gate` keyword arguments and return a
boolean.

## OIDC Helpers

`siwe_django.oidc.claims_for_wallet(wallet)` returns claim shapes compatible with
future SIWE OIDC integration:

```python
{
    "sub": "eip155:1:0x...",
    "preferred_username": "alice.eth",
    "picture": "https://...",
}
```

This package does not implement an OIDC provider in v1.

## Development

```bash
uv sync --extra drf --group dev
uv run ruff check
uv run pytest
uv run python -m build
```
