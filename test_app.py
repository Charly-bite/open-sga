import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

sys.path.insert(0, os.path.join(root_dir, "sga_web"))

from sga_web.app import app
import tara_weight_manager as twm

print("Using tara_weight_manager from:", twm.__file__)

with app.app_context():
    mgr = app.tara_manager
    total_hist = 0
    for pid, data in mgr._product_classifications.items():
        lh = data.get("lote_history", [])
        total_hist += len(lh)

    print(f"Total history entries in app's mgr: {total_hist}")
