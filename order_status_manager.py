#!/usr/bin/env python3
"""
Order Status Manager
Manages a local database of order statuses without modifying SAP.
Provides data for warehouse operators and a web interface for sales team.
"""

import json
import os
import datetime
from typing import Optional, Dict, List, Any
from enum import Enum

# Legacy label → current label. Applied at load time so old JSON files are
# automatically upgraded in memory without a migration script.
STATUS_LABEL_MIGRATIONS = {
    # Old PICKING aliases
    "Preparando": "Entregado",
    "Preparado": "Entregado",
    "Terminado": "Entregado",
    # Old READY aliases
    "Listo para Envío": "Relacion de envio",
    "Listo para Envio": "Relacion de envio",
    "Entregado a almacen": "Relacion de envio",
    "Recibido por almacen": "Relacion de envio",
    "Relación de envío": "Relacion de envio",
    # Old SHIPPED aliases
    "Enviado": "Enviado al cliente",
    "Recibido por cliente": "Enviado al cliente",
}


class OrderStatus(Enum):
    """Possible order statuses — aligned with SAO (Open-OMS)."""

    PENDING = "Pendiente"
    IN_PROGRESS = "En Proceso"
    PICKING = "Entregado"          # Warehouse has finished packing (was "Preparando")
    INVOICING = "Facturacion"
    READY = "Relacion de envio"    # Ready for carrier pickup (was "Recibido por almacen")
    SHIPPED = "Enviado al cliente"
    CANCELLED = "Cancelado"
    ON_HOLD = "En Espera"


class OrderStatusManager:
    """
    Manages order status tracking independently of SAP.
    Stores status in a local JSON file and SQL database for persistence.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize the order status manager.

        Args:
            db_path: Path to the JSON database file. Defaults to 'order_status_db.json'
        """
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "order_status_db.json")

        self.db_path = db_path
        self.orders: Dict[str, Dict[str, Any]] = {}

        # Connect to DB via shared DatabaseClient singleton
        from database_client import get_shared_client

        self.db_client = get_shared_client()
        self.sql_engine = None
        try:
            if self.db_client.is_connected():
                self.sql_engine = self.db_client.get_sql_engine()
        except Exception as e:
            print(f"[WARN] OrderStatusManager DB error: {e}")

        self._last_load_time = 0.0
        self._LOAD_THROTTLE_SECONDS = 5.0

        self._ensure_db_table_exists()
        self._load_database()

    def _ensure_db_table_exists(self):
        """Creates the order_status table if it does not exist."""
        if not self.sql_engine:
            return
        try:
            with self.sql_engine.begin() as conn:
                conn.exec_driver_sql("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='order_status' and xtype='U')
                    CREATE TABLE order_status (
                        order_id VARCHAR(50) PRIMARY KEY,
                        status VARCHAR(100),
                        last_updated VARCHAR(50),
                        data NVARCHAR(MAX)
                    )
                """)
        except Exception as e:
            print(f"⚠️ Could not ensure order_status table exists: {e}")

    def _load_database(self):
        """Load the order status database from SQL or disk."""
        loaded_from_sql = False
        if self.sql_engine:
            try:
                import pandas as pd

                df = pd.read_sql("SELECT * FROM order_status", con=self.sql_engine)
                new_orders = {}
                for _, row in df.iterrows():
                    o_id = str(row["order_id"])
                    try:
                        new_orders[o_id] = json.loads(row["data"])
                    except Exception:
                        pass
                self.orders = new_orders
                loaded_from_sql = True
            except Exception as e:
                print(f"⚠️ Error loading order_status from SQL: {e}")

        if not loaded_from_sql:
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.orders = data.get("orders", {})
                except (json.JSONDecodeError, IOError) as e:
                    print(f"⚠️ Error loading order status database: {e}")
                    self.orders = {}
            else:
                self.orders = {}

        self._normalize_status_labels()
        import time
        self._last_load_time = time.time()

    def _normalize_order_labels(self, order: Dict[str, Any]) -> bool:
        """Normalize legacy status labels for a single order in place."""
        changed = False
        status = order.get("status")
        if status in STATUS_LABEL_MIGRATIONS:
            order["status"] = STATUS_LABEL_MIGRATIONS[status]
            changed = True

        history = order.get("status_history", [])
        for entry in history:
            entry_status = entry.get("status")
            if entry_status in STATUS_LABEL_MIGRATIONS:
                entry["status"] = STATUS_LABEL_MIGRATIONS[entry_status]
                changed = True

            prev_status = entry.get("previous_status")
            if prev_status in STATUS_LABEL_MIGRATIONS:
                entry["previous_status"] = STATUS_LABEL_MIGRATIONS[prev_status]
                changed = True
        return changed

    def _normalize_status_labels(self) -> bool:
        """Normalize legacy status labels to the current naming in memory."""
        changed = False
        for order in self.orders.values():
            if self._normalize_order_labels(order):
                changed = True

        return changed

    def reload_if_needed(self, force=False):
        """Reload the database if throttled time elapsed or forced."""
        import time
        now = time.time()
        if force or (now - getattr(self, "_last_load_time", 0.0)) > getattr(self, "_LOAD_THROTTLE_SECONDS", 5.0):
            self._load_database()

    # SQL MERGE template — used by both _save_database() and _save_order().
    # MERGE avoids TRUNCATE so concurrent writers never erase each other's data.
    _MERGE_SQL_TMPL = """
        MERGE {table} AS target
        USING (VALUES (?, ?, ?, ?)) AS source
            (order_id, status, last_updated, data)
        ON target.order_id = source.order_id
        WHEN MATCHED THEN UPDATE SET
            status       = source.status,
            last_updated = source.last_updated,
            data         = source.data
        WHEN NOT MATCHED THEN INSERT
            (order_id, status, last_updated, data)
            VALUES (source.order_id, source.status,
                    source.last_updated, source.data);
    """

    def _save_database(self):
        """Persist all in-memory orders to SQL (MERGE) and JSON.

        SQL uses MERGE so concurrent writers never truncate each other's rows.
        JSON is written as a plain file (no debounce needed here).
        """
        last_updated = datetime.datetime.now().isoformat()

        # Persist to SQL via MERGE (no TRUNCATE — safe for concurrent writers)
        if self.sql_engine:
            try:
                records = [
                    (
                        str(o_id),
                        o_data.get("status", ""),
                        o_data.get("last_updated", last_updated),
                        json.dumps(o_data, ensure_ascii=False),
                    )
                    for o_id, o_data in self.orders.items()
                ]
                if records:
                    merge_sql = self._MERGE_SQL_TMPL.format(table="order_status")
                    with self.sql_engine.connect() as conn:
                        raw_conn = conn.connection
                        cursor = raw_conn.cursor()
                        for record in records:
                            cursor.execute(merge_sql, record)
                        raw_conn.commit()
                        cursor.close()
            except Exception as e:
                import traceback
                print(f"⚠️ Error saving order_status to SQL: {e}")
                traceback.print_exc()

        # Fallback / sync to JSON
        try:
            data = {"orders": self.orders, "last_updated": last_updated}
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"⚠️ Error saving order_status to JSON: {e}")
            return False

    def _save_order(self, order_id: str) -> bool:
        """Persist a single order to SQL via MERGE without rewriting the whole table.

        This is the preferred method for hot-path writes (status updates) because
        it targets exactly one row and is safe against concurrent writers.
        Falls back to a full _save_database() if SQL is unavailable.
        """
        order_id = str(order_id)
        if order_id not in self.orders:
            return False

        o_data = self.orders[order_id]

        if not self.sql_engine:
            # No SQL connection — fall through to a full save
            return self._save_database()

        try:
            record = (
                order_id,
                o_data.get("status", ""),
                o_data.get("last_updated", ""),
                json.dumps(o_data, ensure_ascii=False),
            )
            merge_sql = self._MERGE_SQL_TMPL.format(table="order_status")
            with self.sql_engine.connect() as conn:
                raw_conn = conn.connection
                cursor = raw_conn.cursor()
                cursor.execute(merge_sql, record)
                raw_conn.commit()
                cursor.close()
            return True
        except Exception as e:
            print(f"⚠️ _save_order({order_id}) failed: {e}")
            # Fallback: full save so at least JSON stays consistent
            return self._save_database()

    def import_from_sap(
        self, sap_order: Dict[str, Any], imported_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Import an order from SAP data without modifying SAP.

        Args:
            sap_order: Order data from SAP connector
            imported_by: Username who imported the order

        Returns:
            The created/updated order record
        """
        order_id = str(sap_order.get("DocNum", sap_order.get("order_id", "")))

        if not order_id:
            raise ValueError("Order must have a DocNum or order_id")

        # If order already exists, just update SAP data but keep status
        existing_status = None
        existing_history = []
        existing_imported_at = datetime.datetime.now().isoformat()
        existing_last_updated = datetime.datetime.now().isoformat()

        if order_id in self.orders:
            existing_status = self.orders[order_id].get("status")
            existing_history = self.orders[order_id].get("status_history", [])
            existing_imported_at = self.orders[order_id].get(
                "imported_at", existing_imported_at
            )
            existing_last_updated = self.orders[order_id].get(
                "last_updated", existing_last_updated
            )

        # Create order record
        order_record = {
            "order_id": order_id,
            "customer_code": sap_order.get("CardCode", ""),
            "customer_name": sap_order.get("CardName", ""),
            "order_date": sap_order.get("DocDate", ""),
            "delivery_date": sap_order.get("DocDueDate", ""),
            "total": sap_order.get("DocTotal", 0),
            "currency": sap_order.get("DocCurrency", "MXN"),
            "comments": sap_order.get("Comments", ""),
            "items": sap_order.get("items", []),
            "sap_status": sap_order.get("sap_status", "Abierto"),
            "status": existing_status or OrderStatus.PENDING.value,
            "status_history": existing_history,
            "imported_at": existing_imported_at,
            "last_updated": existing_last_updated,
            "updated_by": (
                imported_by
                if not existing_status
                else self.orders.get(order_id, {}).get("updated_by", "system")
            ),
            "created_by": (
                imported_by
                if not existing_status
                else self.orders.get(order_id, {}).get("created_by", "system")
            ),
        }

        # Add initial status to history if new order
        if not existing_status:
            order_record["status_history"].append(
                {
                    "status": OrderStatus.PENDING.value,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "user": imported_by,
                    "notes": "Importado desde SAP",
                }
            )

        self.orders[order_id] = order_record
        self._save_database()

        return order_record

    def bulk_import_from_sap(self, sap_orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Import multiple orders from SAP at once.

        Args:
            sap_orders: List of order dictionaries from SAP

        Returns:
            Dictionary with import statistics
        """
        stats = {
            "total": len(sap_orders),
            "imported": 0,
            "updated": 0,
            "errors": 0,
            "error_details": [],
        }

        for sap_order in sap_orders:
            try:
                # Check if order already exists
                order_id = str(sap_order.get("header", {}).get("order_number", ""))
                if not order_id:
                    continue

                was_existing = order_id in self.orders

                # Convert to the format expected by import_from_sap
                order_data = {
                    "DocNum": sap_order["header"]["order_number"],
                    "CardCode": sap_order["header"].get("customer_code", ""),
                    "CardName": sap_order["header"].get("customer_name", ""),
                    "DocDate": sap_order["header"].get("order_date", ""),
                    "DocDueDate": sap_order["header"].get("delivery_date", ""),
                    "DocTotal": sap_order["header"].get("total_value", 0),
                    "DocCurrency": sap_order["header"].get("currency", "MXN"),
                    "sap_status": sap_order["header"].get("sap_status", "Abierto"),
                    "items": sap_order.get("items", []),
                    "updated_by": "system_sync",
                }

                self.import_from_sap(order_data)

                if was_existing:
                    stats["updated"] += 1
                else:
                    stats["imported"] += 1

            except Exception as e:
                stats["errors"] += 1
                stats["error_details"].append(
                    {
                        "order": str(
                            sap_order.get("header", {}).get("order_number", "unknown")
                        ),
                        "error": str(e),
                    }
                )

        return stats

    def update_status(
        self, order_id: str, new_status: str, user: str, notes: str = ""
    ) -> bool:
        """
        Update the status of an order.

        Args:
            order_id: The order ID
            new_status: New status value (from OrderStatus enum)
            user: Username making the change
            notes: Optional notes about the status change

        Returns:
            True if successful, False otherwise
        """
        order_id = str(order_id)

        if order_id not in self.orders:
            # Fallback to load/fetch if not in-memory
            if not self.get_order(order_id):
                print(f"⚠️ Order {order_id} not found")
                return False

        old_status = self.orders[order_id]["status"]
        now_iso = datetime.datetime.now().isoformat()

        # Update status
        self.orders[order_id]["status"] = new_status
        self.orders[order_id]["last_updated"] = now_iso
        self.orders[order_id]["updated_by"] = user

        # Add to history
        self.orders[order_id]["status_history"].append(
            {
                "status": new_status,
                "previous_status": old_status,
                "timestamp": now_iso,
                "user": user,
                "notes": notes,
            }
        )

        # Use targeted single-row MERGE instead of full table rewrite
        return self._save_order(order_id)

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get a single order by ID."""
        self.reload_if_needed()
        order_id = str(order_id)
        if order_id in self.orders:
            return self.orders[order_id]

        if self.sql_engine:
            try:
                with self.sql_engine.connect() as conn:
                    raw_conn = conn.connection
                    cursor = raw_conn.cursor()
                    cursor.execute("SELECT data FROM order_status WHERE order_id = ?", (order_id,))
                    row = cursor.fetchone()
                    cursor.close()
                    if row:
                        order_data = json.loads(row[0])
                        self._normalize_order_labels(order_data)
                        self.orders[order_id] = order_data
                        return order_data
            except Exception as e:
                print(f"⚠️ Error loading order {order_id} from SQL fallback: {e}")
        return None

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Get all orders sorted by last updated."""
        self.reload_if_needed()
        orders_list = list(self.orders.values())
        orders_list.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
        return orders_list

    def get_orders_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get orders filtered by status."""
        self.reload_if_needed()
        return [o for o in self.orders.values() if o.get("status") == status]

    def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get orders that are not shipped or cancelled."""
        self.reload_if_needed()
        inactive_statuses = [
            OrderStatus.SHIPPED.value,
            OrderStatus.CANCELLED.value,
        ]
        active = [
            o for o in self.orders.values() if o.get("status") not in inactive_statuses
        ]
        active.sort(key=lambda x: x.get("order_date", ""), reverse=True)
        return active

    def get_order_count_by_status(self) -> Dict[str, int]:
        """Get count of orders grouped by status."""
        self.reload_if_needed()
        counts = {}
        for status in OrderStatus:
            counts[status.value] = len(self.get_orders_by_status(status.value))
        return counts

    def reconcile_statuses(self) -> int:
        """
        Fix orders where sap_status and local status are out of sync.
        E.g. sap_status='Cerrado' but status='Pendiente'.

        Rules (aligned with SAO):
        - Cerrado + factura_number present  → Facturacion
        - Cerrado + no factura_number       → Entregado (waiting for invoice)
        - Cancelado                         → Cancelado

        Returns the number of orders fixed.
        """
        fixed = 0
        now_iso = datetime.datetime.now().isoformat()

        for order_id, order in list(self.orders.items()):
            sap_status = order.get("sap_status", "")
            local_status = order.get("status", "")

            new_status = None
            if sap_status == "Cerrado":
                has_factura = bool(order.get("factura_number"))
                if has_factura:
                    if local_status not in [
                        OrderStatus.INVOICING.value,
                        OrderStatus.READY.value,
                        OrderStatus.SHIPPED.value,
                    ]:
                        new_status = OrderStatus.INVOICING.value
                else:
                    if local_status not in [
                        OrderStatus.PICKING.value,
                        OrderStatus.INVOICING.value,
                        OrderStatus.READY.value,
                        OrderStatus.SHIPPED.value,
                    ]:
                        new_status = OrderStatus.PICKING.value
            elif (
                sap_status == "Cancelado"
                and local_status != OrderStatus.CANCELLED.value
            ):
                new_status = OrderStatus.CANCELLED.value

            if new_status:
                old_status = order["status"]
                order["status"] = new_status
                order["last_updated"] = now_iso
                order["status_history"].append(
                    {
                        "status": new_status,
                        "previous_status": old_status,
                        "timestamp": now_iso,
                        "user": "system",
                        "notes": f"Reconciliación automática: SAP={sap_status}",
                    }
                )
                fixed += 1

        if fixed > 0:
            self._save_database()

        return fixed

    def delete_order(self, order_id: str) -> bool:
        """Delete an order from the local database."""
        order_id = str(order_id)
        if order_id in self.orders:
            del self.orders[order_id]
            # Issue a targeted DELETE instead of a full table rewrite
            if self.sql_engine:
                try:
                    with self.sql_engine.connect() as conn:
                        raw_conn = conn.connection
                        cursor = raw_conn.cursor()
                        cursor.execute(
                            "DELETE FROM order_status WHERE order_id = ?",
                            (order_id,),
                        )
                        raw_conn.commit()
                        cursor.close()
                except Exception as e:
                    print(f"⚠️ delete_order SQL failed for {order_id}: {e}")
            # Flush JSON to stay consistent
            return self._save_database()
        return False

    def get_status_options(self) -> List[str]:
        """Get list of available status options."""
        return [status.value for status in OrderStatus]

    def export_for_web(self) -> Dict[str, Any]:
        """
        Export order data in a format suitable for the web interface.
        Returns a summary suitable for sales team viewing.
        """
        orders = self.get_all_orders()

        # Create a simplified view for web (hide sensitive/internal data)
        web_orders = []
        for order in orders:
            web_orders.append(
                {
                    "order_id": order.get("order_id"),
                    "customer_name": order.get("customer_name"),
                    "order_date": order.get("order_date"),
                    "delivery_date": order.get("delivery_date"),
                    "status": order.get("status"),
                    "last_updated": order.get("last_updated"),
                    "item_count": len(order.get("items", [])),
                }
            )

        return {
            "orders": web_orders,
            "status_counts": self.get_order_count_by_status(),
            "generated_at": datetime.datetime.now().isoformat(),
        }


# Quick test
if __name__ == "__main__":
    manager = OrderStatusManager()

    # Test import
    test_order = {
        "DocNum": "10168",
        "CardCode": "C001",
        "CardName": "Cliente Prueba",
        "DocDate": "2026-01-22",
        "DocDueDate": "2026-01-25",
        "DocTotal": 5000.00,
        "items": [{"ItemCode": "PROD001", "Description": "Producto 1", "Quantity": 10}],
    }

    result = manager.import_from_sap(test_order)
    print(f"✓ Imported order: {result['order_id']}")

    # Test status update
    manager.update_status(
        "10168", OrderStatus.IN_PROGRESS.value, "admin", "Iniciando preparación"
    )
    print("✓ Updated status")

    # Test get
    order = manager.get_order("10168")
    print(f"✓ Order status: {order['status']}")
    print(f"✓ History: {len(order['status_history'])} entries")
