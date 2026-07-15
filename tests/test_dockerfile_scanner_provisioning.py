"""Confirms the Dockerfile provisions both scanner binaries (WS-A).
Static-analysis test (parses the Dockerfile text) — no Docker daemon
required, so this runs in the normal pytest suite, not just at E2E time."""
from pathlib import Path

DOCKERFILE = Path(__file__).parent.parent / "Dockerfile"


def test_dockerfile_provisions_skill_scanner():
    text = DOCKERFILE.read_text()
    assert "provision_skill_scanner_venv.sh" in text


def test_dockerfile_provisions_mcp_scanner():
    text = DOCKERFILE.read_text()
    assert "provision_mcp_scanner_venv.sh" in text


def test_dockerfile_installs_gpp_for_native_scanner_deps():
    """Both scanners' dependency trees include yara-python (C extension) --
    the base image only had gcc, not g++/build-essential, before this task."""
    text = DOCKERFILE.read_text()
    assert "g++" in text or "build-essential" in text


def test_dockerfile_chowns_scanner_venv_dir_to_runtime_user():
    """Scanner venvs install under /opt/aicontrol, outside the existing
    /app chown -- the non-root aicontrol user couldn't execute them
    without this."""
    text = DOCKERFILE.read_text()
    assert "chown" in text and "/opt/aicontrol" in text
