import sys
try:
    import pyodbc
except ImportError:
    print("pyodbc not installed")
    sys.exit(1)

server = r'192.168.2.187'
database = 'SGA_Database'
username = 'sga_app_user'
password = 'Qu1m1c4B055'

found_driver = None
for d in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server', 'SQL Server Native Client 11.0', 'SQL Server']:
    if d in pyodbc.drivers():
        found_driver = '{' + d + '}'
        break

if not found_driver:
    sys.exit(1)

print(f"Using driver: {found_driver}")

# Connect using IP (port 1433 is now mapped)
conn_str = f"DRIVER={found_driver};SERVER={server},1433;DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes"
try:
    conn = pyodbc.connect(conn_str, timeout=10)
    print("Connection successful!")
    cursor = conn.cursor()
    cursor.execute("SELECT @@VERSION")
    row = cursor.fetchone()
    print("Server version:", row[0])
    conn.close()
except pyodbc.Error as e:
    print("Connection failed:", e)
