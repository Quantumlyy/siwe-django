from __future__ import annotations

from pathlib import Path

import libcst as cst
import pytest
from typer.testing import CliRunner

from siwe_django.cli import doctor_cmd, migrate_payton
from siwe_django.cli.cst import (
    add_settings_block,
    add_to_list_setting,
    ensure_url_include,
)
from siwe_django.cli.main import app
from siwe_django.cli.scaffold import write_login_template

runner = CliRunner()


def _settings_skeleton() -> str:
    return (
        "INSTALLED_APPS = [\n"
        '    "django.contrib.auth",\n'
        '    "django.contrib.sessions",\n'
        "]\n\n"
        "AUTHENTICATION_BACKENDS = [\n"
        '    "django.contrib.auth.backends.ModelBackend",\n'
        "]\n"
    )


def _urls_skeleton() -> str:
    return "from django.urls import path\n\nurlpatterns = []\n"


# -----------------------------------------------------------------------------
# CST mutators
# -----------------------------------------------------------------------------


def test_add_to_list_appends_when_missing():
    source = _settings_skeleton()

    result = add_to_list_setting(source, "INSTALLED_APPS", ["siwe_django"])

    assert '"siwe_django"' in result
    assert result.count('"siwe_django"') == 1


def test_add_to_list_is_idempotent():
    source = add_to_list_setting(
        _settings_skeleton(), "INSTALLED_APPS", ["siwe_django"]
    )
    again = add_to_list_setting(source, "INSTALLED_APPS", ["siwe_django"])

    assert again == source


def test_add_to_list_prepends_authentication_backends():
    source = _settings_skeleton()

    result = add_to_list_setting(
        source,
        "AUTHENTICATION_BACKENDS",
        ["siwe_django.backend.SiweBackend"],
        prepend=True,
    )

    assert (
        result.index("siwe_django.backend.SiweBackend")
        < result.index("django.contrib.auth.backends.ModelBackend")
    )


def test_add_to_list_creates_when_absent():
    source = "X = 1\n"

    result = add_to_list_setting(source, "INSTALLED_APPS", ["siwe_django"])

    assert "INSTALLED_APPS" in result
    assert '"siwe_django"' in result


def test_add_to_list_escapes_string_literals():
    value = 'siwe"django\\custom'
    source = "INSTALLED_APPS = []\n"

    result = add_to_list_setting(source, "INSTALLED_APPS", [value])
    again = add_to_list_setting(result, "INSTALLED_APPS", [value])

    cst.parse_module(result)
    assert '"siwe\\"django\\\\custom"' in result
    assert again == result


def test_add_settings_block_idempotent():
    block = 'SIWE_DJANGO = {"DOMAIN": "example.com"}\n'
    source = _settings_skeleton()

    once = add_settings_block(source, block, name="SIWE_DJANGO")
    twice = add_settings_block(once, block, name="SIWE_DJANGO")

    assert once.count("SIWE_DJANGO") == 1
    assert once == twice


def test_ensure_url_include_appends_to_existing_urlpatterns():
    source = _urls_skeleton()

    result = ensure_url_include(source, "auth/siwe/", "siwe_django.urls")

    assert "include" in result
    assert "siwe_django.urls" in result
    assert "auth/siwe/" in result


def test_ensure_url_include_idempotent():
    once = ensure_url_include(_urls_skeleton(), "auth/siwe/", "siwe_django.urls")
    twice = ensure_url_include(once, "auth/siwe/", "siwe_django.urls")

    assert once == twice


# -----------------------------------------------------------------------------
# scaffold
# -----------------------------------------------------------------------------


def test_write_login_template_drops_file(tmp_path: Path):
    written = write_login_template(tmp_path)

    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert "Sign in with Ethereum" in text
    assert "personal_sign" in text


def test_write_login_template_skips_when_present(tmp_path: Path):
    target = tmp_path / "templates" / "siwe_django" / "siwe_login.html"
    target.parent.mkdir(parents=True)
    target.write_text("custom", encoding="utf-8")

    write_login_template(tmp_path)

    assert target.read_text(encoding="utf-8") == "custom"


# -----------------------------------------------------------------------------
# init command (typer)
# -----------------------------------------------------------------------------


@pytest.fixture
def fake_django_project(tmp_path: Path) -> Path:
    inner = tmp_path / "myproj"
    inner.mkdir()
    (inner / "settings.py").write_text(_settings_skeleton(), encoding="utf-8")
    (inner / "urls.py").write_text(_urls_skeleton(), encoding="utf-8")
    return tmp_path


def test_init_command_patches_settings_and_urls(fake_django_project: Path):
    result = runner.invoke(
        app,
        [
            "init",
            "--project",
            str(fake_django_project),
            "--no-template",
            "--no-migrate",
        ],
    )

    assert result.exit_code == 0, result.output
    settings_text = (fake_django_project / "myproj" / "settings.py").read_text()
    urls_text = (fake_django_project / "myproj" / "urls.py").read_text()
    assert "siwe_django" in settings_text
    assert "siwe_django.backend.SiweBackend" in settings_text
    assert "SIWE_DJANGO" in settings_text
    assert "siwe_django.urls" in urls_text


def test_init_command_reports_no_op_when_already_configured(
    fake_django_project: Path,
):
    runner.invoke(
        app,
        [
            "init",
            "--project",
            str(fake_django_project),
            "--no-template",
            "--no-migrate",
        ],
    )
    second = runner.invoke(
        app,
        [
            "init",
            "--project",
            str(fake_django_project),
            "--no-template",
            "--no-migrate",
        ],
    )

    assert second.exit_code == 0
    assert "nothing to do" in second.output.lower()


def test_init_command_drf_uses_drf_urls(fake_django_project: Path):
    result = runner.invoke(
        app,
        [
            "init",
            "--project",
            str(fake_django_project),
            "--drf",
            "--no-template",
            "--no-migrate",
        ],
    )

    assert result.exit_code == 0, result.output
    urls_text = (fake_django_project / "myproj" / "urls.py").read_text()
    assert "siwe_django.drf.urls" in urls_text


def test_init_command_writes_template_by_default(fake_django_project: Path):
    runner.invoke(
        app,
        ["init", "--project", str(fake_django_project), "--no-migrate"],
    )

    template = (
        fake_django_project / "templates" / "siwe_django" / "siwe_login.html"
    )
    assert template.exists()


def test_init_command_aborts_when_settings_missing(tmp_path: Path):
    result = runner.invoke(
        app,
        ["init", "--project", str(tmp_path), "--no-template", "--no-migrate"],
    )

    assert result.exit_code != 0
    assert "settings.py" in result.output


# -----------------------------------------------------------------------------
# scaffold-templates command
# -----------------------------------------------------------------------------


def test_scaffold_templates_command(fake_django_project: Path):
    result = runner.invoke(
        app,
        ["scaffold-templates", "--project", str(fake_django_project)],
    )

    assert result.exit_code == 0, result.output
    template = (
        fake_django_project / "templates" / "siwe_django" / "siwe_login.html"
    )
    assert template.exists()
    urls_text = (fake_django_project / "myproj" / "urls.py").read_text()
    assert "siwe_django.urls" in urls_text


# -----------------------------------------------------------------------------
# doctor command
# -----------------------------------------------------------------------------


def test_doctor_diagnose_flags_missing_domain_and_uri():
    findings = doctor_cmd.diagnose({})

    severities = {f.severity for f in findings}
    messages = " ".join(f.message for f in findings)
    assert "warning" in severities
    assert "DOMAIN" in messages
    assert "URI" in messages


def test_doctor_diagnose_clean_returns_no_findings():
    findings = doctor_cmd.diagnose(
        {
            "DOMAIN": "example.com",
            "URI": "https://example.com/",
        }
    )

    assert findings == []


def test_doctor_diagnose_flags_chain_without_rpc():
    findings = doctor_cmd.diagnose(
        {
            "DOMAIN": "example.com",
            "URI": "https://example.com/",
            "ALLOWED_CHAIN_IDS": [1, 137],
            "RPC_URLS": {1: "https://example.invalid"},
        }
    )

    messages = "\n".join(f.message for f in findings)
    assert "137" in messages or "without an RPC" in messages


def test_doctor_settings_from_env_parses_rpcs():
    config = doctor_cmd.settings_from_env(
        {
            "SIWE_RPC_1": "https://mainnet.example",
            "SIWE_RPC_137": "https://polygon.example",
            "SIWE_DOMAIN": "example.com",
            "SIWE_ETHID_ENABLED": "1",
        }
    )

    assert config["RPC_URLS"] == {
        1: "https://mainnet.example",
        137: "https://polygon.example",
    }
    assert config["DOMAIN"] == "example.com"
    assert config["ETHID_ENABLED"] is True


# -----------------------------------------------------------------------------
# migrate-from-payton
# -----------------------------------------------------------------------------


def test_migrate_payton_rewrite_text_replaces_known_paths():
    source = (
        "from siwe_auth.backends import SiweBackend\n"
        "from siwe_auth.models import Wallet\n"
        "INSTALLED_APPS = ['siwe_auth']\n"
    )

    rewritten, applied = migrate_payton.rewrite_text(source)

    assert applied >= 2
    assert "siwe_django" in rewritten
    assert "SiweWallet" in rewritten
    assert "siwe_auth" not in rewritten


def test_migrate_payton_rewrite_project(tmp_path: Path):
    target = tmp_path / "app.py"
    target.write_text(
        "from siwe_auth.backends import SiweBackend\n", encoding="utf-8"
    )

    summary = migrate_payton.rewrite_project(tmp_path)

    assert summary.files_modified == 1
    assert summary.replacements_applied >= 1
    assert "siwe_django" in target.read_text(encoding="utf-8")


def test_migrate_payton_command_dry_run(tmp_path: Path):
    target = tmp_path / "app.py"
    target.write_text(
        "from siwe_auth.backends import SiweBackend\n", encoding="utf-8"
    )

    result = runner.invoke(
        app, ["migrate-from-payton", "--project", str(target.parent), "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert "app.py" in result.output
    assert "siwe_auth" in target.read_text(encoding="utf-8")
