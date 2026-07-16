import os
import sys
import json
from sqlalchemy import text

root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "sga_web"))

from sga_web.core.database_client import DatabaseClient


def main():
    c = DatabaseClient()
    c.connect()
    e = c.get_sql_engine()

    with e.connect() as conn:
        with conn.begin():
            # Get all events from product_lote_history
            res = conn.execute(text("""
                SELECT product_id, old_lote, new_lote, old_date, new_date, 
                       old_reinsp_date, new_reinsp_date, event_date, user_name, notes
                FROM product_lote_history
            """))
            events = res.fetchall()

            # Group by product
            product_events = {}
            for row in events:
                pid = row[0]
                if pid not in product_events:
                    product_events[pid] = []

                # Convert to dict
                entry = {
                    "old_lote": str(row[1] or ""),
                    "new_lote": str(row[2] or ""),
                    "old_date": str(row[3] or "")[:10],
                    "new_date": str(row[4] or "")[:10],
                    "old_reinsp_date": str(row[5] or "")[:10],
                    "new_reinsp_date": str(row[6] or "")[:10],
                    "date": str(row[7] or ""),
                    "user": str(row[8] or ""),
                    "notes": str(row[9] or ""),
                }
                product_events[pid].append(entry)

            # Now update the JSON in product_classifications
            updated = 0
            for pid, evs in product_events.items():
                # Read existing JSON
                res = conn.execute(
                    text(
                        "SELECT lote_history FROM product_classifications WHERE product_id = :pid"
                    ),
                    {"pid": pid},
                )
                rows = res.fetchall()

                if not rows:
                    continue
                row = rows[0]

                try:
                    hist = json.loads(row[0] or "[]")
                except Exception:
                    hist = []

                # Merge logic: avoid duplicates
                existing_dates = set(e.get("date") or e.get("timestamp") for e in hist)

                added = False
                for new_ev in evs:
                    if new_ev["date"] not in existing_dates:
                        hist.append(new_ev)
                        existing_dates.add(new_ev["date"])
                        added = True

                if added:
                    # Sort descending
                    hist.sort(
                        key=lambda x: str(x.get("date") or x.get("timestamp") or ""),
                        reverse=True,
                    )
                    conn.execute(
                        text(
                            "UPDATE product_classifications SET lote_history = :hist WHERE product_id = :pid"
                        ),
                        {"hist": json.dumps(hist, ensure_ascii=False), "pid": pid},
                    )
                    updated += 1

            print(f"Updated {updated} products with missing history from SQL table.")


if __name__ == "__main__":
    main()
