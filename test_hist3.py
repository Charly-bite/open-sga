import sys

sys.path.insert(0, "sga_web")
sys.path.insert(0, "sga_web/core")
from tara_weight_manager import TaraWeightManager

# Clear any cached _instance just in case
mgr = TaraWeightManager()
mgr._load_classifications(force=True)

total_hist = 0
for pid, data in mgr._product_classifications.items():
    lh = data.get("lote_history", [])
    total_hist += len(lh)

print(f"Total history entries in mgr: {total_hist}")
