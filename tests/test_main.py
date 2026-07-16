"""Tests for routes/main.py - dashboard and SAP connect."""

from unittest.mock import patch, MagicMock

_ADMIN_DATA = {
    "username": "admin",
    "full_name": "Admin",
    "role": "admin",
    "is_active": True,
    "must_change_password": False,
}


def _login(client, app):
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(
        app.user_manager, "get_current_user", return_value=_ADMIN_DATA
    ), patch.object(
        app.user_manager, "get_user", return_value=_ADMIN_DATA
    ):
        client.post("/login", data={"username": "admin", "password": "pass"})


# ── Index ───────────────────────────────────────────────────────────────────


def test_index_unauthenticated(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_index_authenticated_redirects(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "dashboard" in resp.headers.get("Location", "")


# ── Dashboard ───────────────────────────────────────────────────────────────


def test_dashboard_requires_auth(client):
    resp = client.get("/dashboard")
    assert resp.status_code in (302, 401)


def test_dashboard_loads(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/dashboard")
        assert resp.status_code == 200


def test_dashboard_with_date_filter(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/dashboard?date=2026-01-01")
        assert resp.status_code == 200


# ── SAP connect ─────────────────────────────────────────────────────────────


def test_sap_connect_requires_auth(client):
    resp = client.post("/api/sap/connect")
    assert resp.status_code in (302, 401)


def test_sap_connect_unavailable(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        # SAP is not available locally
        resp = client.post("/api/sap/connect")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
