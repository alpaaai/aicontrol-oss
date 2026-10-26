"""Tests for scripts/issue_license.py -- keygen and per-sale code issuing.
Issued codes must decode with app.core.license_key using the generated
public key."""
import stat
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.core import license_key
from scripts import issue_license

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
