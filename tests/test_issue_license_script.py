"""Tests for scripts/internal/issue_license.py -- keygen and per-sale code issuing.
Issued codes must decode with app.core.license_key using the generated
public key."""
import os
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core import license_key
from scripts.internal import issue_license

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def test_keygen_writes_private_key_and_returns_matching_public_key(tmp_path):
    key_path = tmp_path / "signing.pem"
    public_key = issue_license.generate_keypair(key_path)
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    private_key = issue_license.load_private_key(key_path)
    assert license_key.public_key_to_str(private_key.public_key()) == public_key


def test_keygen_refuses_to_overwrite(tmp_path):
    key_path = tmp_path / "signing.pem"
    key_path.write_text("existing")
    with pytest.raises(FileExistsError):
        issue_license.generate_keypair(key_path)
    assert key_path.read_text() == "existing"


@pytest.mark.parametrize("plan,days", [("trial", 90), ("business", 395), ("enterprise", 395)])
def test_issued_code_verifies_with_default_expiry(tmp_path, plan, days):
    key_path = tmp_path / "signing.pem"
    public_key = issue_license.generate_keypair(key_path)
    code = issue_license.issue_code(
        issue_license.load_private_key(key_path), plan, "buyer@example.com", "pi_123", now=NOW
    )
    with patch.object(license_key, "PUBLIC_KEY", public_key):
        decoded = license_key.decode_license_code(code)
    assert decoded.plan == plan
    assert decoded.email == "buyer@example.com"
    assert decoded.order == "pi_123"
    assert decoded.issued_at == NOW
    assert decoded.expires_at == NOW + timedelta(days=days)


def test_days_override(tmp_path):
    key_path = tmp_path / "signing.pem"
    public_key = issue_license.generate_keypair(key_path)
    code = issue_license.issue_code(
        issue_license.load_private_key(key_path), "enterprise", "dev@aictl.io", "internal", now=NOW, days=3650
    )
    with patch.object(license_key, "PUBLIC_KEY", public_key):
        assert license_key.decode_license_code(code).expires_at == NOW + timedelta(days=3650)


def test_unknown_plan_is_refused(tmp_path):
    key_path = tmp_path / "signing.pem"
    issue_license.generate_keypair(key_path)
    with pytest.raises(ValueError):
        issue_license.issue_code(issue_license.load_private_key(key_path), "community", "a@b.c", "x", now=NOW)


def test_cli_keygen_then_issue_prints_a_verifiable_code(tmp_path, capsys):
    key_path = tmp_path / "signing.pem"
    assert issue_license.main(["keygen", "--out", str(key_path)]) == 0
    public_key = capsys.readouterr().out.strip().splitlines()[-1]

    assert issue_license.main([
        "issue", "--key", str(key_path), "--plan", "business",
        "--email", "buyer@example.com", "--order", "pi_456",
    ]) == 0
    code = capsys.readouterr().out.strip().splitlines()[-1]
    with patch.object(license_key, "PUBLIC_KEY", public_key):
        decoded = license_key.decode_license_code(code)
    assert decoded.plan == "business"
    assert decoded.order == "pi_456"


@pytest.mark.parametrize("days", [0, -1, 3651])
def test_issue_code_rejects_days_outside_1_to_3650(tmp_path, days):
    key_path = tmp_path / "signing.pem"
    issue_license.generate_keypair(key_path)
    with pytest.raises(ValueError):
        issue_license.issue_code(
            issue_license.load_private_key(key_path), "business", "a@b.c", "x", now=NOW, days=days
        )


@pytest.mark.parametrize("days", [1, 3650])
def test_issue_code_accepts_the_days_bounds(tmp_path, days):
    key_path = tmp_path / "signing.pem"
    issue_license.generate_keypair(key_path)
    assert issue_license.issue_code(
        issue_license.load_private_key(key_path), "business", "a@b.c", "x", now=NOW, days=days
    )


def test_cli_rejects_out_of_range_days_without_printing_a_code(tmp_path, capsys):
    key_path = tmp_path / "signing.pem"
    issue_license.generate_keypair(key_path)
    rc = issue_license.main([
        "issue", "--key", str(key_path), "--plan", "business",
        "--email", "a@b.c", "--order", "x", "--days", "0",
    ])
    captured = capsys.readouterr()
    assert rc == 1
    assert "AICTL1" not in captured.out
    assert "days" in captured.err


SH = Path(__file__).resolve().parent.parent / "scripts" / "internal" / "issue_license.sh"


def _run_sh(args, key_path):
    env = {**os.environ, "AICONTROL_LICENSE_SIGNING_KEY": str(key_path)}
    return subprocess.run(["bash", str(SH), *args], capture_output=True, text=True, env=env, cwd="/")


def test_sh_wrapper_issues_a_verifiable_code_from_any_cwd(tmp_path):
    key_path = tmp_path / "signing.pem"
    public_key = issue_license.generate_keypair(key_path)
    result = _run_sh(["enterprise", "buyer@example.com", "pi_123"], key_path)
    assert result.returncode == 0, result.stderr
    code = result.stdout.strip().splitlines()[-1]
    with patch.object(license_key, "PUBLIC_KEY", public_key):
        decoded = license_key.decode_license_code(code)
    assert decoded.plan == "enterprise"
    assert decoded.email == "buyer@example.com"
    assert decoded.order == "pi_123"


def test_sh_wrapper_passes_optional_days(tmp_path):
    key_path = tmp_path / "signing.pem"
    issue_license.generate_keypair(key_path)
    result = _run_sh(["business", "buyer@example.com", "pi_123", "30"], key_path)
    assert result.returncode == 0, result.stderr
    assert "valid 30 days" in result.stdout


def test_sh_wrapper_prints_usage_without_enough_args(tmp_path):
    result = _run_sh(["enterprise"], tmp_path / "signing.pem")
    assert result.returncode == 2
    assert "Usage:" in result.stderr
