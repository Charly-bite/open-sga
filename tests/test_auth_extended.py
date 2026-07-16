"""Tests for auth routes - login, logout, change password."""

from unittest.mock import patch, MagicMock


_ADMIN_DATA = {
    "username": "admin",
    "full_name": "Admin",
    "role": "admin",
    "is_active": True,
    "must_change_password": False,
}


def _login_helper(client, app):
    """Helper to log in a user for tests requiring authentication.

    Also patches get_user so the user_loader can find the user on subsequent requests.
    """
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(
        app.user_manager, "get_current_user", return_value=_ADMIN_DATA
    ), patch.object(
        app.user_manager, "get_user", return_value=_ADMIN_DATA
    ):
        client.post("/login", data={"username": "admin", "password": "pass"})


def test_login_get_renders_form(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_post_empty_fields(client):
    resp = client.post("/login", data={"username": "", "password": ""})
    assert resp.status_code in (200, 302)


def test_login_post_invalid_credentials(client, app):
    with patch.object(app.user_manager, "authenticate", return_value=False):
        resp = client.post(
            "/login", data={"username": "baduser", "password": "badpass"}
        )
        assert resp.status_code == 200


def test_login_post_valid_credentials(client, app):
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(
        app.user_manager, "get_current_user", return_value=_ADMIN_DATA
    ):
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "correct"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers.get("Location", "")


def test_login_inactive_user(client, app):
    user_data = {
        "username": "disabled",
        "full_name": "Disabled",
        "role": "viewer",
        "is_active": False,
    }
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(app.user_manager, "get_current_user", return_value=user_data):
        resp = client.post(
            "/login", data={"username": "disabled", "password": "pass"}
        )
        assert resp.status_code == 200


def test_login_must_change_password(client, app):
    user_data = {
        "username": "newuser",
        "full_name": "New",
        "role": "viewer",
        "is_active": True,
        "must_change_password": True,
    }
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(app.user_manager, "get_current_user", return_value=user_data):
        resp = client.post(
            "/login",
            data={"username": "newuser", "password": "pass"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "change-password" in resp.headers.get("Location", "")


def test_login_redirects_authenticated_user(client, app):
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(
        app.user_manager, "get_current_user", return_value=_ADMIN_DATA
    ), patch.object(
        app.user_manager, "get_user", return_value=_ADMIN_DATA
    ):
        client.post("/login", data={"username": "admin", "password": "pass"})
        resp = client.get("/login")
        assert resp.status_code == 302


def test_logout_redirects_to_login(client, app):
    with patch.object(
        app.user_manager, "authenticate", return_value=True
    ), patch.object(
        app.user_manager, "get_current_user", return_value=_ADMIN_DATA
    ), patch.object(
        app.user_manager, "get_user", return_value=_ADMIN_DATA
    ):
        client.post("/login", data={"username": "admin", "password": "pass"})
        resp = client.get("/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "")


def test_change_password_get(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_helper(client, app)
        resp = client.get("/change-password")
        assert resp.status_code == 200


def test_change_password_missing_fields(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_helper(client, app)
        resp = client.post(
            "/change-password",
            data={
                "current_password": "",
                "new_password": "",
                "confirm_password": "",
            },
        )
        assert resp.status_code == 200


def test_change_password_mismatch(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_helper(client, app)
        resp = client.post(
            "/change-password",
            data={
                "current_password": "old",
                "new_password": "newpass1",
                "confirm_password": "newpass2",
            },
        )
        assert resp.status_code == 200


def test_change_password_too_short(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_helper(client, app)
        resp = client.post(
            "/change-password",
            data={
                "current_password": "old",
                "new_password": "abc",
                "confirm_password": "abc",
            },
        )
        assert resp.status_code == 200


def test_change_password_wrong_current(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_helper(client, app)
        with patch.object(app.user_manager, "authenticate", return_value=False):
            resp = client.post(
                "/change-password",
                data={
                    "current_password": "wrong",
                    "new_password": "newpass123",
                    "confirm_password": "newpass123",
                },
            )
            assert resp.status_code == 200


def test_change_password_success(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_helper(client, app)
        with patch.object(
            app.user_manager, "authenticate", return_value=True
        ), patch.object(
            app.user_manager, "update_user", return_value=(True, "OK")
        ):
            resp = client.post(
                "/change-password",
                data={
                    "current_password": "old",
                    "new_password": "newpass123",
                    "confirm_password": "newpass123",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 302


def test_change_password_update_fails(client, app):
    with patch.object(app.user_manager, "get_user", return_value=_ADMIN_DATA):
        _login_helper(client, app)
        with patch.object(
            app.user_manager, "authenticate", return_value=True
        ), patch.object(
            app.user_manager, "update_user", return_value=(False, "Failed")
        ):
            resp = client.post(
                "/change-password",
                data={
                    "current_password": "old",
                    "new_password": "newpass123",
                    "confirm_password": "newpass123",
                },
            )
            assert resp.status_code == 200
