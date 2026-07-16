import logging
logging.basicConfig(level=logging.ERROR)
from database_client import get_shared_client
from sqlalchemy import text

client = get_shared_client()
engine = client.get_sql_engine()
if engine:
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")).fetchall()
        print("TABLES:", [r[0] for r in tables])
else:
    print("Could not connect to database")
