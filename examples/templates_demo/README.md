# siwe-django templates demo

A minimal Django project that uses **only** Django templates (no React,
no build step) to render a Sign-in with Ethereum page. The bundled
`siwe_django/siwe_login.html` template talks to `window.ethereum`
directly and posts to the standard `siwe-django` endpoints through
`SiweLoginView`.

This is the no-JS-toolchain counterpart to `examples/showcase/` and the
output the `siwe-django init --template` or `siwe-django scaffold-templates`
wizard steps would produce when run against an empty project.

## Run

```bash
cd examples/templates_demo
uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/` and click **Sign in with Ethereum**. The
template uses the wallet's `personal_sign`, posts to `/auth/siwe/verify/`,
and surfaces the JSON response below the button.

## What's wired

- `templates_demo/settings.py` enables `siwe_django` in `INSTALLED_APPS`
  and prepends `siwe_django.backend.SiweBackend`.
- `templates_demo/urls.py` mounts the SIWE endpoints under `/auth/siwe/`
  and mounts `SiweLoginView` at `/`.
- No `RPC_URLS` are configured, so smart contract wallet sigs (EIP-1271
  / EIP-6492) are not supported in this demo. Add an RPC URL to enable
  them.
