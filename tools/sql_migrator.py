import os
import sys
import pandas as pd
import numpy as np

# Add parent dir to path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_sql_connection_string
from sqlalchemy import create_engine

def migrate_csv_to_sql():
    try:
        import pyodbc
    except ImportError:
        print("Error: pyodbc not installed.")
        return

    driver = "{ODBC Driver 17 for SQL Server}"
    if "ODBC Driver 17 for SQL Server" not in pyodbc.drivers():
        if "ODBC Driver 18 for SQL Server" in pyodbc.drivers():
            driver = "{ODBC Driver 18 for SQL Server}"
        else:
            driver = "{SQL Server}"

    raw_conn_str = get_sql_connection_string(driver)
    sql_conn_str = f"mssql+pyodbc:///?odbc_connect={__import__('urllib').parse.quote_plus(raw_conn_str)}"
    print(f"Connecting to SQL Server...")
    
    try:
        engine = create_engine(sql_conn_str)
        with engine.connect():
            print("Connected successfully.")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    unified_db_path = os.path.join(base_dir, 'unified_db')
    
    csv_files = {
        'products_master': 'products_master.csv',
        'h_statements': 'h_statements.csv',
        'p_statements': 'p_statements.csv',
        'pictograms': 'pictograms.csv',
        'product_hazards': 'product_hazards.csv',
        'product_pictograms': 'product_pictograms.csv',
        'product_precautions': 'product_precautions.csv',
        'product_variants': 'product_variants.csv'
    }

    for table_name, csv_file in csv_files.items():
        file_path = os.path.join(unified_db_path, csv_file)
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} not found. Skipping {table_name}.")
            continue
            
        print(f"Migrating {csv_file} to table {table_name}...")
        df = pd.read_csv(file_path)
        df = df.replace({np.nan: None})
        
        try:
            df.to_sql(table_name, engine, if_exists='replace', index=False)
            print(f"Successfully migrated {table_name}.")
        except Exception as e:
            print(f"Failed to migrate {table_name}: {e}")

if __name__ == "__main__":
    migrate_csv_to_sql()
