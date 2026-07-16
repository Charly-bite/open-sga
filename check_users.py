import database_client
from sqlalchemy import text

db = database_client.get_shared_client()
eng = db.get_sql_engine()
with eng.connect() as conn:
    res = conn.execute(text("SELECT name, create_date FROM sys.tables"))
    print("All tables:")
    for row in res:
        print(row)
