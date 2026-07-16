import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

sys.path.insert(0, os.path.join(root_dir, "sga_web"))

from sqlalchemy import text
from sga_web.core.database_client import DatabaseClient

c = DatabaseClient()
c.connect()
e = c.get_sql_engine()

with e.connect() as conn:
    with conn.begin():
        # Delete from product_lote_history
        res = conn.execute(
            text(
                "DELETE FROM product_lote_history WHERE event_date >= '2026-05-13 00:00:00'"
            )
        )
        print(f"Deleted {res.rowcount} bad sync events from today.")
