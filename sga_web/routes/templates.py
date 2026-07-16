"""
Template designer routes for SGA Web
Allows creating/editing label templates with drag-and-drop positioning.
"""

import os
import logging
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from reportlab.graphics.barcode import code128, createBarcodeDrawing
from reportlab.graphics import renderSVG
from reportlab.lib.units import mm

templates_bp = Blueprint("templates", __name__)


def _build_barcode_preview_svg(
    value: str, width_mm: float, bar_height_mm: float, bar_width: float, auto_fit: bool
):
    """Render a barcode preview using the same sizing logic as the PDF generator."""
    txt_str = str(value or "")
    bar_h_pts = max(float(bar_height_mm or 8), 0.1) * mm
    bar_w = max(float(bar_width or 1), 0.3)
    field_w_mm = max(float(width_mm or 0), 0.0)

    barcode = code128.Code128(txt_str, barHeight=bar_h_pts, barWidth=bar_w)
    available_w_pts = field_w_mm * mm if auto_fit and field_w_mm > 0 else barcode.width
    final_bar_w = bar_w

    if auto_fit and field_w_mm > 0 and barcode.width > 0:
        target_bar_w = max(0.3, bar_w * (available_w_pts / barcode.width))
        barcode = code128.Code128(txt_str, barHeight=bar_h_pts, barWidth=target_bar_w)
        final_bar_w = target_bar_w
        if barcode.width > available_w_pts:
            attempt_bw = target_bar_w
            while barcode.width > available_w_pts and attempt_bw > 0.3:
                attempt_bw -= 0.05
                final_bar_w = max(0.3, attempt_bw)
                barcode = code128.Code128(
                    txt_str, barHeight=bar_h_pts, barWidth=final_bar_w
                )

    drawn_w_pts = min(barcode.width, available_w_pts)
    barcode_drawing = createBarcodeDrawing(
        "Code128",
        value=txt_str,
        barHeight=bar_h_pts,
        barWidth=final_bar_w,
        humanReadable=False,
    )
    svg_markup = renderSVG.drawToString(barcode_drawing)
    return {
        "svg": svg_markup,
        "width_mm": drawn_w_pts / mm,
        "height_mm": bar_h_pts / mm,
    }


@templates_bp.route("/")
@login_required
def index():
    """Template list page"""
    templates = current_app.template_manager.list_templates()
    return render_template("templates/index.html", templates=templates)


@templates_bp.route("/designer")
@login_required
def designer():
    """Open designer for a new template"""
    fields = current_app.template_manager.get_available_fields()
    user_warehouse = getattr(current_user, "warehouse", "") or ""
    return render_template(
        "templates/designer.html",
        template_data=None,
        available_fields=fields,
        user_warehouse=user_warehouse,
    )


@templates_bp.route("/designer/<template_id>")
@login_required
def designer_edit(template_id):
    """Open designer to edit an existing template"""
    template_data = current_app.template_manager.get_template(template_id)
    if not template_data:
        return "Plantilla no encontrada", 404
    fields = current_app.template_manager.get_available_fields()
    user_warehouse = getattr(current_user, "warehouse", "") or ""
    return render_template(
        "templates/designer.html",
        template_data=template_data,
        available_fields=fields,
        user_warehouse=user_warehouse,
    )


@templates_bp.route("/api/save", methods=["POST"])
@login_required
def api_save():
    """Save a template (create or update)"""
    if not current_user.is_admin():
        return (
            jsonify({"error": "Solo administradores pueden gestionar plantillas"}),
            403,
        )

    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400

    try:
        saved = current_app.template_manager.save_template(data)
        return jsonify({"success": True, "template": saved})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/api/list")
@login_required
def api_list():
    """Return all templates as JSON"""
    templates = current_app.template_manager.list_templates()
    return jsonify({"templates": templates})


@templates_bp.route("/api/<template_id>")
@login_required
def api_get(template_id):
    """Get a single template"""
    template = current_app.template_manager.get_template(template_id)
    if not template:
        return jsonify({"error": "Plantilla no encontrada"}), 404
    return jsonify({"template": template})


@templates_bp.route("/api/<template_id>", methods=["DELETE"])
@login_required
def api_delete(template_id):
    """Delete a template"""
    if not current_user.is_admin():
        return (
            jsonify({"error": "Solo administradores pueden eliminar plantillas"}),
            403,
        )

    if current_app.template_manager.delete_template(template_id):
        return jsonify({"success": True})
    return jsonify({"error": "Plantilla no encontrada"}), 404


@templates_bp.route("/api/duplicate/<template_id>", methods=["POST"])
@login_required
def api_duplicate(template_id):
    """Duplicate a template"""
    if not current_user.is_admin():
        return (
            jsonify({"error": "Solo administradores pueden duplicar plantillas"}),
            403,
        )

    result = current_app.template_manager.duplicate_template(template_id)
    if result:
        return jsonify({"success": True, "template": result})
    return jsonify({"error": "Plantilla original no encontrada"}), 404


@templates_bp.route("/api/fields")
@login_required
def api_fields():
    """Return available fields for the designer"""
    fields = current_app.template_manager.get_available_fields()
    return jsonify({"fields": fields})


@templates_bp.route("/api/product_data/<product_id>")
@login_required
def api_product_data(product_id):
    """Return product data mapped to template field names for live preview."""
    try:
        import decimal

        smart_label = current_app.smart_label
        product = smart_label.get_product_data(product_id)
        if not product:
            return jsonify({"error": "Producto no encontrado"}), 404

        h_codes = product.get("h_codes", [])
        h_stmts = product.get("h_statements", [])
        p_codes = product.get("p_codes", [])
        p_stmts = product.get("p_statements", [])

        h_text = "\n".join(
            (
                f"{h_codes[i]} - {h_stmts[i]}"
                if i < len(h_stmts) and h_stmts[i]
                else h_codes[i]
            )
            for i in range(len(h_codes))
        )
        p_text = "\n".join(
            (
                f"{p_codes[i]} - {p_stmts[i]}"
                if i < len(p_stmts) and p_stmts[i]
                else p_codes[i]
            )
            for i in range(len(p_codes))
        )

        signal = str(product.get("signal_word", "")).upper()
        is_no_ghs = signal in (
            "NAN",
            "NONE",
            "NO APLICABLE",
            "NO APLICA",
            "N/A",
            "-",
            "",
        )
        if is_no_ghs:
            signal = ""
        signal = signal.replace("(MAJ)", "").strip()

        if not h_text:
            h_text = "No se identifican indicaciones de peligro para este producto."
        if not p_text:
            p_text = "Consultar Hoja de Seguridad (HDS) para mayor información."
        if not signal and is_no_ghs:
            signal = "N/A"

        cas_text = (
            f"CAS No. {product['cas']}" if product.get("cas") else "CAS No. Mezcla"
        )

        try:
            raw_net = str(product.get("quantity", "0")).strip() or "0"
            peso_neto = decimal.Decimal(raw_net)
        except Exception:
            peso_neto = decimal.Decimal("0")

        try:
            raw_tara = str(product.get("peso_tara", "0.0")).strip() or "0.0"
            peso_tara = decimal.Decimal(raw_tara)
        except Exception:
            peso_tara = decimal.Decimal("0.0")

        peso_bruto = peso_neto + peso_tara

        def format_w(weight):
            weight_str = str(weight)
            if "e" in weight_str.lower():
                weight_str = f"{weight:.10f}"
            parts = weight_str.split(".")
            if len(parts) == 1:
                return f"{parts[0]}.00"
            return f"{parts[0]}.{(parts[1] + '00')[:2]}"

        # Map real pictograms to their image URLs
        picto_map = {
            "Bomba explotando": "/static/img/pictograms/bomba.png",
            "Llama": "/static/img/pictograms/llama.png",
            "Llama sobre círculo": "/static/img/pictograms/llama_circulo.png",
            "Cilindro de gas": "/static/img/pictograms/cilindro_gas.png",
            "Corrosión": "/static/img/pictograms/corrosion.png",
            "Calavera": "/static/img/pictograms/calavera.png",
            "Exclamación": "/static/img/pictograms/exclamacion.png",
            "Peligro para la salud": "/static/img/pictograms/peligro_salud.png",
            "Ambiente": "/static/img/pictograms/ambiente.png",
        }
        pictogram_urls = [
            picto_map[p] for p in product.get("pictograms", []) if p in picto_map
        ]

        # Return data keyed by template field names
        from datetime import datetime
        from routes.labels import get_batch_and_tare

        today = datetime.now().strftime("%d/%m/%Y")
        one_year = datetime(
            datetime.now().year + 1, datetime.now().month, datetime.now().day
        ).strftime("%d/%m/%Y")

        # Resolve batch info (lote/tara) correctly combining backend logic + overrides
        tara, lote, fecha, vencimiento = get_batch_and_tare(
            product_id, product.get("quantity", 0)
        )
        batch_number = lote or str(product.get("batch_number", "000000"))

        return jsonify(
            {
                "success": True,
                "product_code": product_id,
                "product_name_display": product.get("product_name")
                or product.get("name", ""),
                "fields": {
                    "product_name": product.get("product_name")
                    or product.get("name", ""),
                    "signal_word": signal,
                    "cas_number": cas_text,
                    "h_statements": h_text,
                    "p_statements": p_text,
                    "internal_code_text": product.get("internal_code", product_id),
                    "internal_code_barcode": product.get("internal_code", product_id),
                    "process_barcode": "01-ENVASADO",
                    "batch_barcode": batch_number,
                    "net_weight_barcode": str(int(peso_neto)),
                    "gross_weight_barcode": f"{format_w(peso_bruto)} KG",
                    "lote_value": batch_number,
                    "peso_bruto_value": f"{format_w(peso_bruto)} KG",
                    "peso_neto_value": f"{format_w(peso_neto)} KG",
                    "peso_tara_value": f"{format_w(peso_tara)} KG",
                    "elab_date_value": today,
                    "reinsp_date_value": one_year,
                },
                "pictogram_urls": pictogram_urls,
            }
        )
    except Exception as e:
        logging.error(f"Error loading product data for live preview: {e}")
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/api/barcode_preview", methods=["POST"])
@login_required
def api_barcode_preview():
    """Return a barcode SVG rendered with the same logic used for PDF generation."""
    try:
        data = request.get_json(silent=True) or {}
        value = str(data.get("value", "") or "")
        width_mm = float(data.get("width_mm", 0) or 0)
        bar_height_mm = float(data.get("bar_height_mm", 8) or 8)
        bar_width = float(data.get("bar_width", 1) or 1)
        auto_fit = bool(data.get("auto_fit", False))

        if not value:
            return jsonify({"error": "Barcode value is required"}), 400

        preview = _build_barcode_preview_svg(
            value, width_mm, bar_height_mm, bar_width, auto_fit
        )
        return jsonify({"success": True, **preview})
    except Exception as e:
        logging.error(f"Barcode preview generation failed: {e}")
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/<template_id>/test_print", methods=["POST"])
@login_required
def test_print_template(template_id):
    """
    Generate a PDF for testing the template with a real product.
    Accepts JSON body: { "product_id": 123, "template_data": {...} }
    """
    from flask import url_for

    try:
        data = request.json
        product_id = data.get("product_id") or data.get("product_code")
        template_data = data.get("template_data")
        output_format = data.get("output_format", "pdf")
        rotation_override = data.get("rotation_override", "default")
        scale_percent = data.get("scale_percent", 100)
        render_dpi_request = int(
            data.get("render_dpi", 200)
        )  # allow caller to request higher DPI

        # User-supplied overrides (batch, weight, dates)
        override_batch = data.get("batch_number")
        override_net_weight = data.get("net_weight")
        override_tara_weight = data.get("tara_weight")
        override_elab_date = data.get("elab_date")
        override_reinsp_date = data.get("reinsp_date")

        if not product_id:
            return jsonify({"error": "Product ID is required"}), 400

        # project_root is needed later for poppler path resolution
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))

        # Use the app's cached label generator (same data source as the rest of the web app)
        # This ensures we use unified_db with all pictograms, not the legacy original_data
        generator = current_app.label_generator

        # Fallback: create a new generator if the cached one isn't available
        if generator is None:
            import sys

            if project_root not in sys.path:
                sys.path.append(project_root)
            from generate_ghs_label import GHSLabelGenerator

            db_path = current_app.config.get(
                "UNIFIED_DB_PATH", os.path.join(project_root, "unified_db")
            )
            generator = GHSLabelGenerator(db_path, manager=current_app.smart_label)

        # Get product data
        product = generator.manager.get_product_data(product_id)

        if not product:
            return jsonify({"error": f"Product {product_id} not found"}), 404

        # Apply user-supplied overrides for batch, weight, and dates
        if override_batch:
            product["batch_number"] = override_batch
        if override_net_weight:
            try:
                product["quantity"] = str(float(override_net_weight))
            except (ValueError, TypeError):
                pass
        if override_tara_weight:
            try:
                product["peso_tara"] = str(float(override_tara_weight))
            except (ValueError, TypeError):
                pass
        if override_elab_date:
            product["batch_date"] = override_elab_date
        if override_reinsp_date:
            product["reinspection_date"] = override_reinsp_date

        # Use provided template data or load from DB
        if not template_data:
            template_data = current_app.template_manager.get_template(template_id)
            if not template_data:
                return jsonify({"error": "Template not found"}), 404

        # Apply rotation override
        if rotation_override != "default":
            try:
                template_data["rotation"] = int(rotation_override)
            except ValueError:
                pass  # Ignore invalid rotation values

        # Apply scaling if requested (scale the canvas dimensions AND allow generator to handle element scaling if supported)
        # However, the current generator doesn't support global scaling easily without modifying the generator class.
        # But we can hack it by modifying the template_data elements or simply telling the user scaling is only for PDF-to-Image conversion?
        # Actually, if we just want to resize the output, maybe we can rely on the printer driver.
        # But if the user says "resize", they might mean standard PDF scaling.
        # Since I cannot easily modify GHSLabelGenerator to scale elements, I will skip scaling for PDF for now
        # unless I implement a transformation matrix.
        # The best place to scale is in the generator.
        # Let's check GHSLabelGenerator... it uses canvas.

        # Actually, simpler approach: If format is image, we can resize the image.
        # For PDF, we can't easily resize without generator support unless we use a PDF library to scale pages.
        # Let's just implement scaling for Image format first, as it's easier.
        pass

        # Generate PDF
        filename = f"test_print_{template_id}_{product_id}.pdf"
        static_tmp = os.path.join(current_app.root_path, "static", "tmp")
        os.makedirs(static_tmp, exist_ok=True)
        output_path = os.path.join(static_tmp, filename)

        generator.generate_from_template(product, template_data, output_path)

        # Handle Output Format
        if output_format.startswith("image"):
            logging.info(
                f"Generating image preview. Format: {output_format}, Scale: {scale_percent}%"
            )
            try:
                # Use cached poppler path from app config (resolved once at startup)
                poppler_path = current_app.config.get("POPPLER_PATH")
                logging.info(f"Using poppler path: {poppler_path}")
                from pdf2image import convert_from_path

                images = convert_from_path(
                    output_path, poppler_path=poppler_path, dpi=render_dpi_request
                )

                if images:
                    is_jpg = "jpg" in output_format or "jpeg" in output_format
                    img_type = "JPEG" if is_jpg else "PNG"
                    img_ext = "jpg" if is_jpg else "png"
                    # Use timestamp to avoid cache issues
                    import time

                    ts = int(time.time())
                    img_filename = (
                        f"test_print_{template_id}_{product_id}_{ts}.{img_ext}"
                    )
                    img_path = os.path.join(static_tmp, img_filename)

                    final_image = images[0]

                    # Apply scaling to the IMAGE if requested
                    if scale_percent != 100:
                        try:
                            # scale_percent comes as 100, 98, 102 etc.
                            # We resize the image. This affects print size if printed "100%"
                            factor = float(scale_percent) / 100.0
                            new_w = int(final_image.width * factor)
                            new_h = int(final_image.height * factor)
                            if new_w > 0 and new_h > 0:
                                final_image = final_image.resize((new_w, new_h))
                        except Exception as scale_e:
                            logging.error(f"Scaling failed: {scale_e}")

                    # Ensure RGB mode for JPEG (png can be RGBA)
                    if is_jpg and final_image.mode == "RGBA":
                        final_image = final_image.convert("RGB")

                    # Save with correct DPI metadata so printed size matches template dimensions
                    render_dpi = render_dpi_request
                    if scale_percent != 100:
                        # Adjust DPI inversely to scaling so physical size stays correct
                        render_dpi = int(
                            render_dpi_request * (100 / float(scale_percent))
                        )
                    final_image.save(img_path, img_type, dpi=(render_dpi, render_dpi))
                    final_url = url_for("static", filename=f"tmp/{img_filename}")

                    return jsonify(
                        {"success": True, "pdf_url": final_url, "format": img_type}
                    )
                else:
                    return jsonify({"error": "No images generated from PDF"}), 500

            except Exception as e:
                # Fallback to PDF if image conversion fails
                logging.error(f"Image conversion failed: {e}")
                import traceback

                traceback.print_exc()
                return (
                    jsonify({"error": f"Falló la conversión a imagen: {str(e)}"}),
                    500,
                )
        else:
            final_url = url_for("static", filename=f"tmp/{filename}")

        return jsonify({"success": True, "pdf_url": final_url})

    except Exception as e:
        logging.error(f"Test print failed: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error generando etiqueta: {str(e)}"}), 500
