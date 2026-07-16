#!/usr/bin/env python3
"""
Create SGA_Development local database snapshot.
Copies all tables from the production SQL Server (SGA_Database) into
a local SQLite file for fully isolated development work.

This approach:
  - Requires NO admin permissions on SQL Server
  - Creates a complete local snapshot for dev
  - Zero risk of corrupting production data
"""

import os
import sys
import sqlite3

# Ensure PYTHONIOENCODING is set for emoji output
if sys.stdout.encoding != "utf-8":
    import io

    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:
        pass

import pyodbc
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_ROOT = os.path.dirname(SCRIPT_DIR)

SQL_SERVER = "192.168.2.237,1433"
SQL_DATABASE = "SGA_Database"
SQL_USER = "sga_app_user"
SQL_PASSWORD = "QuimicaBoss_2026!"

# Output: local SQLite database for dev
SQLITE_PATH = os.path.join(DEV_ROOT, "unified_db", "dev_database.sqlite")


def main():
    print("=" * 60)
    print("  SGA Development Database Snapshot Creator")
    print("=" * 60)
    print(f"  Source: SQL Server {SQL_SERVER}/{SQL_DATABASE}")
    print(f"  Target: {SQLITE_PATH}")
    print("=" * 60)

    # Connect to production SQL Server (read-only operations)
    drivers = ["ODBC Driver 17 for SQL Server", "SQL Server"]
    src_conn = None
    for driver in drivers:
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            f"UID={SQL_USER};"
            f"PWD={SQL_PASSWORD};"
            f"TrustServerCertificate=yes"
        )
        try:
            src_conn = pyodbc.connect(conn_str)
            print(f"\n[OK] Connected to SQL Server using {driver}")
            break
        except pyodbc.Error as e:
            print(f"  Driver '{driver}' failed: {e}")

    if not src_conn:
        print("\n[ERROR] Could not connect to SQL Server")
        sys.exit(1)

    src_cursor = src_conn.cursor()

    # Create/overwrite SQLite database
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)
        print(f"  Removed existing {os.path.basename(SQLITE_PATH)}")

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()
    print(f"[OK] Created SQLite database: {SQLITE_PATH}")

    # Get all user tables
    src_cursor.execute("""
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)
    tables = [row[0] for row in src_cursor.fetchall()]
    print(f"\n[INFO] Found {len(tables)} tables in {SQL_DATABASE}:")

    total_rows = 0
    for table_name in tables:
        try:
            # Read all data from source
            src_cursor.execute(f"SELECT * FROM [{table_name}]")
            columns = [desc[0] for desc in src_cursor.description]
            rows = src_cursor.fetchall()

            # Create table in SQLite
            col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
            sqlite_cur.execute(
                f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})'
            )

            # Insert data
            if rows:
                placeholders = ", ".join(["?" for _ in columns])
                insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'

                # Convert rows to lists of strings (SQLite-friendly)
                clean_rows = []
                for row in rows:
                    clean_row = []
                    for val in row:
                        if val is None:
                            clean_row.append(None)
                        else:
                            clean_row.append(str(val))
                    clean_rows.append(clean_row)

                sqlite_cur.executemany(insert_sql, clean_rows)

            total_rows += len(rows)
            print(f"   [OK] {table_name}: {len(rows)} rows, {len(columns)} columns")

        except Exception as e:
            print(f"   [WARN] {table_name}: {e}")

    sqlite_conn.commit()
    sqlite_conn.close()
    src_cursor.close()
    src_conn.close()

    file_size_mb = os.path.getsize(SQLITE_PATH) / (1024 * 1024)

    print(f"\n{'=' * 60}")
    print("  [DONE] Development database snapshot created!")
    print(f"  Tables: {len(tables)}")
    print(f"  Total rows: {total_rows}")
    print(f"  File size: {file_size_mb:.1f} MB")
    print(f"  Location: {SQLITE_PATH}")
    print(f"{'=' * 60}")

    # Also update the db_client_config.json to point to local SQLite
    config_path = os.path.join(DEV_ROOT, "db_client_config.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        # Keep SQL connection for optional use but set fallback to enabled
        config["database"]["fallback_to_csv"] = True
        config["fallback"]["enabled"] = True
        config["fallback"]["local_database_path"] = "unified_db"

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"\n[OK] Updated {os.path.basename(config_path)} with fallback settings")
    except Exception as e:
        print(f"\n[WARN] Could not update config: {e}")


if __name__ == "__main__":
    main()
