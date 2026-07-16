"""Tests for routes/orders.py - order management, status updates, SAP sync."""

import os
from unittest.mock import patch, MagicMock

_ADMIN_DATA = {
    "username": "admin",
    "full_name": "Admin",
    "role": "admin",
    "is_active": True,
    "must_change_password": False,
}

_OPERATOR_DATA = {
    "username": "operator",
    "full_name": "Operator",
    "role": "operator",
    "is_active": True,
    "must_change_password": False,
}

_VIEWER_DATA = {
    "username": "viewer",
    "full_name": "Viewer",
    "role": "viewer",
    "is_active": True,
    "must_change_password": False,
}


def _login(client, app, user_data=None):
    data = user_data or _ADMIN_DATA
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(
        app.user_manager, "get_current_user", return_value=data
    ), patch.object(
        app.user_manager, "get_user", return_value=data
    ):
        client.post(
            "/login",
            data={"username": data["username"], "password": "pass"},
        )


# ── Orders index ────────────────────────────────────────────────────────────


def test_orders_index_requires_auth(client):
    resp = client.get("/orders/")
    assert resp.status_code in (302, 401)


def test_orders_index_loads(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/orders/")
        assert resp.status_code == 200


def test_orders_index_with_status_filter(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/orders/?status=Pendiente")
        assert resp.status_code == 200


def test_orders_index_with_search(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/orders/?search=12345")
        assert resp.status_code == 200


# ── Order detail ────────────────────────────────────────────────────────────


def test_order_detail_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        with patch.object(
            app.order_status_mgr, "get_order", return_value=None
        ):
            resp = client.get("/orders/NONEXISTENT")
            assert resp.status_code == 404


def test_order_detail_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        mock_order = {
            "order_id": "12345",
            "status": "Pendiente",
            "customer_name": "Test",
            "status_history": [],
        }
        with patch.object(
            app.order_status_mgr, "get_order", return_value=mock_order
        ):
            resp = client.get("/orders/12345")
            assert resp.status_code == 200


# ── Update status ───────────────────────────────────────────────────────────


def test_update_status_requires_permission(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login(client, app, _VIEWER_DATA)
        resp = client.post(
            "/orders/12345/status",
            json={"status": "En Proceso"},
        )
        assert resp.status_code == 403


def test_update_status_missing_status(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_OPERATOR_DATA):
        _login(client, app, _OPERATOR_DATA)
        resp = client.post(
            "/orders/12345/status",
            json={"status": ""},
        )
        assert resp.status_code == 400


def test_update_status_invalid(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_OPERATOR_DATA):
        _login(client, app, _OPERATOR_DATA)
        resp = client.post(
            "/orders/12345/status",
            json={"status": "InvalidStatusXYZ"},
        )
        assert resp.status_code == 400


def test_update_status_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_OPERATOR_DATA):
        _login(client, app, _OPERATOR_DATA)
        mock_result = {"order_id": "12345", "status": "Pendiente"}
        with patch.object(
            app.order_status_mgr, "update_status", return_value=mock_result
        ):
            resp = client.post(
                "/orders/12345/status",
                json={"status": "Pendiente"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


def test_update_status_order_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_OPERATOR_DATA):
        _login(client, app, _OPERATOR_DATA)
        with patch.object(
            app.order_status_mgr, "update_status", return_value=None
        ):
            resp = client.post(
                "/orders/12345/status",
                json={"status": "Pendiente"},
            )
            assert resp.status_code == 404


# ── Add manual order ────────────────────────────────────────────────────────


def test_add_manual_requires_permission(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login(client, app, _VIEWER_DATA)
        resp = client.post(
            "/orders/add",
            json={"order_id": "NEW1", "customer_name": "Test"},
        )
        assert resp.status_code == 403


def test_add_manual_missing_fields(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_OPERATOR_DATA):
        _login(client, app, _OPERATOR_DATA)
        resp = client.post(
            "/orders/add",
            json={"order_id": ""},
        )
        assert resp.status_code == 400


def test_add_manual_duplicate(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_OPERATOR_DATA):
        _login(client, app, _OPERATOR_DATA)
        with patch.object(
            app.order_status_mgr,
            "get_order",
            return_value={"order_id": "EXISTING"},
        ):
            resp = client.post(
                "/orders/add",
                json={"order_id": "EXISTING", "customer_name": "Test"},
            )
            assert resp.status_code == 400


def test_add_manual_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_OPERATOR_DATA):
        _login(client, app, _OPERATOR_DATA)
        with patch.object(
            app.order_status_mgr, "get_order", return_value=None
        ), patch.object(
            app.order_status_mgr,
            "import_from_sap",
            return_value={"order_id": "NEW1"},
        ):
            resp = client.post(
                "/orders/add",
                json={"order_id": "NEW1", "customer_name": "Test Customer"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


# ── Delete order ────────────────────────────────────────────────────────────


def test_delete_order_requires_admin(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_OPERATOR_DATA):
        _login(client, app, _OPERATOR_DATA)
        resp = client.delete("/orders/12345/delete")
        assert resp.status_code == 403


def test_delete_order_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        with patch.object(
            app.order_status_mgr, "delete_order", return_value=False
        ):
            resp = client.delete("/orders/NONEXISTENT/delete")
            assert resp.status_code == 404


def test_delete_order_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        with patch.object(
            app.order_status_mgr, "delete_order", return_value=True
        ):
            resp = client.delete("/orders/12345/delete")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


# ── SAP import ──────────────────────────────────────────────────────────────


def test_import_sap_unavailable(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.post(
            "/orders/import-sap",
            json={"order_number": "12345"},
        )
        assert resp.status_code == 503


def test_load_recent_sap_unavailable(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.post("/orders/load-recent-sap", json={})
        assert resp.status_code == 503


def test_sync_sap_unavailable(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.post("/orders/sync-sap")
        assert resp.status_code == 503


# ── Visor ───────────────────────────────────────────────────────────────────


def test_visor_loads(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/orders/visor")
        assert resp.status_code == 200


def test_api_active_orders(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.get("/orders/api/active")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "orders" in data
        assert "stats" in data


# ── Monitor (public) ───────────────────────────────────────────────────────


def test_monitor_page_loads(client):
    resp = client.get("/orders/monitor")
    assert resp.status_code == 200


def test_public_api_active_no_token(client, app):
    """When MONITOR_TOKEN is not set, access is open."""
    with patch.dict(os.environ, {"MONITOR_TOKEN": ""}, clear=False):
        resp = client.get("/orders/api/public/active")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "orders" in data


@patch.dict(os.environ, {"MONITOR_TOKEN": "secret123"})
def test_public_api_active_with_valid_token(client, app):
    resp = client.get("/orders/api/public/active?token=secret123")
    assert resp.status_code == 200


@patch.dict(os.environ, {"MONITOR_TOKEN": "secret123"})
def test_public_api_active_with_invalid_token(client, app):
    resp = client.get("/orders/api/public/active?token=wrong")
    assert resp.status_code == 401


def test_visor_sync_sap_unavailable(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login(client, app)
        resp = client.post("/orders/visor/sync")
        assert resp.status_code == 503
