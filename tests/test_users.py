"""Tests for routes/users.py - user management CRUD."""

from unittest.mock import patch, MagicMock

_ADMIN_DATA = {
    "username": "admin",
    "full_name": "Admin User",
    "role": "admin",
    "is_active": True,
    "must_change_password": False,
}

_VIEWER_DATA = {
    "username": "viewer",
    "full_name": "Viewer User",
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


# ── Access control ──────────────────────────────────────────────────────────


def test_users_index_requires_login(client):
    resp = client.get("/users/")
    assert resp.status_code in (302, 401)


def test_users_index_requires_admin(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_VIEWER_DATA):
        _login_viewer(client, app)
        resp = client.get("/users/", follow_redirects=False)
        assert resp.status_code == 302
        assert "dashboard" in resp.headers.get("Location", "")


def test_users_index_admin_access(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.user_manager, "list_users", return_value=[]
        ):
            resp = client.get("/users/")
            assert resp.status_code == 200


# ── Add user ────────────────────────────────────────────────────────────────


def test_add_user_missing_fields(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.post(
            "/users/add",
            data={"username": "", "password": ""},
            follow_redirects=False,
        )
        assert resp.status_code == 302


def test_add_user_invalid_role(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.post(
            "/users/add",
            data={
                "username": "newuser",
                "password": "pass123",
                "role": "superadmin",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302


def test_add_user_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.user_manager,
            "create_user",
            return_value=(True, "Created"),
        ):
            resp = client.post(
                "/users/add",
                data={
                    "username": "newuser",
                    "password": "pass123",
                    "full_name": "New User",
                    "role": "viewer",
                    "warehouse": "WH-01",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 302


def test_add_user_failure(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.user_manager,
            "create_user",
            return_value=(False, "Already exists"),
        ):
            resp = client.post(
                "/users/add",
                data={
                    "username": "existing",
                    "password": "pass123",
                    "role": "viewer",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 302


# ── Edit user ───────────────────────────────────────────────────────────────


def test_edit_user_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.user_manager,
            "update_user",
            return_value=(True, "Updated"),
        ):
            resp = client.post(
                "/users/someuser/edit",
                data={
                    "full_name": "Updated Name",
                    "role": "operator",
                    "warehouse": "WH-02",
                    "is_active": "on",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 302


def test_edit_user_with_password(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.user_manager,
            "update_user",
            return_value=(True, "Updated"),
        ):
            resp = client.post(
                "/users/someuser/edit",
                data={
                    "password": "newpass123",
                    "warehouse": "WH-01",
                    "is_active": "on",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 302


def test_edit_user_empty_warehouse(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.post(
            "/users/someuser/edit",
            data={"warehouse": "  ", "is_active": "on"},
            follow_redirects=False,
        )
        assert resp.status_code == 302


def test_edit_user_failure(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.user_manager,
            "update_user",
            return_value=(False, "Failed"),
        ):
            resp = client.post(
                "/users/someuser/edit",
                data={"warehouse": "WH-01", "is_active": "on"},
                follow_redirects=False,
            )
            assert resp.status_code == 302


# ── Delete user ─────────────────────────────────────────────────────────────


def test_delete_user_self(client, app):
    """Admin cannot delete their own account."""
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        resp = client.post("/users/admin/delete", follow_redirects=False)
        assert resp.status_code == 302


def test_delete_user_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.user_manager,
            "delete_user",
            return_value=(True, "Deleted"),
        ):
            resp = client.post(
                "/users/otheruser/delete", follow_redirects=False
            )
            assert resp.status_code == 302


def test_delete_user_failure(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_admin(client, app)
        with patch.object(
            app.user_manager,
            "delete_user",
            return_value=(False, "Not found"),
        ):
            resp = client.post(
                "/users/otheruser/delete", follow_redirects=False
            )
            assert resp.status_code == 302
