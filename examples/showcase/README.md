# siwe-django Showcase

This demo runs a small Django backend and a Vite React frontend against the
local `siwe-django` package. It demonstrates nonce-based SIWE login, Django
sessions, linked wallets, ENS/EthID profile data, and token-gated Django groups.

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
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/auth/siwe/` and
`/api/showcase/` to Django at `http://127.0.0.1:8000`, so no CORS package is
needed.

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
