#!/usr/bin/env python3
"""
Shared File Manager for SGA Multi-System Deployment
Provides thread-safe file locking for concurrent access to JSON/CSV files
"""

import os
import json
import time
import logging
from typing import Any, Dict, Optional
from contextlib import contextmanager
import pandas as pd

if os.name == "nt":
    import msvcrt
else:
    import fcntl

logger = logging.getLogger(__name__)


class FileLockTimeout(Exception):
    """Raised when file lock cannot be acquired within timeout"""

    pass


class SharedFileManager:
    """
    Manages thread-safe access to shared files across multiple systems
    Uses fcntl for file locking (Linux/Unix compatible)
    """

    def __init__(self, base_path: str = None):
        """
        Initialize shared file manager

        Args:
            base_path: Base directory for shared files
                      If None, uses local directory (for testing)
        """
        self.base_path = base_path or os.getcwd()
        self.lock_timeout = 10  # seconds
        self.retry_delay = 0.1  # seconds

    @contextmanager
    def lock_file(
        self, filepath: str, exclusive: bool = False, timeout: Optional[float] = None
    ):
        """
        Context manager for file locking

        Args:
            filepath: Path to file to lock
            exclusive: If True, use exclusive lock (for writing)
                      If False, use shared lock (for reading)
            timeout: Max seconds to wait for lock (default: self.lock_timeout)

        Yields:
            file object (opened in appropriate mode)

        Raises:
            FileLockTimeout: If lock cannot be acquired

        Example:
            with mgr.lock_file('data.json', exclusive=True) as f:
                data = json.load(f)
                data['key'] = 'value'
                f.seek(0)
                f.truncate()
                json.dump(data, f)
        """
        timeout = timeout or self.lock_timeout
        mode = "r+" if exclusive else "r"

        # Determine lock type
        if os.name == "nt":
            # msvcrt locking requires a file length, locking the first position
            lock_type = msvcrt.LK_NBLCK
        else:
            lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH

        # Ensure file exists
        if not os.path.exists(filepath):
            if exclusive:
                # Create empty file
                with open(filepath, "w") as f:
                    json.dump({}, f)
            else:
                raise FileNotFoundError(f"File not found: {filepath}")

        start_time = time.time()
        file_obj = None

        try:
            file_obj = open(filepath, mode)

            # Try to acquire lock with timeout
            while True:
                try:
                    if os.name == "nt":
                        file_obj.seek(0)
                        msvcrt.locking(file_obj.fileno(), lock_type, 1)
                        # move it back based on opening mode
                        if not exclusive:
                            file_obj.seek(0)
                    else:
                        fcntl.flock(file_obj.fileno(), lock_type | fcntl.LOCK_NB)
                    break  # Lock acquired
                except (BlockingIOError, OSError, IOError):
                    if time.time() - start_time > timeout:
                        raise FileLockTimeout(
                            f"Could not acquire {'exclusive' if exclusive else 'shared'} "
                            f"lock on {filepath} within {timeout}s"
                        )
                    time.sleep(self.retry_delay)

            logger.debug(
                f"Acquired {'exclusive' if exclusive else 'shared'} lock on {filepath}"
            )
            yield file_obj

        finally:
            if file_obj:
                try:
                    if os.name == "nt":
                        file_obj.seek(0)
                        msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
                        logger.debug(f"Released lock on {filepath}")
                    else:
                        fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
                        logger.debug(f"Released lock on {filepath}")
                except Exception as e:
                    logger.debug(f"Failed to release lock on {filepath}: {e}")
                file_obj.close()

    def read_json(self, filepath: str, default: Any = None) -> Any:
        """
        Thread-safe read of JSON file

        Args:
            filepath: Path to JSON file
            default: Value to return if file doesn't exist or is empty

        Returns:
            Parsed JSON data or default value
        """
        full_path = os.path.join(self.base_path, filepath)

        if not os.path.exists(full_path):
            logger.warning(f"JSON file not found: {full_path}, returning default")
            return default

        try:
            with self.lock_file(full_path, exclusive=False) as f:
                content = f.read()
                if not content.strip():
                    return default
                f.seek(0)
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {full_path}: {e}")
            return default
        except Exception as e:
            logger.error(f"Error reading {full_path}: {e}")
            return default

    def write_json(self, filepath: str, data: Any, indent: int = 2) -> bool:
        """
        Thread-safe write of JSON file

        Args:
            filepath: Path to JSON file
            data: Data to write (must be JSON serializable)
            indent: JSON indentation level

        Returns:
            True if successful, False otherwise
        """
        full_path = os.path.join(self.base_path, filepath)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        try:
            # Create backup before writing
            if os.path.exists(full_path):
                backup_path = f"{full_path}.bak"
                try:
                    import shutil

                    shutil.copy2(full_path, backup_path)
                except Exception:
                    pass

            with self.lock_file(full_path, exclusive=True) as f:
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=indent, ensure_ascii=False)

            logger.debug(f"Successfully wrote JSON to {full_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing JSON to {full_path}: {e}")
            return False

    def append_to_json_list(self, filepath: str, item: Any) -> bool:
        """
        Thread-safe append to JSON array file
        Useful for history/log files

        Args:
            filepath: Path to JSON file (must contain array)
            item: Item to append

        Returns:
            True if successful, False otherwise
        """
        full_path = os.path.join(self.base_path, filepath)

        try:
            with self.lock_file(full_path, exclusive=True) as f:
                try:
                    data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    data = []

                if not isinstance(data, list):
                    logger.error(f"{filepath} does not contain a list")
                    return False

                data.append(item)

                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Appended item to {full_path}")
            return True

        except Exception as e:
            logger.error(f"Error appending to {full_path}: {e}")
            return False

    def read_csv(self, filepath: str, **kwargs) -> Optional[pd.DataFrame]:
        """
        Thread-safe read of CSV file

        Args:
            filepath: Path to CSV file
            **kwargs: Additional arguments for pd.read_csv

        Returns:
            DataFrame or None if error
        """
        full_path = os.path.join(self.base_path, filepath)

        if not os.path.exists(full_path):
            logger.warning(f"CSV file not found: {full_path}")
            return None

        try:
            with self.lock_file(full_path, exclusive=False) as f:
                return pd.read_csv(f, **kwargs)
        except Exception as e:
            logger.error(f"Error reading CSV {full_path}: {e}")
            return None

    def write_csv(self, filepath: str, df: pd.DataFrame, **kwargs) -> bool:
        """
        Thread-safe write of CSV file

        Args:
            filepath: Path to CSV file
            df: DataFrame to write
            **kwargs: Additional arguments for df.to_csv

        Returns:
            True if successful, False otherwise
        """
        full_path = os.path.join(self.base_path, filepath)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        try:
            # Create backup
            if os.path.exists(full_path):
                backup_path = f"{full_path}.bak"
                try:
                    import shutil

                    shutil.copy2(full_path, backup_path)
                except Exception:
                    pass

            # Write with lock (need to use file handle)
            temp_path = f"{full_path}.tmp"
            df.to_csv(temp_path, **kwargs)

            # Atomic rename with lock
            with self.lock_file(full_path, exclusive=True, timeout=5) as f:
                import shutil

                shutil.move(temp_path, full_path)

            logger.debug(f"Successfully wrote CSV to {full_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing CSV to {full_path}: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False


# ============================================================================
# Helper Functions
# ============================================================================


def get_shared_path_config() -> Dict[str, str]:
    """
    Get shared path configuration
    Checks environment variables and config files

    Returns:
        Dictionary with shared paths
    """
    # Check environment variable first
    shared_base = os.environ.get("SGA_SHARED_PATH")

    # Check config file
    if not shared_base:
        config_file = os.path.join(os.getcwd(), "shared_config.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                    shared_base = config.get("shared_base_path")
            except Exception:
                pass

    # Fallback to local
    if not shared_base:
        shared_base = os.getcwd()
        logger.warning(f"No shared path configured, using local: {shared_base}")

    return {
        "base": shared_base,
        "master_data": os.path.join(shared_base, "master_data"),
        "unified_db": os.path.join(shared_base, "master_data", "unified_db"),
        "assets": os.path.join(shared_base, "assets"),
        "operational": os.path.join(shared_base, "operational"),
        "config": os.path.join(shared_base, "config"),
        "logs": os.path.join(shared_base, "logs"),
    }


# ============================================================================
# Testing
# ============================================================================

if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)

    # Test file locking
    print("Testing SharedFileManager...")

    mgr = SharedFileManager()

    # Test JSON write/read
    test_data = {"test": "data", "timestamp": time.time()}
    mgr.write_json("test_shared.json", test_data)
    read_data = mgr.read_json("test_shared.json")
    assert read_data == test_data, "JSON read/write failed"
    print("✓ JSON read/write OK")

    # Test append
    mgr.write_json("test_list.json", [])
    mgr.append_to_json_list("test_list.json", {"item": 1})
    mgr.append_to_json_list("test_list.json", {"item": 2})
    items = mgr.read_json("test_list.json")
    assert len(items) == 2, "List append failed"
    print("✓ JSON append OK")

    # Test CSV
    df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
    mgr.write_csv("test_data.csv", df, index=False)
    df_read = mgr.read_csv("test_data.csv")
    assert len(df_read) == 3, "CSV read/write failed"
    print("✓ CSV read/write OK")

    # Cleanup
    for f in ["test_shared.json", "test_list.json", "test_data.csv"]:
        if os.path.exists(f):
            os.remove(f)
        if os.path.exists(f + ".bak"):
            os.remove(f + ".bak")

    print("\n✓ All tests passed!")
    print("\nShared path configuration:")
    import pprint

    pprint.pprint(get_shared_path_config())
