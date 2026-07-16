import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "sga_web", "core"))
from order_status_manager import OrderStatusManager
from sap_connector import SAPHanaConnector


def cleanup():
    # Use the absolute path for DB just in case
    db_path = os.path.join(os.path.dirname(__file__), "order_status_db.json")
    manager = OrderStatusManager(db_path=db_path)

    sap = SAPHanaConnector()
    if not sap.connect():
        print("Could not connect to SAP")
        return

    cursor = sap.connection.cursor()
    allowed_slp_codes = (
        "12",
        "23",
        "6",
        "13",
        "14",
        "11",
        "15",
        "5",
        "8",
        "17",
        "3",
        "19",
        "7",
        "4",
        "10",
        "-1",
    )

    order_ids = list(manager.orders.keys())
    if not order_ids:
        print("No orders to check.")
        return

    try:
        chunk_size = 500
        to_delete = []
        for i in range(0, len(order_ids), chunk_size):
            chunk = order_ids[i : i + chunk_size]
            placeholders = ",".join(["?" for _ in chunk])
            query = f"""
                SELECT "DocNum", "SlpCode"
                FROM "SBO_QUIMICABOSS"."ORDR"
                WHERE "DocNum" IN ({placeholders})
            """
            # Need to filter out any non-numeric order_ids just in case
            valid_chunk = []
            for x in chunk:
                try:
                    valid_chunk.append(int(x))
                except ValueError:
                    pass

            placeholders = ",".join(["?" for _ in valid_chunk])
            if not valid_chunk:
                continue

            query = f"""
                SELECT "DocNum", "SlpCode"
                FROM "SBO_QUIMICABOSS"."ORDR"
                WHERE "DocNum" IN ({placeholders})
            """
            cursor.execute(query, valid_chunk)

            # Keep track of orders found in SAP to find deleted ones
            found_in_sap = set()
            for row in cursor.fetchall():
                doc_num = str(int(row[0]))
                slp_code = str(row[1]) if row[1] is not None else None
                found_in_sap.add(doc_num)

                if slp_code not in allowed_slp_codes:
                    to_delete.append(doc_num)

            # If an order is in local DB but NOT in SAP ORDR (maybe deleted in SAP), we can optionally clean it
            # But let's stick to cleaning non-matching SlpCodes

        print(f"Total active orders before: {len(order_ids)}")
        print(f"Found {len(to_delete)} orders to delete (not in allowed sellers).")
        for doc_num in to_delete:
            manager.delete_order(doc_num)
            print(f"Deleted order {doc_num}")

    except Exception as e:
        print("Error:", e)
    finally:
        cursor.close()
        sap.disconnect()


if __name__ == "__main__":
    cleanup()
