"""
Recover ALL lote_history from the old SGAv1.01 production server's
product_classifications.json and merge them into the current SQL database.

This script:
1. Reads old production's product_classifications.json (authoritative pre-migration source)
2. Reads old production's history.json (global event log)
3. For each product, merges missing history entries into the current SQL
   product_classifications.lote_history JSON column
4. Also inserts missing records into product_lote_history SQL table

SQL Schema for product_lote_history:
  id, product_id, old_lote, new_lote, old_date, new_date,
  old_reinsp_date, new_reinsp_date, event_date, user_name, merma_kg, notes
"""

import os
import sys
import json
import re
from datetime import datetime
from sqlalchemy import text

root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "sga_web"))

from sga_web.core.database_client import DatabaseClient

OLD_PROD_CLASSIFICATIONS = (
    r"C:\Users\QB_DESARROLLO\Desktop\SGAv1.01\unified_db\product_classifications.json"
)
OLD_PROD_HISTORY = r"C:\Users\QB_DESARROLLO\Desktop\SGAv1.01\sga_web\history.json"


def normalize_ts(ts):
    """Normalize a timestamp string to a comparable format."""
    if not ts:
        return ""
    ts = str(ts).strip()
    ts = re.sub(r"\.\d+$", "", ts)
    return ts


def make_fingerprint(entry):
    """Create a unique fingerprint for a history entry to detect duplicates."""
    d = normalize_ts(entry.get("date") or entry.get("timestamp") or "")
    new_lote = str(entry.get("new_lote", "")).strip()
    old_lote = str(entry.get("old_lote", "")).strip()
    return f"{d}|{new_lote}|{old_lote}"


def is_valid_date(ts):
    """Check if timestamp looks like a valid date."""
    ts = str(ts).strip()
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}", ts)) and ts != "NaT"


def main():
    c = DatabaseClient()
    c.connect()
    engine = c.get_sql_engine()

    # Load old production data
    with open(OLD_PROD_CLASSIFICATIONS, "r", encoding="latin-1") as f:
        old_classifications = json.load(f)

    with open(OLD_PROD_HISTORY, "r", encoding="latin-1") as f:
        old_history = json.load(f)

    print(f"Old production: {len(old_classifications)} products")
    print(f"Old history.json: {len(old_history)} entries")

    # Build a map of all old lote_history entries per product
    old_history_map = {}
    for pid, data in old_classifications.items():
        lh = data.get("lote_history", [])
        if lh:
            old_history_map[pid] = list(lh)

    # Also extract lote events from history.json
    for h in old_history:
        etype = h.get("event_type", "")
        details = h.get("details", {})
        if etype not in ("MERMA_UPDATE", "LOTE_UPDATE", "product_edit"):
            continue

        pid = details.get("product_id", details.get("product_code", ""))
        if not pid:
            continue

        ts = h.get("timestamp", "")
        if not is_valid_date(ts):
            continue

        entry = {
            "old_lote": details.get("old_lote", ""),
            "new_lote": details.get("new_lote", ""),
            "old_date": details.get("old_date", ""),
            "new_date": details.get("new_date", ""),
            "old_elab_date": details.get("old_elab_date", ""),
            "new_elab_date": details.get("new_elab_date", ""),
            "old_reinsp_date": details.get("old_reinsp_date", ""),
            "new_reinsp_date": details.get("new_reinsp_date", ""),
            "date": ts,
            "user": details.get("user", h.get("user", "")),
        }
        if details.get("merma_kg") is not None:
            entry["merma_kg"] = details["merma_kg"]
        if details.get("notes"):
            entry["notes"] = details["notes"]

        if pid not in old_history_map:
            old_history_map[pid] = []
        old_history_map[pid].append(entry)

    print(f"Products with old history entries: {len(old_history_map)}")
    total_old = sum(len(v) for v in old_history_map.values())
    print(f"Total old history entries to check: {total_old}")

    merged_json = 0
    merged_sql = 0
    skipped = 0

    with engine.connect() as conn:
        with conn.begin():
            # --- Pre-load ALL current JSON histories in bulk ---
            res = conn.execute(
                text("SELECT product_id, lote_history FROM product_classifications")
            )
            all_current = {}
            for row in res.fetchall():
                pid = row[0]
                try:
                    all_current[pid] = json.loads(row[1]) if row[1] else []
                except Exception:
                    all_current[pid] = []

            # --- Pre-load ALL existing SQL table fingerprints in bulk ---
            res = conn.execute(
                text(
                    "SELECT product_id, event_date, new_lote FROM product_lote_history"
                )
            )
            existing_sql_fps = set()
            for row in res.fetchall():
                pid = row[0]
                edate = row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else ""
                nlote = str(row[2] or "")
                existing_sql_fps.add(f"{pid}|{edate}|{nlote}")

            print(
                f"Pre-loaded {len(all_current)} products from SQL, {len(existing_sql_fps)} existing SQL history records"
            )

            for pid, old_entries in old_history_map.items():
                current_history = all_current.get(pid, [])
                product_exists = pid in all_current

                existing_fps = set()
                for entry in current_history:
                    existing_fps.add(make_fingerprint(entry))

                new_entries = []
                for entry in old_entries:
                    fp = make_fingerprint(entry)
                    if fp not in existing_fps and is_valid_date(entry.get("date", "")):
                        new_entries.append(entry)
                        existing_fps.add(fp)

                if not new_entries:
                    skipped += 1
                    continue

                # Merge and sort
                merged_history = current_history + new_entries
                merged_history.sort(
                    key=lambda x: normalize_ts(
                        x.get("date") or x.get("timestamp") or ""
                    ),
                    reverse=True,
                )

                # Update or insert JSON column
                if product_exists:
                    conn.execute(
                        text(
                            "UPDATE product_classifications SET lote_history=:hist WHERE product_id=:pid"
                        ),
                        {"hist": json.dumps(merged_history), "pid": pid},
                    )
                else:
                    old_data = old_classifications.get(pid, {})
                    conn.execute(
                        text(
                            """INSERT INTO product_classifications 
                                (product_id, lote_history, chemical_name, product_type, lote, lote_date, lote_reinspection_date)
                                VALUES (:pid, :hist, :chem, :ptype, :lote, :ldate, :rdate)"""
                        ),
                        {
                            "pid": pid,
                            "hist": json.dumps(merged_history),
                            "chem": old_data.get("chemical_name", ""),
                            "ptype": old_data.get("product_type", ""),
                            "lote": old_data.get("lote", ""),
                            "ldate": old_data.get("lote_date", ""),
                            "rdate": old_data.get("lote_reinspection_date", ""),
                        },
                    )

                merged_json += len(new_entries)

                # Insert into product_lote_history SQL table
                for entry in new_entries:
                    ts = normalize_ts(entry.get("date", ""))
                    if not is_valid_date(ts):
                        continue

                    try:
                        event_date = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        try:
                            event_date = datetime.strptime(ts[:10], "%Y-%m-%d")
                        except Exception:
                            continue

                    # Deduplicate using pre-loaded fingerprints
                    sql_fp = f"{pid}|{event_date.strftime('%Y-%m-%d %H:%M:%S')}|{str(entry.get('new_lote', ''))}"
                    if sql_fp in existing_sql_fps:
                        continue
                    existing_sql_fps.add(sql_fp)

                    conn.execute(
                        text(
                            """INSERT INTO product_lote_history 
                                (product_id, event_date, old_lote, new_lote, old_date, new_date,
                                 old_reinsp_date, new_reinsp_date, user_name, merma_kg, notes)
                                VALUES (:pid, :edate, :ol, :nl, :od, :nd, :ord, :nrd, :uname, :merma, :notes)"""
                        ),
                        {
                            "pid": pid,
                            "edate": event_date,
                            "ol": str(entry.get("old_lote", "")),
                            "nl": str(entry.get("new_lote", "")),
                            "od": str(entry.get("old_date", "")),
                            "nd": str(entry.get("new_date", "")),
                            "ord": str(entry.get("old_reinsp_date", "")),
                            "nrd": str(entry.get("new_reinsp_date", "")),
                            "uname": str(entry.get("user", "")),
                            "merma": entry.get("merma_kg"),
                            "notes": str(entry.get("notes", "") or ""),
                        },
                    )
                    merged_sql += 1

    print(f"\n{'='*60}")
    print("RECOVERY COMPLETE")
    print(f"{'='*60}")
    print(f"  Products checked: {len(old_history_map)}")
    print(f"  Products already up-to-date: {skipped}")
    print(f"  New entries merged into JSON column: {merged_json}")
    print(f"  New entries inserted into SQL table: {merged_sql}")
    print("\n>>> RESTART THE SERVER to see the changes <<<")


if __name__ == "__main__":
    main()
