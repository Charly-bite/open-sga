# SGA SQL Server Migration: Detailed Implementation Plan

## Overview
This document outlines the zero-downtime regression plan to migrate the SGA GHS Label System from a flat-file backend (`.csv`/`.json`) to a relational **Microsoft SQL Server** architecture. 

Currently, **Microsoft SQL Server Engine is NOT installed on this machine**, and Python's `SQLAlchemy` ORM is missing. 

---

## 🛠️ Phase 1: Environment Readiness (Pre-requisites)

### 1.1 Install Database Engine
* **Action:** Download and run the **Microsoft SQL Server 2022 Express** installer.
* **Config:** 
  * Choose "Custom" installation.
  * Enable **Database Engine Services**.
  * **Authentication:** Select **Mixed Mode** (SQL Server authentication and Windows authentication). Set a strong `sa` (sysadmin) password.
* **Network Setup:** Open SQL Server Configuration Manager -> SQL Server Network Configuration -> Protocols. **Enable TCP/IP** so Python can connect locally via port 1433.

### 1.2 Database Provisioning
* **Action:** Install SQL Server Management Studio (SSMS).
* **Script:** Connect to the instance and run:
  ```sql
  CREATE DATABASE SGA_Database;
  GO
  USE SGA_Database;
  CREATE LOGIN sga_app_user WITH PASSWORD = 'YourStrongPassword123';
  CREATE USER sga_app_user FOR LOGIN sga_app_user;
  ALTER ROLE db_owner ADD MEMBER sga_app_user;
  ```

### 1.3 Install Python Dependencies
* **Action:** Add the ORM and ODBC bridging tools to your virtual environment.
* **Command:** `pip install pyodbc sqlalchemy`

---

## 🏗️ Phase 2: Schema Design (DDL)

We will use `NVARCHAR` instead of `VARCHAR` to handle Spanish accents correctly.

### 2.1 Catalogs (No Foreign Keys pointing to them initially to ease ingestion)
* **`h_statements`**: `code (PK, NVARCHAR 10)`, `class (NVARCHAR 50)`, `description (NVARCHAR 500)`
* **`p_statements`**: `code (PK, NVARCHAR 10)`, `type (NVARCHAR 50)`, `text (NVARCHAR 500)`
* **`pictograms`**: `name (PK, NVARCHAR 50)`, `path (NVARCHAR 200)`

### 2.2 Core Tables
* **`products_master`**: `product_id (PK, NVARCHAR 50)`, `name (NVARCHAR 200)`, `signal_word (NVARCHAR 20)`, `un_number (NVARCHAR 20)`, `cas_number (NVARCHAR 50)`, `tara_weight (DECIMAL(10,3))`
* **`users`**: `id (PK, INT IDENTITY(1,1))`, `username (NVARCHAR 50 UNIQUE)`, `password_hash (NVARCHAR 200)`, `role (NVARCHAR 20)`, `warehouse (NVARCHAR 10)`

### 2.3 Relational Tables (Junctions)
* **`product_hazards`**: `product_id (FK)`, `h_code (FK)` (Composite PK)
* **`product_precautions`**: `product_id (FK)`, `p_code (FK)` (Composite PK)

---

## 📦 Phase 3: The Data Ingestion Script (The Migration)

We will create a standalone script called `tools/sql_migrator.py`.
**CRITICAL:** It must handle `NaN` (Not a Number) values from Pandas and convert them to SQL `NULL` properly, or the ingestion will crash.

**Safe Ingestion Steps:**
1. Truncate all SQL tables (if running multiple times).
2. Load `unified_db/*.csv` into Pandas.
3. Clean data: `.fillna(None)` or `.replace({np.nan: None})`.
4. Merge `product_classifications.json` overrides (Custom Tara Weights) into the `products_master` DataFrame in memory.
5. Push DataFrames to SQL Server using `df.to_sql('table_name', engine, if_exists='append', index=False)`.

---

## 🔀 Phase 4: Application Refactor (Dual-Mode Architecture)

To avoid breaking the production system if the SQL DB goes offline, we will implement a **Feature Flag** in `db_client_config.json`.

```json
"database": {
    "engine": "sql", 
    "sql_connection_string": "mssql+pyodbc://sga_app_user:YourStrongPassword123@127.0.0.1/SGA_Database?driver=ODBC+Driver+17+for+SQL+Server",
    "fallback_to_csv": true
}
```

**Refactoring `database_client.py`:**
1. Abstract all data-fetching functions. For example, `get_product(product_id)`.
2. Inside `get_product`:
   * `if config['engine'] == 'sql':` -> Execute `SELECT * FROM products_master WHERE product_id = ?` using SQLAlchemy.
   * `except Exception as e:` -> If SQL fails, fall back to `self._read_csv()`.
3. Update `user_manager.py` to authenticate against `SELECT * FROM users`. If successful, skip the JSON file.

---

## 🧪 Phase 5: Validation & Cutover Strategy

1. **Dry Run (Read Only):** Set the UI to point to SQL. Verify a label generates perfectly in the system and the PDF matches exactly what it did previously. 
2. **Dual-Write (Write Testing):** When saving new Tara Weights from the UI, send the update to the SQL Database *AND* the JSON file simultaneously for 1 week.
3. **Hard Cutover:** Once 100% stable, switch `"fallback_to_csv": false`, set `history.json` to read-only, and fully depend on SQL.