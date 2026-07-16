import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sga_web', '.env'))

# --- SQL Server Environment Variables ---
SQL_SERVER = os.getenv("SQL_SERVER", "192.168.2.187")
SQL_DATABASE = os.getenv("SQL_DATABASE", "SGA_Database")
SQL_USER = os.getenv("SQL_USER", "sga_app_user")
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "")
# Default to 'yes' for immediate local testing if missing, but we highly encourage 'no' in true production
SQL_TRUST_CERTIFICATE = os.getenv("SQL_TRUST_CERTIFICATE", "yes").lower()


def get_sql_connection_string(driver="{ODBC Driver 17 for SQL Server}"):
    """
    Generates a secure ODBC connection string based on the .env file.
    Validates that a password exists to fail fast gracefully.
    """
    if not SQL_PASSWORD:
        logging.error("CRITICAL: SQL_PASSWORD is empty! Please check your .env file.")
        raise ValueError("Missing SQL_PASSWORD in environment config.")

    conn_str = f"DRIVER={driver};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USER};PWD={SQL_PASSWORD}"
    # The legacy {SQL Server} driver does not support TrustServerCertificate;
    # only add it for modern ODBC Driver 17/18.
    if "ODBC Driver" in driver:
        conn_str += f";TrustServerCertificate={SQL_TRUST_CERTIFICATE}"
    return conn_str


# --- SAP HANA Environment Variables ---
SAP_USER = os.getenv("SAP_USER", "SYSTEM")
SAP_PASSWORD = os.getenv("SAP_PASSWORD", "")
SAP_SERVER = os.getenv("DB_SERVER", "192.168.2.237")

# --- Overall App Config ---
SGA_ENV = os.getenv("SGA_ENV", "development").lower()

if SGA_ENV == "production" and SQL_TRUST_CERTIFICATE == "yes":
    logging.warning(
        "⚠️ SECURITY WARNING: SGA_ENV is 'production' but SQL_TRUST_CERTIFICATE is 'yes'. Consider deploying certificates and setting this to 'no' to prevent MITM attacks."
    )
