# SGA GHS Label System: Enterprise Production Roadmap

This document outlines the comprehensive strategy to elevate the SGA backend and frontend architecture from a functional prototype to a scalable, secure, and highly resilient enterprise application.

---

## 🛡️ Phase 1: Security & Configuration Management (Immediate Priority)

### 1.1 Eliminate Hardcoded Secrets
**Current State:** SQL Server and SAP HANA credentials are hardcoded in plain text across various files (`run_full_sql_migration.py`, `db_backup.py`, `sap_connector.py`).
*   **Action Item:** Implement `python-dotenv`.
*   **Task:** Move all configuration (IPs, Ports, UIDs, PWDs) to a local `.env` file (which is git-ignored).
*   **Task:** Create a `config.py` module using `pydantic` or `os.environ` to centrally load and validate these variables at startup.

### 1.2 Encrypted Traffic & Authentication setup
*   **Action Item:** Ensure `TrustServerCertificate=no` for production if a valid SSL/TLS certificate can be installed on the SQL Server (192.168.2.237) to prevent Man-in-the-Middle attacks.
*   **Action Item:** Force password hashing algorithms in `user_manager.py` (e.g., `bcrypt` or `argon2`) instead of plain text or weak hashes before migrating them fully into the `users` SQL table.

---

## 🏗️ Phase 2: Architecture Refactoring & Resilience

### 2.1 Object-Relational Mapping (ORM) Implementation
**Current State:** Database queries are running via raw `pyodbc` string formatting.
*   **Action Item:** Introduce **SQLAlchemy**.
*   **Why:** Prevents SQL injection, dramatically reduces boilerplate code, and allows Python objects (like `SmartLabel` and `User`) to map directly to your optimally typed SQL tables.
*   **Task:** Create `models.py` defining the SQLAlchemy classes (e.g., `class ProductMaster(Base):`).

### 2.2 Dual-Mode Architecture (The "Offline" Fallback)
**Current State:** The SQL connection is a hard dependency. If the server goes down, the warehouse stops printing.
*   **Action Item:** Implement the Cache Fallback Strategy defined in `SQL_IMPLEMENTATION_PLAN.md`.
*   **Task:** Refactor `database_client.py`. When a product is fetched from SQL successfully, asynchronously write an updated row to the local `unified_db/*.csv` repository.
*   **Task:** Wrap database calls in `try/except pyodbc.OperationalError`. On failure, the UI throws a non-intrusive warning ("Offline Mode Active") and reads directly from the local CSV cache.

### 2.3 Connection Pooling
*   **Action Item:** Use SQLAlchemy's `QueuePool` for SQL Server and keep a persistent connection pool for `sap_connector.py`. Creating a new TCP connection to HANA or SQL Server per label scan is highly inefficient and creates network bottlenecks.

---

## 🧩 Phase 3: Codebase Modularization (Maintainability)

### 3.1 Disaggregate the Monolith (`ghs_label_gui.py`)
**Current State:** The main GUI file is extremely large (>5,400 lines), mixing UI design, event bindings, and business logic.
*   **Action Item:** Split the UI using the MVC (Model-View-Controller) pattern.
    *   `views/`: `main_window.py`, `settings_panel.py`, `operator_dashboard.py`.
    *   `controllers/`: Existing `sga_controller.py` should be expanded to handle all button clicks and route them to `smart_label.py`.
    *   `components/`: Extract custom Tkinter widgets into their own directory (e.g., `barcode_scanner_input.py`).

### 3.2 Standardized Testing Framework
**Current State:** Ad-hoc scripts (`test_db.py`, `test_sap.py`).
*   **Action Item:** Implement `pytest`. 
*   **Task:** Create `/tests/` directory. Write automated Unit Tests for the core logic (e.g., verifying that a specific Barcode resolves to the correct Father/Son product ignoring the UI).

---

## 🚀 Phase 4: User Experience (UX) & Asynchronous Processing

### 4.1 UI Thread Unblocking
**Current State:** When querying SAP HANA or a slow SQL query, the Tkinter app might briefly "freeze" (Not Responding).
*   **Action Item:** Implement Python `threading` or `asyncio` for all database and network network calls. 
*   **Task:** Use Tkinter `after()` methods or a thread-safe message queue so the UI shows a generic loading spinner (e.g., `Retrieving GHS Data...`) rather than locking up the Windows window.

---

## 📦 Phase 5: DevOps, Release Management & Monitoring

### 5.1 Automated `.exe` Distribution (Over-The-Air Updates)
**Current State:** Users likely rely on manual copying of the compiled `.exe` after `build_windows.bat` finishes.
*   **Action Item:** Build a self-updater mechanism. 
*   **Task:** Host the latest stable `sga_app_vX.X.exe` and a `version.json` file on a shared network drive (`\\192.168.2.xxx\Releases`) or internal web server. 
*   **Task:** On boot, the app checks `version.json`. If an update is available, it downloads the new executable, shuts itself down, swaps the files via a tiny `.bat` wrapper, and restarts seamlessly.

### 5.2 Centralized Logging
**Current State:** `logging.basicConfig()` writes to standard output or local text files scattered across terminals.
*   **Action Item:** Forward critical application errors specifically to a new SQL Table (`application_errors_log`).
*   **Why:** You (the developer) can query the SQL Server to see exactly what errors operators are encountering in real-time across all warehouse terminals, without explicitly checking their local machines. Include attributes: `operator_id`, `error_traceback`, `module`, and `timestamp`.

### 5.3 Advanced Database Backups
*   **Action Item:** Upgrade `db_backup.py`.
*   **Task:** Implement Backup Retention. After generating a new `.bak` file, add Python logic to scan the backup directory and `os.remove()` any `.bak` files older than 30 days to prevent the 192.168.2.237 server drive from running out of storage space.

---

## 🏁 Summary of Next Steps for Development:
1. Initialize a `.env` file and refactor configuration.
2. Implement **SQLAlchemy** to connect your Python models to the newly optimized SQL tables.
3. Build the Offline/Local CSV fallback into `database_client.py`.
4. Wrap network queries in `threading` to keep the UI smooth.
5. Establish the **Auto-Updater** logic for your warehouse users.