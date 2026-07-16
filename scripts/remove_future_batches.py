import json
import os
from datetime import datetime


def remove_future_batches():
    file_path = "unified_db/product_classifications.json"

    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        db = json.load(f)

    today = datetime.now().date().isoformat()
    count = 0

    for prod_id, product in db.items():
        lotes_info = product.get("lotes_info", {})

        # Identify lots in the future
        lotes_to_remove = []
        for lote, details in lotes_info.items():
            fecha_elab = str(details.get("fecha_elaboracion", "")).strip()
            if len(fecha_elab) >= 10:
                if fecha_elab[:10] > today:
                    lotes_to_remove.append(lote)

        for lote in lotes_to_remove:
            print(
                f"Eliminando lote {lote} para el producto {prod_id} (Fecha: {lotes_info[lote].get('fecha_elaboracion')})"
            )
            del lotes_info[lote]
            count += 1

            # Reset main active batch if it was the one removed
            if product.get("lote") == lote:
                product["lote"] = ""
                product["lote_date"] = ""
                product["lote_reinspection_date"] = ""

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

    print(f"Se eliminaron {count} lotes exitosamente del archivo JSON local.")


if __name__ == "__main__":
    remove_future_batches()
