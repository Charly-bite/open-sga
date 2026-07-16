import sys

sys.path.insert(0, "sga_web")
sys.path.insert(0, "sga_web/core")
from database_client import DatabaseClient
import pandas as pd
import traceback

c = DatabaseClient()
c.connect()
e = c.get_sql_engine()
df_history = pd.read_sql(
    "SELECT * FROM product_lote_history ORDER BY product_id, event_date DESC", con=e
)

classifications = {"VAR-QB00001": {}}
hist_count = 0
try:
    for _, hist_row in df_history.iterrows():
        pid = str(hist_row["product_id"])
        entry = classifications.setdefault(pid, {})
        if "lote_history" not in entry or not isinstance(entry["lote_history"], list):
            entry["lote_history"] = []

        # Convert SQL row to history entry format
        h_entry = {
            "old_lote": hist_row.get("old_lote"),
            "new_lote": hist_row.get("new_lote"),
            "old_date": (
                str(hist_row.get("old_date") or "")[:10]
                if hist_row.get("old_date")
                else ""
            ),
            "new_date": (
                str(hist_row.get("new_date") or "")[:10]
                if hist_row.get("new_date")
                else ""
            ),
            "user": hist_row.get("user_name", "Sistema"),
            "timestamp": (
                str(hist_row.get("event_date") or "")[:19]
                if hist_row.get("event_date")
                else ""
            ),
            "source": "sql_recovery",
            "notes": hist_row.get("notes", ""),
        }

        ts = h_entry["timestamp"]
        if not any(
            x.get("timestamp") == ts or x.get("date") == ts
            for x in entry["lote_history"]
        ):
            entry["lote_history"].append(h_entry)
            hist_count += 1

    print(f"Success! Built {hist_count} entries.")
except Exception as ex:
    print(f"Exception: {ex}")
    traceback.print_exc()
