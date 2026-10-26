"""Tests for app.core.license_key -- signed license code encode/decode.

Codes are signed with an ephemeral Ed25519 keypair per test and the module's
PUBLIC_KEY is patched to match, so no real signing key is involved."""
import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core import license_key

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def _payload(**overrides) -> dict:
    payload = {
        "plan": "business",
        "email": "buyer@example.com",
        "order": "pi_123",
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(days=395)).timestamp()),
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def signing_key():
    key = Ed25519PrivateKey.generate()
    with patch.object(license_key, "PUBLIC_KEY", license_key.public_key_to_str(key.public_key())):
        yield key


def test_valid_code_decodes_to_its_payload(signing_key):
    code = license_key.encode_license_code(signing_key, _payload())
    decoded = license_key.decode_license_code(code)
    assert decoded.plan == "business"
    assert decoded.email == "buyer@example.com"
    assert decoded.order == "pi_123"
    assert decoded.expires_at == NOW + timedelta(days=395)
    assert code.startswith("AICTL1.")


def test_surrounding_whitespace_is_ignored(signing_key):
    code = license_key.encode_license_code(signing_key, _payload())
    assert license_key.decode_license_code(f"  {code}\n") is not None


def test_edited_payload_is_rejected(signing_key):
    code = license_key.encode_license_code(signing_key, _payload(plan="business"))
    prefix, _, signature = code.split(".")
    forged = base64.urlsafe_b64encode(json.dumps(_payload(plan="enterprise")).encode()).rstrip(b"=").decode()
    assert license_key.decode_license_code(f"{prefix}.{forged}.{signature}") is None


def test_edited_signature_is_rejected(signing_key):
    code = license_key.encode_license_code(signing_key, _payload())
    prefix, payload, signature = code.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    assert license_key.decode_license_code(f"{prefix}.{payload}.{flipped}") is None


def test_code_signed_by_another_key_is_rejected(signing_key):
    other = Ed25519PrivateKey.generate()
    code = license_key.encode_license_code(other, _payload())
    assert license_key.decode_license_code(code) is None


@pytest.mark.parametrize("code", ["", "garbage", "AICTL1.only-two", "AICTL2.a.b", "AICTL1.!!!.###"])
def test_malformed_code_is_rejected(signing_key, code):
    assert license_key.decode_license_code(code) is None


@pytest.mark.parametrize("plan", ["community", "gold", None])
def test_signed_code_with_unknown_plan_is_rejected(signing_key, plan):
    code = license_key.encode_license_code(signing_key, _payload(plan=plan))
    assert license_key.decode_license_code(code) is None


def test_signed_code_missing_exp_is_rejected(signing_key):
    payload = _payload()
    del payload["exp"]
    code = license_key.encode_license_code(signing_key, payload)
    assert license_key.decode_license_code(code) is None


def test_empty_public_key_rejects_everything():
    key = Ed25519PrivateKey.generate()
    code = license_key.encode_license_code(key, _payload())
    with patch.object(license_key, "PUBLIC_KEY", ""):
        assert license_key.decode_license_code(code) is None


def test_is_expired_compares_against_now(signing_key):
    code = license_key.encode_license_code(signing_key, _payload(exp=int(NOW.timestamp())))
    decoded = license_key.decode_license_code(code)
    assert decoded.is_expired(NOW - timedelta(seconds=1)) is False
    assert decoded.is_expired(NOW) is True


@pytest.mark.parametrize("value", [10**18, -(10**18)])
def test_signed_code_with_out_of_range_exp_is_rejected(signing_key, value):
    code = license_key.encode_license_code(signing_key, _payload(exp=value))
    assert license_key.decode_license_code(code) is None


def test_signed_code_with_out_of_range_iat_decodes_without_an_issue_date(signing_key):
    code = license_key.encode_license_code(signing_key, _payload(iat=10**18))
    decoded = license_key.decode_license_code(code)
    assert decoded is not None
    assert decoded.issued_at is None
