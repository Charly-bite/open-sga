"""Tests for routes/products.py - product CRUD and search."""

from unittest.mock import patch, MagicMock

_ADMIN_DATA = {
    "username": "admin",
    "full_name": "Admin",
    "role": "admin",
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


def _login_admin(client, app):
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(
        app.user_manager, "get_current_user", return_value=_ADMIN_DATA
    ), patch.object(
        app.user_manager, "get_user", return_value=_ADMIN_DATA
    ):
        client.post("/login", data={"username": "admin", "password": "pass"})


def _login_viewer(client, app):
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(
        app.user_manager, "get_current_user", return_value=_VIEWER_DATA
    ), patch.object(
        app.user_manager, "get_user", return_value=_VIEWER_DATA
    ):
        client.post("/login", data={"username": "viewer", "password": "pass"})


# ── Products index ──────────────────────────────────────────────────────────


def test_products_index_requires_auth(client):
    resp = client.get("/products/")
    assert resp.status_code in (302, 401)


def test_products_index_loads(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/")
        assert resp.status_code == 200


def test_products_index_with_search(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/?search=acetona")
        assert resp.status_code == 200


def test_products_index_with_pagination(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/?page=2")
        assert resp.status_code == 200


def test_products_index_with_signal_filter(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/?signal=PELIGRO")
        assert resp.status_code == 200


def test_products_index_signal_filter_none(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/?signal=NONE")
        assert resp.status_code == 200


def test_products_index_pending_tab(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/?tab=pending")
        assert resp.status_code == 200


def test_products_index_with_sorting(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/?sort_by=product_id&sort_dir=desc")
        assert resp.status_code == 200


# ── Products search ─────────────────────────────────────────────────────────


def test_products_search_requires_auth(client):
    resp = client.get("/products/search?q=test")
    assert resp.status_code in (302, 401)


def test_products_search_empty_query(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/search?q=")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["products"] == []


def test_products_search_with_query(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/search?q=acetona&limit=5")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data


# ── Product detail ──────────────────────────────────────────────────────────


def test_product_detail_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        mock_product = {
            "product_id": "TEST001",
            "chemical_name": "Test Product",
            "h_statements": [],
            "p_statements": [],
            "pictograms": [],
        }
        with patch.object(
            app.smart_label, "get_product_data", return_value=mock_product
        ):
            resp = client.get("/products/TEST001")
            assert resp.status_code == 200


def test_product_detail_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.smart_label, "get_product_data", return_value=None
        ):
            resp = client.get("/products/NONEXISTENT")
            assert resp.status_code == 404


# ── Product edit ────────────────────────────────────────────────────────────


def test_product_edit_requires_admin(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login_viewer(client, app)
        resp = client.post(
            "/products/TEST001/edit",
            json={"Chemical Name": "Updated"},
        )
        assert resp.status_code == 403


def test_product_edit_get(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        mock_product = {"product_id": "TEST001", "chemical_name": "Test"}
        with patch.object(
            app.smart_label, "get_product_data", return_value=mock_product
        ):
            resp = client.get("/products/TEST001/edit")
            assert resp.status_code == 200


def test_product_edit_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.smart_label, "get_product_data", return_value=None
        ):
            resp = client.get("/products/NONEXISTENT/edit")
            assert resp.status_code == 404


def test_product_edit_post_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        mock_product = {"product_id": "TEST001", "chemical_name": "Test"}
        with patch.object(
            app.smart_label, "get_product_data", return_value=mock_product
        ), patch.object(
            app.smart_label, "update_product", return_value=True
        ), patch.object(
            app.smart_label, "reload"
        ):
            resp = client.post(
                "/products/TEST001/edit",
                json={"Chemical Name": "Updated Name"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


def test_product_edit_post_failure(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        mock_product = {"product_id": "TEST001", "chemical_name": "Test"}
        with patch.object(
            app.smart_label, "get_product_data", return_value=mock_product
        ), patch.object(
            app.smart_label, "update_product", return_value=False
        ):
            resp = client.post(
                "/products/TEST001/edit",
                json={"Chemical Name": "Updated Name"},
            )
            assert resp.status_code == 500


# ── Product add ─────────────────────────────────────────────────────────────


def test_product_add_get(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/products/add")
        assert resp.status_code == 200


def test_product_add_requires_admin(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login_viewer(client, app)
        resp = client.post(
            "/products/add",
            json={"Codigo interno": "NEW001", "Chemical Name": "New Product"},
        )
        assert resp.status_code == 403


def test_product_add_missing_fields(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.post(
            "/products/add",
            json={"Codigo interno": ""},
        )
        assert resp.status_code == 400


def test_product_add_duplicate(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.smart_label,
            "get_product_data",
            return_value={"product_id": "EXISTING"},
        ):
            resp = client.post(
                "/products/add",
                json={
                    "Codigo interno": "EXISTING",
                    "Chemical Name": "Test",
                },
            )
            assert resp.status_code == 400


def test_product_add_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.smart_label, "get_product_data", return_value=None
        ), patch.object(
            app.smart_label, "add_product", return_value=True
        ), patch.object(
            app.smart_label, "reload"
        ):
            resp = client.post(
                "/products/add",
                json={
                    "Codigo interno": "NEW001",
                    "Chemical Name": "New Product",
                },
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


def test_product_add_failure(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.smart_label, "get_product_data", return_value=None
        ), patch.object(
            app.smart_label, "add_product", return_value=False
        ):
            resp = client.post(
                "/products/add",
                json={
                    "Codigo interno": "NEW001",
                    "Chemical Name": "New Product",
                },
            )
            assert resp.status_code == 500


# ── Product delete ──────────────────────────────────────────────────────────


def test_product_delete_requires_admin(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login_viewer(client, app)
        resp = client.post("/products/TEST001/delete")
        assert resp.status_code == 403


def test_product_delete_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.smart_label, "get_product_data", return_value=None
        ):
            resp = client.post("/products/NONEXISTENT/delete")
            assert resp.status_code == 404


def test_product_delete_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        mock_product = {"product_id": "TEST001", "name": "Test Product"}
        with patch.object(
            app.smart_label, "get_product_data", return_value=mock_product
        ), patch.object(
            app.smart_label, "delete_product", return_value=True
        ), patch.object(
            app.smart_label, "reload"
        ):
            resp = client.post("/products/TEST001/delete")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


def test_product_delete_failure(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        mock_product = {"product_id": "TEST001", "name": "Test Product"}
        with patch.object(
            app.smart_label, "get_product_data", return_value=mock_product
        ), patch.object(
            app.smart_label, "delete_product", return_value=False
        ):
            resp = client.post("/products/TEST001/delete")
            assert resp.status_code == 500
