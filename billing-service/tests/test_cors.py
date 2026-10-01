from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_checkout_preflight_allowed_from_aictl_io():
    response = client.options(
        "/billing/checkout",
        headers={
            "Origin": "https://aictl.io",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "https://aictl.io"


def test_checkout_preflight_rejected_from_arbitrary_origin():
    response = client.options(
        "/billing/checkout",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers.keys()}
