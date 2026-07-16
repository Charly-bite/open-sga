#!/usr/bin/env python3
"""
Configuration Manager for Shared SGA Deployment
Handles path resolution, variable substitution, and mount checking
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SharedConfigManager:
    """
    Manages configuration for multi-system SGA deployment
    Handles path variables, mount checking, and fallbacks
    """

    def __init__(self, config_file: str = None):
        """
        Initialize configuration manager

        Args:
            config_file: Path to configuration JSON file
        """
        if config_file is None:
            base = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            config_file = os.path.join(base, "config", "shared_config.json")
        self.config_file = config_file
        self.config = {}
        self.resolved_paths = {}
        self._load_config()

    def _load_config(self):
        """Load and validate configuration file"""
        if not os.path.exists(self.config_file):
            logger.warning(f"Config file not found: {self.config_file}, using defaults")
            self._use_defaults()
            return

        try:
            with open(self.config_file, "r") as f:
                self.config = json.load(f)

            # Resolve path variables
            self._resolve_paths()

            # Check mount point
            if self.config.get("network", {}).get("mount_check_enabled", True):
                self._check_mount_point()

            logger.info(f"Loaded configuration from {self.config_file}")
            logger.info(f"System: {self.get('system_id')} ({self.get('system_role')})")
            logger.info(f"Shared path: {self.get_path('base')}")

        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self._use_defaults()

    def _use_defaults(self):
        """Use default local configuration"""
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        self.config = {
            "deployment_type": "local",
            "system_id": "standalone",
            "system_role": "administrator",
            "shared_base_path": base_dir,
            "paths": {},
            "files": {},
            "local_cache": {"enabled": False},
            "network": {"mount_check_enabled": False},
            "file_locking": {"enabled": False},
        }

        self.resolved_paths = {
            "base": base_dir,
            "master_data": os.path.join(base_dir, "original_data"),
            "unified_db": os.path.join(base_dir, "unified_db"),
            "assets": os.path.join(base_dir, "assets"),
            "operational": base_dir,
            "config": base_dir,
            "logs": base_dir,
            "generated_labels": os.path.join(base_dir, "generated_labels"),
        }

        logger.info("Using default local configuration")

    def _resolve_paths(self):
        """Resolve path variables like ${shared_base_path}"""
        # First, resolve base path
        base_path = self.config.get("shared_base_path", os.getcwd())

        # Expand environment variables
        base_path = os.path.expandvars(base_path)
        base_path = os.path.expanduser(base_path)

        self.resolved_paths["base"] = base_path

        # Resolve path variables
        paths_config = self.config.get("paths", {})
        variables = {
            "shared_base_path": base_path,
            "date": datetime.now().strftime("%Y%m%d"),
            "system_id": self.config.get("system_id", "unknown"),
        }

        for key, value in paths_config.items():
            resolved = value
            for var_name, var_value in variables.items():
                resolved = resolved.replace(f"${{{var_name}}}", str(var_value))
            self.resolved_paths[key] = resolved

        # Resolve file paths
        files_config = self.config.get("files", {})
        for key, value in files_config.items():
            resolved = value
            # First substitute path variables
            for path_key, path_value in self.resolved_paths.items():
                resolved = resolved.replace(f"${{{path_key}}}", path_value)
            # Then other variables
            for var_name, var_value in variables.items():
                resolved = resolved.replace(f"${{{var_name}}}", str(var_value))
            self.resolved_paths[f"file_{key}"] = resolved

    def _check_mount_point(self):
        """Check if network share is mounted"""
        mount_path = self.config.get("network", {}).get("mount_path")

        if not mount_path:
            return True

        if not os.path.ismount(mount_path) and not os.path.exists(mount_path):
            error_msg = f"Shared folder not mounted at: {mount_path}"

            if self.config.get("network", {}).get("fallback_to_local", False):
                logger.warning(f"{error_msg} - Falling back to local mode")
                self._use_defaults()
                return False
            else:
                logger.error(error_msg)
                raise RuntimeError(
                    f"Network share not available at {mount_path}\n"
                    f"Please mount the share or update configuration"
                )

        logger.info(f"Network share mounted at: {mount_path}")
        return True

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key (supports dot notation: 'network.timeout')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def get_path(self, path_key: str, create: bool = False) -> str:
        """
        Get resolved path

        Args:
            path_key: Path key (e.g., 'master_data', 'unified_db')
            create: If True, create directory if it doesn't exist

        Returns:
            Resolved absolute path
        """
        path = self.resolved_paths.get(path_key)

        if not path:
            logger.warning(f"Path key not found: {path_key}")
            return os.getcwd()

        if create and not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                logger.info(f"Created directory: {path}")
            except Exception as e:
                logger.error(f"Could not create directory {path}: {e}")

        return path

    def get_file_path(self, file_key: str) -> str:
        """
        Get resolved file path

        Args:
            file_key: File key (e.g., 'label_queue', 'users')

        Returns:
            Resolved absolute file path
        """
        return self.resolved_paths.get(f"file_{file_key}", "")

    def is_shared_mode(self) -> bool:
        """Check if running in shared/network mode"""
        return self.config.get("deployment_type") == "shared"

    def is_admin(self) -> bool:
        """Check if this system is an administrator"""
        return self.config.get("system_role") == "administrator"

    def get_system_id(self) -> str:
        """Get system identifier"""
        return self.config.get("system_id", "unknown")

    def is_file_locking_enabled(self) -> bool:
        """Check if file locking is enabled"""
        return self.get("file_locking.enabled", False)

    def get_lock_timeout(self) -> float:
        """Get file lock timeout in seconds"""
        return self.get("file_locking.lock_timeout_seconds", 10.0)

    def get_all_paths(self) -> Dict[str, str]:
        """Get all resolved paths"""
        return self.resolved_paths.copy()

    def save_config(self, filepath: Optional[str] = None):
        """
        Save current configuration to file

        Args:
            filepath: Path to save config (default: self.config_file)
        """
        filepath = filepath or self.config_file

        try:
            with open(filepath, "w") as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved configuration to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False


# ============================================================================
# Testing
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Testing SharedConfigManager...\n")

    # Test with config file
    config = SharedConfigManager("shared_config.json")

    print(f"System ID: {config.get_system_id()}")
    print(f"System Role: {config.get('system_role')}")
    print(f"Deployment Type: {config.get('deployment_type')}")
    print(f"Is Admin: {config.is_admin()}")
    print(f"Is Shared Mode: {config.is_shared_mode()}")
    print(f"File Locking: {config.is_file_locking_enabled()}")

    print("\nResolved Paths:")
    for key, path in config.get_all_paths().items():
        exists = "✓" if os.path.exists(path) else "✗"
        print(f"  {exists} {key:20s} → {path}")

    print("\nFile Paths:")
    for file_key in ["label_queue", "history", "users"]:
        path = config.get_file_path(file_key)
        print(f"  {file_key:20s} → {path}")

    print("\n✓ Configuration loaded successfully")
