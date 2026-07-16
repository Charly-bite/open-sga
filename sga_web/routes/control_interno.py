"""
Control Interno routes for SGA Web
Product classification, tara weight management, and internal control panel.
Uses CLASIFICACION.xlsx rules for 5 product categories:
  - LIQUIDOS: Standard liquid chemicals
  - VISCOSOS: Viscous/thick products (gels, pastes, silicones)
  - POLVOS: Powder/solid products
  - COLORES: Dyes and colorants
  - LIGEROS: Light liquids (fragrances, essences, light solvents)
Each category has its own tara weight table mapping net weight → container tara.
"""

import logging
import pandas as pd
import io
from datetime import datetime
from typing import Optional
from flask import send_file, Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user

control_bp = Blueprint("control", __name__)
logger = logging.getLogger(__name__)

# Guard: lote recovery from history runs only once per app lifecycle
_lote_recovery_done = False


def run_startup_lote_recovery(app):
    """Run the one-time lote recovery during app startup instead of first request.

    This shifts ~10s of work from the first user search to server boot time.
    """
    global _lote_recovery_done
    if _lote_recovery_done:
        return

    tara_mgr = app.tara_manager
    history_mgr = getattr(app, "history_mgr", None)
    if not history_mgr:
        _lote_recovery_done = True
        return

    needs_persist = False
    try:
        lote_overrides = _extract_user_lote_overrides(tara_mgr, history_mgr)
        for pid, override in lote_overrides.items():
            if pid not in tara_mgr._product_classifications:
                continue
            class_data = tara_mgr._product_classifications[pid]
            current_lote = _primary_lote_value(class_data.get("lote", ""))
            target_lote = override.get("lote", "")
            if not target_lote:
                continue
            target_date = override.get("lote_date", "")
            target_reinsp = override.get("lote_reinspection_date", "")
            if (
                current_lote != target_lote
                or _normalize_iso_date(class_data.get("lote_date", "")) != target_date
                or _normalize_iso_date(class_data.get("lote_reinspection_date", ""))
                != target_reinsp
            ):
                class_data["lote"] = target_lote
                if target_date:
                    class_data["lote_date"] = target_date
                if target_reinsp:
                    class_data["lote_reinspection_date"] = target_reinsp
                lotes_info = class_data.get("lotes_info", {})
                if not isinstance(lotes_info, dict):
                    lotes_info = {}
                lotes_info[target_lote] = {
                    "fecha_elaboracion": target_date,
                    "fecha_inspeccion": target_reinsp,
                }
                class_data["lotes_info"] = lotes_info
                needs_persist = True
        if needs_persist:
            tara_mgr._save_classifications()
            logger.info(
                "[RECOVER] Recovered stale lote fields from history overrides (startup)"
            )
    except Exception as exc:
        logger.warning(f"Lote override recovery failed at startup (non-fatal): {exc}")

    _lote_recovery_done = True


def _parse_history_datetime(raw_value: str) -> datetime:
    """Parse history timestamps defensively and return minimum datetime on failure."""
    raw = str(raw_value or "").strip()
    if not raw:
        return datetime.min

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.min


def _extract_user_lote_overrides(tara_mgr, history_mgr) -> dict:
    """Build latest lote override map from classification history and global logs."""
    overrides = {}

    def _upsert(
        product_id: str,
        lote: str,
        lote_date: str,
        reinsp_date: str,
        user_name: str,
        ts_raw: str,
        source: str,
    ):
        pid = str(product_id or "").strip()
        lote_clean = _primary_lote_value(lote)
        if not pid or not lote_clean:
            return

        ts = _parse_history_datetime(ts_raw)
        if ts == datetime.min:
            return

        payload = {
            "lote": lote_clean,
            "lote_date": _normalize_iso_date(lote_date),
            "lote_reinspection_date": _normalize_iso_date(reinsp_date),
            "user": str(user_name or "unknown").strip() or "unknown",
            "timestamp": ts,
            "source": source,
        }
        current = overrides.get(pid)
        if current is None or ts > current["timestamp"]:
            overrides[pid] = payload

    # 1) Recover from per-product lote_history (most reliable source)
    for pid, class_data in tara_mgr._product_classifications.items():
        history = class_data.get("lote_history", [])
        if not isinstance(history, list):
            continue
        for entry in history:
            if not isinstance(entry, dict):
                continue
            _upsert(
                product_id=pid,
                lote=entry.get("new_lote", ""),
                lote_date=entry.get("new_elab_date", entry.get("new_date", "")),
                reinsp_date=entry.get("new_reinsp_date", ""),
                user_name=entry.get("user", ""),
                ts_raw=entry.get("timestamp", entry.get("date", "")),
                source="classification_history",
            )

    # 2) Recover from global history logs (SQL/JSON)
    try:
        events = history_mgr.get_history()
    except Exception as exc:
        logger.warning(f"Could not read global history for lote recovery: {exc}")
        events = []

    for ev in events:
        if not isinstance(ev, dict):
            continue
        details = ev.get("details", {})
        if not isinstance(details, dict):
            continue

        product_id = details.get("product_id") or details.get("item_code")
        if not product_id:
            continue

        lote_value = (
            details.get("new_lote")
            or details.get("lote")
            or details.get("batch_number")
        )
        if not lote_value:
            continue

        _upsert(
            product_id=product_id,
            lote=lote_value,
            lote_date=details.get(
                "new_elab_date",
                details.get(
                    "new_date", details.get("lote_date", details.get("batch_date", ""))
                ),
            ),
            reinsp_date=details.get(
                "new_reinsp_date", details.get("lote_reinspection_date", "")
            ),
            user_name=ev.get("user", details.get("user", "")),
            ts_raw=ev.get(
                "timestamp", details.get("timestamp", details.get("date", ""))
            ),
            source="history_log",
        )

    return overrides


def _primary_lote_value(lote_value: str) -> str:
    """Return the first lote token from a potentially comma-separated value."""
    raw = str(lote_value or "").strip()
    if not raw:
        return ""
    raw = raw.replace("|", ",")
    return raw.split(",")[-1].strip()


def _normalize_iso_date(date_value: str) -> str:
    """Normalize a date string to YYYY-MM-DD when possible."""
    raw = str(date_value or "").strip()
    if not raw:
        return ""

    candidate = raw[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(candidate, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return raw


def _format_date_for_ui(d: str) -> str:
    """Convert YYYY-MM-DD back to DD/MM/YYYY for text inputs in UI."""
    if not d:
        return ""
    d = str(d).strip()
    if len(d) >= 10 and d[4] == "-" and d[7] == "-":
        try:
            dt = datetime.strptime(d[:10], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            pass
    return d


def _default_reinspection_date(elab_date: str) -> str:
    """Default reinsp date = elaboration date + 1 year (leap-year safe)."""
    normalized = _normalize_iso_date(elab_date)
    if not normalized:
        return ""

    had_00_day = False
    parse_bd = normalized
    if parse_bd.startswith("00/"):
        parse_bd = "01/" + parse_bd[3:]
        had_00_day = True
    elif "/" in parse_bd and len(parse_bd.split("/")) == 2:
        parts = parse_bd.split("/")
        parse_bd = f"01/{parts[0]}/{parts[1]}"
        had_00_day = True

    try:
        dt = datetime.strptime(parse_bd, "%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(parse_bd, "%d/%m/%Y")
        except ValueError:
            return ""

    try:
        next_year = dt.replace(year=dt.year + 1)
    except ValueError:
        # Handles Feb 29 -> Feb 28 next year
        next_year = dt.replace(year=dt.year + 1, day=28)

    if had_00_day:
        if "/" in normalized and len(normalized.split("/")) == 2:
            return next_year.strftime("%m/%Y")
        else:
            return next_year.strftime("00/%m/%Y")

    return next_year.strftime("%Y-%m-%d")


def _resolve_lote_dates(class_data: dict, lote_value: Optional[str] = None):
    """Resolve F.Elaboracion and F.Reinspeccion dates for the active lote."""
    if not isinstance(class_data, dict):
        return "", ""

    elab = str(class_data.get("lote_date", "") or "").strip()
    reinsp = str(class_data.get("lote_reinspection_date", "") or "").strip()

    lote = _primary_lote_value(
        lote_value if lote_value is not None else class_data.get("lote", "")
    )
    lotes_info = class_data.get("lotes_info", {})
    if lote and isinstance(lotes_info, dict):
        info = lotes_info.get(lote, {})
        if isinstance(info, dict):
            elab = str(info.get("fecha_elaboracion", elab) or "").strip()
            reinsp = str(info.get("fecha_inspeccion", reinsp) or "").strip()

    elab = _normalize_iso_date(elab)
    reinsp = _normalize_iso_date(reinsp)
    if not reinsp and elab:
        reinsp = _default_reinspection_date(elab)

    return elab, reinsp


@control_bp.route("/")
@login_required
def index():
    """Control Interno main page."""
    tara_mgr = current_app.tara_manager

    # Initialize classifications if not done yet
    _total = tara_mgr.initialize_classifications(
        smart_label_manager=current_app.smart_label
    )
    summary = tara_mgr.get_classification_summary()
    stats = tara_mgr.get_summary_stats()

    return render_template("control_interno/index.html", summary=summary, stats=stats)


# ─── API Endpoints ───────────────────────────────────────────────────────────


@control_bp.route("/api/products")
@login_required
def api_products():
    """Paginated, filterable product classification list."""
    tara_mgr = current_app.tara_manager
    tara_mgr.initialize_classifications(smart_label_manager=current_app.smart_label)

    # Lote recovery now runs at app startup (see run_startup_lote_recovery).
    # Safety net: if startup didn't run it yet, do it now.
    if not _lote_recovery_done:
        run_startup_lote_recovery(current_app)

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("search", "").strip()
    product_type = request.args.get("product_type", "").strip()
    status = request.args.get("status", "").strip()

    products, total = tara_mgr.get_classifications(
        page=page,
        per_page=per_page,
        search=search,
        product_type=product_type,
        status=status,
    )

    # Enrich with tara history and lote expiration check
    from datetime import datetime

    for p in products:
        elab_date, reinsp_date = _resolve_lote_dates(p)
        p["lote_date"] = _format_date_for_ui(elab_date)
        p["lote_reinspection_date"] = _format_date_for_ui(reinsp_date)

        pid = p.get("product_id", "")
        history = tara_mgr.get_product_known_tara(pid)

        # Merge type-specific general tara table so they show up as known
        ptype = p.get("product_type")
        if ptype:
            type_table = tara_mgr.get_tara_table_for_type(ptype)
            for k, v in type_table.items():
                if k not in history:
                    history[k] = v

        p["tara_history"] = [
            {"peso_neto": k, "tara_kg": v}
            for k, v in sorted(history.items())
            if v >= 0  # Filter out logically deleted items
        ]

        # Check active lote expiration
        p["requires_attention"] = False
        if reinsp_date:
            try:
                insp_date = datetime.strptime(reinsp_date, "%Y-%m-%d")
                # 6 months = roughly 180 days
                if (insp_date - datetime.now()).days <= 180:
                    p["requires_attention"] = True
            except ValueError:
                pass

    return jsonify(
        {
            "products": products,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        }
    )


@control_bp.route("/api/products/<product_id>", methods=["GET"])
@login_required
def api_product_detail(product_id):
    """Get single product classification detail."""
    tara_mgr = current_app.tara_manager
    tara_mgr._load_classifications()
    classification = tara_mgr.get_classification(product_id)
    if not classification:
        return jsonify({"error": "Product not found"}), 404

    # ── Recover latest lote from history if stored value is stale ──────
    try:
        lote_history = classification.get("lote_history", [])
        if isinstance(lote_history, list) and lote_history:
            # lote_history is ordered newest-first; take the most recent entry
            latest = lote_history[0]
            if isinstance(latest, dict):
                hist_lote = _primary_lote_value(latest.get("new_lote", ""))
                current_lote = _primary_lote_value(classification.get("lote", ""))
                if hist_lote and hist_lote != current_lote:
                    classification["lote"] = hist_lote
                    hist_date = _normalize_iso_date(
                        latest.get("new_elab_date", latest.get("new_date", ""))
                    )
                    hist_reinsp = _normalize_iso_date(latest.get("new_reinsp_date", ""))
                    if hist_date:
                        classification["lote_date"] = hist_date
                    if hist_reinsp:
                        classification["lote_reinspection_date"] = hist_reinsp
                    # Persist recovery
                    lotes_info = classification.get("lotes_info", {})
                    if not isinstance(lotes_info, dict):
                        lotes_info = {}
                    lotes_info[hist_lote] = {
                        "fecha_elaboracion": hist_date,
                        "fecha_inspeccion": hist_reinsp,
                    }
                    classification["lotes_info"] = lotes_info
                    tara_mgr._save_classifications()
                    logger.info(
                        f"🔄 Recovered lote for {product_id}: {current_lote} → {hist_lote}"
                    )
    except Exception as exc:
        logger.warning(f"Lote recovery in detail failed for {product_id}: {exc}")

    # Format history dates for UI
    try:
        lote_history = classification.get("lote_history", [])
        if isinstance(lote_history, list) and lote_history:
            formatted_history = []
            for entry in lote_history:
                if isinstance(entry, dict):
                    fe = dict(entry)
                    fe["old_date"] = _format_date_for_ui(fe.get("old_date", ""))
                    fe["new_date"] = _format_date_for_ui(fe.get("new_date", ""))
                    fe["old_elab_date"] = _format_date_for_ui(fe.get("old_elab_date", ""))
                    fe["new_elab_date"] = _format_date_for_ui(fe.get("new_elab_date", ""))
                    fe["old_reinsp_date"] = _format_date_for_ui(fe.get("old_reinsp_date", ""))
                    fe["new_reinsp_date"] = _format_date_for_ui(fe.get("new_reinsp_date", ""))
                    formatted_history.append(fe)
            classification["lote_history"] = formatted_history
    except Exception as exc:
        logger.warning(f"Lote history formatting failed for {product_id}: {exc}")

    elab_date, reinsp_date = _resolve_lote_dates(classification)
    classification["lote_date"] = _format_date_for_ui(elab_date)
    classification["lote_reinspection_date"] = _format_date_for_ui(reinsp_date)

    classification["requires_attention"] = False
    if reinsp_date:
        try:
            insp_date = datetime.strptime(reinsp_date, "%Y-%m-%d")
            if (insp_date - datetime.now()).days <= 180:
                classification["requires_attention"] = True
        except ValueError:
            pass

    history = tara_mgr.get_product_known_tara(product_id)

    ptype = classification.get("product_type")
    if ptype:
        type_table = tara_mgr.get_tara_table_for_type(ptype)
        for k, v in type_table.items():
            if k not in history:
                history[k] = v

    classification["tara_history"] = [
        {"peso_neto": k, "tara_kg": v} for k, v in sorted(history.items()) if v >= 0
    ]

    return jsonify(classification)


@control_bp.route("/api/lotes/template", methods=["GET"])
@login_required
def api_lotes_template():
    """Generates an Excel template for bulk lote upload."""
    df = pd.DataFrame(columns=["ID", "LOTE", "F.ELABORACION", "F.REINSPECCION"])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Lotes")
        # Adjust column widths
        worksheet = writer.sheets["Lotes"]
        worksheet.set_column("A:A", 15)
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:D", 18)

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="Plantilla_Lotes.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@control_bp.route("/api/lotes/upload", methods=["POST"])
@login_required
def api_lotes_upload():
    """Handles bulk lote upload via Excel."""
    if "file" not in request.files:
        return jsonify({"error": "No se adjuntó ningún archivo"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400

    try:
        df = pd.read_excel(file, dtype=str)
        df = df.fillna("")

        required_cols = {"ID", "LOTE", "F.ELABORACION", "F.REINSPECCION"}
        if not required_cols.issubset(set(df.columns)):
            return (
                jsonify(
                    {
                        "error": f'El archivo debe contener las columnas: {", ".join(required_cols)}'
                    }
                ),
                400,
            )

        tara_mgr = current_app.tara_manager
        updated_count = 0
        user_name = current_user.username if current_user else "Sistema"
        timestamp = datetime.now().isoformat()

        for index, row in df.iterrows():
            prod_id = str(row["ID"]).strip()
            lote = str(row["LOTE"]).strip()
            elaboracion = _normalize_iso_date(str(row["F.ELABORACION"]).strip())

            # Block future dates
            if elaboracion:
                try:
                    parsed_elab = datetime.strptime(elaboracion, "%Y-%m-%d")
                    if parsed_elab.date() > datetime.now().date():
                        return (
                            jsonify(
                                {
                                    "error": f"La fecha de elaboración ({elaboracion}) del lote {lote} para {prod_id} no puede estar en el futuro."
                                }
                            ),
                            400,
                        )
                except ValueError:
                    pass

            inspeccion = _normalize_iso_date(str(row["F.REINSPECCION"]).strip())
            if not inspeccion and elaboracion:
                inspeccion = _default_reinspection_date(elaboracion)

            if not prod_id or not lote:
                continue

            class_data = tara_mgr.get_classification(prod_id)
            if not class_data:
                continue

            old_lote = class_data.get("lote", "")
            old_elab, old_reinsp = _resolve_lote_dates(class_data, old_lote)
            if (
                old_lote == lote
                and old_elab == elaboracion
                and old_reinsp == inspeccion
            ):
                continue  # Skip if no change

            # Update Lote history
            if "lote_history" not in class_data:
                class_data["lote_history"] = []

            class_data["lote_history"].insert(
                0,
                {
                    "old_lote": old_lote,
                    "new_lote": lote,
                    "old_date": old_elab,
                    "new_date": elaboracion,
                    "old_elab_date": old_elab,
                    "new_elab_date": elaboracion,
                    "old_reinsp_date": old_reinsp,
                    "new_reinsp_date": inspeccion,
                    "user": user_name,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": timestamp,
                },
            )

            class_data["lote"] = lote
            class_data["lote_date"] = elaboracion
            class_data["lote_reinspection_date"] = inspeccion

            # Ensure info structure
            if "lotes_info" not in class_data or not isinstance(
                class_data["lotes_info"], dict
            ):
                class_data["lotes_info"] = {}

            class_data["lotes_info"][lote] = {
                "fecha_elaboracion": elaboracion,
                "fecha_inspeccion": inspeccion,
            }

            if tara_mgr.update_classification(prod_id, class_data):
                updated_count += 1
                try:
                    current_app.history_mgr.add_entry(
                        event_type="product_edit",
                        username=current_user.username if current_user else "Sistema",
                        details={
                            "product_code": prod_id,
                            "changes": class_data,
                            "source": "control_interno_excel",
                        },
                    )
                except Exception as e:
                    logger.error(f"Error logging lote history for {prod_id}: {e}")

        return jsonify(
            {"message": f"Se actualizaron {updated_count} productos exitosamente."}
        )

    except Exception as e:
        logger.error(f"Error procesando plantilla de lotes: {e}", exc_info=True)
        return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500


@control_bp.route("/api/products/<product_id>", methods=["PUT"])
@login_required
def api_update_product(product_id):
    """Update product classification."""
    tara_mgr = current_app.tara_manager
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Lote History tracking
    if "lote" in data or "lote_date" in data or "lote_reinspection_date" in data:
        curr_class = tara_mgr.get_classification(product_id)
        if curr_class:
            old_lote = curr_class.get("lote", "")
            new_lote = str(data.get("lote", old_lote)).strip()
            old_date, old_reinsp = _resolve_lote_dates(curr_class, old_lote)
            new_date = _normalize_iso_date(str(data.get("lote_date", old_date)).strip())

            # Validate that the selected/entered date is not in the future
            if new_date:
                try:
                    parsed_elab = datetime.strptime(new_date, "%Y-%m-%d")
                    if parsed_elab.date() > datetime.now().date():
                        return (
                            jsonify(
                                {
                                    "error": f"La fecha de elaboración ({new_date}) no puede estar en el futuro."
                                }
                            ),
                            400,
                        )
                except ValueError:
                    pass

            new_reinsp = _normalize_iso_date(
                str(data.get("lote_reinspection_date", old_reinsp)).strip()
            )
            if not new_reinsp and new_date:
                new_reinsp = _default_reinspection_date(new_date)

            force_history = data.get("force_history", False)
            merma_kg = data.get("merma_kg")

            if (
                old_lote != new_lote
                or old_date != new_date
                or old_reinsp != new_reinsp
                or force_history
                or merma_kg is not None
            ):
                history = curr_class.get("lote_history", [])
                entry = {
                    "old_lote": old_lote,
                    "new_lote": new_lote,
                    "old_date": old_date,
                    "new_date": new_date,
                    "old_elab_date": old_date,
                    "new_elab_date": new_date,
                    "old_reinsp_date": old_reinsp,
                    "new_reinsp_date": new_reinsp,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user": current_user.username,
                }
                if merma_kg is not None:
                    entry["merma_kg"] = float(merma_kg)
                if "notes_lote" in data:
                    entry["notes"] = data["notes_lote"]
                history.insert(0, entry)

                # Zero-data loss SQL Log
                try:
                    entry_log = dict(entry)
                    entry_log["product_id"] = product_id
                    current_app.history_mgr.add_entry(
                        event_type="MERMA_UPDATE",
                        username=current_user.username,
                        details=entry_log,
                    )
                except Exception as e:
                    logger.error(f"Failed to log MERMA SQL: {e}")

                data["lote"] = new_lote
                data["lote_date"] = new_date
                data["lote_reinspection_date"] = new_reinsp
                data["lote_history"] = history

                if not new_lote:
                    data["lotes_info"] = {}
                else:
                    lotes_info = curr_class.get("lotes_info", {})
                    if not isinstance(lotes_info, dict):
                        lotes_info = {}
                    target_lote = _primary_lote_value(new_lote)
                    if target_lote:
                        lotes_info[target_lote] = {
                            "fecha_elaboracion": new_date,
                            "fecha_inspeccion": new_reinsp,
                        }
                        data["lotes_info"] = lotes_info

    success = tara_mgr.update_classification(product_id, data)
    if success:
        # Save batch changes of Control Interno to history
        try:
            current_app.history_mgr.add_entry(
                event_type="product_edit",
                username=current_user.username,
                details={
                    "product_code": product_id,
                    "changes": data,
                    "source": "control_interno",
                },
            )
        except Exception as e:
            logger.error(f"Failed to write history for {product_id}: {e}")

        return jsonify({"success": True, "message": "Clasificación actualizada"})
    return jsonify({"error": "Product not found"}), 404


@control_bp.route("/api/lotes/sync-missing-sap", methods=["POST"])
@login_required
def api_sync_missing_lotes_from_sap():
    """
    Fill missing lotes from SAP and then re-apply latest user lote edits from logs.

    Priority order:
      1) User edits recovered from lote_history/history logs
      2) SAP latest batch data for products still missing lote
    """
    tara_mgr = current_app.tara_manager
    history_mgr = current_app.history_mgr
    sap = current_app.sap_connector

    if not getattr(current_app, "sap_available", False) or sap is None:
        return jsonify({"error": "SAP no disponible en este entorno"}), 503

    payload = request.get_json(silent=True) or {}
    try:
        max_items = int(payload.get("max_items", 1200))
    except (TypeError, ValueError):
        max_items = 1200
    max_items = max(1, min(max_items, 5000))

    try:
        tara_mgr._load_classifications()
        classifications = tara_mgr._product_classifications

        # Recover latest user modifications first, then we apply them after SAP fill.
        user_overrides = _extract_user_lote_overrides(tara_mgr, history_mgr)

        # Candidate products are those currently missing lote.
        missing_ids = [
            pid
            for pid, data in classifications.items()
            if not _primary_lote_value(data.get("lote", ""))
        ][:max_items]

        # Fetch latest batches for missing products in bulk
        sap_updates = 0
        recovered_overrides = 0
        touched = set()
        sap_checked = len(missing_ids)

        if missing_ids:
            batch_data = sap.get_all_latest_batches(missing_ids)
        else:
            batch_data = {}

        # 1) Fill only missing lotes from SAP
        for pid, batch in batch_data.items():
            if not batch or not batch.get("batch_number"):
                continue

            class_data = classifications.get(pid, {})
            if _primary_lote_value(class_data.get("lote", "")):
                continue

            lote = _primary_lote_value(batch.get("batch_number", ""))
            lote_date = _normalize_iso_date(batch.get("manufacturing_date", ""))
            reinsp = _normalize_iso_date(batch.get("expiry_date", ""))
            if not reinsp and lote_date:
                reinsp = _default_reinspection_date(lote_date)

            class_data["lote"] = lote
            class_data["lote_date"] = lote_date
            class_data["lote_reinspection_date"] = reinsp

            lotes_info = class_data.get("lotes_info", {})
            if not isinstance(lotes_info, dict):
                lotes_info = {}
            lotes_info[lote] = {
                "fecha_elaboracion": lote_date,
                "fecha_inspeccion": reinsp,
            }
            class_data["lotes_info"] = lotes_info

            classifications[pid] = class_data
            touched.add(pid)
            sap_updates += 1

        # 2) Re-apply user overrides with higher priority (from logs/history)
        for pid, override in user_overrides.items():
            if pid not in classifications:
                continue

            class_data = classifications[pid]
            current_lote = _primary_lote_value(class_data.get("lote", ""))
            target_lote = _primary_lote_value(override.get("lote", ""))
            if not target_lote:
                continue

            target_lote_date = _normalize_iso_date(override.get("lote_date", ""))
            target_reinsp = _normalize_iso_date(
                override.get("lote_reinspection_date", "")
            )
            if not target_reinsp and target_lote_date:
                target_reinsp = _default_reinspection_date(target_lote_date)

            same_lote = current_lote == target_lote
            same_dates = (
                _normalize_iso_date(class_data.get("lote_date", "")) == target_lote_date
                and _normalize_iso_date(class_data.get("lote_reinspection_date", ""))
                == target_reinsp
            )
            if same_lote and same_dates:
                continue

            class_data["lote"] = target_lote
            if target_lote_date:
                class_data["lote_date"] = target_lote_date
            if target_reinsp:
                class_data["lote_reinspection_date"] = target_reinsp

            lotes_info = class_data.get("lotes_info", {})
            if not isinstance(lotes_info, dict):
                lotes_info = {}
            lotes_info[target_lote] = {
                "fecha_elaboracion": target_lote_date,
                "fecha_inspeccion": target_reinsp,
            }
            class_data["lotes_info"] = lotes_info

            classifications[pid] = class_data
            touched.add(pid)
            recovered_overrides += 1

        if touched:
            tara_mgr._save_classifications()

        result = {
            "success": True,
            "missing_before": len(missing_ids),
            "sap_candidates": len(batch_data) if "batch_data" in locals() else 0,
            "sap_checked_missing": sap_checked,
            "sap_updates": sap_updates,
            "user_overrides_reapplied": recovered_overrides,
            "total_products_updated": len(touched),
        }

        try:
            history_mgr.add_entry(
                event_type="LOTE_SYNC_RECOVERY",
                username=current_user.username,
                details=result,
            )
        except Exception as exc:
            logger.warning(f"Could not write lote sync recovery history: {exc}")

        return jsonify(result)
    except Exception as e:
        logger.error(f"Global trace error in sync-missing-sap: {e}", exc_info=True)
        import traceback

        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@control_bp.route("/api/lote-history/<product_id>", methods=["PUT"])
@login_required
def api_update_lote_history_note(product_id):
    """Update notes for a specific lote history entry."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    entry_date = data.get("date")
    notes = data.get("notes", "")

    tara_mgr = current_app.tara_manager
    curr_class = tara_mgr.get_classification(product_id)
    if not curr_class:
        return jsonify({"error": "Product not found"}), 404

    history = curr_class.get("lote_history", [])
    updated = False
    for entry in history:
        if entry.get("date") == entry_date or entry.get("timestamp") == entry_date:
            entry["notes"] = notes
            updated = True
            break

    if updated:
        if tara_mgr.update_classification(product_id, curr_class):
            return jsonify({"success": True})
    return jsonify({"error": "History entry not found"}), 404


@control_bp.route("/api/lote-history", methods=["GET"])
@login_required
def api_lote_history():
    """Get global lote change history."""
    tara_mgr = current_app.tara_manager
    tara_mgr._load_classifications(force=True)
    history_list = []

    # Extract all lote_history from all products
    for pid, data in tara_mgr._product_classifications.items():
        lh = data.get("lote_history", [])
        for entry in lh:
            # Inject product info into each history entry
            enriched_entry = dict(entry)
            enriched_entry["product_id"] = pid
            enriched_entry["chemical_name"] = data.get("chemical_name", "")
            
            # Format dates for UI
            enriched_entry["old_date"] = _format_date_for_ui(enriched_entry.get("old_date", ""))
            enriched_entry["new_date"] = _format_date_for_ui(enriched_entry.get("new_date", ""))
            enriched_entry["old_elab_date"] = _format_date_for_ui(enriched_entry.get("old_elab_date", ""))
            enriched_entry["new_elab_date"] = _format_date_for_ui(enriched_entry.get("new_elab_date", ""))
            enriched_entry["old_reinsp_date"] = _format_date_for_ui(enriched_entry.get("old_reinsp_date", ""))
            enriched_entry["new_reinsp_date"] = _format_date_for_ui(enriched_entry.get("new_reinsp_date", ""))
            
            history_list.append(enriched_entry)

    # Filter by month if provided (YYYY-MM)
    filter_month = request.args.get("month", "").strip()
    if filter_month and len(filter_month) == 7:
        filtered_list = []
        for x in history_list:
            ts = x.get("date") or x.get("timestamp") or ""
            if ts.startswith(filter_month):
                filtered_list.append(x)
        history_list = filtered_list

    # Sort by date descending
    history_list.sort(
        key=lambda x: x.get("date") or x.get("timestamp", ""), reverse=True
    )

    # Simple pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    total = len(history_list)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = history_list[start:end]

    return jsonify(
        {
            "history": paginated,
            "total": total,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
        }
    )


@control_bp.route("/api/bulk-update", methods=["POST"])
@login_required
def api_bulk_update():
    """Bulk update product types."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    product_ids = data.get("product_ids", [])
    product_type = data.get("product_type", "")

    if not product_ids or not product_type:
        return jsonify({"error": "product_ids and product_type required"}), 400

    tara_mgr = current_app.tara_manager
    count = tara_mgr.bulk_update_type(product_ids, product_type)
    return jsonify({"success": True, "updated": count})


@control_bp.route("/api/summary")
@login_required
def api_summary():
    """Classification summary stats."""
    tara_mgr = current_app.tara_manager
    summary = tara_mgr.get_classification_summary()
    stats = tara_mgr.get_summary_stats()
    return jsonify({**summary, **stats})


@control_bp.route("/api/auto-classify", methods=["POST"])
@login_required
def api_auto_classify():
    """Run auto-classification on unclassified products."""
    tara_mgr = current_app.tara_manager
    count = tara_mgr.auto_classify_products()
    return jsonify({"success": True, "classified": count})


@control_bp.route("/api/containers")
@login_required
def api_containers():
    """Return the container catalog."""
    from tara_weight_manager import CONTAINER_CATALOG

    return jsonify(CONTAINER_CATALOG)


@control_bp.route("/api/product-types")
@login_required
def api_product_types():
    """Return available product types."""
    from tara_weight_manager import PRODUCT_TYPES

    return jsonify(PRODUCT_TYPES)


@control_bp.route("/api/import-excel", methods=["POST"])
@login_required
def api_import_excel():
    """
    Import product classifications from CLASIFICACION.xlsx.
    Maps each product to its category (liquido, viscoso, polvo, color, ligero)
    based on which sheet it appears in.
    """
    tara_mgr = current_app.tara_manager
    result = tara_mgr.import_from_excel()
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 400


@control_bp.route("/api/tara-table/<product_type>")
@login_required
def api_tara_table(product_type):
    """
    Return the tara weight lookup table for a specific product type.
    Each type has its own mapping: net_weight_kg → tara_kg.
    e.g. GET /api/tara-table/viscoso → {1: 0.29, 2: 0.29, ..., 20: 1.2}
    """
    tara_mgr = current_app.tara_manager
    table = tara_mgr.get_tara_table_for_type(product_type)
    if not table:
        return jsonify({"error": f"No tara table for type: {product_type}"}), 404
    return jsonify(
        {
            "product_type": product_type,
            "tara_table": {str(k): v for k, v in sorted(table.items())},
        }
    )


@control_bp.route("/api/resolve-tara", methods=["POST"])
@login_required
def api_resolve_tara():
    """
    Resolve the best tara weight for a product and net weight.
    Uses priority: product history → type-specific table → statistical default.

    Body: {"product_id": "IFF-QB00007", "peso_neto": 5.0}
    Returns: {"tara_kg": 0.28, "source": "type_table", "product_type": "liquido"}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    product_id = data.get("product_id", "").strip()
    peso_neto = data.get("peso_neto", 0)
    try:
        peso_neto = float(peso_neto)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid peso_neto"}), 400

    tara_mgr = current_app.tara_manager
    tara_kg = tara_mgr.resolve_best_tara(peso_neto, product_id)
    product_type = tara_mgr._get_product_type(product_id) if product_id else None

    # Determine source
    source = "default"
    if product_id and product_id in tara_mgr._product_tara_cache:
        if peso_neto in tara_mgr._product_tara_cache[product_id]:
            source = "product_history"
    if source == "default" and product_type:
        from tara_weight_manager import resolve_tara_by_type

        type_tara = resolve_tara_by_type(product_type, peso_neto)
        if type_tara is not None and type_tara == tara_kg:
            source = "type_table"

    # Check for packaging notes (multi-container rules)
    packaging_note = tara_mgr.get_packaging_notes(peso_neto)

    return jsonify(
        {
            "tara_kg": tara_kg,
            "source": source,
            "product_type": product_type,
            "packaging_note": packaging_note,
        }
    )


@control_bp.route("/api/classification-sources")
@login_required
def api_classification_sources():
    """
    Return breakdown of classification sources (manual, excel, auto, unclassified).
    Useful for dashboard analytics.
    """
    tara_mgr = current_app.tara_manager
    sources = {"manual": 0, "excel": 0, "auto": 0, "unclassified": 0}
    for p in tara_mgr._product_classifications.values():
        src = p.get("type_source", "")
        if not p.get("product_type"):
            sources["unclassified"] += 1
        elif src in sources:
            sources[src] += 1
        else:
            sources["auto"] += 1

    return jsonify(sources)


@control_bp.route("/api/tara-tables")
@login_required
def api_all_tara_tables():
    """
    Return all type-specific tara weight tables at once.
    Useful for the client to build a full reference view.
    """
    from tara_weight_manager import TARA_BY_TYPE

    result = {}
    for ptype, table in TARA_BY_TYPE.items():
        result[ptype] = {str(k): v for k, v in sorted(table.items())}
    return jsonify(result)
