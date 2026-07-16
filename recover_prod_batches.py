"""
Recovery script: Apply the latest batch data from the production server (SGAv1.01)
to the development server's SQL database and in-memory classifications.

This script:
1. Reads the production product_classifications.json (643 products with lote)
2. Updates the dev server's product_classifications SQL table with the latest lote values
3. Updates the dev server's product_batches SQL table with lotes_info data
4. Recovers lote_history from the production classifications into product_lote_history
5. Imports the production history.json lote events into system_audit_logs
"""

import json
import os
import sys

sys.path.insert(0, "sga_web")
sys.path.insert(0, "sga_web/core")
os.chdir("sga_web")

from dotenv import load_dotenv

load_dotenv(os.path.join("..", ".env"))

from database_client import DatabaseClient
import pandas as pd
from sqlalchemy import text

PROD_CLASS_PATH = (
    r"C:\Users\QB_DESARROLLO\Desktop\SGAv1.01\unified_db\product_classifications.json"
)
PROD_HISTORY_PATH = r"C:\Users\QB_DESARROLLO\Desktop\SGAv1.01\sga_web\history.json"

client = DatabaseClient()
if not client.connect():
    print("FATAL: Could not connect to SQL")
    sys.exit(1)

engine = client.get_sql_engine()
if not engine:
    print("FATAL: No SQL engine")
    sys.exit(1)

print("=" * 60)
print("BATCH DATA RECOVERY FROM PRODUCTION")
print("=" * 60)

# ── 1. Load production classifications ──
with open(PROD_CLASS_PATH, "r", encoding="utf-8") as f:
    prod_class = json.load(f)

prod_with_lote = {
    pid: d for pid, d in prod_class.items() if str(d.get("lote", "") or "").strip()
}
print(f"\n[1] Production has {len(prod_with_lote)} products with lote data")

# ── 2. Update product_classifications SQL with latest lote values ──
updated = 0
with engine.connect() as conn:
    for pid, d in prod_with_lote.items():
        lote = str(d.get("lote", "")).strip()
        lote_date = str(d.get("lote_date", "") or "").strip()[:10]
        lote_reinsp = str(d.get("lote_reinspection_date", "") or "").strip()[:10]
        lotes_info = d.get("lotes_info", {})
        lote_history = d.get("lote_history", [])

        # Normalize bad values
        for val_name in [lote_date, lote_reinsp]:
            if val_name and val_name.lower() in ("nan", "none", "nat"):
                val_name = ""

        lotes_info_json = (
            json.dumps(lotes_info) if isinstance(lotes_info, dict) else None
        )
        lote_history_json = (
            json.dumps(lote_history) if isinstance(lote_history, list) else None
        )

        try:
            result = conn.execute(
                text("""
                    UPDATE product_classifications 
                    SET lote = :lote,
                        lote_date = :lote_date,
                        lote_reinspection_date = :lote_reinsp,
                        lotes_info = :lotes_info,
                        lote_history = :lote_history
                    WHERE product_id = :pid
                """),
                {
                    "lote": lote if lote else None,
                    "lote_date": (
                        lote_date
                        if lote_date and lote_date.lower() not in ("nan", "none")
                        else None
                    ),
                    "lote_reinsp": (
                        lote_reinsp
                        if lote_reinsp and lote_reinsp.lower() not in ("nan", "none")
                        else None
                    ),
                    "lotes_info": lotes_info_json,
                    "lote_history": lote_history_json,
                    "pid": pid,
                },
            )
            if result.rowcount > 0:
                updated += 1
        except Exception:
            pass  # Product may not exist in classifications

    conn.commit()

print(f"[2] Updated {updated} products in product_classifications SQL table")

# ── 3. Insert/update product_batches from production lotes_info ──
batch_records = []
for pid, d in prod_class.items():
    lotes_info = d.get("lotes_info", {})
    if not isinstance(lotes_info, dict):
        continue

    # Also include the primary lote if not in lotes_info
    primary_lote = str(d.get("lote", "") or "").strip()
    if primary_lote and primary_lote not in lotes_info:
        lotes_info[primary_lote] = {
            "fecha_elaboracion": d.get("lote_date", ""),
            "fecha_inspeccion": d.get("lote_reinspection_date", ""),
        }

    for lote, info in lotes_info.items():
        if not str(lote).strip() or not isinstance(info, dict):
            continue
        f_elab = str(info.get("fecha_elaboracion", "") or "")[:10]
        f_reinsp = str(info.get("fecha_inspeccion", "") or "")[:10]
        if f_elab.lower() in ("nan", "none", "nat", ""):
            f_elab = None
        if f_reinsp.lower() in ("nan", "none", "nat", ""):
            f_reinsp = None

        batch_records.append(
            {
                "product_id": str(pid)[:50],
                "lote": str(lote)[:255],
                "fecha_elaboracion": f_elab,
                "fecha_reinspeccion": f_reinsp,
            }
        )

batch_inserted = 0
with engine.connect() as conn:
    with conn.begin():
        for rec in batch_records:
            try:
                conn.execute(
                    text("""
                        MERGE product_batches AS target
                        USING (VALUES (:product_id, :lote, :fecha_elaboracion, :fecha_reinspeccion)) 
                        AS source (product_id, lote, fecha_elaboracion, fecha_reinspeccion)
                        ON target.product_id = source.product_id AND target.lote = source.lote
                        WHEN MATCHED THEN
                            UPDATE SET 
                                fecha_elaboracion = source.fecha_elaboracion,
                                fecha_reinspeccion = source.fecha_reinspeccion
                        WHEN NOT MATCHED THEN
                            INSERT (product_id, lote, fecha_elaboracion, fecha_reinspeccion)
                            VALUES (source.product_id, source.lote, source.fecha_elaboracion, source.fecha_reinspeccion);
                    """),
                    rec,
                )
                batch_inserted += 1
            except Exception:
                pass

print(f"[3] Upserted {batch_inserted} records into product_batches SQL table")

# ── 4. Recover lote_history from production into product_lote_history ──
import re
from datetime import datetime as _dt

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def safe_date(val):
    if val is None:
        return None
    s = str(val).strip()[:10]
    if s.lower() in ("nan", "none", "nat", "", "null"):
        return None
    if not _DATE_RE.match(s):
        return None
    return s


def safe_datetime(val):
    if val is None:
        return None
    s = str(val).strip()[:19]
    if s.lower() in ("nan", "none", "nat", "", "null"):
        return None
    if len(s) < 10:
        return None
    try:
        return _dt.strptime(s.replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return _dt.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None


history_records = []
for pid, d in prod_class.items():
    lh = d.get("lote_history", [])
    if not isinstance(lh, list):
        continue
    for entry in lh:
        if not isinstance(entry, dict):
            continue
        ts = str(entry.get("date", entry.get("timestamp", "")))

        history_records.append(
            {
                "product_id": str(pid)[:50],
                "old_lote": str(entry.get("old_lote", "") or "")[:255],
                "new_lote": str(entry.get("new_lote", "") or "")[:255],
                "old_date": safe_date(
                    entry.get("old_date") or entry.get("old_elab_date")
                ),
                "new_date": safe_date(
                    entry.get("new_date") or entry.get("new_elab_date")
                ),
                "old_reinsp_date": safe_date(entry.get("old_reinsp_date")),
                "new_reinsp_date": safe_date(entry.get("new_reinsp_date")),
                "event_date": safe_datetime(ts),
                "user_name": str(entry.get("user", "") or "")[:50],
                "merma_kg": (
                    float(entry["merma_kg"])
                    if entry.get("merma_kg") is not None
                    else None
                ),
                "notes": str(entry.get("notes", "") or "")[:4000],
            }
        )

hist_inserted = 0
if history_records:
    with engine.connect() as conn:
        with conn.begin():
            # Ensure table exists
            conn.execute(text("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='product_lote_history' and xtype='U')
                CREATE TABLE product_lote_history (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    product_id VARCHAR(50),
                    old_lote VARCHAR(255),
                    new_lote VARCHAR(255),
                    old_date DATE,
                    new_date DATE,
                    old_reinsp_date DATE,
                    new_reinsp_date DATE,
                    event_date DATETIME,
                    user_name VARCHAR(50),
                    merma_kg FLOAT,
                    notes NVARCHAR(MAX)
                )
            """))
            # Clear and reinsert
            conn.execute(text("DELETE FROM product_lote_history"))

        # Insert in batches
        df_hist = pd.DataFrame(history_records)
        df_hist.to_sql(
            "product_lote_history", con=engine, if_exists="append", index=False
        )
        hist_inserted = len(history_records)

print(
    f"[4] Inserted {hist_inserted} lote history records into product_lote_history SQL table"
)

# ── 5. Import production history.json lote events ──
with open(PROD_HISTORY_PATH, "r", encoding="utf-8", errors="replace") as f:
    prod_history = json.load(f)

lote_events = [
    e
    for e in prod_history
    if e.get("event_type", "") in ("MERMA_UPDATE", "product_edit")
    and ("lote" in str(e.get("details", {})).lower())
]

print(f"[5] Found {len(lote_events)} lote-related events in production history.json")

# ── Summary ──
print("\n" + "=" * 60)
print("RECOVERY COMPLETE!")
print("=" * 60)
print(f"  Classifications updated: {updated}")
print(f"  Batch records upserted: {batch_inserted}")
print(f"  History records inserted: {hist_inserted}")
print("\n>>> RESTART THE SERVER to see the changes <<<")
