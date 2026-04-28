"""Typer application exposing siwe-django wizard subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import doctor_cmd, init_cmd, migrate_payton

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="siwe-django setup wizard.",
)


def _abort(console: Console, message: str) -> None:
    console.print(f"[red]error:[/red] {message}")
    raise typer.Exit(code=1)


@app.command("init")
def init_command(
    project: Path = typer.Option(
        Path.cwd(), "--project", "-p", help="Project root containing manage.py."
    ),
    settings: Optional[Path] = typer.Option(
        None,
        "--settings",
        help="Path to settings.py. Auto-detected when not provided.",
    ),
    drf: bool = typer.Option(
        False, "--drf", help="Wire the DRF endpoints (`siwe_django.drf.urls`)."
    ),
    domain: str = typer.Option(
        "example.com",
        "--domain",
        help="SIWE DOMAIN value to write into settings.",
    ),
    uri: str = typer.Option(
        "https://example.com/",
        "--uri",
        help="SIWE URI value to write into settings.",
    ),
    template: bool = typer.Option(
        False,
        "--template",
        help="Drop the starter siwe_login.html template.",
    ),
    no_template: bool = typer.Option(
        False,
        "--no-template",
        help="Deprecated no-op. Templates are skipped unless --template is set.",
        hidden=True,
    ),
    no_migrate: bool = typer.Option(
        False,
        "--no-migrate",
        help="Skip running manage.py migrate after patching settings.",
    ),
) -> None:
    """Patch settings.py + urls.py to use siwe-django."""
    console = Console()
    project = project.resolve()
    settings_path = settings or init_cmd.detect_settings_path(project)
    if settings_path is None:
        _abort(
            console,
            "could not auto-detect settings.py. Pass --settings explicitly.",
        )
    assert settings_path is not None
    settings_path = settings_path.resolve()
    options = init_cmd.InitOptions(
        project_root=project,
        settings_path=settings_path,
        urls_path=init_cmd.detect_urls_path(settings_path),
        use_drf=drf,
        domain=domain,
        uri=uri,
        scaffold_template=template,
        run_migrate=not no_migrate,
        manage_path=init_cmd.detect_manage_py(project),
    )
    init_cmd.run_init(options, console)


@app.command("scaffold-templates")
def scaffold_command(
    project: Path = typer.Option(
        Path.cwd(), "--project", "-p", help="Project root."
    ),
    settings: Optional[Path] = typer.Option(
        None, "--settings", help="Path to settings.py for the URL include step."
    ),
    drf: bool = typer.Option(
        False, "--drf", help="Mount the DRF urls instead of the vanilla ones."
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace an existing starter template.",
    ),
) -> None:
    """Drop a starter Django sign-in template + URL include into the project."""
    from .scaffold import patch_root_urls, write_login_template

    console = Console()
    project = project.resolve()
    written = write_login_template(project, overwrite=overwrite)
    console.print(f"[green]✓[/green] wrote {written}")
    settings_path = settings or init_cmd.detect_settings_path(project)
    if settings_path is None:
        console.print(
            "[yellow]could not auto-detect settings.py — skipping URL include[/yellow]"
        )
        return
    urls_path = init_cmd.detect_urls_path(settings_path)
    dotted = "siwe_django.drf.urls" if drf else "siwe_django.urls"
    if patch_root_urls(urls_path, "auth/siwe/", dotted):
        console.print(f"[green]✓[/green] patched {urls_path}")


@app.command("doctor")
def doctor_command(
    json_output: bool = typer.Option(
        False, "--json", help="Print findings as JSON for CI consumption."
    ),
) -> None:
    """Diagnose an existing siwe-django installation."""
    console = Console()
    try:
        import django
        from django.conf import settings as django_settings

        django.setup()
        config = dict(getattr(django_settings, "SIWE_DJANGO", {}) or {})
    except Exception:
        config = doctor_cmd.settings_from_env()

    findings = doctor_cmd.diagnose(config)

    if json_output:
        typer.echo(doctor_cmd.to_json(findings))
        raise typer.Exit(code=1 if doctor_cmd.has_blocking(findings) else 0)

    if not findings:
        console.print("[green]✓[/green] no issues detected.")
        return

    table = Table(title="siwe-django doctor")
    table.add_column("severity")
    table.add_column("message")
    for finding in findings:
        colour = "red" if finding.is_blocking else "yellow"
        table.add_row(f"[{colour}]{finding.severity}[/{colour}]", finding.message)
    console.print(table)
    if doctor_cmd.has_blocking(findings):
        raise typer.Exit(code=1)


@app.command("migrate-from-payton")
def migrate_payton_command(
    project: Path = typer.Option(
        Path.cwd(), "--project", "-p", help="Project root to rewrite."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print what would change without writing."
    ),
) -> None:
    """Rewrite payton/django-siwe-auth references to siwe-django."""
    console = Console()
    project = project.resolve()
    if dry_run:
        files = [
            path
            for path in project.rglob("*.py")
            if not any(
                part in {".venv", "venv", "node_modules"} for part in path.parts
            )
        ]
        affected = []
        for path in files:
            text = path.read_text(encoding="utf-8")
            _, count = migrate_payton.rewrite_text(text)
            if count:
                affected.append((path, count))
        console.print(json.dumps({"files": [str(p) for p, _ in affected]}))
        return

    summary = migrate_payton.rewrite_project(project)
    console.print(
        f"[green]✓[/green] {summary.replacements_applied} replacement(s) "
        f"across {summary.files_modified} of {summary.files_scanned} files."
    )
    console.print("\nFollow-ups:")
    for item in migrate_payton.POST_MIGRATION_CHECKLIST:
        console.print(f"  - {item}")


if __name__ == "__main__":  # pragma: no cover
    app()
