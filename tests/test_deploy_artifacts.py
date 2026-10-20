"""Tests for the self-hosted deployment artifacts: container entrypoint,
compose files, frontend runtime-config script, verify.sh."""
import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _shim(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(script: Path, args: list[str], env: dict, bin_dir: Path | None = None):
    full_env = {"PATH": f"{bin_dir}:{os.environ['PATH']}" if bin_dir else os.environ["PATH"], **env}
    return subprocess.run(["sh", str(script), *args], capture_output=True, text=True, env=full_env, timeout=30)


# ── API container entrypoint ────────────────────────────────────────────────

ENTRYPOINT = ROOT / "docker-entrypoint.sh"


def test_entrypoint_runs_migrations_then_the_command(tmp_path):
    _shim(tmp_path, "alembic", f'echo "alembic $@" >> {tmp_path}/calls.log')
    result = _run(ENTRYPOINT, ["sh", "-c", f"echo started >> {tmp_path}/calls.log"], {}, tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "calls.log").read_text().splitlines() == ["alembic upgrade head", "started"]


def test_entrypoint_skips_migrations_when_disabled(tmp_path):
    _shim(tmp_path, "alembic", f'echo "alembic $@" >> {tmp_path}/calls.log')
    result = _run(ENTRYPOINT, ["sh", "-c", f"echo started >> {tmp_path}/calls.log"],
                  {"RUN_MIGRATIONS": "false"}, tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "calls.log").read_text().splitlines() == ["started"]


def test_entrypoint_does_not_start_the_app_when_migrations_fail(tmp_path):
    """Starting against a half-migrated schema is worse than not starting."""
    _shim(tmp_path, "alembic", "exit 3")
    result = _run(ENTRYPOINT, ["sh", "-c", f"echo started >> {tmp_path}/calls.log"], {}, tmp_path)
    assert result.returncode != 0
    assert not (tmp_path / "calls.log").exists()


# ── compose files ───────────────────────────────────────────────────────────

def _compose(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text())


def test_app_images_are_version_pinnable():
    """`:latest` hard-coded means an operator cannot pin or roll back a version."""
    services = _compose("docker-compose.app.yml")["services"]
    for name in ("api", "frontend"):
        image = services[name]["image"]
        assert "${AICONTROL_VERSION:-latest}" in image, f"{name} image is not pinnable: {image}"


def test_every_service_bounds_its_container_logs():
    """json-file logging is unbounded by default and fills the host disk."""
    for compose_file in ("docker-compose.yml", "docker-compose.app.yml"):
        for name, service in _compose(compose_file)["services"].items():
            options = service.get("logging", {}).get("options", {})
            assert options.get("max-size") and options.get("max-file"), f"{compose_file}:{name} logs are unbounded"


def test_frontend_healthcheck_uses_a_tool_present_in_the_image_and_ipv4():
    """nginx:alpine's busybox wget is guaranteed; resolving `localhost` there can
    pick ::1 while nginx listens on IPv4 only."""
    check = " ".join(_compose("docker-compose.app.yml")["services"]["frontend"]["healthcheck"]["test"])
    assert "127.0.0.1" in check and "localhost" not in check
    assert "curl" not in check


# ── frontend runtime config ─────────────────────────────────────────────────

FRONTEND_CONFIG = ROOT / "frontend" / "docker-entrypoint.d" / "40-aicontrol-config.sh"


def test_frontend_config_script_writes_the_api_url(tmp_path):
    result = _run(FRONTEND_CONFIG, [], {"AICONTROL_API_URL": "https://aicontrol.example.com:8001", "AICONTROL_CONFIG_DIR": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    content = (tmp_path / "config.js").read_text()
    assert 'apiUrl: "https://aicontrol.example.com:8001"' in content


def test_frontend_config_script_with_no_url_leaves_the_build_default(tmp_path):
    result = _run(FRONTEND_CONFIG, [], {"AICONTROL_CONFIG_DIR": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert "apiUrl" not in (tmp_path / "config.js").read_text()


def test_frontend_config_script_rejects_a_value_that_could_break_out_of_the_string(tmp_path):
    result = _run(FRONTEND_CONFIG, [], {"AICONTROL_API_URL": 'x"};alert(1);//', "AICONTROL_CONFIG_DIR": str(tmp_path)})
    assert result.returncode != 0
    assert not (tmp_path / "config.js").exists()


# ── verify.sh ───────────────────────────────────────────────────────────────

def test_verify_script_works_on_a_fresh_install_without_demo_data(tmp_path):
    """verify.sh used to exit immediately unless ADMIN_TOKEN (demo seed data)
    was set, so it could never validate a real customer install."""
    _shim(tmp_path, "docker", 'echo "/var/run/postgresql:5432 - accepting connections; alembic_version"')
    _shim(tmp_path, "curl", 'case "$*" in *health*) echo \'{"status":"ok","database":"ok"}\';; *setup/status*) echo \'{"setup_required":true}\';; *) echo 200;; esac')
    env = {k: v for k, v in os.environ.items() if k not in ("ADMIN_TOKEN",)}
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    result = subprocess.run(["bash", str(ROOT / "verify.sh")], capture_output=True, text=True, env=env,
                            cwd=tmp_path, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 failed" in result.stdout
