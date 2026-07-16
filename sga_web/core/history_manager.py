import json
import os
from datetime import datetime, timedelta


class HistoryManager:
    """
    Manages a persistent log of application events (SAP Imports, Print Jobs).
    Stores data in a local JSON file and via DatabaseClient in SQL Server.
    Auto-prunes entries older than max_age_days to prevent unbounded growth.
    """

    def __init__(self, history_file=None, max_entries=500, max_age_days=30):
        if history_file is None:
            base = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            # Search multiple candidate locations for the history file
            candidates = [
                os.path.join(base, "data", "history.json"),  # Standard path
                os.path.join(base, "sga_web", "history.json"),  # Legacy path
                os.path.join(base, "history.json"),  # Project root
            ]
            history_file = next(
                (c for c in candidates if os.path.exists(c)),
                candidates[0],  # Default to standard path if none found
            )
        self.history_file = history_file
        self.max_entries = max_entries
        self.max_age_days = max_age_days

        # Connect to DB via DatabaseClient
        from database_client import DatabaseClient

        self.db_client = DatabaseClient()
        self.sql_engine = None
        try:
            if self.db_client.connect():
                self.sql_engine = self.db_client.get_sql_engine()
        except Exception as e:
            print(f"⚠️ HistoryManager DB error: {e}")

        self._ensure_file_exists()
        self._ensure_db_table_exists()
        self._prune()

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
        if not os.path.exists(self.history_file):
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([], f)

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
            history = self._get_history_from_json()
            history.append(entry)

            # Auto-prune before saving
            history = self._filter_entries(history)

            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving history to JSON: {e}")

    def _prune(self):
        """Remove old entries on startup."""
        try:
            history = self._get_history_from_json()
            pruned = self._filter_entries(history)
            if len(pruned) < len(history):
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump(pruned, f, indent=4, ensure_ascii=False)
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
                    # Ensure we don't delete MERMA_UPDATE or LABEL_GENERATION_METRICS
                    conn.exec_driver_sql(
                        f"DELETE FROM history_logs WHERE timestamp < '{cutoff}' AND event_type NOT IN ('MERMA_UPDATE', 'LABEL_GENERATION_METRICS')"  # nosec B608
                    )

                    # prune by max entries (keep newest N)  - slightly complex in T-SQL, omitting for brevity unless needed
            except Exception as e:
                print(f"⚠️ Error pruning SQL history: {e}")

    def _filter_entries(self, history):
        """Keep only recent entries within max_age_days, capped at max_entries."""
        cutoff = (datetime.now() - timedelta(days=self.max_age_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        # Do not prune EVENT_TYPES related to shrinkage (mermas)
        filtered = [
            e
            for e in history
            if e.get("timestamp", "") >= cutoff or e.get("event_type") == "MERMA_UPDATE"
        ]
        # Cap to max_entries (keep newest), but prioritize preserving mermas
        if len(filtered) > self.max_entries:
            # We keep all mermas, limit the rest
            mermas = [e for e in filtered if e.get("event_type") == "MERMA_UPDATE"]
            others = [e for e in filtered if e.get("event_type") != "MERMA_UPDATE"]
            allowed_others = max(0, self.max_entries - len(mermas))
            filtered = mermas + others[-allowed_others:]
            # Re-sort just in case
            filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""))

        return filtered

    def _get_history_from_json(self):
        try:
            if not os.path.exists(self.history_file):
                return []
            # Try UTF-8 first, then fall back to latin-1/cp1252 for files
            # that contain non-UTF-8 characters (e.g. SAP product names)
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    with open(self.history_file, "r", encoding=enc) as f:
                        return json.load(f)
                except UnicodeDecodeError:
                    continue
            # Last resort: read with errors='replace'
            with open(self.history_file, "r", encoding="utf-8", errors="replace") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def get_history(self):
        """
        Retrieve all history entries. Attempts from SQL first, then JSON.
        """
        if self.sql_engine:
            try:
                import pandas as pd

                df = pd.read_sql_table("history_logs", con=self.sql_engine)
                # Parse back to history format
                history = []
                # SQL records are ordered by id, but we typically sort by timestamp.
                df = df.sort_values(by="timestamp")
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
                return history[-self.max_entries :]  # return top N
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

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump([], f)
