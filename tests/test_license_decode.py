"""Tests for app.core.license decode_license_key()."""
import base64
import json
import time
import uuid

import pytest
from unittest.mock import patch

from app.core.license import decode_license_key, LicenseInfo, LicenseError


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _tamper_payload(token: str, new_payload: dict) -> str:
    """Replace the payload in a JWT without re-signing (signature becomes invalid)."""
    header_b64, _, sig_b64 = token.split(".")
    new_p = _b64url(json.dumps(new_payload, separators=(",", ":")).encode())
    return f"{header_b64}.{new_p}.{sig_b64}"


def test_community_returns_community_plan_when_key_empty():
    result = decode_license_key("")
    assert result.plan == "community"
    assert result.company is None
    assert result.is_enterprise is False
    assert result.is_business is False


def test_invalid_jwt_raises_license_error():
    with pytest.raises(LicenseError, match="invalid"):
        decode_license_key("not.a.jwt")


def test_wrong_issuer_raises_license_error(test_rsa_keypair, patch_license_public_key):
    """A valid JWT signed with the test key but wrong issuer should fail."""
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes

    private_key, _ = test_rsa_keypair
    payload = {
        "iss": "evil.com",
        "jti": str(uuid.uuid4()),
        "company": "Evil Corp",
        "email": "evil@evil.com",
        "plan": "enterprise",
        "issued_at": int(time.time()),
        "exp": int(time.time()) + 86400,
    }
    header = {"alg": "RS256", "typ": "JWT"}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = private_key.sign(f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256())
    token = f"{h}.{p}.{_b64url(sig)}"

    with pytest.raises(LicenseError, match="issuer"):
        decode_license_key(token)


def test_expired_token_raises_license_error(expired_enterprise_token, patch_license_public_key):
    with pytest.raises(LicenseError, match="expired"):
        decode_license_key(expired_enterprise_token)


def test_valid_enterprise_token_returns_enterprise_plan(valid_enterprise_token, patch_license_public_key):
    info = decode_license_key(valid_enterprise_token)
    assert info.plan == "enterprise"
    assert info.is_enterprise is True
    assert info.is_business is True
    assert info.company == "Test Corp"


def test_valid_business_token_returns_business_plan(valid_business_token, patch_license_public_key):
    info = decode_license_key(valid_business_token)
    assert info.plan == "business"
    assert info.is_enterprise is False
    assert info.is_business is True


def test_license_info_to_dict(valid_enterprise_token, patch_license_public_key):
    info = decode_license_key(valid_enterprise_token)
    d = info.to_dict()
    assert d["plan"] == "enterprise"
    assert "expires_at" in d
    assert "company" in d
    assert "email" in d
    assert "jti" not in d
    assert "iss" not in d
