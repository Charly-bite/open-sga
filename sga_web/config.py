"""
SGA Web Application Configuration
"""

import os
import logging
from datetime import timedelta
from dotenv import load_dotenv

# Load .env once so SQL/SAP settings are available for legacy imports.
load_dotenv()

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)


def get_sql_connection_string(driver="{ODBC Driver 17 for SQL Server}"):
    """Compatibility helper used by root managers importing `config` from sga_web path."""
    sql_server = os.getenv("SQL_SERVER", "192.168.2.187")
    sql_database = os.getenv("SQL_DATABASE", "SGA_Database")
    sql_user = os.getenv("SQL_USER", "sga_app_user")
    sql_password = os.getenv("SQL_PASSWORD", "")
    sql_trust = os.getenv("SQL_TRUST_CERTIFICATE", "yes").lower()

    if not sql_password:
        logging.error("CRITICAL: SQL_PASSWORD is empty! Please check your .env file.")
        raise ValueError("Missing SQL_PASSWORD in environment config.")

    conn_str = (
        f"DRIVER={driver};SERVER={sql_server};DATABASE={sql_database};"
        f"UID={sql_user};PWD={sql_password}"
    )
    # The legacy {SQL Server} driver does not support TrustServerCertificate;
    # only add it for modern ODBC Driver 17/18.
    if "ODBC Driver" in driver:
        conn_str += f";TrustServerCertificate={sql_trust}"
    return conn_str


def _generate_secret_key():
    """Generate a persistent secret key if none provided via env."""
    import secrets

    key_file = os.path.join(BASE_DIR, ".flask_secret_key")
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    # Try to load from file (persists across restarts)
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    # Generate new key and persist
    key = secrets.token_hex(32)
    try:
        with open(key_file, "w") as f:
            f.write(key)
    except Exception:
        pass  # If we can't write, at least use the generated key for this session
    return key


def _resolve_db_path_safe():
    """Resolve the database path with a timeout guard.

    When the primary engine is SQL (db_client_config.json → database.engine == 'sql'),
    we skip SMB path resolution entirely and default to the local unified_db directory
    for backward-compatible CSV fallback paths.

    For CSV-over-SMB mode, we wrap os.path.exists() in a thread with a 3-second timeout
    to prevent startup hangs when the SMB share is unreachable.
    """
    import json
    import threading

    # Check if the deployment uses SQL as primary engine → skip SMB completely
    db_client_cfg_path = os.path.join(PARENT_DIR, "db_client_config.json")
    try:
        if os.path.exists(db_client_cfg_path):
            with open(db_client_cfg_path, "r") as f:
                client_cfg = json.load(f)
            if client_cfg.get("database", {}).get("engine") == "sql":
                logging.info(
                    "[CONFIG] SQL engine detected — skipping SMB path resolution"
                )
                return os.path.join(PARENT_DIR, "unified_db"), "local_sql_mode"
    except Exception:
        pass

    # Legacy CSV mode: resolve via db_connector but guard against SMB timeout
    import db_connector

    server_cfg = db_connector.load_server_config(
        os.path.join(BASE_DIR, "server_config.json")
    )

    result = [None, None]

    def _resolve():
        try:
            result[0], result[1] = db_connector.get_db_path(server_cfg)
        except Exception as e:
            logging.warning(f"[CONFIG] db_connector.get_db_path failed: {e}")

    t = threading.Thread(target=_resolve, daemon=True)
    t.start()
    t.join(timeout=3)  # Wait at most 3 seconds

    if result[0] is not None:
        db_path, db_source = result[0], result[1]
        if db_source == "server":
            return db_path, db_source
        else:
            return os.path.join(PARENT_DIR, db_path), db_source

    # Timeout or failure: safe fallback
    logging.warning(
        "[CONFIG] DB path resolution timed out — using local unified_db fallback"
    )
    return os.path.join(PARENT_DIR, "unified_db"), "local_timeout_fallback"


class Config:
    """Base configuration"""

    SECRET_KEY = _generate_secret_key()

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_NAME = "sga_session"  # Prevent collision with SAO on same IP
    SESSION_COOKIE_SECURE = False  # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"  # CSRF mitigation
    WTF_CSRF_TIME_LIMIT = (
        None  # CSRF token lifetime matches session (no separate expiry)
    )

    # Database path — resolved with timeout guard to prevent SMB hangs
    UNIFIED_DB_PATH, DB_SOURCE = _resolve_db_path_safe()

    ORIGINAL_DATA_PATH = os.path.join(PARENT_DIR, "original_data")

    # Assets
    ASSETS_PATH = os.path.join(PARENT_DIR, "assets")
    PICTOGRAMS_PATH = os.path.join(ASSETS_PATH, "pictograms")

    # Generated files
    GENERATED_LABELS_PATH = os.path.join(BASE_DIR, "generated_labels")

    # User database
    USERS_FILE = os.path.join(PARENT_DIR, "users.json")

    # SAP Configuration (optional)
    SAP_HOST = os.environ.get("SAP_HOST", "20.0.1.9")
    SAP_PORT = int(os.environ.get("SAP_PORT", 30015))
    SAP_SCHEMA = os.environ.get("SAP_SCHEMA", "SBO_QUIMICABOSS")

    # Open OMS Webhook
    OPEN_OMS_HOST = os.environ.get("OPEN_OMS_HOST", "")
    OPEN_OMS_API_KEY = os.environ.get("OPEN_OMS_API_KEY", "")

    # Pagination
    ITEMS_PER_PAGE = 25


class DevelopmentConfig(Config):
    """Development configuration"""

    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    """Testing configuration"""

    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False


# Configuration mapping
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
