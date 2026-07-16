"""Extract all May 2026 lote changes from production history and classifications."""

import json
import os

# ── 1. Extract from production history.json ──
prod_history_path = r"C:\Users\QB_DESARROLLO\Desktop\SGAv1.01\sga_web\history.json"
with open(prod_history_path, "r", encoding="utf-8", errors="replace") as f:
    data = json.load(f)

lote_updates = {}
for e in data:
    ts = e.get("timestamp", "")
    if not (ts.startswith("2026-05") or ts.startswith("2026-04")):
        continue
    details = e.get("details", {})
    pid = details.get("product_id") or details.get("product_code", "")
    if not pid:
        continue

    event_type = e.get("event_type", "")

    if event_type == "MERMA_UPDATE":
        new_lote = details.get("new_lote", "")
        if new_lote:
            lote_updates[pid] = {
                "lote": new_lote,
                "lote_date": details.get("new_elab_date", details.get("new_date", "")),
                "lote_reinspection_date": details.get("new_reinsp_date", ""),
                "timestamp": ts,
                "user": e.get("user", ""),
            }
    elif event_type == "product_edit":
        changes = details.get("changes", {})
        new_lote = changes.get("lote", "")
        if new_lote:
            lote_updates[pid] = {
                "lote": new_lote,
                "lote_date": changes.get("lote_date", ""),
                "lote_reinspection_date": changes.get("lote_reinspection_date", ""),
                "timestamp": ts,
                "user": e.get("user", ""),
            }

print(f"Products with lote updates in April-May 2026: {len(lote_updates)}")
for pid in sorted(lote_updates.keys()):
    info = lote_updates[pid]
    print(
        f"  {pid}: lote={info['lote']}, elab={info['lote_date']}, reinsp={info['lote_reinspection_date']}, by={info['user']} @ {info['timestamp']}"
    )

# ── 2. Also check production product_classifications.json for latest data ──
prod_class_path = (
    r"C:\Users\QB_DESARROLLO\Desktop\SGAv1.01\unified_db\product_classifications.json"
)
if os.path.exists(prod_class_path):
    with open(prod_class_path, "r", encoding="utf-8") as f:
        prod_class = json.load(f)

    prod_with_lote = {
        pid: d for pid, d in prod_class.items() if str(d.get("lote", "") or "").strip()
    }
    print(f"\nProduction classifications with lote: {len(prod_with_lote)}")
else:
    print(f"\nProduction classifications file not found at {prod_class_path}")

# ── 3. Extract lote_history entries from production classifications ──
all_history_entries = []
if os.path.exists(prod_class_path):
    for pid, d in prod_class.items():
        lh = d.get("lote_history", [])
        if isinstance(lh, list):
            for entry in lh:
                if isinstance(entry, dict):
                    ts = str(entry.get("date", entry.get("timestamp", "")))
                    if ts.startswith("2026-05") or ts.startswith("2026-04"):
                        all_history_entries.append(
                            {
                                "product_id": pid,
                                "old_lote": entry.get("old_lote", ""),
                                "new_lote": entry.get("new_lote", ""),
                                "date": ts,
                                "user": entry.get("user", ""),
                            }
                        )

print(f"\nLote history entries from April-May 2026: {len(all_history_entries)}")
for h in sorted(all_history_entries, key=lambda x: x["date"])[-20:]:
    print(
        f"  {h['product_id']}: {h['old_lote']} -> {h['new_lote']} by {h['user']} @ {h['date']}"
    )
