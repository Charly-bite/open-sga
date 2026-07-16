"""
Authentication routes for SGA Web
"""
import logging

logger = logging.getLogger(__name__)

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    session,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from models import User
from extensions import limiter

auth_bp = Blueprint("auth", __name__)


def _is_safe_url(target):
    """Validate that redirect target is a safe relative URL (prevents open redirect)."""
    from urllib.parse import urlparse, urljoin
    from flask import request as _req

    ref_url = urlparse(_req.host_url)
    test_url = urlparse(urljoin(_req.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login page — TEMPORARY: password bypass enabled"""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        remember = request.form.get("remember", False)

        if not username:
            flash("Por favor ingrese su usuario", "error")
            return render_template("auth/login.html")

        # ── TEMPORARY BYPASS: skip password, login by username only ──
        user_manager = current_app.user_manager
        # Try to find the user in SQL or JSON
        data = user_manager._load_data()
        user_data = None
        for u in data.get("users", []):
            if u["username"].lower() == username.lower():
                user_data = u
                break

        if user_data is None:
            # User not found — create a temporary session as operator
            user_data = {
                "username": username,
                "role": "operator",
                "full_name": username,
                "warehouse": "",
                "must_change_password": False,
            }

        if not user_data.get("is_active", True):
            flash(
                "Su cuenta ha sido desactivada. Contacte al administrador.", "error"
            )
            return render_template("auth/login.html")

        user = User(user_data)
        login_result = login_user(user, remember=remember)
        session.permanent = True

        logger.info(f"[LOGIN] login_user({user.username}) returned: {login_result}")
        logger.info(f"[LOGIN] user.is_active={user.is_active}, session keys={list(session.keys())}")
        logger.info(f"[LOGIN] session._user_id={session.get('_user_id', 'NOT SET')}")

        if not login_result:
            logger.error(f"[LOGIN] login_user FAILED for {user.username}!")
            flash("Error al iniciar sesión. Intente de nuevo.", "error")
            return render_template("auth/login.html")

        flash(f"Bienvenido, {user.full_name}", "success")

        next_page = request.args.get("next")
        if next_page and not _is_safe_url(next_page):
            next_page = None
        target = next_page or url_for("main.dashboard")
        logger.info(f"[LOGIN] Redirecting to: {target}")
        return redirect(target)

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """User logout"""
    logout_user()
    flash("Sesión cerrada exitosamente", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password page"""
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate
        if not all([current_password, new_password, confirm_password]):
            flash("Todos los campos son requeridos", "error")
            return render_template("auth/change_password.html")

        if new_password != confirm_password:
            flash("Las contraseñas nuevas no coinciden", "error")
            return render_template("auth/change_password.html")

        if len(new_password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres", "error")
            return render_template("auth/change_password.html")

        # Verify current password
        user_manager = current_app.user_manager
        if not user_manager.authenticate(current_user.username, current_password):
            flash("Contraseña actual incorrecta", "error")
            return render_template("auth/change_password.html")

        # Change password using update_user method
        req_user = {"username": current_user.username, "role": current_user.role}
        success, message = user_manager.update_user(
            current_user.username, requesting_user=req_user, password=new_password
        )
        if success:
            flash("Contraseña cambiada exitosamente", "success")
            return redirect(url_for("main.dashboard"))
        else:
            flash(f"Error al cambiar la contraseña: {message}", "error")

    return render_template("auth/change_password.html")
