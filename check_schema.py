import os
import sys
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
        text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='product_lote_history' ORDER BY ORDINAL_POSITION"
        )
    )
    print("product_lote_history columns:")
    for row in res:
        print(f"  {row[0]}")

    print()
    res = conn.execute(
        text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='product_classifications' ORDER BY ORDINAL_POSITION"
        )
    )
    print("product_classifications columns:")
    for row in res:
        print(f"  {row[0]}")
