# siwe-django

Reusable Django authentication for Sign-In with Ethereum (SIWE / EIP-4361).

`siwe-django` provides a nonce-based SIWE login flow, session login, wallet
linking for existing Django users, an optional Ethereum-native user model,
optional Django REST Framework views, ENS and Ethereum Identity Kit profile
enrichment, and token-gated Django group sync.

## Install

```bash
pip install siwe-django
```

For the optional DRF views:

```bash
pip install "siwe-django[drf]"
```

For the setup wizard CLI:

```bash
pip install "siwe-django[cli]"
siwe-django init        # patch settings.py + urls.py + drop a template
siwe-django doctor      # diagnose an existing install (CI-friendly --json)
siwe-django scaffold-templates  # add the bundled sign-in template
siwe-django migrate-from-payton # rewrite payton/django-siwe-auth references
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
    "ETHID_ENABLED": True,
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

- `GET /nonce/`: returns `{ nonce, expiresAt, domain, uri, statement,
  ethereumIdentityKit }` and binds the nonce to the current Django session.
- `POST /verify/`: accepts `{ message, signature }`, verifies the SIWE message
  with strict domain, URI, chain, nonce, and bound optional-field
  (`Resources`, `Request ID`, `Not Before`) checks, logs in the user, and returns
  user and wallet data.
- `GET /me/`: returns the current authenticated SIWE identity.
- `POST /logout/`: destroys the Django session.
- `POST /link/`: links another verified wallet to the current user.
- `GET /wallets/`: lists the current user's wallets.
- `DELETE /wallets/<id>/`: unlinks a wallet.
- `GET /profile/<address-or-ens>/`: proxies a display-ready Ethereum Identity
  Kit profile from the Eth Follow public API.

## Frontend Flow

1. Fetch `GET /auth/siwe/nonce/`.
2. Create an EIP-4361 SIWE message with the returned nonce, domain, URI, and
   statement.
3. Ask the wallet to sign the prepared SIWE message.
4. Submit `{ message, signature }` to `POST /auth/siwe/verify/`.

The server consumes each nonce after the first successful verification, so replay
attempts fail.

### Optional EIP-4361 fields

`siwe_django.services.issue_nonce` accepts `resources`, `request_id`, and
`not_before` keyword arguments and binds them to the issued nonce. When the
client signs a message that uses these fields, `verify_siwe_message` enforces
that:

- the signed `Resources` are a subset of the issued `resources`,
- the signed `Request ID` matches the bound value,
- the signed `Not Before` matches the bound timestamp.

### ReCap (ERC-5573)

`siwe_django.recap` ships helpers to build and parse ReCap capability URIs so
relying parties can scope a sign-in to specific abilities:

```python
from siwe_django.recap import encode_recap
from siwe_django.services import issue_nonce

recap_uri = encode_recap({"https://api.example.com": {"crud/read": [{}]}})
issue_nonce(request, resources=["https://api.example.com", recap_uri])
```

`siwe_django.recap.find_recap_in_resources(resources)` returns the decoded
`{"att": ..., "prf": ...}` payload from a SIWE message's `Resources` list, or
`None` when no ReCap is present.

### Smart contract wallets

`siwe-django` verifies smart contract wallet signatures via:

- **EIP-1271** for already-deployed contract wallets (Safe, multisigs, …).
- **EIP-6492** for counterfactual wallets that have not yet been deployed
  (Coinbase Smart Wallet, Privy, …). The upstream `signinwithethereum`
  library calls the EIP-6492 universal validator over `eth_call` so we never
  need a deployed contract.

Both paths require `RPC_URLS` to contain a provider for the wallet's chain.
Without it the contract check fails and the request is rejected.

## Showcase Demo

The repository includes a full Django + Vite React demo under
`examples/showcase/`. It uses the local package, Ethereum Identity Kit, Wagmi,
Viem, DRF, Django sessions, ENS/EthID profile enrichment, linked wallets, and a
custom local token gate that syncs the `demo-holders` Django group.

```bash
cd examples/showcase/backend
uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000

cd ../frontend
npm install
npm run dev
```

Open `http://localhost:5173`. See `examples/showcase/README.md` for optional
RPC, ENS, EthID, and demo gate environment variables.

## Ethereum Identity Kit

Ethereum Identity Kit is a React component library for SIWE, ENS profiles, and
EFP social data. `siwe-django` stays framework-agnostic on the backend while
returning the exact data frontend integrations need.

The nonce response includes `ethereumIdentityKit` metadata:

```json
{
  "nonce": "abc123...",
  "ethereumIdentityKit": {
    "statement": "Sign in with Ethereum.",
    "expirationTime": 300000,
    "messageParams": {
      "domain": "example.com",
      "uri": "https://example.com/",
      "version": "1",
      "nonce": "abc123..."
    }
  }
}
```

With `ethereum-identity-kit`:

```tsx
import { useSiwe } from "ethereum-identity-kit";

const { handleSignIn } = useSiwe({
  getNonce: async () => {
    const response = await fetch("/auth/siwe/nonce/", { credentials: "include" });
    const data = await response.json();
    return data.nonce;
  },
  verifySignature: async (message, _nonce, signature) => {
    const response = await fetch("/auth/siwe/verify/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ message, signature }),
    });
    return response.ok;
  },
  statement: "Sign in with Ethereum.",
  expirationTime: 300000,
});
```

When `ETHID_ENABLED` is true, login/linking stores display-ready profile data on
`SiweWallet`: ENS records, header, description, display name, avatar, EFP profile
URL, follower count, following count, and the raw EthID profile payload.
Serialized wallet responses include `displayName`, `avatar`, `profile`, and
`ethereumIdentityKit.addressOrName` for direct use with profile cards, avatars,
and tooltips.

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
| `CLOCK_SKEW_SECONDS` | `60` | Tolerance applied to `Issued At`, `Not Before`, and `Expiration Time` checks. Set to `0` for strict comparison. |
| `ALLOWED_CHAIN_IDS` | `None` | Optional allow-list for message chain IDs. |
| `RPC_URLS` | `{}` | Chain ID to RPC URL map for contract wallet and token checks. |
| `ENS_ENABLED` | `False` | Enable ENS name/avatar lookup. |
| `ENS_RPC_URL` | `None` | RPC URL used for ENS lookup. |
| `ETHID_ENABLED` | `False` | Enrich wallets from Ethereum Identity Kit / Eth Follow APIs during auth. |
| `ETHID_PROFILE_PROXY_ENABLED` | `True` | Enable public `GET /profile/<address-or-ens>/` proxy endpoint. |
| `ETHID_API_BASE_URL` | `https://api.ethfollow.xyz/api/v1` | EthID/EFP API root. |
| `ETHID_TIMEOUT_SECONDS` | `2` | Timeout for EthID API calls. |
| `ETHID_CACHE_FRESH` | `False` | Request fresh EthID data instead of cached API data. |
| `AUTO_CREATE_USERS` | `True` | Create a user when a new wallet signs in. |
| `USER_FACTORY` | built-in | Dotted path for custom user creation. |
| `RATE_LIMITS` | `{}` | Optional per-view limits like `{ "verify": "5/m" }`. |
| `RATE_LIMIT_TRUST_X_FORWARDED_FOR` | `False` | Use the first `X-Forwarded-For` address for rate limits. Enable only behind a trusted proxy that strips client-supplied forwarding headers. |
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

### EFP and ENS gates

Gates are not limited to on-chain holdings. The Ethereum Identity Kit / EFP
graph is a first-class authorization primitive:

```python
SIWE_DJANGO = {
    "ETHID_ENABLED": True,
    "TOKEN_GATES": [
        {"type": "efp_followed_by", "source": "team.example.eth", "group": "team"},
        {"type": "efp_min_followers", "threshold": 100, "group": "popular"},
        {"type": "efp_tag", "source": "team.example.eth", "tag": "vip", "group": "vip"},
        {"type": "efp_not_blocked_by", "source": "team.example.eth", "group": "members"},
        {"type": "ens_required", "group": "ens-holders"},
    ],
}
```

| Type | Passes when |
| --- | --- |
| `efp_follower_of` | wallet follows `target` |
| `efp_followed_by` | `source` follows the wallet |
| `efp_mutual` | wallet and `hub` follow each other |
| `efp_min_followers` | wallet has at least `threshold` followers |
| `efp_tag` | `source` has tagged the wallet with `tag` |
| `efp_not_blocked_by` | `source` has not blocked or muted the wallet |
| `ens_required` | wallet has a primary ENS name |

EFP and ENS gates ignore `chain_id`. They reuse the existing `TOKEN_GATES`
group-sync semantics, so a failed gate removes the matching `Group` rather
than blocking sign-in.

## OIDC Helpers

`siwe_django.oidc.claims_for_wallet(wallet)` returns claim shapes compatible with
future SIWE OIDC integration:

```python
{
    "sub": "eip155:1:0x...",
    "preferred_username": "alice.eth",
    "picture": "https://...",
    "profile": "https://efp.app/alice.eth",
    "followers_count": 5368,
    "following_count": 10,
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
