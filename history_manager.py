import json
import os
from datetime import datetime, timedelta


class HistoryManager:
    """
    Manages a persistent log of application events (SAP Imports, Print Jobs).
    Stores data in a local JSON file and via DatabaseClient in SQL Server.
    Auto-prunes entries older than max_age_days to prevent unbounded growth.
    """

    def __init__(self, history_file="history.json", max_entries=500, max_age_days=30):
        self.history_file = history_file
        self.max_entries = max_entries
        self.max_age_days = max_age_days

        # Connect to DB via shared DatabaseClient singleton
        from database_client import get_shared_client

        self.db_client = get_shared_client()
        self.sql_engine = None
        try:
            if self.db_client.is_connected():
                self.sql_engine = self.db_client.get_sql_engine()
        except Exception as e:
            print(f"[WARN] HistoryManager DB error: {e}")

        self._ensure_file_exists()
        self._ensure_db_table_exists()
        # self._prune()  # Disabled: Causes SQL Server deadlocks/hangs on startup with large tables

    def _ensure_db_table_exists(self):
        """Creates the history_logs table if it does not exist."""
        if not self.sql_engine:
            return
        try:

            with self.sql_engine.begin() as conn:
                # Use raw SQL to create table if missing
                conn.exec_driver_sql("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='history_logs' and xtype='U')
                    CREATE TABLE history_logs (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        timestamp VARCHAR(50),
                        event_type VARCHAR(50),
                        username VARCHAR(50),
                        details NVARCHAR(MAX)
                    )
                """)
        except Exception as e:
            print(f"⚠️ Could not ensure history_logs table exists: {e}")

    def _ensure_file_exists(self):
        from sga_web.core.shared_file_manager import SharedFileManager

        if not os.path.exists(self.history_file):
            file_manager = SharedFileManager()
            file_manager.write_json(self.history_file, [])

    def add_entry(self, event_type, details, username=None):
        """
        Add a new event to the history log.

        Args:
            event_type (str): Category (e.g., 'SAP_IMPORT', 'PRINT_JOB')
            details (dict): Structured details about the event
            username (str, optional): Username who performed the action
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = username or "system"

        entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "user": user,
            "details": details,
        }

        # Try writing to sql
        if self.sql_engine:
            try:
                details_json = json.dumps(details, ensure_ascii=False)
                with self.sql_engine.connect() as conn:
                    raw_conn = conn.connection
                    cursor = raw_conn.cursor()
                    cursor.execute(
                        "INSERT INTO history_logs (timestamp, event_type, username, details) VALUES (?, ?, ?, ?)",
                        (timestamp, event_type, user, details_json),
                    )
                    raw_conn.commit()
                    cursor.close()
            except Exception as e:
                import traceback

                print(f"⚠️ Error saving history to SQL: {e}")
                traceback.print_exc()

        # Fallback / sync to JSON
        try:
            from sga_web.core.shared_file_manager import SharedFileManager

            file_manager = SharedFileManager()

            history = self._get_history_from_json()
            history.append(entry)

            # Auto-prune before saving
            history = self._filter_entries(history)

            file_manager.write_json(self.history_file, history, indent=4)
        except Exception as e:
            print(f"Error saving history to JSON: {e}")

    def _prune(self):
        """Remove old entries on startup."""
        try:
            from sga_web.core.shared_file_manager import SharedFileManager

            file_manager = SharedFileManager()

            history = self._get_history_from_json()
            pruned = self._filter_entries(history)
            if len(pruned) < len(history):
                file_manager.write_json(self.history_file, pruned, indent=4)
                print(f"📋 History pruned: {len(history)} → {len(pruned)} entries")
        except Exception:
            pass

        # Also prune SQL if connected
        if self.sql_engine:
            try:
                cutoff = (datetime.now() - timedelta(days=self.max_age_days)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                with self.sql_engine.begin() as conn:
                    # simplistic prune based on timestamp string
                    conn.exec_driver_sql(
                        f"DELETE FROM history_logs WHERE timestamp < '{cutoff}'"
                    )

                    # prune by max entries (keep newest N)  - slightly complex in T-SQL, omitting for brevity unless needed
            except Exception as e:
                print(f"⚠️ Error pruning SQL history: {e}")

    def _filter_entries(self, history):
        """Keep only recent entries within max_age_days, capped at max_entries."""
        cutoff = (datetime.now() - timedelta(days=self.max_age_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        filtered = [e for e in history if e.get("timestamp", "") >= cutoff]
        # Cap to max_entries (keep newest)
        if len(filtered) > self.max_entries:
            filtered = filtered[-self.max_entries :]
        return filtered

    def _get_history_from_json(self):
        try:
            if not os.path.exists(self.history_file):
                return []

            from sga_web.core.shared_file_manager import SharedFileManager

            file_manager = SharedFileManager()
            data = file_manager.read_json(self.history_file, default=[])
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def get_history(self, event_type=None, limit=None):
        """
        Retrieve history entries. Attempts from SQL first, then JSON.

        Args:
            event_type: Optional filter for specific event types (e.g. 'product_edit')
            limit: Max entries to return (defaults to self.max_entries)

        Results are cached for 60 seconds to avoid repeated DB hits.
        """
        if limit is None:
            limit = self.max_entries

        # Check TTL cache (60 second window)
        cache_key = f"{event_type or 'all'}:{limit}"
        import time as _time

        now = _time.time()
        if hasattr(self, "_history_cache") and cache_key in self._history_cache:
            cached_data, cached_at = self._history_cache[cache_key]
            if now - cached_at < 60:
                return cached_data

        result = self._fetch_history(event_type, limit)

        # Store in cache
        if not hasattr(self, "_history_cache"):
            self._history_cache = {}
        self._history_cache[cache_key] = (result, now)
        return result

    def _fetch_history(self, event_type=None, limit=500):
        """Internal: fetch history from SQL or JSON."""
        if self.sql_engine:
            try:
                import pandas as pd
                from sqlalchemy import text

                # Build targeted SQL query instead of loading the full table
                where_clause = ""
                params = {}
                if event_type:
                    where_clause = "WHERE event_type = :evt"
                    params["evt"] = event_type

                # Use string formatting for TOP n since SQL Server can have issues
                # parameterizing TOP without parenthesis. limit is always an int.
                query = text(f"""
                    SELECT TOP {int(limit)} id, timestamp, event_type, username, details
                    FROM history_logs WITH (NOLOCK)
                    {where_clause}
                    ORDER BY id DESC
                """)

                df = pd.read_sql(query, con=self.sql_engine, params=params)
                # Parse back to history format
                history = []
                for _, row in df.iterrows():
                    details = {}
                    try:
                        details = json.loads(row["details"])
                    except Exception:
                        pass
                    history.append(
                        {
                            "timestamp": str(row["timestamp"]),
                            "event_type": str(row["event_type"]),
                            "user": str(row["username"]),
                            "details": details,
                        }
                    )
                # Reverse so oldest is first (matches original behavior)
                history.reverse()
                return history
            except Exception as e:
                print(f"⚠️ Error reading history from SQL: {e}")

        return self._get_history_from_json()

    def clear_history(self):
        if self.sql_engine:
            try:
                with self.sql_engine.begin() as conn:
                    conn.exec_driver_sql("TRUNCATE TABLE history_logs")
            except Exception as e:
                print(f"⚠️ Error clearing SQL history: {e}")

        try:
            from sga_web.core.shared_file_manager import SharedFileManager

            file_manager = SharedFileManager()
            file_manager.write_json(self.history_file, [])
        except Exception as e:
            print(f"⚠️ Error clearing JSON history: {e}")
