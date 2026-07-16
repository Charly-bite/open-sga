"""
Product database routes for SGA Web
"""

import os
import tempfile
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app, send_file
from flask_login import login_required, current_user

products_bp = Blueprint("products", __name__)


def _save_error_payload(smart_label, default_message):
    """Build a user-facing payload with DB path and save error details when available."""
    if hasattr(smart_label, "get_last_save_status"):
        status = smart_label.get_last_save_status() or {}
        if status.get("error"):
            save_path = status.get("path") or getattr(smart_label, "data_dir", "")
            return {
                "error": f"{default_message}. Ruta: {save_path}. Detalle: {status['error']}",
                "save_error": status.get("error"),
                "save_path": save_path,
                "db_mode": status.get("mode")
                or getattr(smart_label, "connection_mode", None),
            }
    return {"error": default_message}


@products_bp.route("/")
@login_required
def index():
    """Product database browser"""
    smart_label = current_app.smart_label

    # Get pagination params
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config.get("ITEMS_PER_PAGE", 25)
    search = request.args.get("search", "").strip()
    signal_filter = request.args.get("signal", "").strip().upper()
    tab = request.args.get("tab", "all")
    sort_by = request.args.get("sort_by", "")
    sort_dir = request.args.get("sort_dir", "asc")

    # Get products
    if smart_label.df_products is not None:
        df = smart_label.df_products.fillna("")

        # EXCLUSIONS: globally hide non-chemical / invalid products from the web view
        if "product_id" in df.columns:
            # Filter out AF (Actives), SE (Salaries), LUB-QB (partner liquids), and ANTICIPO
            exclude_mask = df["product_id"].str.contains(
                r"^(?:AF|SE)", regex=True, na=False
            ) | (df["product_id"] == "ANTICIPO")
            df = df[~exclude_mask]

        # Pendientes Laboratorio filter
        if tab == "pending":
            import pandas as pd

            mask_pending = pd.Series(False, index=df.index)

            # Sin Palabra de Advertencia (Señal)
            if "signal_word" in df.columns:
                sw = df["signal_word"].astype(str).str.strip().str.upper()
                mask_pending = (
                    mask_pending
                    | (sw == "")
                    | (sw == "-")
                    | (sw == "NAN")
                    | (sw == "NONE")
                )
            elif "Signal Word" in df.columns:
                sw = df["Signal Word"].astype(str).str.strip().str.upper()
                mask_pending = (
                    mask_pending
                    | (sw == "")
                    | (sw == "-")
                    | (sw == "NAN")
                    | (sw == "NONE")
                )

            # O marcado explícitamente para actualización por el script de sincronización
            if "needs_update" in df.columns:
                mask_pending = mask_pending | (
                    df["needs_update"].astype(str).str.upper() == "Y"
                )

            df = df[mask_pending]

        # Signal word filter
        if signal_filter:
            sw_col = (
                "signal_word"
                if "signal_word" in df.columns
                else ("Signal Word" if "Signal Word" in df.columns else None)
            )
            if sw_col:
                if signal_filter == "NONE":
                    # Find empty, NaN, "no aplicable", etc
                    sw_vals = df[sw_col].astype(str).str.strip().str.upper()
                    mask_sw = (
                        (sw_vals == "")
                        | (sw_vals == "NAN")
                        | (sw_vals == "NONE")
                        | (sw_vals == "NO APLICABLE")
                        | (sw_vals == "-")
                    )
                else:
                    mask_sw = (
                        df[sw_col]
                        .astype(str)
                        .str.upper()
                        .str.contains(signal_filter, na=False, regex=False)
                    )
                df = df[mask_sw]

        # PERF-01: Search specific columns instead of O(rows*cols) full-row scan
        if search:
            s = search.lower()
            _SEARCH_COLS = [
                "product_id",
                "chemical_name",
                "cas_number",
                "signal_word",
                "Codigo interno",
                "Chemical Name",
                "CAS Number",
                "Signal Word",
            ]
            cols = [c for c in _SEARCH_COLS if c in df.columns]
            mask = (
                df[cols]
                .apply(
                    lambda col: col.astype(str)
                    .str.lower()
                    .str.contains(s, na=False, regex=False)
                )
                .any(axis=1)
            )
            df = df[mask]

        # Sorting
        if sort_by:
            # Map standard field names to actual DataFrame columns based on data source
            sort_col_map = {
                "product_id": (
                    "product_id" if "product_id" in df.columns else "Codigo interno"
                ),
                "chemical_name": (
                    "chemical_name"
                    if "chemical_name" in df.columns
                    else "Chemical Name"
                ),
                "cas_number": (
                    "cas_number" if "cas_number" in df.columns else "CAS Number"
                ),
                "signal_word": (
                    "signal_word" if "signal_word" in df.columns else "Signal Word"
                ),
            }
            actual_sort_col = sort_col_map.get(sort_by, sort_by)

            if actual_sort_col in df.columns:
                ascending = sort_dir != "desc"
                df = df.sort_values(
                    by=actual_sort_col,
                    ascending=ascending,
                    key=lambda col: col.astype(str).str.lower(),
                )

        # Pagination
        total = len(df)
        start = (page - 1) * per_page
        end = start + per_page
        products_raw = df.iloc[start:end].fillna("").to_dict("records")

        # Enrich with pictograms
        picto_name_map = {
            "GHS01": "Bomba explotando",
            "GHS02": "Llama",
            "GHS03": "Llama sobre círculo",
            "GHS04": "Cilindro de gas",
            "GHS05": "Corrosión",
            "GHS06": "Calavera",
            "GHS07": "Exclamación",
            "GHS08": "Peligro para la salud",
            "GHS09": "Ambiente",
        }

        products = []
        for p in products_raw:
            product_id = str(p.get("product_id", "")).strip()
            # Skip rows with empty product_id (ghost rows)
            if not product_id:
                total -= 1
                continue
            # Get pictograms for this product
            pictograms = []
            if (
                smart_label.df_product_pictograms is not None
                and not smart_label.df_product_pictograms.empty
            ):
                picto_mask = (
                    smart_label.df_product_pictograms["product_id"].astype(str)
                    == product_id
                )
                picto_ids = smart_label.df_product_pictograms[picto_mask][
                    "pictogram_id"
                ].tolist()
                for pid in picto_ids:
                    if pid in picto_name_map:
                        pictograms.append(picto_name_map[pid])

            p["pictograms"] = pictograms
            products.append(p)

        total_pages = (total + per_page - 1) // per_page
    else:
        products = []
        total = 0
        total_pages = 0

    return render_template(
        "products/index.html",
        products=products,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        signal=signal_filter,
        tab=tab,
        sort_by=sort_by,
        sort_dir=sort_dir,
        can_edit=current_user.can_edit_products(),
    )


@products_bp.route("/search")
@login_required
def search():
    """Search products API"""
    try:
        smart_label = current_app.smart_label
        query = request.args.get("q", "").strip().lower()
        limit = request.args.get("limit", 20, type=int)

        if not query or smart_label.df_products is None:
            return jsonify({"products": []})

        # Remove duplicates by product code/id
        df = smart_label.df_products.fillna("")
        if "product_id" in df.columns:
            df = df.drop_duplicates(subset=["product_id"])
            # Filter out non-chemical items (Actives, Salaries, etc.)
            exclude_mask = df["product_id"].astype(str).str.contains(
                r"^(?:AF|SE)", case=False, regex=True, na=False
            ) | (df["product_id"].astype(str).str.upper() == "ANTICIPO")
            df = df[~exclude_mask]
        elif "Codigo interno" in df.columns:
            df = df.drop_duplicates(subset=["Codigo interno"])
            # Filter out non-chemical items (Actives, Salaries, etc.)
            exclude_mask = df["Codigo interno"].astype(str).str.contains(
                r"^(?:AF|SE)", case=False, regex=True, na=False
            ) | (df["Codigo interno"].astype(str).str.upper() == "ANTICIPO")
            df = df[~exclude_mask]

        # PERF-01: Search specific columns instead of full-row scan
        _SEARCH_COLS = [
            "product_id",
            "chemical_name",
            "cas_number",
            "signal_word",
            "Codigo interno",
            "Chemical Name",
            "CAS Number",
            "Signal Word",
        ]
        cols = [c for c in _SEARCH_COLS if c in df.columns]
        mask = (
            df[cols]
            .apply(
                lambda col: col.astype(str)
                .str.lower()
                .str.contains(query, na=False, regex=False)
            )
            .any(axis=1)
        )
        results = df[mask].head(limit)

        products = []
        for _, row in results.iterrows():
            products.append(
                {
                    "code": row.get("product_id", row.get("Codigo interno", "")),
                    "name": row.get("chemical_name", row.get("Chemical Name", "")),
                    "cas": row.get("cas_number", row.get("CAS Number", "")),
                    "signal": row.get("signal_word", row.get("Signal Word", "")),
                }
            )

        return jsonify({"products": products})
    except Exception as e:
        logging.error(f"Error in /products/search: {e}")
        return jsonify({"error": "Error interno de búsqueda", "details": str(e)}), 500


@products_bp.route("/<code>")
@login_required
def detail(code):
    """Product detail view"""
    smart_label = current_app.smart_label
    product = smart_label.get_product_data(code)

    if not product:
        return render_template("errors/404.html"), 404

    # H/P statements and pictograms are already in the product data from get_product_data()
    h_statements = product.get("h_statements", [])
    p_statements = product.get("p_statements", [])
    pictograms = product.get("pictograms", [])

    return render_template(
        "products/detail.html",
        product=product,
        h_statements=h_statements,
        p_statements=p_statements,
        pictograms=pictograms,
        can_edit=current_user.can_edit_products(),
    )


@products_bp.route("/<code>/edit", methods=["GET", "POST"])
@login_required
def edit(code):
    """Edit product - Admin only"""
    if not current_user.can_edit_products():
        return jsonify({"error": "Sin permisos para editar productos"}), 403

    smart_label = current_app.smart_label
    product = smart_label.get_product_data(code)

    if not product:
        return render_template("errors/404.html"), 404

    if request.method == "POST":
        data = request.get_json()

        # Update product using manager (handles both legacy and normalized formats)
        if smart_label.update_product(code, data):
            # Log change
            # Log change
            current_app.history_mgr.add_entry(
                event_type="product_edit",
                username=current_user.username,
                details={"product_code": code, "changes": data},
            )

            # Reload SmartLabelManager so changes are immediately available
            try:
                current_app.smart_label.reload()
            except Exception as e:
                logging.warning(f"Could not reload smart_label after edit: {e}")

            return jsonify({"success": True})

        payload = _save_error_payload(
            smart_label, "Error al guardar cambios o producto no encontrado"
        )
        logging.warning(f"Product edit save failed for {code}: {payload}")
        return jsonify(payload), 500

    return render_template("products/edit.html", product=product)


@products_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """Add new product - Admin only"""
    if not current_user.can_edit_products():
        return jsonify({"error": "Sin permisos para agregar productos"}), 403

    if request.method == "POST":
        data = request.get_json()

        # Validate required fields
        required = ["Codigo interno", "Chemical Name"]
        for field in required:
            if not data.get(field):
                return jsonify({"error": f"Campo requerido: {field}"}), 400

        # Check if code already exists
        smart_label = current_app.smart_label
        if smart_label.get_product_data(data["Codigo interno"]):
            return jsonify({"error": "Código de producto ya existe"}), 400

        # Add product
        success = smart_label.add_product(data)

        if success:
            # Log addition
            # Log addition
            current_app.history_mgr.add_entry(
                event_type="product_add",
                username=current_user.username,
                details={"product_code": data["Codigo interno"]},
            )

            # Reload SmartLabelManager so new changes are immediately available
            try:
                current_app.smart_label.reload()
            except Exception as e:
                logging.warning(f"Could not reload smart_label after add: {e}")

            # Refresh the label generator cache so new product can be printed
            try:
                from generate_ghs_label import GHSLabelGenerator

                current_app.label_generator = GHSLabelGenerator(
                    current_app.config["UNIFIED_DB_PATH"],
                    manager=current_app.smart_label,
                )
            except Exception as e:
                logging.warning(f"Could not refresh label generator after add: {e}")

            return jsonify({"success": True, "code": data["Codigo interno"]})

        payload = _save_error_payload(smart_label, "Error al agregar producto")
        logging.warning(
            f"Product add save failed for {data.get('Codigo interno')}: {payload}"
        )
        return jsonify(payload), 500

    return render_template("products/add.html")


@products_bp.route("/<code>/delete", methods=["POST"])
@login_required
def delete(code):
    """Delete product - Admin only"""
    if not current_user.can_edit_products():
        return jsonify({"error": "Sin permisos para eliminar productos"}), 403

    smart_label = current_app.smart_label
    product = smart_label.get_product_data(code)

    if not product:
        return jsonify({"error": "Producto no encontrado"}), 404

    product_name = product.get("name", product.get("product_name", code))

    if smart_label.delete_product(code):
        # Reload SmartLabelManager so product list is immediately updated
        try:
            current_app.smart_label.reload()
        except Exception as e:
            logging.warning(f"Could not reload smart_label after delete: {e}")

        # Refresh label generator cache
        try:
            from generate_ghs_label import GHSLabelGenerator

            current_app.label_generator = GHSLabelGenerator(
                current_app.config["UNIFIED_DB_PATH"], manager=current_app.smart_label
            )
        except Exception as e:
            logging.warning(f"Could not refresh label generator after delete: {e}")

        # Log deletion
        current_app.history_mgr.add_entry(
            event_type="product_delete",
            username=current_user.username,
            details={"product_code": code, "product_name": product_name},
        )
        return jsonify({"success": True})

    payload = _save_error_payload(smart_label, "Error al eliminar producto")
    logging.warning(f"Product delete save failed for {code}: {payload}")
    return jsonify(payload), 500


# =============================================================================
# P1-04 — Product Master Sync (SAP → Local unified_db)
# =============================================================================


@products_bp.route("/api/sync", methods=["POST"])
@login_required
def sap_sync():
    """
    [P1-04] Bulk sync product master data from SAP OITM to local SQL Database.
    Never overwrites existing GHS columns (signal_word, cas_number, etc.)
    unless they are empty in the local DB.

    Accepts optional JSON body:
      { "updated_since": "YYYY-MM-DD",   # incremental mode
        "limit": 2000 }

    Returns:
      { success, synced, updated, added, skipped, timestamp }
    """
    if not current_user.can_edit_products():
        return jsonify({"error": "Sin permisos para sincronizar productos"}), 403

    try:
        body = request.get_json(silent=True) or {}
        updated_since = body.get("updated_since")
        limit = int(body.get("limit", 2000))

        import sys

        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if root_dir not in sys.path:
            sys.path.append(root_dir)

        from sync_sap_to_db import run_sync

        stats = run_sync(limit=limit, updated_since=updated_since)

        if not stats.get("success"):
            return jsonify({"error": stats.get("error", "Error en sync")}), 500

        # Reload SmartLabelManager so new products are immediately available
        try:
            current_app.smart_label.reload()
        except Exception:
            pass

        return jsonify(
            {
                "success": True,
                "synced": stats.get("synced", 0),
                "added": stats.get("added", 0),
                "updated": stats.get("updated", 0),
                "skipped": stats.get("skipped", 0),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@products_bp.route("/api/generate_label/<code>", methods=["GET"])
@login_required
def generate_label(code):
    """Generate a GHS label PDF directly for a product"""
    if not current_user.can_print_labels():
        return jsonify({"error": "Sin permisos para generar etiquetas"}), 403

    smart_label = current_app.smart_label
    product_data = smart_label.get_product_data(code)

    if not product_data:
        return jsonify({"error": "Producto no encontrado"}), 404

    try:
        generator = current_app.label_generator

        # Generate to temp file
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_path = tmp.name
        tmp.close()

        # Set default values for batch/quantity (quick label from database)
        tara_class = current_app.tara_manager.get_classification(code)
        if tara_class:
            product_data["batch_number"] = tara_class.get(
                "lote", product_data.get("batch_number", "")
            )
            product_data["batch_date"] = tara_class.get(
                "lote_date", product_data.get("batch_date", "")
            )
            product_data["reinspection_date"] = tara_class.get(
                "lote_reinspection_date", ""
            )
        else:
            product_data["batch_number"] = product_data.get("batch_number", "")
            product_data["batch_date"] = product_data.get("batch_date", "")

        product_data["peso_tara"] = product_data.get("peso_tara", 0)
        product_data["quantity"] = product_data.get("quantity", 0)
        product_data["warehouse"] = product_data.get("warehouse", "")

        generator.generate_label(product_data, tmp_path)

        # Also save a copy in generated_labels
        output_dir = current_app.config["GENERATED_LABELS_PATH"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_code = code.replace("/", "_").replace("\\", "_")
        final_path = os.path.join(output_dir, f"etiqueta_{safe_code}_{timestamp}.pdf")

        import shutil

        shutil.copy2(tmp_path, final_path)

        # Log to history
        current_app.history_mgr.add_entry(
            event_type="PRINT_JOB",
            username=current_user.username,
            details={"count": 1, "items": [code], "source": "product_detail"},
        )

        response = send_file(
            tmp_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f"etiqueta_{safe_code}.pdf",
        )
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        return response

    except Exception as e:
        logging.error(f"Error generating label for {code}: {e}")
        import traceback

        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
