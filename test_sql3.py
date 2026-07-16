import json
import sys

sys.path.insert(0, "sga_web")
sys.path.insert(0, "sga_web/core")
from database_client import DatabaseClient
from sqlalchemy import text

PROD_CLASS_PATH = (
    r"C:\Users\QB_DESARROLLO\Desktop\SGAv1.01\unified_db\product_classifications.json"
)

client = DatabaseClient()
client.connect()
engine = client.get_sql_engine()

with open(PROD_CLASS_PATH, "r", encoding="utf-8") as f:
    prod_class = json.load(f)

# Find a product that has lote_history but wasn't updated
prod_with_lote = {
    pid: d for pid, d in prod_class.items() if str(d.get("lote", "") or "").strip()
}

errors = []
success = 0
with engine.connect() as conn:
    for pid, d in prod_with_lote.items():
        lote_history = d.get("lote_history", [])
        if not lote_history:
            continue

        lote_history_json = json.dumps(lote_history)
        try:
            result = conn.execute(
                text(
                    "UPDATE product_classifications SET lote_history = :lh WHERE product_id = :pid"
                ),
                {"lh": lote_history_json, "pid": pid},
            )
            if result.rowcount > 0:
                success += 1
            else:
                errors.append(f"{pid}: 0 rows affected")
        except Exception as e:
            errors.append(f"{pid}: Exception {e}")

    conn.commit()

print(f"Success: {success}")
print(f"Errors: {len(errors)}")
if errors:
    print("First 5 errors:")
    for e in errors[:5]:
        print(e)
