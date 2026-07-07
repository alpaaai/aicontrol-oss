"""Tests for POST/GET /admission-scans."""
import uuid
import pytest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport


@contextmanager
def _auth(role: str = "admin"):
    from app.main import app
    from app.core.auth import _get_verified_token
    app.dependency_overrides[_get_verified_token] = lambda: {"role": role}
    try:
        yield app
    finally:
        app.dependency_overrides.pop(_get_verified_token, None)


@pytest.mark.asyncio
async def test_create_admission_scan_requires_admin():
    with _auth(role="agent") as app:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/admission-scans", json={"target_type": "skill", "target_ref": "/some/path"}
            )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_admission_scan_runs_requested_scanner_and_persists_findings():
    from app.services.scanners.port import Finding

    fake_scan = AsyncMock(return_value=[
        Finding(severity="high", rule_id="r1", message="Found a thing"),
    ])

    with _auth(role="admin") as app, patch(
        "app.services.scanners.registry.SCANNER_REGISTRY",
        {"skill_scanner": type("FakeAdapter", (), {"scan": fake_scan, "name": "skill_scanner"})()},
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/admission-scans",
                json={"target_type": "skill", "target_ref": "/some/skill", "scanners": ["skill_scanner"]},
            )

    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    assert data[0]["scanner_name"] == "skill_scanner"
    assert data[0]["status"] == "completed"
    assert data[0]["findings"][0]["rule_id"] == "r1"
    fake_scan.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_admission_scan_marks_failed_on_scanner_exception():
    fake_scan = AsyncMock(side_effect=RuntimeError("boom"))

    with _auth(role="admin") as app, patch(
        "app.services.scanners.registry.SCANNER_REGISTRY",
        {"skill_scanner": type("FakeAdapter", (), {"scan": fake_scan, "name": "skill_scanner"})()},
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/admission-scans",
                json={"target_type": "skill", "target_ref": "/some/skill", "scanners": ["skill_scanner"]},
            )

    assert response.status_code == 201
    data = response.json()
    assert data[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_list_admission_scans_returns_200():
    with _auth(role="admin") as app:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/admission-scans")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_admission_scan_detail_404_for_unknown_id():
    with _auth(role="admin") as app:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/admission-scans/{uuid.uuid4()}")
    assert response.status_code == 404
