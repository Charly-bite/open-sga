import pyodbc
import datetime
import logging
from config import get_sql_connection_string

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("db_backup.log"), logging.StreamHandler()],
)


def backup_database():
    # Database is configured from environment variables in config.py
    from config import SQL_DATABASE

    database = SQL_DATABASE

    # Determine the driver
    drivers = pyodbc.drivers()
    driver = "{ODBC Driver 17 for SQL Server}"
    if "ODBC Driver 17 for SQL Server" not in drivers:
        if "ODBC Driver 18 for SQL Server" in drivers:
            driver = "{ODBC Driver 18 for SQL Server}"
        elif "SQL Server" in drivers:
            driver = "{SQL Server}"

    # Get connection string securely from our .env config
    conn_str = get_sql_connection_string(driver)

    try:
        # Note: autocommit=True is REQUIRED to run BACKUP DATABASE commands via pyodbc
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()

        # Determine backup filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # CRITICAL: This path is local to the MACHINE HOSTING SQL SERVER (192.168.2.237), not the machine running python!
        # Usually 'C:\Backups\' or 'C:\Program Files\Microsoft SQL Server\MSSQL16.MSSQLSERVER\MSSQL\Backup\'
        # We will use the default SQL Server backup directory using a dynamic query if possible, or a standard path.

        # Let's get the default backup directory
        cursor.execute(r"""
            DECLARE @BackupDir NVARCHAR(4000);
            EXEC master.dbo.xp_instance_regread 
                N'HKEY_LOCAL_MACHINE', 
                N'Software\Microsoft\MSSQLServer\MSSQLServer', 
                N'BackupDirectory', 
                @BackupDir OUTPUT;
            SELECT @BackupDir;
        """)
        row = cursor.fetchone()

        if row and row[0]:
            backup_dir = row[0]
        else:
            backup_dir = r"C:\Backups"  # Fallback

        backup_file = f"{backup_dir}\\{database}_Full_{timestamp}.bak"

        logging.info(f"Starting backup of {database}...")
        logging.info(f"Target destination (on SQL Server machine): {backup_file}")

        backup_sql = f"BACKUP DATABASE [{database}] TO DISK = N'{backup_file}' WITH FORMAT, INIT, NAME = 'Full Backup of {database}', STATS = 10"
        cursor.execute(backup_sql)

        # To get the messages/stats from the backup command
        while cursor.nextset():
            pass

        logging.info(f"✅ Backup completed successfully: {backup_file}")

    except Exception as e:
        logging.error(f"❌ Backup failed: {e}")
    finally:
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    backup_database()
