import json

import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "sga_web"))

from sga_web.core.database_client import DatabaseClient

client = DatabaseClient()
client.connect()
conn = client.get_sql_engine().raw_connection()
cursor = conn.cursor()
print("Connected to SQL via DatabaseClient.")

PROD_HISTORY_PATH = r"C:\Users\QB_DESARROLLO\Desktop\SGAv1.01\sga_web\history.json"
with open(PROD_HISTORY_PATH, "r", encoding="utf-8", errors="replace") as f:
    prod_history = json.load(f)

lote_events = [
    e
    for e in prod_history
    if e.get("event_type", "") in ("MERMA_UPDATE", "product_edit")
    and ("lote" in str(e.get("details", {})).lower())
]

inserted = 0
for e in lote_events:
    details = e.get("details", {})

    # We might have MERMA_UPDATE with details containing product_id, old_lote, new_lote, etc.
    # OR we might have product_edit with details.changes.lote_history

    # Let's extract any history entries inside these events
    entries_to_insert = []

    if e["event_type"] == "MERMA_UPDATE":
        if "product_id" in details and "new_lote" in details:
            entries_to_insert.append(
                {
                    "product_id": details["product_id"],
                    "old_lote": details.get("old_lote", ""),
                    "new_lote": details.get("new_lote", ""),
                    "old_date": details.get("old_date", ""),
                    "new_date": details.get("new_date", ""),
                    "old_reinsp_date": details.get("old_reinsp_date", ""),
                    "new_reinsp_date": details.get("new_reinsp_date", ""),
                    "date": details.get("date") or e.get("timestamp"),
                    "user": details.get("user") or e.get("user", "Sistema"),
                    "merma_kg": details.get("merma_kg"),
                }
            )

    elif e["event_type"] == "product_edit":
        changes = details.get("changes", {})
        if "lote_history" in changes:
            # Changes usually contain the WHOLE lote_history array, but we only want the ones that match this event's date
            # Actually, to be safe, we can just insert ALL of them if they are not already in the DB.
            pid = details.get("product_code")
            if pid:
                for hist in changes["lote_history"]:
                    # We will insert it. The SQL unique constraints or our checking will prevent dupes
                    entries_to_insert.append(
                        {
                            "product_id": pid,
                            "old_lote": hist.get("old_lote", ""),
                            "new_lote": hist.get("new_lote", ""),
                            "old_date": hist.get("old_date", ""),
                            "new_date": hist.get("new_date", ""),
                            "old_reinsp_date": hist.get("old_reinsp_date", ""),
                            "new_reinsp_date": hist.get("new_reinsp_date", ""),
                            "date": hist.get("date")
                            or hist.get("timestamp")
                            or e.get("timestamp"),
                            "user": hist.get("user") or e.get("user", "Sistema"),
                            "notes": hist.get("notes"),
                        }
                    )

    for entry in entries_to_insert:
        pid = entry["product_id"]
        ts = str(entry["date"]).strip()

        # Validate timestamp
        if not ts or ts.lower() in ("nan", "nat", "none"):
            continue

        # Try to parse it to ensure it's a valid datetime
        try:
            # Simple check if it looks like a datetime
            if len(ts) < 10:
                continue
        except Exception:
            continue

        # Check if already exists in product_lote_history table
        cursor.execute(
            "SELECT id FROM product_lote_history WHERE product_id = ? AND event_date = ?",
            (pid, ts),
        )
        exists_in_sql = bool(cursor.fetchone())
        old_lote = entry.get("old_lote") or None
        new_lote = entry.get("new_lote") or None
        old_date = entry.get("old_date") or None
        new_date = entry.get("new_date") or None
        if str(old_date).lower() == "nan":
            old_date = None
        if str(new_date).lower() == "nan":
            new_date = None
        old_reinsp_date = entry.get("old_reinsp_date") or None
        new_reinsp_date = entry.get("new_reinsp_date") or None
        user_name = entry.get("user", "Sistema")
        merma_kg = entry.get("merma_kg") or None
        notes = entry.get("notes") or None

        try:
            # 1. Insert into product_lote_history if not exists
            if not exists_in_sql:
                cursor.execute(
                    """
                    INSERT INTO product_lote_history 
                    (product_id, old_lote, new_lote, old_date, new_date, old_reinsp_date, new_reinsp_date, event_date, user_name, merma_kg, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        pid,
                        old_lote,
                        new_lote,
                        old_date,
                        new_date,
                        old_reinsp_date,
                        new_reinsp_date,
                        ts,
                        user_name,
                        merma_kg,
                        notes,
                    ),
                )
        except Exception:
            pass  # Probably already exists

        try:
            # 2. Append to product_classifications lote_history
            cursor.execute(
                "SELECT lote_history FROM product_classifications WHERE product_id = ?",
                (pid,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                import json

                try:
                    hist = json.loads(row[0])
                except Exception:
                    hist = []
            else:
                hist = []

            # Create dict matching what the app expects in memory
            mem_entry = {
                "old_lote": old_lote or "",
                "new_lote": new_lote or "",
                "old_date": old_date or "",
                "new_date": new_date or "",
                "old_elab_date": entry.get("old_elab_date", ""),
                "new_elab_date": entry.get("new_elab_date", ""),
                "old_reinsp_date": old_reinsp_date or "",
                "new_reinsp_date": new_reinsp_date or "",
                "date": ts,
                "user": user_name,
                "notes": notes or "",
            }
            if merma_kg is not None:
                mem_entry["merma_kg"] = merma_kg

            # Check if this exact timestamp already exists in JSON
            exists = any(h.get("date") == ts or h.get("timestamp") == ts for h in hist)
            if not exists:
                hist.append(mem_entry)
                cursor.execute(
                    "UPDATE product_classifications SET lote_history = ? WHERE product_id = ?",
                    (json.dumps(hist), pid),
                )
                conn.commit()
                inserted += 1
                print(f"Appended history JSON for {pid} at {ts}")
        except Exception as ex:
            print(f"Error appending for {pid} at {ts}: {ex}")

print(f"Total inserted from history.json: {inserted}")
