import sys

sys.path.append("sga_web/core")
sys.path.append("sga_web")
from database_client import DatabaseClient
import pandas as pd

client = DatabaseClient()
if client.connect():
    engine = client.get_sql_engine()
    df = pd.read_sql(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'order_status'",
        con=engine,
    )
    print(df)
