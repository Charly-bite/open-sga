import json
from database_client import DatabaseClient

try:
    client = DatabaseClient()
    client.connect()
    engine = client.get_sql_engine()

    with open("order_status_db.json", "r", encoding="utf-8") as f:
        data = json.load(f).get("orders", {})

    records = []
    for o_id, o_data in data.items():
        records.append(
            (
                str(o_id),
                o_data.get("status", ""),
                o_data.get("last_updated", ""),
                json.dumps(o_data),
            )
        )

    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE order_status")
        conn.exec_driver_sql("""
            CREATE TABLE order_status (
                order_id VARCHAR(50) PRIMARY KEY,
                status VARCHAR(100),
                last_updated VARCHAR(50),
                data NVARCHAR(MAX)
            )
        """)
        if records:
            conn.connection.cursor().executemany(
                "INSERT INTO order_status (order_id, status, last_updated, data) VALUES (?, ?, ?, ?)",
                records,
            )
            conn.connection.commit()

    print(f"Fixed! Imported {len(records)} orders with correct schema.")
except Exception as e:
    print(f"Error: {e}")
