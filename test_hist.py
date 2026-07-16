import sys

sys.path.insert(0, "sga_web")
sys.path.insert(0, "sga_web/core")
from tara_weight_manager import TaraWeightManager

mgr = TaraWeightManager()

history_list = []
for pid, data in mgr._product_classifications.items():
    lh = data.get("lote_history", [])
    if lh:
        print(f"Product {pid} has {len(lh)} history entries")
    for entry in lh:
        enriched_entry = dict(entry)
        enriched_entry["product_id"] = pid
        enriched_entry["chemical_name"] = data.get("chemical_name", "")
        history_list.append(enriched_entry)

print(f"\nTotal history entries: {len(history_list)}")
for x in history_list[-5:]:
    print(x)
