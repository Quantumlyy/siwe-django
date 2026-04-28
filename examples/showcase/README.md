# siwe-django Showcase

This demo runs a small Django backend and a Vite React frontend against the
local `siwe-django` package. It demonstrates nonce-based SIWE login, Django
sessions, linked wallets, Reown AppKit wallet connection, ENS/EthID profile
data, and token-gated Django groups.

## Backend

From the repository root:

```bash
uv sync --extra drf --group dev
cd examples/showcase/backend
uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000
```

Optional environment:

```bash
export SIWE_DEMO_SECRET_KEY="dev-secret"
export SIWE_DEMO_ETHID_ENABLED="true"
export SIWE_DEMO_ENS_RPC_URL="https://mainnet.example/rpc"
export SIWE_DEMO_RPC_URL_1="https://mainnet.example/rpc"
export SIWE_DEMO_HOLDER_ADDRESSES="0xabc...,0xdef..."
```

The demo token gate is intentionally custom and local. It grants the
`demo-holders` Django group when the signed-in wallet address appears in
`SIWE_DEMO_HOLDER_ADDRESSES`.

## Frontend

In another terminal:

```bash
cd examples/showcase/frontend
npm install
export VITE_REOWN_PROJECT_ID="<project-id>"  # optional; enables AppKit + WalletConnect
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/auth/siwe/` and
`/api/showcase/` to Django at `http://127.0.0.1:8000`, so no CORS package is
needed. Without `VITE_REOWN_PROJECT_ID`, the demo falls back to injected browser
wallets so local development still works without a Reown project.

If port `8000` is already in use, run Django on another port and point Vite at
it:

```bash
uv run python manage.py runserver 127.0.0.1:8001
VITE_SHOWCASE_BACKEND_URL=http://127.0.0.1:8001 npm run dev
```

## Build Checks

```bash
uv run ruff check
uv run pytest
uv run python -m build
cd examples/showcase/frontend && npm run build
```

## Deploy to Fly.io

The showcase ships a multi-stage `Dockerfile` (Bun builds the Vite bundle,
Python runs `gunicorn` behind WhiteNoise) and a `fly.toml` that mounts a
1 GB volume for SQLite. One Fly app serves the React SPA and the Django
endpoints under a single origin so CSRF and session cookies stay
same-origin.

From the repository root:

```bash
# 1) Edit examples/showcase/fly.toml: set `app = "<your-fly-app>"` and the
#    SIWE_DEMO_ALLOWED_HOSTS / SIWE_DEMO_DOMAIN / SIWE_DEMO_URI / 
#    SIWE_DEMO_CSRF_TRUSTED_ORIGINS values to match the Fly hostname you
#    intend to use (or your custom domain).

# 2) Create the app + the SQLite volume.
fly launch --config examples/showcase/fly.toml --no-deploy
fly volumes create showcase_data --region lhr --size 1

# 3) Set the secrets (everything not in `fly.toml`'s [env]).
fly secrets set \
    SIWE_DEMO_SECRET_KEY="$(openssl rand -hex 32)" \
    SIWE_DEMO_RPC_URL_1="https://mainnet.infura.io/v3/<key>"

# 4) Deploy.
fly deploy --config examples/showcase/fly.toml
```

Hit `https://<your-fly-app>.fly.dev/` and the React SPA loads; sign-in,
session, wallet linking, and token-gate sync all work end-to-end.

To switch off SQLite-on-volume in favour of managed Postgres, swap the
`DATABASES` block in `backend/showcase/settings.py` for one that reads
`DATABASE_URL` and remove the `[[mounts]]` section from `fly.toml`.
