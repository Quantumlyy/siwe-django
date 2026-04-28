"""Drop a working Django sign-in template + app into an existing project."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from .cst import ensure_url_include

TEMPLATE_RELATIVE_PATH = "siwe_django/siwe_login.html"


def _bundled_template_text() -> str:
    return (
        resources.files("siwe_django")
        .joinpath("templates", "siwe_django", "siwe_login.html")
        .read_text(encoding="utf-8")
    )


def write_login_template(target_root: Path, *, overwrite: bool = False) -> Path:
    """Write the bundled sign-in template into ``target_root/templates/...``.

    Returns the path written. If the file exists and ``overwrite`` is False,
    leaves the existing file alone.
    """
    target = target_root / "templates" / TEMPLATE_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        return target
    target.write_text(_bundled_template_text(), encoding="utf-8")
    return target


def patch_root_urls(urls_path: Path, route: str, dotted_path: str) -> bool:
    """Mount ``include(dotted_path)`` at ``route`` in the project's root
    ``urls.py``. Returns True when the file was modified.
    """
    if not urls_path.exists():
        urls_path.write_text(
            "from django.urls import include, path\n\nurlpatterns = []\n",
            encoding="utf-8",
        )
    original = urls_path.read_text(encoding="utf-8")
    updated = ensure_url_include(original, route, dotted_path)
    if updated != original:
        urls_path.write_text(updated, encoding="utf-8")
        return True
    return False
