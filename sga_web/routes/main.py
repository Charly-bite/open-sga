"""
Main dashboard routes for SGA Web
"""

from flask import Blueprint, render_template, current_app, request
from flask_login import login_required, current_user

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Landing page - redirect to login or dashboard"""
    if current_user.is_authenticated:
        from flask import redirect, url_for

        return redirect(url_for("main.dashboard"))
    from flask import redirect, url_for

    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard with quick stats"""
    # Fetch history for stats and activity table
    all_history = current_app.history_mgr.get_history()

    # Compute "Etiquetas Impresas Hoy" — only today's print events
    from datetime import datetime

    today_str = datetime.now().strftime("%Y-%m-%d")
    printed_labels_today = sum(
        (
            h.get("details", {}).get("count", 0)
            if isinstance(h.get("details"), dict)
            else 0
        )
        for h in all_history
        if h.get("event_type", h.get("type"))
        in ["PRINT_JOB", "PRINT_JOB_HTML", "DIRECT_PRINT_JOB", "LABEL_GENERATION"]
        and h.get("timestamp", "").startswith(today_str)
    )

    stats = {"printed_labels_today": printed_labels_today}

    # Get recent history for the selected or current day with enhanced formatting
    selected_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    history = [
        h for h in all_history if h.get("timestamp", "").startswith(selected_date)
    ]
    history.reverse()

    # Enhance history entries with readable event types and details
    event_type_mapping = {
        "PRINT_JOB": "Impresión",
        "PRINT_JOB_HTML": "Impresión HTML",
        "DIRECT_PRINT_JOB": "Impresión Directa",
        "PRINT_DIRECT": "Impresión Directa",
        "PRINT_ORDER": "Impresión Pedido",
        "SAP_IMPORT": "Importación SAP",
        "LABEL_GENERATION": "Etiqueta Generada",
        "PRODUCT_ADD": "Producto Agregado",
        "PRODUCT_EDIT": "Producto Editado",
        "ORDER_UPDATE": "Pedido Actualizado",
        "LOGIN": "Inicio de Sesión",
        "LOGOUT": "Cierre de Sesión",
        "MERMA_UPDATE": "Merma Update",
    }

    for entry in history:
        # Map event type
        event_type = entry.get("event_type", entry.get("type", "UNKNOWN"))
        entry["type_display"] = event_type_mapping.get(
            event_type, event_type.replace("_", " ").title()
        )
        entry["type"] = event_type

        # Format details in a human-readable way
        details = entry.get("details", {})
        if isinstance(details, dict):
            # Try to extract an order reference if present
            order_ref = details.get("order") or details.get("order_id")
            order_str = f" [Pedido: {order_ref}]" if order_ref else ""

            if "count" in details and "items" in details:
                # Print job format
                count = details.get("count", 0)
                items = details.get("items", [])
                if count == 1:
                    entry["details_display"] = (
                        f"1 etiqueta: {items[0]}{order_str}"
                        if items
                        else f"1 etiqueta{order_str}"
                    )
                else:
                    items_preview = ", ".join(items[:3])
                    if len(items) > 3:
                        items_preview += f", +{len(items)-3} más"
                    entry["details_display"] = (
                        f"{count} etiquetas: {items_preview}{order_str}"
                    )
            elif "product_code" in details and "changes" in details:
                # Product Edit format
                changes = details["changes"]
                change_strs = []
                if isinstance(changes, dict):
                    if "lote" in changes:
                        change_strs.append(f"Lote: '{changes['lote']}'")
                    if "lote_date" in changes:
                        change_strs.append(f"Fecha: '{changes['lote_date']}'")
                    if not change_strs:
                        change_strs = [f"{k}: '{v}'" for k, v in changes.items()][:2]

                changes_str = ", ".join(change_strs) if change_strs else "Modificado"
                entry["details_display"] = (
                    f"Producto: {details['product_code']} - {changes_str}{order_str}"
                )
            elif "order_id" in details:
                entry["details_display"] = f"Pedido #{details['order_id']}"
            elif "product_id" in details:
                entry["details_display"] = (
                    f"Producto: {details['product_id']}{order_str}"
                )
            else:
                # Generic dict display
                display_str = ", ".join(
                    f"{k}: {v}"
                    for k, v in details.items()
                    if v and k not in ["order", "order_id"]
                )[:80]
                entry["details_display"] = f"{display_str}{order_str}"
        elif isinstance(details, str):
            entry["details_display"] = details
        else:
            entry["details_display"] = str(details) if details else "-"

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_history=history,
        selected_date=selected_date,
    )


@main_bp.route("/api/sap/connect", methods=["POST"])
@login_required
def connect_sap():
    """Attempt to connect to SAP HANA manually"""
    from flask import jsonify

    if not current_app.sap_available:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "El conector SAP no está disponible (hdbcli no instalado o deshabilitado)",
                    "status": "Desconectado",
                }
            ),
            400,
        )

    connector = current_app.sap_connector
    if not connector:
        # Try to re-initialize if it was None (e.g. startup error)
        try:
            from sap_connector import SAPHanaConnector
            import os

            sap_user = os.environ.get("SAP_USER")
            sap_pass = os.environ.get("SAP_PASS")
            if sap_user and sap_pass:
                connector = SAPHanaConnector(
                    host=os.environ.get("SAP_HOST", "20.0.1.9"),
                    port=int(os.environ.get("SAP_PORT", 30015)),
                    username=sap_user,
                    password=sap_pass,
                    schema=os.environ.get("SAP_SCHEMA", "SBO_QUIMICABOSS"),
                )
                current_app.sap_connector = connector
            else:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Credenciales SAP no configuradas",
                        }
                    ),
                    500,
                )
        except Exception as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Error al inicializar conector: {str(e)}",
                    }
                ),
                500,
            )

    try:
        # Check if already connected
        if connector.connected:
            # Test if connection is actually alive
            try:
                connector.test_connection()
                return jsonify(
                    {
                        "success": True,
                        "message": "Ya conectado a SAP HANA",
                        "status": "Conectado",
                    }
                )
            except Exception:
                # Connection might be stale, try to reconnect
                connector.disconnect()

        # Connect
        if connector.connect():
            return jsonify(
                {
                    "success": True,
                    "message": "Conexión exitosa a SAP HANA",
                    "status": "Conectado",
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Fallo la conexión a SAP HANA",
                        "status": "Desconectado",
                    }
                ),
                500,
            )

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Error de conexión: {str(e)}",
                    "status": "Error",
                }
            ),
            500,
        )
