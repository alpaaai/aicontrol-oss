"""Tests that routers are mounted and startup runs."""
import pytest
from httpx import AsyncClient, ASGITransport


def _all_paths(routes):
    """Flatten app.routes, descending into FastAPI's _IncludedRouter wrappers."""
    paths = []
    for r in routes:
        if hasattr(r, "path"):
            paths.append(r.path)
        elif hasattr(r, "original_router"):
            paths.extend(_all_paths(r.original_router.routes))
    return paths


@pytest.mark.asyncio
async def test_intercept_route_exists():
    """POST /intercept route must be registered on the app."""
    from app.main import app
    routes = _all_paths(app.routes)
    assert "/intercept" in routes


@pytest.mark.asyncio
async def test_health_still_works():
    """GET /health must still return 200 after router changes."""
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
