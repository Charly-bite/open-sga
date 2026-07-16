import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sga_web"))
from sga_web.app import create_app

app = create_app("development")
with app.app_context():
    tara_mgr = app.tara_manager
    sap = app.sap_connector

    tara_mgr._load_classifications()
    classifications = tara_mgr._product_classifications

    def _primary_lote_value(lote_str: str):
        return (lote_str or "").split(",")[-1].strip()

    missing_ids = [
        pid
        for pid, data in classifications.items()
        if not _primary_lote_value(data.get("lote", ""))
    ]

    print(f"Missing: {len(missing_ids)}")

    batch_data = sap.get_all_latest_batches(missing_ids)
    print(f"Batches from SAP: {len(batch_data)}")

    touched = 0
    for pid, batch in batch_data.items():
        if not batch or not batch.get("batch_number"):
            continue

        class_data = classifications.get(pid, {})
        lote = _primary_lote_value(batch.get("batch_number", ""))
        lote_date = batch.get("manufacturing_date")
        reinsp = batch.get("expiry_date")

        class_data["lote"] = lote
        class_data["lote_date"] = lote_date
        class_data["lote_reinspection_date"] = reinsp
        classifications[pid] = class_data
        touched += 1

    print(f"Touched: {touched}")
    if touched > 0:
        tara_mgr._save_classifications()
        print("Guardado exitoso.")
