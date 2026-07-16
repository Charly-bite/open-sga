"""
SAP HANA Connector for GHS Label System (SGA Integration)

Connects to SAP HANA via hdbcli (native Python driver) to retrieve:
- Material Master Data (MARA/MAKT)
- Sales Orders (VBAK/VBAP)
- Customer Information (KNA1)
- Inventory/Stock Data (MARD)

Configuration:
    Host: 20.0.1.9
    Port: 30015
    Driver: hdbcli (SAP HANA Python Client)
"""

from hdbcli import dbapi
import pandas as pd
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SAPHanaConnector:
    """
    Production connector for SAP HANA database.
    Uses hdbcli (native Python driver) for connectivity.
    """

    # Default connection configuration
    DEFAULT_HOST = "20.0.1.9"
    DEFAULT_PORT = 30015
    DEFAULT_SCHEMA = "SBO_QUIMICABOSS"
    DEFAULT_USER = "SYSTEM"
    DEFAULT_PASS = "Qui20Mi25B#"

    # SAP Business One Table mappings
    TABLES = {
        "items": "OITM",  # Item Master Data
        "item_groups": "OITB",  # Item Groups (ASHLAND, BASF, IFF, etc.)
        "sales_orders": "ORDR",  # Sales Order Header
        "sales_order_lines": "RDR1",  # Sales Order Lines
        "customers": "OCRD",  # Business Partners (Customers)
        "warehouses": "OWHS",  # Warehouses
        "item_warehouse": "OITW",  # Item Warehouse Info (Stock)
        "item_batch_stock": "OIBT",  # Item Batch Stock per Warehouse (live quantities)
        "invoices": "OINV",  # A/R Invoices
        "invoice_lines": "INV1",  # Invoice Lines
        "delivery_notes": "ODLN",  # Delivery Notes
        "delivery_lines": "DLN1",  # Delivery Lines
        "batches": "OBTN",  # Batch Number Master Data
    }

    # SAP GHS Pictogram Code → Local PNG filename mapping (from D-02 data quality note)
    PICTOGRAM_CODE_MAP = {
        "G": "flame",  # GHS02 - Flame
        "H": "health_hazard",  # GHS08 - Health Hazard
        "I": "environment",  # GHS09 - Environmental Hazard
        "E": "corrosion",  # GHS05 - Corrosion
        "g": "exclamation",  # GHS07 - Exclamation Mark
        "h": "skull_crossbones",  # GHS06 - Skull & Crossbones
        "A": "exploding_bomb",  # GHS01 - Exploding Bomb
        "B": "flame_over_circle",  # GHS03 - Flame Over Circle
        "C": "gas_cylinder",  # GHS04 - Gas Cylinder
        "1": None,  # Not applicable / No pictogram
        "N": None,  # No Aplicable
    }

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        schema: str = None,
    ):
        """
        Initialize SAP HANA connector.

        Args:
            host: SAP HANA server hostname/IP (default: '20.0.1.9')
            port: SAP HANA port (default: 30015)
            username: SAP HANA username
            password: SAP HANA password
            schema: SAP schema name (e.g., 'SAPABAP1', 'SAPHANADB')
        """
        self.host = host or self.DEFAULT_HOST
        self.port = port or self.DEFAULT_PORT
        self.username = username or self.DEFAULT_USER
        self.password = password or self.DEFAULT_PASS
        self.schema = schema or self.DEFAULT_SCHEMA
        self._local = threading.local()
        self._local.connection = None
        self._local.connected = False

    def connect(self, username: str = None, password: str = None) -> bool:
        """
        Establish connection to SAP HANA.

        Args:
            username: Override username
            password: Override password

        Returns:
            bool: True if connection successful
        """
        user = username or self.username
        pwd = password or self.password

        if not user or not pwd:
            raise ValueError(
                "Username and password are required for SAP HANA connection"
            )

        try:
            logger.info(f"Connecting to SAP HANA at {self.host}:{self.port}...")
            self._local.connection = dbapi.connect(
                address=self.host,
                port=self.port,
                user=user,
                password=pwd,
                timeout=10,
                connectTimeout=10000,
            )
            self._local.connected = True
            logger.info("[OK] SAP HANA connection established successfully")

            # Auto-detect schema if not provided
            if not self.schema:
                self._detect_schema()

            return True

        except dbapi.Error as e:
            logger.error(f"[ERROR] SAP HANA connection failed: {e}")
            self._local.connected = False
            self._local.connection = None
            raise

        except Exception as e:
            logger.error(
                f"[ERROR] Fatal error establishing SAP connection: {str(e)}",
                exc_info=True,
            )
            self._local.connection = None
            self._local.connected = False
            return False

    def _detect_schema(self):
        """Auto-detect the SAP Business One schema containing item master tables."""
        try:
            cursor = getattr(self._local, "connection", None).cursor()
            # Query to find schemas containing OITM table (SAP B1 Items)
            query = """
                SELECT SCHEMA_NAME 
                FROM SYS.TABLES 
                WHERE TABLE_NAME = 'OITM'
                LIMIT 1
            """
            cursor.execute(query)
            row = cursor.fetchone()
            if row:
                self.schema = row[0]
                logger.info(f"[SCHEMA] Auto-detected schema: {self.schema}")
            cursor.close()
        except Exception as e:
            logger.warning(f"Could not auto-detect schema: {e}")

    @property
    def connected(self) -> bool:
        """Check if the current thread is connected to SAP HANA."""
        # Active check using the driver's isconnected() method to handle dropped connections
        conn = getattr(self._local, "connection", None)
        if conn and hasattr(conn, "isconnected") and not conn.isconnected():
            self._local.connected = False

        try:
            return self._local.connected
        except AttributeError:
            return False

    @property
    def connection(self):
        """Get the current thread's SAP HANA connection."""
        return getattr(self._local, "connection", None)

    def disconnect(self):
        """Close the database connection."""
        if getattr(self._local, "connection", None):
            getattr(self._local, "connection", None).close()
            self._local.connected = False
            logger.info("SAP HANA connection closed")

    def _get_table_name(self, table_key: str) -> str:
        """Get fully qualified table name with schema."""
        table = self.TABLES.get(table_key, table_key)
        if self.schema:
            return f'"{self.schema}"."{table}"'
        return f'"{table}"'

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection and return system info.

        Returns:
            dict: Connection status and SAP system information
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        try:
            cursor = getattr(self._local, "connection", None).cursor()

            # Get HANA version
            cursor.execute("SELECT VERSION FROM SYS.M_DATABASE")
            version = cursor.fetchone()[0]

            # Get current timestamp
            cursor.execute("SELECT CURRENT_TIMESTAMP FROM DUMMY")
            server_time = cursor.fetchone()[0]

            # Count materials (if accessible)
            material_count = 0
            try:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self._get_table_name('materials')}"  # nosec B608
                )
                material_count = cursor.fetchone()[0]
            except Exception:
                pass

            cursor.close()

            return {
                "status": "connected",
                "host": self.host,
                "schema": self.schema,
                "hana_version": version,
                "server_time": str(server_time),
                "material_count": material_count,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # MATERIAL MASTER QUERIES
    # =========================================================================

    def get_materials(self, language: str = "S", limit: int = 1000) -> pd.DataFrame:
        """
        Retrieve material master data with descriptions.

        Args:
            language: Language key ('S' = Spanish, 'E' = English)
            limit: Maximum rows to return

        Returns:
            DataFrame with material data
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        query = f"""\
            SELECT 
                m.MATNR as material_number,
                m.MTART as material_type,
                m.MATKL as material_group,
                m.MEINS as base_unit,
                m.BRGEW as gross_weight,
                m.NTGEW as net_weight,
                m.GEWEI as weight_unit,
                t.MAKTX as description,
                t.SPRAS as language
            FROM {self._get_table_name('materials')} m
            LEFT JOIN {self._get_table_name('material_texts')} t 
                ON m.MATNR = t.MATNR AND t.SPRAS = ?
            WHERE m.MATNR IS NOT NULL
            LIMIT {limit}
        """

        return pd.read_sql(
            query, getattr(self._local, "connection", None), params=[language]
        )

    def get_material_by_code(
        self, material_number: str, language: str = "S"
    ) -> Optional[Dict]:
        """
        Get single material by material number.

        Args:
            material_number: SAP Material Number (MATNR)
            language: Language key

        Returns:
            Material data dictionary or None
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        query = f"""\
            SELECT 
                m.MATNR as material_number,
                m.MTART as material_type,
                m.MATKL as material_group,
                m.MEINS as base_unit,
                m.BRGEW as gross_weight,
                m.NTGEW as net_weight,
                t.MAKTX as description
            FROM {self._get_table_name('materials')} m
            LEFT JOIN {self._get_table_name('material_texts')} t 
                ON m.MATNR = t.MATNR AND t.SPRAS = ?
            WHERE m.MATNR = ?
        """

        cursor = getattr(self._local, "connection", None).cursor()
        cursor.execute(query, [language, material_number])
        row = cursor.fetchone()
        cursor.close()

        if row:
            columns = [
                "material_number",
                "material_type",
                "material_group",
                "base_unit",
                "gross_weight",
                "net_weight",
                "description",
            ]
            return dict(zip(columns, row))
        return None

    def search_materials(
        self, search_term: str, language: str = "S", limit: int = 50
    ) -> pd.DataFrame:
        """
        Search materials by description or number.

        Args:
            search_term: Text to search for
            language: Language key
            limit: Maximum results

        Returns:
            DataFrame with matching materials
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        query = f"""\
            SELECT 
                m.MATNR as material_number,
                t.MAKTX as description,
                m.MTART as material_type,
                m.MEINS as base_unit
            FROM {self._get_table_name('materials')} m
            LEFT JOIN {self._get_table_name('material_texts')} t 
                ON m.MATNR = t.MATNR AND t.SPRAS = ?
            WHERE UPPER(m.MATNR) LIKE UPPER(?)
               OR UPPER(t.MAKTX) LIKE UPPER(?)
            LIMIT {limit}
        """

        search_pattern = f"%{search_term}%"
        return pd.read_sql(
            query,
            getattr(self._local, "connection", None),
            params=[language, search_pattern, search_pattern],
        )

    # =========================================================================
    # SALES ORDER QUERIES (SAP Business One)
    # =========================================================================

    def get_sales_orders(self, days_back: int = 30, limit: int = 500) -> pd.DataFrame:
        """
        Retrieve recent sales orders from SAP Business One.

        Args:
            days_back: Number of days to look back
            limit: Maximum rows

        Returns:
            DataFrame with sales order headers
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        query = f"""\
            SELECT 
                "DocNum" as order_number,
                "CardCode" as customer_code,
                "CardName" as customer_name,
                "DocDate" as order_date,
                "DocDueDate" as delivery_date,
                "DocTotal" as total_value,
                "DocCur" as currency,
                "DocEntry" as doc_entry
            FROM {self._get_table_name('sales_orders')}
            WHERE "DocDate" >= ADD_DAYS(CURRENT_DATE, -{days_back})
              AND "SlpCode" IN ('12', '23', '6', '13', '14', '11', '15', '5', '8', '17', '3', '19', '7', '4', '10', '-1')
            ORDER BY "DocDate" DESC
            LIMIT {limit}
        """

        return pd.read_sql(query, getattr(self._local, "connection", None))

    # End of file (Watchdog trigger)

    def get_recent_orders(self, limit: int = 10, only_open: bool = False) -> List[Dict]:
        """
        Get recent sales orders from SAP Business One.

        Args:
            limit: Maximum number of orders to fetch (default: 10)
            only_open: If True, only fetch open orders (default: False)

        Returns:
            List of dictionaries with order headers and items
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        # Query for recent orders
        slp_codes = "('12', '23', '6', '13', '14', '11', '15', '5', '8', '17', '3', '19', '7', '4', '10', '-1')"
        where_clause = f'WHERE T0."SlpCode" IN {slp_codes}'

        if only_open:
            where_clause += ' AND T0."DocStatus" = \'O\' AND (T0."CANCELED" = \'N\' OR T0."CANCELED" IS NULL)'

        query = f"""\
            SELECT 
                T0."DocNum" AS order_number,
                T0."DocEntry" AS doc_entry
            FROM {self._get_table_name('sales_orders')} T0
            {where_clause}
            ORDER BY T0."DocNum" DESC
            LIMIT {limit}
        """

        cursor = getattr(self._local, "connection", None).cursor()
        cursor.execute(query)
        order_numbers = cursor.fetchall()
        cursor.close()

        # Fetch detailed data for each order
        all_orders = []
        for row in order_numbers:
            order_num = int(row[0])
            order_details = self.get_order_details(order_num)
            if order_details:
                all_orders.append(order_details)

        return all_orders

    def get_all_open_orders(self) -> List[Dict]:
        """
        Get all open sales orders from SAP Business One.
        Kept for backward compatibility.

        Returns:
            List of dictionaries with order headers and items
        """
        return self.get_recent_orders(limit=100, only_open=True)

    def get_order_details(self, order_number: int) -> Optional[Dict]:
        """
        Get complete order details with line items (SAP Business One).

        Args:
            order_number: SAP B1 Sales Order Number (DocNum)

        Returns:
            Dictionary with order header and items
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        # Get header
        header_query = f"""\
            SELECT 
                T0."DocNum" AS order_number,
                T0."CardCode" AS customer_code,
                T0."CardName" AS customer_name,
                T0."DocDate" AS order_date,
                T0."DocTime" AS order_time,
                T0."DocDueDate" AS delivery_date,
                T0."DocTotal" AS total_value,
                T0."DocCur" AS currency,
                T0."DocEntry" AS doc_entry,
                T0."DocStatus" AS doc_status,
                T0."CANCELED" AS canceled,
                T0."Printed" AS printed,
                T3."SlpName" AS creator_name,
                T3."SlpName" AS updater_name
            FROM {self._get_table_name('sales_orders')} T0
            LEFT JOIN {self.schema}."OSLP" T3 ON T0."SlpCode" = T3."SlpCode"
            WHERE T0."DocNum" = ?
        """

        cursor = getattr(self._local, "connection", None).cursor()
        cursor.execute(header_query, [order_number])
        header_row = cursor.fetchone()

        if not header_row:
            cursor.close()
            return None

        # Map SAP status to readable status
        # Columns: 0=DocNum, 1=CardCode, 2=CardName, 3=DocDate, 4=DocTime,
        #          5=DocDueDate, 6=DocTotal, 7=DocCur, 8=DocEntry, 9=DocStatus, 10=CANCELED, 11=Printed
        doc_status = header_row[9] if len(header_row) > 9 else "O"
        canceled = header_row[10] if len(header_row) > 10 else "N"

        # Determine SAP status
        if canceled == "Y":
            sap_status = "Cancelado"
        elif doc_status == "C":
            sap_status = "Cerrado"
        else:
            sap_status = "Abierto"

        # Format date and time
        order_date = str(header_row[3])
        order_time = header_row[4]

        # Convert SAP time format (HHMM integer) to HH:MM:SS
        # Example: 1644 = 16:44, 800 = 08:00
        try:
            if order_time and order_time > 0:
                time_str = str(int(order_time)).zfill(4)  # Pad to 4 digits: 800 -> 0800
                hours = int(time_str[:2])
                minutes = int(time_str[2:4])
                order_datetime = f"{order_date} {hours:02d}:{minutes:02d}:00"
            else:
                order_datetime = f"{order_date}"
        except Exception:
            order_datetime = f"{order_date}"

        # Get Invoice number (Factura) if it exists
        # Invoices can be linked directly to Sales Orders (BaseType=17) or via Delivery Notes (BaseType=15)
        invoice_query = f"""\
            SELECT DISTINCT T0."DocNum"
            FROM {self._get_table_name('invoices')} T0
            INNER JOIN {self._get_table_name('invoice_lines')} T1 ON T0."DocEntry" = T1."DocEntry"
            WHERE (T1."BaseType" = 17 AND T1."BaseEntry" = ?)
               OR (T1."BaseType" = 15 AND T1."BaseEntry" IN (
                   SELECT "DocEntry" FROM {self._get_table_name('delivery_lines')} WHERE "BaseType" = 17 AND "BaseEntry" = ?
               ))
        """
        try:
            cursor.execute(invoice_query, [int(header_row[8]), int(header_row[8])])
            inv_row = cursor.fetchone()
            factura_number = str(int(inv_row[0])) if inv_row else None
        except Exception as e:
            logger.warning(
                f"Could not fetch invoice number for order {order_number}: {e}"
            )
            factura_number = None

        header = {
            "order_number": int(header_row[0]),
            "customer_code": header_row[1],
            "customer_name": header_row[2],
            "order_date": order_datetime,
            "delivery_date": str(header_row[5]),
            "total_value": float(header_row[6]) if header_row[6] else 0,
            "currency": header_row[7],
            "doc_entry": int(header_row[8]),
            "sap_status": sap_status,
            "doc_status": doc_status,
            "canceled": canceled,
            "factura_number": factura_number,
            "creator_name": (
                header_row[12]
                if len(header_row) > 12 and header_row[12]
                else "SAP System"
            ),
            "updater_name": (
                header_row[13]
                if len(header_row) > 13 and header_row[13]
                else "SAP System"
            ),
        }

        # Get line items — includes UDF columns (P1-02: Order Line UDFs)
        items_query = f"""\
            SELECT 
                T1."LineNum"        AS line_number,
                T1."ItemCode"       AS item_code,
                T1."Dscription"     AS description,
                T1."Quantity"       AS quantity,
                T1."unitMsr"        AS unit,
                T1."Price"          AS unit_price,
                T1."LineTotal"      AS line_total,
                T1."WhsCode"        AS warehouse,
                T1."U_Tara"         AS u_tara,
                T1."U_NumEtiqueta"  AS u_num_etiqueta,
                T1."U_Presentacion" AS u_presentacion,
                T1."U_KilosPre"     AS u_kilos_pre
            FROM {self._get_table_name('sales_order_lines')} T1
            WHERE T1."DocEntry" = ?
            ORDER BY T1."LineNum"
        """

        cursor.execute(items_query, [header["doc_entry"]])
        items = []
        for row in cursor.fetchall():

            def _safe_float(v):
                try:
                    return float(v) if v is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0

            items.append(
                {
                    "line_number": int(row[0]),
                    "item_code": row[1],
                    "description": row[2],
                    "quantity": _safe_float(row[3]),
                    "unit": row[4],
                    "unit_price": _safe_float(row[5]),
                    "line_total": _safe_float(row[6]),
                    "warehouse": row[7],
                    # P1-02 UDFs
                    "u_tara": _safe_float(row[8]),
                    "u_num_etiqueta": int(_safe_float(row[9])) if row[9] else 0,
                    "u_presentacion": str(row[10]).strip() if row[10] else "",
                    "u_kilos_pre": _safe_float(row[11]),
                }
            )

        cursor.close()

        return {"header": header, "items": items}

    def get_orders_status_batch(self, order_numbers: List[int]) -> Dict[int, Dict]:
        """
        Fetch the SAP status for multiple orders in a single query.

        Args:
            order_numbers: List of DocNum integers

        Returns:
            Dict mapping DocNum → {sap_status, doc_status, canceled, updater_name, customer_name}
        """
        if not order_numbers:
            return {}

        if not self.connected:
            try:
                self.connect()
            except Exception:
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        results = {}

        # Process in chunks of 500 to avoid SQL IN-clause limits
        chunk_size = 500
        for i in range(0, len(order_numbers), chunk_size):
            chunk = order_numbers[i : i + chunk_size]
            placeholders = ",".join(["?" for _ in chunk])

            query = f"""\
                SELECT 
                    T0."DocNum",
                    T0."DocStatus",
                    T0."CANCELED",
                    T0."CardName",
                    T3."SlpName" AS updater_name
                FROM {self._get_table_name('sales_orders')} T0
                LEFT JOIN {self.schema}."OSLP" T3 ON T0."SlpCode" = T3."SlpCode"
                WHERE T0."DocNum" IN ({placeholders})
            """

            try:
                cursor = getattr(self._local, "connection", None).cursor()
                cursor.execute(query, chunk)

                for row in cursor.fetchall():
                    doc_num = int(row[0])
                    doc_status = row[1] or "O"
                    canceled = row[2] or "N"
                    customer_name = row[3] or ""
                    updater_name = row[4] or "SAP System"

                    if canceled == "Y":
                        sap_status = "Cancelado"
                    elif doc_status == "C":
                        sap_status = "Cerrado"
                    else:
                        sap_status = "Abierto"

                    results[doc_num] = {
                        "sap_status": sap_status,
                        "doc_status": doc_status,
                        "canceled": canceled,
                        "updater_name": updater_name,
                        "customer_name": customer_name,
                    }

                cursor.close()
            except Exception as e:
                logger.error(f"Batch status query failed for chunk {i}: {e}")
                # Try to reconnect for next chunk
                try:
                    self.connect()
                except Exception:
                    pass

        return results

    # =========================================================================
    # BATCH / LOT QUERIES
    # =========================================================================

    def get_batch_dates(
        self, item_code: str, batch_number: str = None
    ) -> Optional[Dict]:
        """
        Get manufacturing date (Fecha de Fabricación) and expiry date (Fecha de Vencimiento)
        from SAP HANA Batch Master Data (OBTN).

        Args:
            item_code: SAP Item Code
            batch_number: Optional specific batch/lot number. If None, returns the most recent batch.

        Returns:
            Dictionary with 'manufacturing_date' and 'expiry_date' (as YYYY-MM-DD strings), or None
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        try:
            if batch_number:
                query = f"""\
                    SELECT
                        "DistNumber" AS batch_number,
                        "MnfDate" AS manufacturing_date,
                        "ExpDate" AS expiry_date
                    FROM {self._get_table_name('batches')}
                    WHERE "ItemCode" = ? AND "DistNumber" = ?
                    LIMIT 1
                """
                cursor = getattr(self._local, "connection", None).cursor()
                cursor.execute(query, [item_code, batch_number])
            else:
                # Get the most recent batch for this item
                query = f"""\
                    SELECT
                        "DistNumber" AS batch_number,
                        "MnfDate" AS manufacturing_date,
                        "ExpDate" AS expiry_date
                    FROM {self._get_table_name('batches')}
                    WHERE "ItemCode" = ?
                    ORDER BY "MnfDate" DESC, "DistNumber" DESC
                    LIMIT 1
                """
                cursor = getattr(self._local, "connection", None).cursor()
                cursor.execute(query, [item_code])

            row = cursor.fetchone()
            cursor.close()

            if row:

                def _format_date(val):
                    """Convert SAP date value to YYYY-MM-DD string."""
                    if val is None:
                        return ""
                    if isinstance(val, datetime):
                        return val.strftime("%Y-%m-%d")
                    # Handle date objects
                    if hasattr(val, "strftime"):
                        return val.strftime("%Y-%m-%d")
                    # Handle string dates
                    s = str(val).strip()
                    if not s or s == "None":
                        return ""
                    # Try ISO format first (YYYY-MM-DD)
                    if len(s) >= 10 and s[4] == "-":
                        return s[:10]
                    # Try DD/MM/YYYY
                    if "/" in s:
                        parts = s.split("/")
                        if len(parts) == 3:
                            return f"{int(parts[2]):04d}-{int(parts[1]):02d}-{int(parts[0]):02d}"
                    return s

                result = {
                    "batch_number": str(row[0]) if row[0] else "",
                    "manufacturing_date": _format_date(row[1]),
                    "expiry_date": _format_date(row[2]),
                }
                logger.info(
                    f"[BATCH] Batch dates for {item_code}: mfg={result['manufacturing_date']}, exp={result['expiry_date']}"
                )
                return result

            return None

        except Exception as e:
            logger.warning(f"Could not fetch batch dates from SAP for {item_code}: {e}")
            return None

    def get_all_latest_batches(self, item_codes: List[str] = None) -> Dict[str, Dict]:
        """
        Bulk-fetch the latest batch (most recent MnfDate) for all batch-managed
        items in a single efficient SQL query.

        Args:
            item_codes: Optional list of item codes to filter.
                        If None, fetches for ALL batch-managed items.

        Returns:
            Dict mapping ItemCode → {batch_number, manufacturing_date, expiry_date}
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        results = {}
        try:
            oitm = self._get_table_name("items")
            obtn = self._get_table_name("batches")

            base_query = f"""\
                SELECT "ItemCode", "DistNumber", "MnfDate", "ExpDate"
                FROM (
                    SELECT
                        B."ItemCode",
                        B."DistNumber",
                        B."MnfDate",
                        B."ExpDate",
                        ROW_NUMBER() OVER (
                            PARTITION BY B."ItemCode"
                            ORDER BY B."MnfDate" DESC, B."DistNumber" DESC
                        ) AS rn
                    FROM {obtn} B
                    INNER JOIN {oitm} I ON B."ItemCode" = I."ItemCode"
                    WHERE I."ManBtchNum" = 'Y'
                      AND (I."validFor" = 'Y' OR I."validFor" IS NULL)
                      AND (I."frozenFor" = 'N' OR I."frozenFor" IS NULL)
                      AND I."ItemCode" NOT LIKE 'AF%'
                      AND I."ItemCode" NOT LIKE 'SE%'
                      
                      AND I."ItemCode" != 'ANTICIPO'
                      {{ITEM_FILTER}}
                ) ranked
                WHERE rn = 1
            """

            def _format_date(val):
                if val is None:
                    return ""
                if isinstance(val, datetime):
                    return val.strftime("%Y-%m-%d")
                if hasattr(val, "strftime"):
                    return val.strftime("%Y-%m-%d")
                s = str(val).strip()
                if not s or s == "None":
                    return ""
                if len(s) >= 10 and s[4] == "-":
                    return s[:10]
                return s

            if item_codes:
                chunk_size = 500
                for i in range(0, len(item_codes), chunk_size):
                    chunk = item_codes[i : i + chunk_size]
                    placeholders = ",".join(["?" for _ in chunk])
                    query = base_query.replace(
                        "{ITEM_FILTER}", f'AND B."ItemCode" IN ({placeholders})'
                    )
                    cursor = getattr(self._local, "connection", None).cursor()
                    cursor.execute(query, chunk)
                    for row in cursor.fetchall():
                        item_code = str(row[0]).strip()
                        results[item_code] = {
                            "batch_number": str(row[1]) if row[1] else "",
                            "manufacturing_date": _format_date(row[2]),
                            "expiry_date": _format_date(row[3]),
                        }
                    cursor.close()
            else:
                query = base_query.replace("{ITEM_FILTER}", "")
                cursor = getattr(self._local, "connection", None).cursor()
                cursor.execute(query)
                for row in cursor.fetchall():
                    item_code = str(row[0]).strip()
                    results[item_code] = {
                        "batch_number": str(row[1]) if row[1] else "",
                        "manufacturing_date": _format_date(row[2]),
                        "expiry_date": _format_date(row[3]),
                    }
                cursor.close()

            logger.info(
                f"[BATCH] Bulk batch sync: fetched latest batch for {len(results)} items"
            )
            return results

        except Exception as e:
            logger.error(f"[ERROR] Error in bulk batch fetch from SAP: {e}")
            return results

    # =========================================================================
    # STOCK / INVENTORY QUERIES
    # =========================================================================

    def get_item_weights(self, item_code: str) -> Dict[str, float]:
        """
        [T-02] Get gross and tare weight for an item from SAP OITM.
        Replaces inline raw SQL in labels.py.

        Args:
            item_code: SAP Item Code

        Returns:
            dict with 'gross_weight' and 'tare_weight' (floats, 0.0 if not found)
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        try:
            query = f"""\
                SELECT "BWeight1" AS gross_weight,
                       "BWeight2" AS tare_weight
                FROM {self._get_table_name('items')}
                WHERE "ItemCode" = ?
            """
            cursor = getattr(self._local, "connection", None).cursor()
            cursor.execute(query, [item_code])
            row = cursor.fetchone()
            cursor.close()
            if row:
                return {
                    "gross_weight": float(row[0]) if row[0] else 0.0,
                    "tare_weight": float(row[1]) if row[1] else 0.0,
                }
        except Exception as e:
            logger.warning(
                f"Could not fetch item weights from SAP for {item_code}: {e}"
            )
        return {"gross_weight": 0.0, "tare_weight": 0.0}

    def get_item_ghs_data(self, item_code: str) -> Optional[Dict]:
        """
        [P1-01] Read GHS UDF fields from SAP OITM for an item.
        Returns signal word, H-statements, P-statements, and pictogram codes
        mapped to local PNG filenames.

        Pictogram code mapping (D-02):
            G → flame, H → health_hazard, I → environment, E → corrosion,
            g → exclamation, h → skull_crossbones, A → exploding_bomb,
            B → flame_over_circle, C → gas_cylinder, 1/N → None

        Args:
            item_code: SAP Item Code (e.g. 'IFF-QB00122')

        Returns:
            dict with keys: signal_word, h_statements (str), p_statements (str),
            pictograms (list[str] of PNG names without extension), or None if not found
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        try:
            query = f"""\
                SELECT
                    "U_Word"        AS signal_word,
                    "U_Peligro"     AS h_statements,
                    "U_Prudencia"   AS p_statements,
                    "U_Pictograma1" AS picto1,
                    "U_Pictograma2" AS picto2,
                    "U_Pictograma3" AS picto3,
                    "U_Pictograma4" AS picto4
                FROM {self._get_table_name('items')}
                WHERE "ItemCode" = ?
            """
            cursor = getattr(self._local, "connection", None).cursor()
            cursor.execute(query, [item_code])
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            signal_word = str(row[0]).strip() if row[0] else ""
            h_statements = str(row[1]).strip() if row[1] else ""
            p_statements = str(row[2]).strip() if row[2] else ""
            raw_pictos = [row[3], row[4], row[5], row[6]]

            # Map SAP single-letter codes → pictogram PNG names
            pictograms = []
            for code in raw_pictos:
                if code:
                    code_str = str(code).strip()
                    mapped = self.PICTOGRAM_CODE_MAP.get(code_str)
                    if mapped and mapped not in pictograms:
                        pictograms.append(mapped)

            # 'No Aplicable' variants → skip label generation hint
            no_ghs = signal_word.upper() in ("NO APLICABLE", "N/A", "NO APLICA", "")

            result = {
                "signal_word": signal_word,
                "h_statements": h_statements,
                "p_statements": p_statements,
                "pictograms": pictograms,
                "no_ghs": no_ghs,
            }
            logger.info(
                f"[GHS] UDF data for {item_code}: signal='{signal_word}', pictos={pictograms}"
            )
            return result

        except Exception as e:
            logger.warning(
                f"Could not fetch GHS UDF data from SAP for {item_code}: {e}"
            )
            return None

    def get_item_batches(self, item_code: str, warehouse: str = None) -> List[Dict]:
        """
        [P1-03] Get live batch stock for an item per warehouse.
        Joins OIBT (live quantities) with OBTN (dates) so operator can pick
        the correct batch instead of guessing.

        Args:
            item_code: SAP Item Code
            warehouse:  Optional warehouse code filter (e.g. '01')

        Returns:
            List of dicts: batch_number, warehouse, quantity,
                           manufacturing_date, expiry_date
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        try:
            oibt = f'"{self.schema}"."OIBT"'
            obtn = f'"{self.schema}"."OBTN"'
            where = 'WHERE T0."ItemCode" = ?'
            params: list = [item_code]
            if warehouse:
                where += ' AND T0."WhsCode" = ?'
                params.append(warehouse)

            query = f"""\
                SELECT
                    T0."ItemCode"    AS item_code,
                    T0."BatchNum"    AS batch_number,
                    T0."WhsCode"     AS warehouse,
                    T0."Quantity"    AS quantity,
                    T1."MnfDate"     AS manufacturing_date,
                    T1."ExpDate"     AS expiry_date
                FROM {oibt} T0
                LEFT JOIN {obtn} T1
                    ON T0."ItemCode" = T1."ItemCode"
                   AND T0."BatchNum" = T1."DistNumber"
                {where}
                  AND T0."Quantity" > 0
                ORDER BY T1."MnfDate" DESC, T1."DistNumber" DESC
            """
            cursor = getattr(self._local, "connection", None).cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()

            def _fmt(val):
                if val is None:
                    return ""
                if hasattr(val, "strftime"):
                    return val.strftime("%Y-%m-%d")
                s = str(val).strip()
                return s[:10] if len(s) >= 10 else s

            batches = []
            for r in rows:
                batches.append(
                    {
                        "item_code": str(r[0]),
                        "batch_number": str(r[1]),
                        "warehouse": str(r[2]),
                        "quantity": float(r[3]) if r[3] else 0.0,
                        "manufacturing_date": _fmt(r[4]),
                        "expiry_date": _fmt(r[5]),
                    }
                )
            logger.info(
                f"[BATCH] Found {len(batches)} batches for {item_code} whs={warehouse or 'ALL'}"
            )
            return batches

        except Exception as e:
            logger.warning(f"Could not fetch batch stock from SAP for {item_code}: {e}")
            return []

    def sync_products_from_sap(
        self, limit: int = 2000, updated_since: str = None
    ) -> Dict:
        """
        [P1-04] Bulk sync product master data from SAP OITM to a DataFrame
        ready for merging with local unified_db/products_master.csv.

        Only READS from SAP — never overwrites local GHS data.  The caller
        (products route) is responsible for the CSV merge.

        Args:
            limit:         Max items to fetch (default 2000).
            updated_since: Optional ISO date string ('YYYY-MM-DD') to fetch
                           only items updated on or after this date (incremental).

        Returns:
            dict with 'data' (list of dicts), 'count' (int), 'timestamp' (str)
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        try:
            oitm = self._get_table_name("items")
            oitb = f'"{self.schema}"."OITB"'

            # Exclude specific non-chemical prefixes from syncing at the source layer
            # Also exclude inactive/frozen items (validFor='N' and frozenFor='Y' concepts)
            base_filters = [
                "T0.\"ItemCode\" NOT LIKE 'AF%'",
                "T0.\"ItemCode\" NOT LIKE 'SE%'",
                "T0.\"ItemCode\" != 'ANTICIPO'",
                'T0."validFor" = \'Y\' OR T0."validFor" IS NULL',
                'T0."frozenFor" = \'N\' OR T0."frozenFor" IS NULL',
            ]

            date_filter = " AND ".join(base_filters)
            date_filter = f"WHERE {date_filter}"

            params: list = []
            if updated_since:
                date_filter += ' AND T0."UpdateDate" >= ?'
                params.append(updated_since)

            query = f"""\
                SELECT
                    T0."ItemCode"       AS item_code,
                    T0."ItemName"       AS item_name,
                    T0."FrgnName"       AS foreign_name,
                    T1."ItmsGrpNam"     AS item_group,
                    T0."SalUnitMsr"     AS sale_unit,
                    T0."BWeight1"       AS gross_weight,
                    T0."BWeight2"       AS tare_weight,
                    T0."SWeight1"       AS ship_weight,
                    T0."ManBtchNum"     AS batch_managed,
                    T0."DfltWH"         AS default_warehouse,
                    T0."UpdateDate"     AS last_sap_update,
                    T0."U_Word"         AS signal_word,
                    T0."U_Pictograma1"  AS picto1,
                    T0."U_Pictograma2"  AS picto2,
                    T0."U_Pictograma3"  AS picto3,
                    T0."U_Pictograma4"  AS picto4
                FROM {oitm} T0
                LEFT JOIN {oitb} T1 ON T0."ItmsGrpCod" = T1."ItmsGrpCod"
                {date_filter}
                ORDER BY T0."ItemCode"
                LIMIT {limit}
            """
            cursor = getattr(self._local, "connection", None).cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()

            cols = [
                "item_code",
                "item_name",
                "foreign_name",
                "item_group",
                "sale_unit",
                "gross_weight",
                "tare_weight",
                "ship_weight",
                "batch_managed",
                "default_warehouse",
                "last_sap_update",
                "signal_word",
                "picto1",
                "picto2",
                "picto3",
                "picto4",
            ]

            data = []
            for r in rows:
                row_dict = dict(zip(cols, r))
                # Normalise date
                upd = row_dict.get("last_sap_update")
                row_dict["last_sap_update"] = (
                    upd.strftime("%Y-%m-%d")
                    if hasattr(upd, "strftime")
                    else str(upd or "")
                )
                data.append(row_dict)

            logger.info(f"[OK] SAP product sync: {len(data)} items fetched")
            return {
                "data": data,
                "count": len(data),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        except Exception as e:
            logger.error(f"[ERROR] Error syncing products from SAP: {e}")
            raise

    # =========================================================================
    # CUSTOM QUERIES FOR GHS/SGA INTEGRATION
    # =========================================================================

    def get_materials_for_ghs_sync(self, material_group: str = None) -> pd.DataFrame:
        """
        Get materials that need GHS label data synchronization.

        Args:
            material_group: Optional filter by material group (MATKL)

        Returns:
            DataFrame with materials for GHS mapping
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        base_query = f"""\
            SELECT 
                m.MATNR as sap_matnr,
                t.MAKTX as chemical_name,
                m.MATKL as material_group,
                m.MEINS as base_unit,
                m.BRGEW as gross_weight,
                m.GEWEI as weight_unit
            FROM {self._get_table_name('materials')} m
            LEFT JOIN {self._get_table_name('material_texts')} t 
                ON m.MATNR = t.MATNR AND t.SPRAS = 'S'
            WHERE m.MATNR IS NOT NULL
        """

        if material_group:
            base_query += f" AND m.MATKL = '{material_group}'"

        base_query += " ORDER BY m.MATNR"

        return pd.read_sql(base_query, getattr(self._local, "connection", None))

    def execute_query(self, query: str, params: list = None) -> pd.DataFrame:
        """
        Execute a custom SQL query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            DataFrame with results
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        return pd.read_sql(
            query, getattr(self._local, "connection", None), params=params or []
        )

    def list_tables(self, schema: str = None) -> pd.DataFrame:
        """
        List all tables in a schema.

        Args:
            schema: Schema name (default: auto-detected schema)

        Returns:
            DataFrame with table names
        """
        if not self.connected:
            try:
                self.connect()
            except Exception:
                # If connection fails, let the caller handle the specific error or raise ConnectionError
                raise ConnectionError(
                    "Not connected to SAP HANA and auto-connection failed"
                )

        target_schema = schema or self.schema

        query = """
            SELECT TABLE_NAME, TABLE_TYPE 
            FROM SYS.TABLES 
            WHERE SCHEMA_NAME = ?
            ORDER BY TABLE_NAME
        """

        return pd.read_sql(
            query, getattr(self._local, "connection", None), params=[target_schema]
        )


# =============================================================================
# MOCK CONNECTOR (for testing without SAP HANA)
# =============================================================================


class SAPHanaMockConnector(SAPHanaConnector):
    """
    Mock connector for development/testing without SAP HANA access.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mock_materials = {
            "IFF-QB00122": {
                "material_number": "IFF-QB00122",
                "material_type": "CHEM",
                "material_group": "QBQ",
                "base_unit": "KG",
                "gross_weight": 1.0,
                "net_weight": 1.0,
                "description": "1181-D MENTA",
            },
            "VAR-QB00005": {
                "material_number": "VAR-QB00005",
                "material_type": "CHEM",
                "material_group": "QBQ",
                "base_unit": "LT",
                "gross_weight": 0.9,
                "net_weight": 0.9,
                "description": "ACEITE DE PINO Y55",
            },
        }

        self._mock_orders = {
            "300050": {
                "header": {
                    "order_number": "300050",
                    "order_date": "2026-01-09",
                    "customer_number": "0001000123",
                    "customer_name": "Cliente Ejemplo S.A.",
                    "net_value": 15000.00,
                    "currency": "MXN",
                },
                "items": [
                    {
                        "item_number": "000010",
                        "material_number": "IFF-QB00122",
                        "description": "1181-D MENTA",
                        "quantity": 12,
                        "unit": "KG",
                        "net_value": 8400.00,
                    },
                    {
                        "item_number": "000020",
                        "material_number": "VAR-QB00005",
                        "description": "ACEITE DE PINO Y55",
                        "quantity": 5,
                        "unit": "LT",
                        "net_value": 6600.00,
                    },
                ],
            }
        }

    def connect(self, username: str = None, password: str = None) -> bool:
        logger.info("🔶 Using MOCK SAP HANA connector (no real database)")
        self._local.connected = True
        self.schema = "MOCK_SCHEMA"
        return True

    def test_connection(self) -> Dict[str, Any]:
        return {
            "status": "connected (mock)",
            "dsn": "MOCK",
            "schema": "MOCK_SCHEMA",
            "hana_version": "2.0.0 (Mock)",
            "server_time": str(datetime.now()),
            "material_count": len(self._mock_materials),
        }

    def get_material_by_code(
        self, material_number: str, language: str = "S"
    ) -> Optional[Dict]:
        return self._mock_materials.get(material_number)

    def get_order_details(self, order_number: str) -> Optional[Dict]:
        return self._mock_orders.get(str(order_number))

    def get_materials_for_ghs_sync(self, material_group: str = None) -> pd.DataFrame:
        data = list(self._mock_materials.values())
        df = pd.DataFrame(data)
        df.rename(columns={"material_number": "sap_matnr"}, inplace=True)
        return df


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def get_sap_connector(use_mock: bool = False, **kwargs) -> SAPHanaConnector:
    """
    Factory function to get appropriate SAP connector.

    Args:
        use_mock: If True, return mock connector for testing
        **kwargs: Connection parameters (dsn, username, password, schema)

    Returns:
        SAPHanaConnector instance
    """
    if use_mock:
        return SAPHanaMockConnector(**kwargs)
    return SAPHanaConnector(**kwargs)


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import getpass

    print("=" * 60)
    print("SAP HANA Connection Test")
    print("=" * 60)

    # Ask for credentials
    use_mock = input("Use mock connector? (y/n): ").strip().lower() == "y"

    if use_mock:
        connector = get_sap_connector(use_mock=True)
        connector.connect()
    else:
        # Use defaults if available
        default_user = getattr(SAPHanaConnector, "DEFAULT_USER", "")
        default_pass = getattr(SAPHanaConnector, "DEFAULT_PASS", "")

        prompt_user = (
            f"SAP Username [{default_user}]: " if default_user else "SAP Username: "
        )
        username = input(prompt_user).strip() or default_user

        password = ""
        if default_pass and username == default_user:
            prompt_pass = "SAP Password [saved default]: "
            password = getpass.getpass(prompt_pass)
            if not password:
                password = default_pass
        else:
            password = getpass.getpass("SAP Password: ")

        connector = get_sap_connector(
            dsn="SAP Hana", username=username, password=password
        )

        try:
            connector.connect()
        except Exception as e:
            print(f"Connection failed: {e}")
            exit(1)

    # Test connection
    info = connector.test_connection()
    print("\n📊 Connection Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")

    # Test material lookup
    print("\n🔍 Testing material lookup...")
    material = connector.get_material_by_code("IFF-QB00122")
    if material:
        print(f"  Found: {material.get('description')}")

    # Test order lookup
    print("\n📦 Testing order lookup...")
    order = connector.get_order_details("300050")
    if order:
        print(f"  Order: {order['header']['order_number']}")
        print(f"  Customer: {order['header']['customer_name']}")
        print(f"  Items: {len(order['items'])}")

    connector.disconnect()
    print("\n✅ Test complete!")
