"""
REST API routes for SGA Web
For AJAX calls and external integrations
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required

api_bp = Blueprint("api", __name__)


@api_bp.route("/products")
@login_required
def list_products():
    """List products API"""
    smart_label = current_app.smart_label

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("search", "").strip().lower()

    if smart_label.df_products is None:
        return jsonify({"products": [], "total": 0})

    df = smart_label.df_products.copy()

    # Search filter
    if search:
        mask = df.apply(lambda row: search in str(row).lower(), axis=1)
        df = df[mask]

    total = len(df)
    start = (page - 1) * per_page
    end = start + per_page

    products = []
    for _, row in df.iloc[start:end].iterrows():
        products.append(
            {
                "code": row.get("Codigo interno", ""),
                "name": row.get("Chemical Name", ""),
                "cas": row.get("CAS Number", ""),
                "signal": row.get("Signal Word", ""),
                "pictograms": row.get("Pictogramas", ""),
            }
        )

    return jsonify(
        {
            "products": products,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }
    )


@api_bp.route("/products/<code>")
@login_required
def get_product(code):
    """Get single product"""
    smart_label = current_app.smart_label
    product = smart_label.get_product_data(code)

    if not product:
        return jsonify({"error": "Product not found"}), 404

    return jsonify({"product": product})


@api_bp.route("/orders")
@login_required
def list_orders():
    """List orders API"""
    order_mgr = current_app.order_status_mgr
    status = request.args.get("status", "")

    orders = list(order_mgr.orders.values())

    if status:
        orders = [o for o in orders if o.get("status") == status]

    orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return jsonify({"orders": orders})


@api_bp.route("/orders/<order_id>")
@login_required
def get_order(order_id):
    """Get single order"""
    order_mgr = current_app.order_status_mgr
    order = order_mgr.get_order(order_id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    return jsonify({"order": order})


@api_bp.route("/stats")
@login_required
def get_stats():
    """Get dashboard statistics"""
    smart_label = current_app.smart_label
    order_mgr = current_app.order_status_mgr

    from order_status_manager import OrderStatus

    stats = {
        "products": {
            "total": (
                len(smart_label.df_products)
                if smart_label.df_products is not None
                else 0
            )
        },
        "orders": {"total": len(order_mgr.orders), "by_status": {}},
        "sap": {
            "available": current_app.sap_available,
            "connected": current_app.sap_connector is not None
            and getattr(current_app.sap_connector, "connected", False),
        },
    }

    # Count by status
    for status in OrderStatus:
        count = len(
            [o for o in order_mgr.orders.values() if o.get("status") == status.value]
        )
        stats["orders"]["by_status"][status.value] = count

    return jsonify(stats)


@api_bp.route("/history")
@login_required
def get_history():
    """Get recent history"""
    limit = request.args.get("limit", 50, type=int)

    history = current_app.history_mgr.get_history()
    history.reverse()

    return jsonify({"history": history[:limit]})


@api_bp.route("/sap/test")
@login_required
def test_sap_connection():
    """Test SAP connection"""
    if not current_app.sap_available:
        return jsonify({"connected": False, "error": "hdbcli not installed"})

    try:
        from sap_connector import SAPHanaConnector

        sap = SAPHanaConnector()
        connected = sap.connect()

        if connected:
            sap.disconnect()

        return jsonify({"connected": connected})
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


@api_bp.route("/pictograms/<name>")
def get_pictogram(name):
    """Serve pictogram image"""
    import os
    from flask import send_file

    # Map Spanish pictogram names to file names
    name_map = {
        "Bomba explotando": "bomba",
        "Llama": "llama",
        "Llama sobre círculo": "llama_circulo",
        "Cilindro de gas": "cilindro_gas",
        "Corrosión": "corrosion",
        "Calavera": "calavera",
        "Exclamación": "exclamacion",
        "Peligro para la salud": "peligro_salud",
        "Ambiente": "ambiente",
    }

    # Get the file name (use mapping if available, otherwise normalize)
    file_name = name_map.get(name, name.lower().replace(" ", "_"))
    pictogram_path = os.path.join(
        current_app.config["PICTOGRAMS_PATH"], f"{file_name}.png"
    )

    if os.path.exists(pictogram_path):
        return send_file(pictogram_path, mimetype="image/png")

    return jsonify({"error": "Pictogram not found"}), 404


@api_bp.route("/tara/suggestions")
@login_required
def api_tara_suggestions():
    """
    Get smart tara weight suggestions for a given net weight and product.
    Returns a list of container options sorted by likelihood.

    Query params: peso_neto (float), product_code (str, optional)
    Returns: {"suggestions": [...]}
    """
    tara_mgr = current_app.tara_manager

    peso_neto = request.args.get("peso_neto", 0, type=float)
    product_code = request.args.get("product_code", "").strip()

    if peso_neto <= 0:
        return jsonify({"suggestions": []})

    try:
        suggestions = tara_mgr.get_smart_suggestions(peso_neto, product_code or None)

        # Format suggestions for frontend
        formatted = []
        for sug in suggestions:
            formatted.append(
                {
                    "id": sug.get("id", ""),
                    "name": sug.get("name", sug.get("label", "")),
                    "tara_kg": sug.get("tara_kg", 0),
                    "material": sug.get("material", ""),
                    "is_default": sug.get("is_default", False),
                    "usage_pct": sug.get("usage_pct", 0),
                    "source": sug.get("source", ""),
                    "label": sug.get("label", ""),
                }
            )

        return jsonify({"suggestions": formatted})
    except Exception as e:
        import logging

        logging.error(f"Error getting tara suggestions: {e}")
        return jsonify({"suggestions": [], "error": str(e)})
