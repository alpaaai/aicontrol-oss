"""Tests for app.core.license_gate plan-gating dependencies."""
import pytest
from unittest.mock import patch
from fastapi import HTTPException

from app.core.license_gate import require_enterprise_license, require_business_license
from app.core.license import LicenseInfo, LicenseError


def _community_info():
    return LicenseInfo(plan="community", company=None, email=None, expires_at=None)

def _business_info():
    return LicenseInfo(plan="business", company="Acme", email="a@acme.com", expires_at=None)

def _enterprise_info():
    return LicenseInfo(plan="enterprise", company="Aon", email="a@aon.com", expires_at=None)


def test_enterprise_gate_allows_enterprise():
    with patch("app.core.license_gate.get_license_info", return_value=_enterprise_info()):
        require_enterprise_license()  # should not raise


def test_enterprise_gate_blocks_community():
    with patch("app.core.license_gate.get_license_info", return_value=_community_info()):
        with pytest.raises(HTTPException) as exc:
            require_enterprise_license()
        assert exc.value.status_code == 402


def test_enterprise_gate_blocks_business():
    with patch("app.core.license_gate.get_license_info", return_value=_business_info()):
        with pytest.raises(HTTPException) as exc:
            require_enterprise_license()
        assert exc.value.status_code == 402


def test_business_gate_allows_business():
    with patch("app.core.license_gate.get_license_info", return_value=_business_info()):
        require_business_license()  # should not raise


def test_business_gate_allows_enterprise():
    with patch("app.core.license_gate.get_license_info", return_value=_enterprise_info()):
        require_business_license()  # enterprise includes business


def test_business_gate_blocks_community():
    with patch("app.core.license_gate.get_license_info", return_value=_community_info()):
        with pytest.raises(HTTPException) as exc:
            require_business_license()
        assert exc.value.status_code == 402


def test_invalid_key_raises_402():
    """A tampered or malformed key should return 402, not 500."""
    with patch("app.core.license_gate.get_license_info",
               side_effect=HTTPException(status_code=402, detail="invalid")):
        with pytest.raises(HTTPException) as exc:
            require_enterprise_license()
        assert exc.value.status_code == 402
