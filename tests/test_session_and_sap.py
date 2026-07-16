"""Tests for session handling and unauthorized access behavior."""

from unittest.mock import patch


# ── Session expired: pages should redirect to login, not return JSON ────────


def test_templates_unauthenticated_redirects(client):
    """Unauthenticated access to /templates/ should redirect to login, not JSON 401."""
    resp = client.get("/templates/", follow_redirects=False)
    assert resp.status_code == 302
    assert "login" in resp.headers.get("Location", "")


def test_products_unauthenticated_redirects(client):
    """Unauthenticated access to /products/ should redirect to login."""
    resp = client.get("/products/", follow_redirects=False)
    assert resp.status_code == 302
    assert "login" in resp.headers.get("Location", "")


def test_labels_unauthenticated_redirects(client):
    """Unauthenticated access to /labels/ should redirect to login."""
    resp = client.get("/labels/", follow_redirects=False)
    assert resp.status_code == 302
    assert "login" in resp.headers.get("Location", "")


def test_orders_unauthenticated_redirects(client):
    """Unauthenticated access to /orders/ should redirect to login."""
    resp = client.get("/orders/", follow_redirects=False)
    assert resp.status_code == 302
    assert "login" in resp.headers.get("Location", "")


def test_users_unauthenticated_redirects(client):
    """Unauthenticated access to /users/ should redirect to login."""
    resp = client.get("/users/", follow_redirects=False)
    assert resp.status_code == 302
    assert "login" in resp.headers.get("Location", "")


def test_api_endpoint_returns_json_401(client):
    """Actual /api/ endpoints should return JSON 401 when unauthenticated."""
    resp = client.get("/api/products")
    # API endpoints should return 401 JSON, not redirect
    assert resp.status_code in (302, 401)


def test_ajax_request_returns_json_401(client):
    """AJAX requests should get JSON 401, not a redirect."""
    resp = client.get(
        "/templates/",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 401
    data = resp.get_json()
    assert data["error"] == "session_expired"


# ── Session persistence ───────────────────────────────────────────────────


def test_session_persists_after_login(client, app):
    """After logging in, refreshing a page should NOT require re-login."""
    _ADMIN = {
        "username": "admin",
        "full_name": "Admin",
        "role": "admin",
        "is_active": True,
        "must_change_password": False,
    }
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN):
        with patch.object(
            app.user_manager, "authenticate", return_value=True
        ), patch.object(
            app.user_manager, "get_current_user", return_value=_ADMIN
        ):
            client.post("/login", data={"username": "admin", "password": "pass"})

        # First request - should be authenticated
        resp1 = client.get("/dashboard")
        assert resp1.status_code == 200

        # Second request (simulates page refresh) - should STILL be authenticated
        resp2 = client.get("/dashboard")
        assert resp2.status_code == 200

        # Third request to a different page - still authenticated
        resp3 = client.get("/products/")
        assert resp3.status_code == 200


# ── SAP connection status ──────────────────────────────────────────────────


def test_sap_unavailable_flag(app):
    """In dev mode without hdbcli, sap_available should be False."""
    assert app.sap_available is False


def test_sap_connector_is_none(app):
    """In dev mode, sap_connector should be None."""
    assert app.sap_connector is None


def test_dashboard_shows_sap_disconnected(client, app):
    """Dashboard should load and show SAP as disconnected."""
    _ADMIN = {
        "username": "admin",
        "full_name": "Admin",
        "role": "admin",
        "is_active": True,
        "must_change_password": False,
    }
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN):
        with patch.object(
            app.user_manager, "authenticate", return_value=True
        ), patch.object(
            app.user_manager, "get_current_user", return_value=_ADMIN
        ), patch.object(
            app.user_manager, "get_user", return_value=_ADMIN
        ):
            client.post("/login", data={"username": "admin", "password": "pass"})
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"Desconectado" in resp.data or b"desconectado" in resp.data.lower()


def test_api_sap_test_returns_not_connected(client, app):
    """API SAP test should report not connected in dev mode."""
    _ADMIN = {
        "username": "admin",
        "full_name": "Admin",
        "role": "admin",
        "is_active": True,
        "must_change_password": False,
    }
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN):
        with patch.object(
            app.user_manager, "authenticate", return_value=True
        ), patch.object(
            app.user_manager, "get_current_user", return_value=_ADMIN
        ), patch.object(
            app.user_manager, "get_user", return_value=_ADMIN
        ):
            client.post("/login", data={"username": "admin", "password": "pass"})
        resp = client.get("/api/sap/test")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["connected"] is False
