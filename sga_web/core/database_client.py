#!/usr/bin/env python3
"""
Database Client Connection Manager for SGA System
Automatically discovers and connects to the database server.
Falls back to local database if server unavailable.

Usage:
    # Auto-connect on startup
    from database_client import DatabaseClient

    db_client = DatabaseClient()
    if db_client.connect():
        db_path = db_client.get_database_path()
        # Use db_path for loading data

Features:
    - Auto-discovery of database server
    - Automatic fallback to local database
    - Connection retry with exponential backoff
    - Local caching for performance
    - Background sync when server available
"""

import os
import sys
import json
import time
import socket
import logging
import shutil
import subprocess
from typing import Optional, Dict
from datetime import datetime

try:
    from sqlalchemy import create_engine
    from sqlalchemy.engine import Engine

    SQL_AVAILABLE = True
except ImportError:
    SQL_AVAILABLE = False
    from typing import Any

    Engine = Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DatabaseClient:
    """
    Manages database connection for client installations.
    Handles server discovery, connection, and fallback to local DB.
    """

    def __init__(self, config_file: str = None):
        """
        Initialize database client

        Args:
            config_file: Path to client configuration file
        """
        if config_file is None:
            base = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            # Search config/ subdirectory first, then project root
            candidates = [
                os.path.join(base, "config", "db_client_config.json"),
                os.path.join(base, "db_client_config.json"),
            ]
            config_file = next(
                (c for c in candidates if os.path.exists(c)), candidates[0]
            )
        self.base_dir = BASE_DIR
        self.config_file = (
            config_file
            if os.path.isabs(config_file)
            else os.path.join(self.base_dir, config_file)
        )
        self.config = {}
        self.connected = False
        self.database_path = None
        self.connection_mode = None  # 'server' or 'local'
        self.last_sync = None
        self.sql_engine = None

        self._load_config()

    def _load_config(self):
        """Load client configuration"""
        if not os.path.exists(self.config_file):
            logger.warning(f"Client config not found: {self.config_file}")
            logger.info("Using local database mode")
            self._use_local_mode()
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            logger.info("Loaded client configuration")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self._use_local_mode()

    def _use_local_mode(self):
        """Configure for local database mode"""
        self.config = {
            "deployment_type": "local",
            "database": {"primary_path": os.path.join(self.base_dir, "unified_db")},
            "fallback": {"enabled": True, "local_database_path": "unified_db"},
        }

    def connect(self) -> bool:
        """
        Connect to database (server or local fallback)

        Returns:
            True if connection successful
        """
        logger.info("=" * 60)
        logger.info("🔗 Iniciando conexión a base de datos...")

        db_config = self.config.get("database", {})

        # Try SQL Connection first if configured
        if db_config.get("engine") == "sql" and SQL_AVAILABLE:
            from config import get_sql_connection_string

            try:
                # We dynamically construct the connection string securely from environment variables
                import pyodbc

                driver = "{ODBC Driver 17 for SQL Server}"
                if "ODBC Driver 17 for SQL Server" not in pyodbc.drivers():
                    if "ODBC Driver 18 for SQL Server" in pyodbc.drivers():
                        driver = "{ODBC Driver 18 for SQL Server}"
                    else:
                        driver = "{SQL Server}"

                sql_conn_str = f"mssql+pyodbc:///?odbc_connect={__import__('urllib').parse.quote_plus(get_sql_connection_string(driver))}"

                logger.info("📡 Intentando conexión a SQL Server...")
                self.sql_engine = create_engine(
                    sql_conn_str,
                    fast_executemany=False,
                    use_setinputsizes=False,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                )
                # Verify connection
                with self.sql_engine.connect() as conn:
                    pass
                self.connected = True
                self.connection_mode = "sql"
                logger.info("✅ Conectado exitosamente a SQL Server")

                # If we don't need CSV fallback, we can return early.
                # But it's good to resolve database_path anyway for backward compatibility.
                fallback_path = db_config.get(
                    "primary_path", os.path.join(self.base_dir, "unified_db")
                )
                if os.path.exists(fallback_path):
                    self.database_path = fallback_path
                return True
            except Exception as e:
                logger.error(f"❌ Error conectando a SQL Server: {e}")
                self.sql_engine = None
                if not db_config.get("fallback_to_csv", True):
                    return False
                logger.info("⚠️ Pasando a modo fallback CSV...")
        # Try server connection first (if configured)
        if self.config.get("deployment_type") == "client":
            if self._connect_to_server():
                logger.info("✅ Conectado al servidor de base de datos")
                return True

            # Server connection failed, try fallback
            if self.config.get("fallback", {}).get("enabled", True):
                logger.warning("⚠️  Servidor no disponible, usando base de datos local")
                if self._connect_to_local():
                    logger.info("✅ Usando base de datos local")
                    return True

            logger.error("❌ No se pudo conectar a la base de datos")
            return False
        else:
            # Local mode
            if self._connect_to_local():
                logger.info("✅ Usando base de datos local")
                return True

            logger.error("❌ Base de datos local no encontrada")
            return False

    def _connect_to_server(self) -> bool:
        """
        Attempt to connect to database server

        Returns:
            True if successful
        """
        server_config = self.config.get("server", {})
        self.config.get("database", {})
        retry_config = self.config.get("retry", {})

        hostname = server_config.get("hostname")
        ip_address = server_config.get("ip_address")
        share_name = server_config.get("share_name")

        if not all([hostname, ip_address, share_name]):
            logger.error("Configuración de servidor incompleta")
            return False

        # Try multiple connection methods
        max_attempts = retry_config.get("max_attempts", 3)
        delay = retry_config.get("delay_seconds", 5)

        for attempt in range(1, max_attempts + 1):
            logger.info(
                f"Intento {attempt}/{max_attempts} de conexión al servidor {hostname}..."
            )

            # Check server reachability
            if not self._ping_server(ip_address):
                logger.warning(f"  Servidor {ip_address} no responde")
                if attempt < max_attempts:
                    time.sleep(delay)
                    if retry_config.get("exponential_backoff"):
                        delay *= 2
                continue

            # Try to mount/access the share
            if sys.platform == "win32":
                db_path = self._try_windows_share(hostname, ip_address, share_name)
            else:
                db_path = self._try_linux_mount(ip_address, share_name)

            if db_path and os.path.exists(db_path):
                self.database_path = db_path
                self.connected = True
                self.connection_mode = "server"
                self.last_sync = datetime.now()

                # Verify database integrity
                if self._verify_database(db_path):
                    self._sync_local_fallback_to_server(db_path)
                    logger.info(f"  ✅ Base de datos accesible en: {db_path}")
                    return True
                else:
                    logger.warning("  ⚠️  Base de datos incompleta en servidor")

            if attempt < max_attempts:
                time.sleep(delay)
                if retry_config.get("exponential_backoff"):
                    delay *= 2

        return False

    def _sync_local_fallback_to_server(self, server_path: str):
        """
        Push pending local fallback updates to the server share after reconnect.

        The sync is marker-based to avoid overwriting server files when no
        offline edits were made.
        """
        fallback_cfg = self.config.get("fallback", {})
        if not fallback_cfg.get("sync_on_reconnect", False):
            return

        local_rel_path = fallback_cfg.get("local_database_path", "unified_db")
        local_path = os.path.join(self.base_dir, local_rel_path)
        marker_path = os.path.join(local_path, ".pending_sync.json")

        if not os.path.exists(marker_path):
            return

        try:
            with open(marker_path, "r", encoding="utf-8") as f:
                marker = json.load(f)
        except Exception as e:
            logger.warning(f"No se pudo leer marcador de sincronizacion local: {e}")
            return

        changed_files = marker.get("changed_files", [])
        if not changed_files:
            logger.info(
                "Marcador de sincronizacion encontrado, pero sin archivos pendientes."
            )
            try:
                os.remove(marker_path)
            except Exception:
                pass
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        synced = 0
        attempted = 0

        for rel_name in changed_files:
            local_file = os.path.join(local_path, rel_name)
            server_file = os.path.join(server_path, rel_name)

            if not os.path.exists(local_file):
                continue

            if os.path.abspath(local_file) == os.path.abspath(server_file):
                continue

            attempted += 1

            # Keep server rollback path before overwriting with fallback edits.
            if os.path.exists(server_file):
                backup_file = f"{server_file}.pre_sync_{timestamp}.bak"
                try:
                    shutil.copy2(server_file, backup_file)
                except Exception as e:
                    logger.warning(f"No se pudo crear backup de {rel_name}: {e}")

            try:
                shutil.copy2(local_file, server_file)
                synced += 1
            except Exception as e:
                logger.error(f"Error sincronizando {rel_name} a servidor: {e}")

        if synced > 0:
            logger.info(
                f"✅ Sincronizacion de fallback completada: {synced} archivo(s) enviados al servidor."
            )

        # Remove marker only when all pending files were successfully synced.
        if attempted == 0 or synced == attempted:
            try:
                os.remove(marker_path)
            except Exception as e:
                logger.warning(f"No se pudo limpiar marcador de sincronizacion: {e}")

    def _connect_to_local(self) -> bool:
        """
        Connect to local fallback database

        Returns:
            True if successful
        """
        local_path = self.config.get("fallback", {}).get(
            "local_database_path", "unified_db"
        )
        db_path = os.path.join(self.base_dir, local_path)

        if not os.path.exists(db_path):
            logger.error(f"Base de datos local no encontrada: {db_path}")
            return False

        if self._verify_database(db_path):
            self.database_path = db_path
            self.connected = True
            self.connection_mode = "local"
            logger.info(f"Base de datos local: {db_path}")
            return True

        return False

    def _ping_server(self, ip_address: str, timeout: int = 3) -> bool:
        """
        Check if server is reachable

        Args:
            ip_address: Server IP address
            timeout: Timeout in seconds

        Returns:
            True if server responds
        """
        try:
            # Try socket connection to SMB port (445) or NFS port (2049)
            ports = [445, 2049] if sys.platform != "win32" else [445]

            for port in ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip_address, port))
                sock.close()

                if result == 0:
                    return True

            return False
        except Exception as e:
            logger.debug(f"Ping error: {e}")
            return False

    def _try_windows_share(
        self, hostname: str, ip_address: str, share_name: str
    ) -> Optional[str]:
        """
        Try to access Windows network share

        Args:
            hostname: Server hostname
            ip_address: Server IP address
            share_name: Share name

        Returns:
            Path if accessible, None otherwise
        """
        # Try both hostname and IP address
        paths_to_try = [
            f"\\\\{ip_address}\\{share_name}",  # Try IP first (more reliable)
            f"\\\\{hostname}\\{share_name}",  # Then try hostname
        ]

        # Optional credentials:
        # - username from config.server.username or env SGA_SHARE_USER
        # - password from config.server.password or env referenced by config.server.password_env
        server_cfg = self.config.get("server", {})
        username = server_cfg.get("username") or os.getenv("SGA_SHARE_USER")
        password = server_cfg.get("password")
        password_env = server_cfg.get("password_env")
        if (not password) and password_env:
            password = os.getenv(password_env)

        # Build credential attempts (non-interactive, no prompt).
        # IMPORTANT: only use `net use` when an explicit password is available;
        # otherwise Windows may prompt interactively and block startup.
        cred_attempts = []
        if username and password is not None:
            cred_attempts.append((username, password))

        for unc_path in paths_to_try:
            # Check if already accessible
            if os.path.exists(unc_path):
                return unc_path

            # Try explicit SMB session establishment (only when password provided)
            if cred_attempts:
                for user, pwd in cred_attempts:
                    try:
                        # Clear stale session for this UNC (ignore failures)
                        subprocess.run(
                            ["net", "use", unc_path, "/delete", "/y"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )

                        cmd = [
                            "net",
                            "use",
                            unc_path,
                            "/persistent:no",
                            f"/user:{user}",
                            pwd,
                        ]

                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=15,
                        )

                        # Success if command succeeded and UNC becomes reachable
                        if result.returncode == 0 and os.path.exists(unc_path):
                            return unc_path
                    except Exception as e:
                        logger.debug(f"net use failed for {unc_path}: {e}")

            # Try to access without mapping (Windows handles this automatically)
            try:
                test_path = os.path.join(unc_path, "manifest.json")
                if os.path.exists(test_path):
                    return unc_path
            except Exception as e:
                logger.debug(f"Windows share access error for {unc_path}: {e}")

        return None

    def _try_linux_mount(self, ip_address: str, share_name: str) -> Optional[str]:
        """
        Try to mount Linux NFS share

        Args:
            ip_address: Server IP
            share_name: Share name

        Returns:
            Mount path if successful, None otherwise
        """
        mount_point = f"/mnt/{share_name}"

        # Check if already mounted
        if os.path.exists(mount_point) and os.path.ismount(mount_point):
            return mount_point

        # Try to mount (requires sudo)
        try:
            import subprocess

            # Create mount point if doesn't exist
            if not os.path.exists(mount_point):
                subprocess.run(["sudo", "mkdir", "-p", mount_point], check=True)

            # Mount NFS share
            mount_cmd = [
                "sudo",
                "mount",
                "-t",
                "nfs",
                f"{ip_address}:/path/to/unified_db",
                mount_point,
            ]
            result = subprocess.run(mount_cmd, capture_output=True, timeout=10)

            if result.returncode == 0 and os.path.ismount(mount_point):
                return mount_point
        except Exception as e:
            logger.debug(f"Linux mount error: {e}")

        return None

    def _verify_database(self, db_path: str) -> bool:
        """
        Verify database integrity

        Args:
            db_path: Path to database directory

        Returns:
            True if database is valid
        """
        required_files = [
            "products_master.csv",
            "h_statements.csv",
            "p_statements.csv",
            "manifest.json",
        ]

        for file in required_files:
            file_path = os.path.join(db_path, file)
            if not os.path.exists(file_path):
                logger.warning(f"  ⚠️  Archivo faltante: {file}")
                return False

        return True

    def get_database_path(self) -> Optional[str]:
        """
        Get the current database path

        Returns:
            Path to database directory, or None if not connected
        """
        return self.database_path

    def get_connection_mode(self) -> Optional[str]:
        """
        Get the current connection mode

        Returns:
            'server', 'local', or None
        """
        return self.connection_mode

    def is_connected(self) -> bool:
        """Check if connected to database"""
        return self.connected

    def get_connection_status(self) -> Dict:
        """
        Get detailed connection status

        Returns:
            Dictionary with connection information
        """
        return {
            "connected": self.connected,
            "mode": self.connection_mode,
            "database_path": self.database_path,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "config_file": self.config_file,
        }

    def disconnect(self):
        """Disconnect from database"""
        if self.connected:
            logger.info("Desconectando de la base de datos...")
            self.connected = False
            self.database_path = None
            self.connection_mode = None

    def get_sql_engine(self) -> Optional["Engine"]:
        """Returns the SQLAlchemy engine if connected via SQL, else None."""
        return self.sql_engine


def test_connection():
    """Test database connection"""
    print("=" * 70)
    print("🧪 PRUEBA DE CONEXIÓN A BASE DE DATOS")
    print("=" * 70)

    client = DatabaseClient()

    if client.connect():
        client.get_connection_status()
        print("\n✅ Conexión exitosa!")
        db_path = client.get_database_path()
        if db_path:
            files = os.listdir(db_path)
            csv_files = [f for f in files if f.endswith(".csv")]
            print(f"   Archivos CSV: {len(csv_files)}")
            for f in csv_files[:5]:
                print(f"      - {f}")

        client.disconnect()
        return True
    else:
        print("\n❌ No se pudo conectar a la base de datos")
        return False


if __name__ == "__main__":
    # import sys  # already imported at top

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_connection()
    else:
        print("Uso: python database_client.py --test")
