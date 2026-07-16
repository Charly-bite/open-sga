import sys

sys.path.insert(0, "sga_web")
sys.path.insert(0, "sga_web/core")
from database_client import DatabaseClient
import pandas as pd

c = DatabaseClient()
c.connect()
e = c.get_sql_engine()
df = pd.read_sql(
    "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'product_classifications'",
    con=e,
)
print(df.to_string())
