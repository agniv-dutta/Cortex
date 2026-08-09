"""Smoke test: app imports and healthz responds (no DB required)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_schema():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/v1/queries" in resp.json()["paths"]
    assert "/v1/decisions" in resp.json()["paths"]
