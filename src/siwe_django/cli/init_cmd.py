"""``siwe-django init`` — patch a Django project to use siwe-django."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Template

from rich.console import Console

from .cst import add_settings_block, add_to_list_setting
from .scaffold import patch_root_urls, write_login_template

_SIWE_DJANGO_BLOCK = Template(
    'SIWE_DJANGO = {\n'
    '    "DOMAIN": "$domain",\n'
    '    "URI": "$uri",\n'
    '    "STATEMENT": "Sign in with Ethereum.",\n'
    '    "ALLOWED_CHAIN_IDS": [1, 11155111],\n'
    '}\n'
)


@dataclass(frozen=True)
class InitOptions:
    project_root: Path
    settings_path: Path
    urls_path: Path
    use_drf: bool
    domain: str
    uri: str
    scaffold_template: bool
    run_migrate: bool
    manage_path: Path | None = None


def detect_settings_path(project_root: Path) -> Path | None:
    candidates = [
        path
        for path in project_root.glob("*/settings.py")
        if path.parent.name not in {"siwe_django", "tests"}
    ]
    if len(candidates) == 1:
        return candidates[0]
    nested = [
        path
        for path in project_root.glob("*/*/settings.py")
        if "site-packages" not in path.parts
    ]
    if len(nested) == 1:
        return nested[0]
    return None


def detect_urls_path(settings_path: Path) -> Path:
    return settings_path.with_name("urls.py")


def detect_manage_py(project_root: Path) -> Path | None:
    candidate = project_root / "manage.py"
    return candidate if candidate.exists() else None


def patch_settings(options: InitOptions) -> list[str]:
    """Apply settings.py edits. Returns a list of human-readable change notes."""
    notes: list[str] = []
    source = options.settings_path.read_text(encoding="utf-8")
    original = source

    source = add_to_list_setting(source, "INSTALLED_APPS", ["siwe_django"])
    source = add_to_list_setting(
        source,
        "AUTHENTICATION_BACKENDS",
        ["siwe_django.backend.SiweBackend"],
        prepend=True,
    )

    block = _SIWE_DJANGO_BLOCK.substitute(domain=options.domain, uri=options.uri)
    source = add_settings_block(source, block, name="SIWE_DJANGO")

    if source != original:
        options.settings_path.write_text(source, encoding="utf-8")
        notes.append(f"patched {options.settings_path}")
    return notes


def patch_urls(options: InitOptions) -> list[str]:
    notes: list[str] = []
    dotted = (
        "siwe_django.drf.urls" if options.use_drf else "siwe_django.urls"
    )
    if patch_root_urls(options.urls_path, "auth/siwe/", dotted):
        notes.append(f"patched {options.urls_path}")
    return notes


def scaffold_template(options: InitOptions) -> list[str]:
    if not options.scaffold_template:
        return []
    written = write_login_template(options.project_root)
    return [f"wrote {written}"]


def run_migrate(options: InitOptions) -> list[str]:
    if not options.run_migrate or options.manage_path is None:
        return []
    cmd = [sys.executable, str(options.manage_path), "migrate", "--noinput"]
    completed = subprocess.run(
        cmd,
        cwd=options.project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return [
            f"migrate failed (exit {completed.returncode}):"
            f"\n{completed.stderr.strip()}"
        ]
    return ["ran manage.py migrate"]


def run_init(options: InitOptions, console: Console | None = None) -> list[str]:
    """Apply all init steps and return the list of change notes (also printed)."""
    console = console or Console()
    notes: list[str] = []
    notes.extend(patch_settings(options))
    notes.extend(patch_urls(options))
    notes.extend(scaffold_template(options))
    notes.extend(run_migrate(options))
    for note in notes:
        console.print(f"[green]✓[/green] {note}")
    if not notes:
        console.print(
            "[yellow]nothing to do — settings already include siwe_django[/yellow]"
        )
    return notes


_RPC_ENV_RE = re.compile(r"^SIWE_RPC_([A-Z0-9_]+)=(.*)$", re.MULTILINE)


def upsert_env_example(env_path: Path, rpcs: dict[str, str]) -> None:
    """Add ``SIWE_RPC_<NAME>=...`` entries to ``.env.example`` (creating the
    file if absent). Existing entries are preserved.
    """
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    existing = {match.group(1) for match in _RPC_ENV_RE.finditer(text)}
    additions = "\n".join(
        f"SIWE_RPC_{name.upper()}={url}"
        for name, url in rpcs.items()
        if name.upper() not in existing
    )
    if additions:
        suffix = "\n" if text and not text.endswith("\n") else ""
        env_path.write_text(text + suffix + additions + "\n", encoding="utf-8")
