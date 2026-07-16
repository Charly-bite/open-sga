"""Verify history counts by month from SQL database directly."""

import os
import sys
import json
from collections import Counter
from sqlalchemy import text

root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "sga_web"))

from sga_web.core.database_client import DatabaseClient

c = DatabaseClient()
c.connect()
e = c.get_sql_engine()

with e.connect() as conn:
    res = conn.execute(
        text("SELECT product_id, lote_history FROM product_classifications")
    )
    rows = res.fetchall()

history_list = []
for row in rows:
    pid = row[0]
    if row[1]:
        try:
            hist = json.loads(row[1])
            for h in hist:
                h["product_id"] = pid
                history_list.append(h)
        except Exception:
            pass

months = Counter()
for h in history_list:
    ts = str(h.get("date") or h.get("timestamp") or "")
    if ts.startswith("20"):
        m = ts[:7]
        months[m] += 1

print("History entries by month (from SQL):")
for m in sorted(months.keys()):
    print(f"  {m}: {months[m]} events")
total = sum(months.values())
print(f"Total valid history entries: {total}")

# Show first 5 for May
may = [
    h
    for h in history_list
    if str(h.get("date") or h.get("timestamp") or "").startswith("2026-05")
]
may.sort(key=lambda x: str(x.get("date") or x.get("timestamp") or ""), reverse=True)
print("\nFirst 5 May entries:")
for h in may[:5]:
    d = h.get("date") or h.get("timestamp")
    pid = h.get("product_id")
    nl = h.get("new_lote")
    print(f"  {d} {pid} -> {nl}")

# Show first 5 for April
apr = [
    h
    for h in history_list
    if str(h.get("date") or h.get("timestamp") or "").startswith("2026-04")
]
apr.sort(key=lambda x: str(x.get("date") or x.get("timestamp") or ""), reverse=True)
print("\nFirst 5 April entries:")
for h in apr[:5]:
    d = h.get("date") or h.get("timestamp")
    pid = h.get("product_id")
    nl = h.get("new_lote")
    print(f"  {d} {pid} -> {nl}")
