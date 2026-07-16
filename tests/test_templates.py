"""Tests for routes/templates.py - template designer, CRUD, barcode preview."""

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


# ── Template index ──────────────────────────────────────────────────────────


def test_templates_index_requires_auth(client):
    resp = client.get("/templates/")
    assert resp.status_code in (302, 401)


def test_templates_index_loads(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/templates/")
        assert resp.status_code == 200


# ── Designer ────────────────────────────────────────────────────────────────


def test_designer_new(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/templates/designer")
        assert resp.status_code == 200


def test_designer_edit_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        mock_template = {
            "id": "t1",
            "name": "Test Template",
            "elements": [],
            "canvas": {"width": 100, "height": 50},
            "rotation": 0,
        }
        with patch.object(
            app.template_manager, "get_template", return_value=mock_template
        ):
            resp = client.get("/templates/designer/t1")
            assert resp.status_code == 200


def test_designer_edit_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.template_manager, "get_template", return_value=None
        ):
            resp = client.get("/templates/designer/nonexistent")
            assert resp.status_code == 404


# ── API save ────────────────────────────────────────────────────────────────


def test_api_save_requires_admin(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login_viewer(client, app)
        resp = client.post(
            "/templates/api/save",
            json={"name": "Test"},
        )
        assert resp.status_code == 403


def test_api_save_no_data(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.post(
            "/templates/api/save",
            data="",
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_api_save_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        saved = {"id": "t1", "name": "Test Template"}
        with patch.object(
            app.template_manager, "save_template", return_value=saved
        ):
            resp = client.post(
                "/templates/api/save",
                json={"name": "Test Template"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


def test_api_save_exception(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.template_manager,
            "save_template",
            side_effect=Exception("Disk full"),
        ):
            resp = client.post(
                "/templates/api/save",
                json={"name": "Test"},
            )
            assert resp.status_code == 500


# ── API list ────────────────────────────────────────────────────────────────


def test_api_list(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/templates/api/list")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "templates" in data


# ── API get ─────────────────────────────────────────────────────────────────


def test_api_get_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.template_manager,
            "get_template",
            return_value={"id": "t1"},
        ):
            resp = client.get("/templates/api/t1")
            assert resp.status_code == 200


def test_api_get_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.template_manager, "get_template", return_value=None
        ):
            resp = client.get("/templates/api/nonexistent")
            assert resp.status_code == 404


# ── API delete ──────────────────────────────────────────────────────────────


def test_api_delete_requires_admin(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login_viewer(client, app)
        resp = client.delete("/templates/api/t1")
        assert resp.status_code == 403


def test_api_delete_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.template_manager, "delete_template", return_value=True
        ):
            resp = client.delete("/templates/api/t1")
            assert resp.status_code == 200


def test_api_delete_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.template_manager, "delete_template", return_value=False
        ):
            resp = client.delete("/templates/api/nonexistent")
            assert resp.status_code == 404


# ── API duplicate ───────────────────────────────────────────────────────────


def test_api_duplicate_requires_admin(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login_viewer(client, app)
        resp = client.post("/templates/api/duplicate/t1")
        assert resp.status_code == 403


def test_api_duplicate_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.template_manager,
            "duplicate_template",
            return_value={"id": "t1-copy"},
        ):
            resp = client.post("/templates/api/duplicate/t1")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


def test_api_duplicate_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.template_manager, "duplicate_template", return_value=None
        ):
            resp = client.post("/templates/api/duplicate/nonexistent")
            assert resp.status_code == 404


# ── API fields ──────────────────────────────────────────────────────────────


def test_api_fields(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.get("/templates/api/fields")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "fields" in data


# ── API barcode preview ─────────────────────────────────────────────────────


def test_api_barcode_preview_empty_value(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.post(
            "/templates/api/barcode_preview",
            json={"value": ""},
        )
        assert resp.status_code == 400


def test_api_barcode_preview_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.post(
            "/templates/api/barcode_preview",
            json={"value": "TEST123", "bar_height_mm": 8, "bar_width": 1},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "svg" in data


# ── API product data ────────────────────────────────────────────────────────


def test_api_product_data_not_found(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.smart_label, "get_product_data", return_value=None
        ):
            resp = client.get("/templates/api/product_data/NONEXISTENT")
            assert resp.status_code == 404
