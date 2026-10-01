"""Tests for AUDIT_AND_FIX_PLAN.md Section 4 (Compliance Report Export):

4.2 — soc2 and iso_42001 as actually-requested frameworks, in both mock mode
      and (mocked-LLM) live-shape mode.
4.3 — llm_model stored on the report reflects the actually-configured model,
      not a hardcoded constant.
4.4 — soc2/iso_42001 narrative-only scope limitation is explicitly disclosed
      in the generated report.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import require_admin
from app.core.license_gate import require_enterprise_license
import enterprise.compliance.service as service_module


def _setup_auth_overrides():
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[require_enterprise_license] = lambda: None


def _teardown_auth_overrides():
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(require_enterprise_license, None)


def _fake_write_factory(tmp_path):
    def _fake_write(rid, content, ext):
        p = tmp_path / f"{rid}.{ext}"
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
        return str(p)
    return _fake_write


async def _generate_md_report(frameworks: list[str], tmp_path):
    _setup_auth_overrides()
    try:
        with patch("enterprise.compliance.service.LocalFileStorage") as mock_cls:
            mock_storage = MagicMock()
            mock_cls.return_value = mock_storage
            mock_storage.write.side_effect = _fake_write_factory(tmp_path)

            with patch.object(service_module.settings, "LLM_MOCK_ENABLED", True):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/enterprise/compliance/report",
                        json={
                            "date_from": "2026-01-01",
                            "date_to": "2026-03-31",
                            "frameworks": frameworks,
                            "format": "md",
                        },
                    )
    finally:
        _teardown_auth_overrides()
    return response


@pytest.mark.asyncio
async def test_soc2_mock_mode_report_generates_with_real_narrative(tmp_path):
    response = await _generate_md_report(["soc2"], tmp_path)
    assert response.status_code == 200
    assert b"SOC 2 Type II" in response.content
    assert b"CC6.1" in response.content
    assert b"CC7.2" in response.content


@pytest.mark.asyncio
async def test_iso_42001_mock_mode_report_generates_with_real_narrative(tmp_path):
    response = await _generate_md_report(["iso_42001"], tmp_path)
    assert response.status_code == 200
    assert b"ISO 42001" in response.content
    assert b"Clause 6.1" in response.content
    assert b"Clause 9.1" in response.content


async def _generate_md_report_live_shape(frameworks: list[str], tmp_path, fake_llm_json: str):
    _setup_auth_overrides()
    try:
        with patch("enterprise.compliance.service.LocalFileStorage") as mock_cls:
            mock_storage = MagicMock()
            mock_cls.return_value = mock_storage
            mock_storage.write.side_effect = _fake_write_factory(tmp_path)

            with patch.object(service_module.settings, "LLM_MOCK_ENABLED", False):
                with patch.object(service_module.AIClient, "complete", new=AsyncMock(return_value=fake_llm_json)):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        response = await client.post(
                            "/enterprise/compliance/report",
                            json={
                                "date_from": "2026-01-01",
                                "date_to": "2026-03-31",
                                "frameworks": frameworks,
                                "format": "md",
                            },
                        )
    finally:
        _teardown_auth_overrides()
    return response


@pytest.mark.asyncio
async def test_soc2_live_shape_report_generates_from_llm_response(tmp_path):
    fake_json = json.dumps({"soc2": "## SOC 2 Type II\n\nLive-shape narrative content.\n"})
    response = await _generate_md_report_live_shape(["soc2"], tmp_path, fake_json)
    assert response.status_code == 200
    assert b"Live-shape narrative content." in response.content


@pytest.mark.asyncio
async def test_iso_42001_live_shape_report_generates_from_llm_response(tmp_path):
    fake_json = json.dumps({"iso_42001": "## ISO 42001\n\nLive-shape narrative content.\n"})
    response = await _generate_md_report_live_shape(["iso_42001"], tmp_path, fake_json)
    assert response.status_code == 200
    assert b"Live-shape narrative content." in response.content


@pytest.mark.asyncio
async def test_llm_model_stored_on_report_reflects_configured_model_not_hardcoded(tmp_path):
    fake_json = json.dumps({"soc2": "## SOC 2\n\nContent.\n"})
    _setup_auth_overrides()
    try:
        with patch("enterprise.compliance.service.LocalFileStorage") as mock_cls:
            mock_storage = MagicMock()
            mock_cls.return_value = mock_storage
            mock_storage.write.side_effect = _fake_write_factory(tmp_path)

            with patch.object(service_module.settings, "LLM_MOCK_ENABLED", False):
                with patch.object(service_module.settings, "LLM_MODEL", "test-configured-model-xyz"):
                    with patch.object(service_module.AIClient, "complete", new=AsyncMock(return_value=fake_json)):
                        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                            await client.post(
                                "/enterprise/compliance/report",
                                json={
                                    "date_from": "2026-01-01",
                                    "date_to": "2026-03-31",
                                    "frameworks": ["soc2"],
                                    "format": "md",
                                },
                            )
                            list_response = await client.get("/enterprise/compliance/reports")
    finally:
        _teardown_auth_overrides()

    reports = list_response.json()
    assert reports[0]["llm_model"] == "test-configured-model-xyz"


@pytest.mark.asyncio
async def test_soc2_report_discloses_narrative_only_scope_limitation(tmp_path):
    response = await _generate_md_report(["soc2"], tmp_path)
    assert response.status_code == 200
    text = response.content.decode()
    assert "SOC 2" in text
    assert "no per-policy control mapping" in text.lower() or "narrative-only" in text.lower()


@pytest.mark.asyncio
async def test_iso_42001_report_discloses_narrative_only_scope_limitation(tmp_path):
    response = await _generate_md_report(["iso_42001"], tmp_path)
    assert response.status_code == 200
    text = response.content.decode()
    assert "ISO 42001" in text
    assert "no per-policy control mapping" in text.lower() or "narrative-only" in text.lower()


@pytest.mark.asyncio
async def test_eu_ai_act_report_does_not_get_narrative_only_disclaimer(tmp_path):
    response = await _generate_md_report(["eu_ai_act"], tmp_path)
    assert response.status_code == 200
    text = response.content.decode()
    assert "no per-policy control mapping" not in text.lower()
