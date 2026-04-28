"""``siwe-django migrate-from-payton`` — best-effort rewrite of a project that
uses ``payton/django-siwe-auth`` to use ``siwe-django`` instead.

Scope: this only does textual rewrites (imports, settings keys, URL includes)
and prints a checklist of items the developer must verify manually (custom
``Wallet`` model migration, group manager rewrites, etc.). It does not touch
existing data — destructive migrations stay opt-in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Order matters: targeted renames run before the catch-all package rename so
# `Wallet`/`Nonce` only get replaced inside contexts that are clearly the
# payton models (qualified by the package name).
REGEX_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsiwe_auth\.models\.Wallet\b"), "siwe_django.models.SiweWallet"),
    (re.compile(r"\bsiwe_auth\.models\.Nonce\b"), "siwe_django.models.SiweNonce"),
    (
        re.compile(
            r"(from\s+siwe_auth\.models\s+import\s+(?:[^\n]*?,\s*)?)Wallet\b"
        ),
        r"\1SiweWallet",
    ),
    (
        re.compile(
            r"(from\s+siwe_auth\.models\s+import\s+(?:[^\n]*?,\s*)?)Nonce\b"
        ),
        r"\1SiweNonce",
    ),
    (re.compile(r"\bsiwe_auth\b"), "siwe_django"),
    (re.compile(r"\bCREATE_ENS_PROFILE_ON_AUTHN\b"), "ENS_ENABLED"),
)

POST_MIGRATION_CHECKLIST = (
    "Replace any custom group managers (django-siwe-auth's `CUSTOM_GROUPS`) "
    "with `TOKEN_GATES` entries — siwe-django ships ERC-20/721/1155 + EFP/ENS"
    " gates out of the box.",
    "If your project relies on django-siwe-auth's `Wallet` model as the user"
    " model, plan a data migration into `siwe_django.SiweWallet` (linked to"
    " `AUTH_USER_MODEL`).",
    "Re-run `python manage.py migrate` after the rewrite.",
    "Update any front-end calls to use the siwe-django endpoints "
    "(`/auth/siwe/nonce/`, `/auth/siwe/verify/`, `/auth/siwe/me/`).",
)


@dataclass(frozen=True)
class RewriteSummary:
    files_scanned: int
    files_modified: int
    replacements_applied: int


def rewrite_text(source: str) -> tuple[str, int]:
    """Apply known replacements to ``source``. Returns the new text + count."""
    new_source = source
    applied = 0
    for pattern, replacement in REGEX_REPLACEMENTS:
        new_source, count = pattern.subn(replacement, new_source)
        applied += count
    return new_source, applied


def _iter_python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if not any(part in {".venv", "venv", "node_modules"} for part in path.parts)
    ]


def rewrite_project(root: Path) -> RewriteSummary:
    files = _iter_python_files(root)
    modified = 0
    total_applied = 0
    for path in files:
        original = path.read_text(encoding="utf-8")
        rewritten, applied = rewrite_text(original)
        if applied:
            path.write_text(rewritten, encoding="utf-8")
            modified += 1
            total_applied += applied
    return RewriteSummary(
        files_scanned=len(files),
        files_modified=modified,
        replacements_applied=total_applied,
    )
