import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

sys.path.insert(0, os.path.join(root_dir, "sga_web"))

from sga_web.app import app

with app.app_context():
    tara_mgr = app.tara_manager
    history_list = []

    # Extract all lote_history from all products
    for pid, data in tara_mgr._product_classifications.items():
        lh = data.get("lote_history", [])
        for entry in lh:
            # Inject product info into each history entry
            enriched_entry = dict(entry)
            enriched_entry["product_id"] = pid
            enriched_entry["chemical_name"] = data.get("chemical_name", "")
            history_list.append(enriched_entry)

    print(f"Total entries before filter: {len(history_list)}")

    # Filter by month if provided (YYYY-MM)
    filter_month = "2026-05"
    if filter_month and len(filter_month) == 7:
        filtered_list = []
        for x in history_list:
            ts = x.get("date") or x.get("timestamp") or ""
            if ts.startswith(filter_month):
                filtered_list.append(x)
        history_list = filtered_list

    print(f"Total entries after filter {filter_month}: {len(history_list)}")
    for h in history_list[:5]:
        print(h)
