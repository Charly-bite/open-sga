"""
User management routes for SGA Web
"""

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)
from flask_login import login_required, current_user
from user_manager import UserRole

users_bp = Blueprint("users", __name__)


def admin_required(f):
    """Decorator to require admin role"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash("Acceso denegado: Se requieren permisos de administrador", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)

    return decorated_function


@users_bp.route("/")
@login_required
@admin_required
def index():
    """List all users"""
    user_manager = current_app.user_manager

    # Create request context user dict
    requesting_user = {
        "username": current_user.username,
        "role": current_user.role,
        "full_name": current_user.full_name,
    }

    users = user_manager.list_users(requesting_user=requesting_user)
    return render_template("users/index.html", users=users, UserRole=UserRole)


@users_bp.route("/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    """Create a new user"""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    full_name = request.form.get("full_name", "").strip()
    warehouse = request.form.get("warehouse", "").strip()
    role_str = request.form.get("role", "viewer")

    if not username or not password:
        flash("Usuario y contraseña son requeridos", "error")
        return redirect(url_for("users.index"))

    try:
        role = UserRole(role_str)
    except ValueError:
        flash("Rol inválido", "error")
        return redirect(url_for("users.index"))

    user_manager = current_app.user_manager

    # Create request context user dict
    requesting_user = {
        "username": current_user.username,
        "role": current_user.role,
        "full_name": current_user.full_name,
    }

    success, message = user_manager.create_user(
        username=username,
        password=password,
        role=role,
        full_name=full_name,
        warehouse=warehouse,
        requesting_user=requesting_user,
    )

    if success:
        flash(f"Usuario {username} creado exitosamente", "success")
    else:
        flash(f"Error al crear usuario: {message}", "error")

    return redirect(url_for("users.index"))


@users_bp.route("/<username>/edit", methods=["POST"])
@login_required
@admin_required
def edit_user(username):
    """Edit user details"""
    user_manager = current_app.user_manager

    full_name = request.form.get("full_name")
    warehouse = request.form.get("warehouse")
    role_str = request.form.get("role")
    password = request.form.get("password")
    is_active = request.form.get("is_active") == "on"

    update_data = {"is_active": is_active}

    if full_name:
        update_data["full_name"] = full_name

    if warehouse is not None:
        if not warehouse.strip():
            flash("El almacén no puede estar vacío", "error")
            return redirect(url_for("users.index"))
        update_data["warehouse"] = warehouse.strip()

    if role_str:
        try:
            update_data["role"] = UserRole(role_str)
        except ValueError:
            pass

    if password:
        update_data["password"] = password

    # Create request context user dict
    requesting_user = {
        "username": current_user.username,
        "role": current_user.role,
        "full_name": current_user.full_name,
    }

    success, message = user_manager.update_user(
        username, requesting_user=requesting_user, **update_data
    )

    if success:
        flash(f"Usuario {username} actualizado", "success")
    else:
        flash(f"Error al actualizar: {message}", "error")

    return redirect(url_for("users.index"))


@users_bp.route("/<username>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(username):
    """Delete a user"""
    user_manager = current_app.user_manager

    if username == current_user.username:
        flash("No puedes eliminar tu propia cuenta", "error")
        return redirect(url_for("users.index"))

    # Create request context user dict
    requesting_user = {
        "username": current_user.username,
        "role": current_user.role,
        "full_name": current_user.full_name,
    }

    success, message = user_manager.delete_user(
        username, requesting_user=requesting_user
    )

    if success:
        flash(f"Usuario {username} eliminado", "success")
    else:
        flash(f"Error al eliminar: {message}", "error")

    return redirect(url_for("users.index"))
