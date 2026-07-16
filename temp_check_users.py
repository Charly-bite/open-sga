import logging
logging.basicConfig(level=logging.ERROR)
from database_client import get_shared_client
from sqlalchemy import text

client = get_shared_client()
engine = client.get_sql_engine()
if engine:
    with engine.connect() as conn:
        users = conn.execute(text("SELECT username FROM SGA_Users")).fetchall()
        print("SGA_Users:", [u[0] for u in users])
        try:
            users_old = conn.execute(text("SELECT username FROM users")).fetchall()
            print("users:", [u[0] for u in users_old])
        except Exception as e:
            print("Table 'users' doesn't exist.")
else:
    print("Could not connect to database")
