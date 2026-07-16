import os
import sys
import json
from sqlalchemy import text

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "sga_web"))

from sga_web.core.database_client import DatabaseClient

c = DatabaseClient()
c.connect()
e = c.get_sql_engine()

with e.connect() as conn:
    with conn.begin():
        # 1. Delete from product_lote_history table
        res = conn.execute(
            text(
                "DELETE FROM product_lote_history WHERE event_date >= '2026-05-13 00:00:00'"
            )
        )
        print(f"Deleted {res.rowcount} bad sync events from product_lote_history.")

        # 2. Clean the lote_history JSON column in product_classifications
        res = conn.execute(
            text("SELECT product_id, lote_history FROM product_classifications")
        )
        rows = res.fetchall()

        cleaned = 0
        for row in rows:
            pid = row[0]
            hist_str = row[1]
            if hist_str:
                try:
                    hist_list = json.loads(hist_str)
                    new_hist = []
                    changed = False
                    for h in hist_list:
                        ts = str(h.get("date") or h.get("timestamp") or "")
                        if ts.startswith("2026-05-13"):
                            changed = True
                        else:
                            new_hist.append(h)

                    if changed:
                        conn.execute(
                            text(
                                "UPDATE product_classifications SET lote_history = :hist WHERE product_id = :pid"
                            ),
                            {"hist": json.dumps(new_hist), "pid": pid},
                        )
                        cleaned += 1
                except Exception as ex:
                    print(f"Error parsing history for {pid}: {ex}")

        print(f"Cleaned JSON history for {cleaned} products.")
