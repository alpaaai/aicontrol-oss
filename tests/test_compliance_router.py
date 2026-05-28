"""End-to-end tests for compliance report router.

Uses AsyncClient + ASGITransport (matching the existing project pattern).
PDF-format tests require weasyprint system libraries and are skipped on hosts
without them (confirmed working in Docker).
"""
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import require_admin
from app.core.license_gate import require_enterprise_license
from app.models.database import get_db
import enterprise.compliance.service as service_module


def _weasyprint_available() -> bool:
    import ctypes.util
    return ctypes.util.find_library("pangoft2-1.0-0") is not None


def _setup_auth_overrides():
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[require_enterprise_license] = lambda: None


def _teardown_auth_overrides():
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(require_enterprise_license, None)


@pytest.mark.asyncio
async def test_post_compliance_report_md_returns_200(tmp_path):
    def _fake_write(rid, content, ext):
        p = tmp_path / f"{rid}.{ext}"
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
        return str(p)

    _setup_auth_overrides()
    try:
        with patch("enterprise.compliance.service.LocalFileStorage") as mock_cls:
            mock_storage = MagicMock()
            mock_cls.return_value = mock_storage
            mock_storage.write.side_effect = _fake_write

            with patch.object(service_module.settings, "LLM_MOCK_ENABLED", True):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/enterprise/compliance/report",
                        json={
                            "date_from": "2026-01-01",
                            "date_to": "2026-03-31",
                            "frameworks": ["eu_ai_act"],
                            "format": "md",
                        },
                    )
    finally:
        _teardown_auth_overrides()

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_post_compliance_report_md_content_type(tmp_path):
    def _fake_write(rid, content, ext):
        p = tmp_path / f"{rid}.{ext}"
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
        return str(p)

    _setup_auth_overrides()
    try:
        with patch("enterprise.compliance.service.LocalFileStorage") as mock_cls:
            mock_storage = MagicMock()
            mock_cls.return_value = mock_storage
            mock_storage.write.side_effect = _fake_write

            with patch.object(service_module.settings, "LLM_MOCK_ENABLED", True):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/enterprise/compliance/report",
                        json={
                            "date_from": "2026-01-01",
                            "date_to": "2026-03-31",
                            "frameworks": ["eu_ai_act"],
                            "format": "md",
                        },
                    )
    finally:
        _teardown_auth_overrides()

    assert "text/markdown" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_post_compliance_report_md_has_content(tmp_path):
    def _fake_write(rid, content, ext):
        p = tmp_path / f"{rid}.{ext}"
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
        return str(p)

    _setup_auth_overrides()
    try:
        with patch("enterprise.compliance.service.LocalFileStorage") as mock_cls:
            mock_storage = MagicMock()
            mock_cls.return_value = mock_storage
            mock_storage.write.side_effect = _fake_write

            with patch.object(service_module.settings, "LLM_MOCK_ENABLED", True):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/enterprise/compliance/report",
                        json={
                            "date_from": "2026-01-01",
                            "date_to": "2026-03-31",
                            "frameworks": ["eu_ai_act"],
                            "format": "md",
                        },
                    )
    finally:
        _teardown_auth_overrides()

    assert len(response.content) > 100
    assert b"Compliance Report" in response.content or b"AIControl" in response.content


@pytest.mark.asyncio
async def test_get_compliance_reports_list_returns_200():
    _setup_auth_overrides()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/enterprise/compliance/reports")
    finally:
        _teardown_auth_overrides()

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _weasyprint_available(),
    reason="weasyprint system libraries not available on this host",
)
async def test_post_compliance_report_pdf_returns_pdf_bytes(tmp_path):
    def _fake_write(rid, content, ext):
        p = tmp_path / f"{rid}.{ext}"
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
        return str(p)

    _setup_auth_overrides()
    try:
        with patch("enterprise.compliance.service.LocalFileStorage") as mock_cls:
            mock_storage = MagicMock()
            mock_cls.return_value = mock_storage
            mock_storage.write.side_effect = _fake_write

            with patch.object(service_module.settings, "LLM_MOCK_ENABLED", True):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/enterprise/compliance/report",
                        json={
                            "date_from": "2026-01-01",
                            "date_to": "2026-03-31",
                            "frameworks": ["eu_ai_act"],
                            "format": "pdf",
                        },
                    )
    finally:
        _teardown_auth_overrides()

    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"
