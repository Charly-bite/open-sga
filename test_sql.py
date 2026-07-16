import os
import sys
from dotenv import load_dotenv
load_dotenv('sga_web/.env')

from config import get_sql_connection_string
from sqlalchemy import create_engine, text

import urllib.parse
conn_str = get_sql_connection_string()
params = urllib.parse.quote_plus(conn_str)
sql_url = f"mssql+pyodbc:///?odbc_connect={params}"
print(f"Connecting with: {sql_url}")
engine = create_engine(sql_url)
print("Engine created. Connecting...")
with engine.connect() as conn:
    print("Connected. Querying sys.dm_exec_requests...")
    res = conn.execute(text("""
        SELECT session_id, status, command, blocking_session_id, wait_type, wait_time, wait_resource 
        FROM sys.dm_exec_requests 
        WHERE blocking_session_id <> 0 OR wait_time > 0
    """))
    for r in res.fetchall():
        print(r)
print("Done.")
