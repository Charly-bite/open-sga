#!/usr/bin/env python3
"""
Standalone SAP to Local DB Sync
Performs a safe merge of SAP Master Data (OITM) into unified_db/products_master.csv.
Called automatically by watchdog.py for background updates, and can be run manually.
"""

import os
import sys
import logging
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sga_web", "core"))
from sap_connector import SAPHanaConnector

# Config logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("SAP-Sync")


def run_sync(limit=2000, updated_since=None):
    logger.info("Iniciando sincronizacion con SAP HANA...")

    sap = SAPHanaConnector()
    if not sap.connect():
        logger.error("No se pudo conectar a SAP. Abortando sincronizacion.")
        return {"success": False, "error": "No connect"}

    try:
        result = sap.sync_products_from_sap(limit=limit, updated_since=updated_since)
        sap_data = result.get("data", [])
    except Exception as e:
        logger.error(f"Error al obtener datos de SAP: {e}")
        sap.disconnect()
        return {"success": False, "error": str(e)}

    sap.disconnect()

    sql_engine = None
    try:
        from database_client import DatabaseClient

        client = DatabaseClient()
        if client.connect():
            base_db_path = client.get_database_path()
            sql_engine = client.get_sql_engine()
            client.disconnect()
            csv_path = os.path.join(base_db_path, "products_master.csv")
            logger.info(f"Usando base de datos remota/activa: {csv_path}")
        else:
            csv_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "unified_db",
                "products_master.csv",
            )
            logger.info(f"Usando base de datos local: {csv_path}")
    except Exception as e:
        logger.error(f"Error detectando base de datos principal, usando local. {e}")
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "unified_db",
            "products_master.csv",
        )

    df_local = pd.DataFrame()
    loaded_from_sql = False

    if sql_engine:
        try:
            df_local = pd.read_sql_table("products_master", con=sql_engine)
            # Ensure columns format to string
            for col in df_local.columns:
                df_local[col] = df_local[col].astype(str).replace("nan", "")
            loaded_from_sql = True
            logger.info(
                f"Cargada master de productos desde SQL ({len(df_local)} registros)"
            )
        except Exception as e:
            logger.error(f"No se pudo cargar de SQL: {e}")

    if not loaded_from_sql:
        if os.path.exists(csv_path):
            df_local = pd.read_csv(csv_path, dtype=str).fillna("")

    PROTECTED_COLS = {"signal_word", "cas_number", "chemical_name", "emergency_phone"}
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    added = 0
    updated = 0
    skipped = 0

    new_rows = []

    for sap_row in sap_data:
        item_code = str(sap_row.get("item_code", "")).strip()
        if not item_code:
            skipped += 1
            continue

        if not df_local.empty and "product_id" in df_local.columns:
            mask = df_local["product_id"] == item_code
            if mask.any():
                idx = df_local.index[mask][0]
                if not df_local.at[idx, "sap_matnr"]:
                    df_local.at[idx, "sap_matnr"] = item_code
                df_local.at[idx, "sap_sync_date"] = now_str

                for local_col, sap_col in [
                    ("signal_word", "signal_word"),
                    ("chemical_name", "item_name"),
                ]:
                    if local_col in PROTECTED_COLS and not df_local.at[idx, local_col]:
                        val = str(sap_row.get(sap_col, "")).strip()
                        if val:
                            df_local.at[idx, local_col] = val
                updated += 1
                continue

        # New product to add
        new_rows.append(
            {
                "product_id": item_code,
                "chemical_name": str(sap_row.get("item_name", "")).strip(),
                "cas_number": "",
                "signal_word": str(sap_row.get("signal_word", "")).strip(),
                "emergency_phone": "",
                "last_updated": now_str,
                "needs_update": "Y",
                "sap_matnr": item_code,
                "sap_sync_date": now_str,
                "is_active": "Y",
            }
        )
        added += 1

    if new_rows:
        df_new = pd.DataFrame(new_rows)
        if df_local.empty:
            df_local = df_new
        else:
            df_local = pd.concat([df_local, df_new], ignore_index=True)

    if added > 0 or updated > 0:
        logger.info(f"Guardando {added} nuevos y {updated} actualizados...")
        if sql_engine:
            try:
                with sql_engine.begin() as conn:
                    conn.exec_driver_sql("TRUNCATE TABLE products_master")
                df_local.to_sql(
                    "products_master", con=sql_engine, if_exists="append", index=False
                )
                logger.info("Guardado en SQL exitosamente.")
            except Exception as e:
                logger.error(f"Error guardando en SQL: {e}")

        # Also save to CSV fallback
        df_local.to_csv(csv_path, index=False)
        logger.info(f"Guardado en CSV fallback: {csv_path}")
    else:
        logger.info("Sincronizacion completada, no hubo cambios locales que guardar.")

    stats = {
        "success": True,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "synced": len(sap_data),
    }
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser("Sync SAP Products to Local Database")
    parser.add_argument("--limit", type=int, default=2000, help="Max items to fetch")
    args = parser.parse_args()

    stats = run_sync(limit=args.limit)
    print(f"\nResult: {stats}")
