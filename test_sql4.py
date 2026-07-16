import sys

sys.path.insert(0, "sga_web")
sys.path.insert(0, "sga_web/core")
from database_client import DatabaseClient
import pandas as pd

c = DatabaseClient()
c.connect()
e = c.get_sql_engine()
df = pd.read_sql(
    "SELECT COUNT(*) as c FROM product_classifications WHERE lote_history IS NOT NULL",
    con=e,
)
print("Total NOT NULL:", df.iloc[0]["c"])
df = pd.read_sql(
    "SELECT COUNT(*) as c FROM product_classifications WHERE lote_history = '[]'", con=e
)
print("Total == [] :", df.iloc[0]["c"])
df = pd.read_sql(
    "SELECT COUNT(*) as c FROM product_classifications WHERE lote_history IS NULL",
    con=e,
)
print("Total NULL :", df.iloc[0]["c"])
