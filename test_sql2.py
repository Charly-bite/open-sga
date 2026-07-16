import sys

sys.path.insert(0, "sga_web")
sys.path.insert(0, "sga_web/core")
from database_client import DatabaseClient
import pandas as pd

client = DatabaseClient()
client.connect()
engine = client.get_sql_engine()

df = pd.read_sql(
    "SELECT COUNT(*) as c FROM product_classifications WHERE lote_history IS NOT NULL AND lote_history != '[]'",
    con=engine,
)
print("Count of non-empty lote_history:", df.iloc[0]["c"])
