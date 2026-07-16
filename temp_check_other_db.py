import logging
logging.basicConfig(level=logging.ERROR)
from database_client import get_shared_client
from sqlalchemy import text

client = get_shared_client()
engine = client.get_sql_engine()
if engine:
    with engine.connect() as conn:
        for db in ["QB_WMS", "DB_QuimicaBoss"]:
            try:
                tables = conn.execute(text(f"SELECT TABLE_NAME FROM {db}.INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")).fetchall()
                print(f"--- {db} ---")
                print([r[0] for r in tables])
            except Exception as e:
                pass
else:
    print("Could not connect to database")
