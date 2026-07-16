"""Tests for routes/api.py - REST API endpoints."""

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


# ── /api/products ───────────────────────────────────────────────────────────


def test_api_products_requires_auth(client):
    resp = client.get("/api/products")
    assert resp.status_code in (302, 401)


def test_api_products_list(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/products")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data
        assert "total" in data


def test_api_products_with_search(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/products?search=acetona")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data


def test_api_products_pagination(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/products?page=1&per_page=5")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["page"] == 1
        assert data["per_page"] == 5


# ── /api/products/<code> ────────────────────────────────────────────────────


def test_api_product_detail_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        mock_product = {"product_id": "123", "chemical_name": "Test"}
        with patch.object(
            app.smart_label, "get_product_data", return_value=mock_product
        ):
            resp = client.get("/api/products/123")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["product"]["product_id"] == "123"


def test_api_product_detail_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        with patch.object(
            app.smart_label, "get_product_data", return_value=None
        ):
            resp = client.get("/api/products/NONEXISTENT")
            assert resp.status_code == 404


# ── /api/orders ─────────────────────────────────────────────────────────────


def test_api_orders_list(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/orders")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "orders" in data


def test_api_orders_with_status_filter(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/orders?status=Pendiente")
        assert resp.status_code == 200


# ── /api/orders/<id> ────────────────────────────────────────────────────────


def test_api_order_detail_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        mock_order = {"order_id": "ORD-001", "status": "Pendiente"}
        with patch.object(
            app.order_status_mgr, "get_order", return_value=mock_order
        ):
            resp = client.get("/api/orders/ORD-001")
            assert resp.status_code == 200


def test_api_order_detail_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        with patch.object(
            app.order_status_mgr, "get_order", return_value=None
        ):
            resp = client.get("/api/orders/NONEXISTENT")
            assert resp.status_code == 404


# ── /api/stats ──────────────────────────────────────────────────────────────


def test_api_stats(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data
        assert "orders" in data
        assert "sap" in data


# ── /api/history ────────────────────────────────────────────────────────────


def test_api_history(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "history" in data


def test_api_history_with_limit(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/history?limit=5")
        assert resp.status_code == 200


# ── /api/sap/test ───────────────────────────────────────────────────────────


def test_api_sap_test_unavailable(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        # SAP is not available locally
        resp = client.get("/api/sap/test")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["connected"] is False


# ── /api/pictograms/<name> ──────────────────────────────────────────────────


def test_api_pictogram_not_found(client, app):
    resp = client.get("/api/pictograms/nonexistent")
    assert resp.status_code == 404


# ── /api/tara/suggestions ──────────────────────────────────────────────────


def test_api_tara_suggestions_zero_weight(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/api/tara/suggestions?peso_neto=0")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["suggestions"] == []


def test_api_tara_suggestions_valid(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        mock_suggestions = [
            {"id": "C1", "name": "Cubeta 20L", "tara_kg": 1.2, "material": "Plastic"}
        ]
        with patch.object(
            app.tara_manager,
            "get_smart_suggestions",
            return_value=mock_suggestions,
        ):
            resp = client.get("/api/tara/suggestions?peso_neto=25")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["suggestions"]) == 1
