#!/usr/bin/env python3
"""
User Management System for SGA
Handles authentication, permissions, and user administration

Auth Source: SQL Server (single source of truth)
JSON backup: Written on every save as disaster-recovery export only — never read for auth.
"""

import json
import os
import hashlib
import secrets
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User permission levels"""

    ADMIN = "admin"  # Full access: user management, add/edit chemicals, print labels
    OPERATOR = (
        "operator"  # Can print labels and scan products, but NOT add/edit chemicals
    )
    VIEWER = "viewer"  # Read-only access, can only view data


class UserManager:
    """Manages user authentication and permissions — SQL-backed"""

    def __init__(self, users_file: str = "users.json"):
        self._lock = threading.RLock()
        self.users_file = users_file  # JSON backup path (write-only export)
        self.sql_engine = None
        try:
            from database_client import DatabaseClient

            client = DatabaseClient()
            if client.connect():
                self.sql_engine = client.get_sql_engine()
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Warning initializing DB in user_manager: {e}")

        self._ensure_defaults()
        self._current_user = None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _ensure_defaults(self):
        """Ensure the SGA_Users table has at least one admin account."""
        if self.sql_engine is None:
            logger.error(
                "SQL engine is not available — falling back to JSON user store"
            )
            self._ensure_json_defaults()
            return

        from sqlalchemy import text

        try:
            with self.sql_engine.begin() as conn:
                # Ensure table exists (idempotent)
                conn.execute(text("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SGA_Users' AND xtype='U')
                BEGIN
                    CREATE TABLE SGA_Users (
                        username NVARCHAR(50) PRIMARY KEY,
                        password_hash NVARCHAR(255) NOT NULL,
                        role NVARCHAR(50) NOT NULL,
                        full_name NVARCHAR(100),
                        email NVARCHAR(100),
                        warehouse NVARCHAR(50),
                        created_at DATETIME2,
                        last_login DATETIME2,
                        is_active BIT DEFAULT 1,
                        must_change_password BIT DEFAULT 0
                    )
                END
                """))

                # Check if any admin exists
                row = conn.execute(
                    text("SELECT COUNT(*) FROM SGA_Users WHERE role = 'admin'")
                ).scalar()

                if row == 0:
                    # Seed a default admin
                    pwd_hash = self._hash_password("admin123")
                    conn.execute(
                        text("""
                        INSERT INTO SGA_Users
                            (username, password_hash, role, full_name, email, warehouse,
                             created_at, is_active, must_change_password)
                        VALUES
                            (:u, :p, 'admin', 'Administrator', '', '',
                             :now, 1, 1)
                    """),
                        {
                            "u": "admin",
                            "p": pwd_hash,
                            "now": datetime.now().isoformat(),
                        },
                    )
                    print("⚠️  Default admin account created in SQL")
                    print("   Username: admin")
                    print("   Password: admin123")
                    print("   Please change this password immediately!")
        except Exception as e:
            logger.error(f"Error in _ensure_defaults: {e}")

    def _ensure_json_defaults(self):
        """Seed a JSON user store with a default admin when SQL is unavailable."""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                users = data.get("users", [])
                # Check if admin has a valid hash (not a placeholder)
                for user in users:
                    if user["username"] == "admin" and "$" in user.get(
                        "password_hash", ""
                    ):
                        return  # Already seeded with a proper hash

            # Create / reseed the default admin
            pwd_hash = self._hash_password("admin123")
            data = {
                "users": [
                    {
                        "username": "admin",
                        "password_hash": pwd_hash,
                        "role": "admin",
                        "full_name": "Administrator",
                        "email": "",
                        "warehouse": "",
                        "created_at": datetime.now().isoformat(),
                        "last_login": None,
                        "is_active": True,
                        "must_change_password": False,
                    }
                ]
            }
            os.makedirs(os.path.dirname(os.path.abspath(self.users_file)), exist_ok=True)
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print("⚠️  Default admin account created in JSON (dev mode)")
            print("   Username: admin")
            print("   Password: admin123")
        except Exception as e:
            logger.error(f"Error creating JSON defaults: {e}")

    # ------------------------------------------------------------------
    # Data Access — SQL is the single source of truth
    # ------------------------------------------------------------------

    def _load_data(self) -> Dict[str, Any]:
        """Load users from SQL database, falling back to JSON in dev mode."""
        # Lazy retry: if SQL engine wasn't available at init, try again now
        if self.sql_engine is None:
            try:
                from database_client import DatabaseClient

                client = DatabaseClient()
                if client.connect():
                    self.sql_engine = client.get_sql_engine()
                    if self.sql_engine:
                        logger.info("UserManager: SQL engine acquired on retry")
            except Exception:
                pass

        if self.sql_engine is None:
            return self._load_json_fallback()

        from sqlalchemy import text

        try:
            with self.sql_engine.connect() as conn:
                result = conn.execute(text("SELECT * FROM SGA_Users"))
                users_list = []
                for row in result:
                    user = dict(row._mapping)

                    # Format dates back to string for backwards compatibility
                    if user.get("created_at"):
                        if hasattr(user["created_at"], "isoformat"):
                            user["created_at"] = user["created_at"].isoformat()
                        else:
                            user["created_at"] = str(user["created_at"])

                    if user.get("last_login"):
                        if hasattr(user["last_login"], "isoformat"):
                            user["last_login"] = user["last_login"].isoformat()
                        else:
                            user["last_login"] = str(user["last_login"])

                    # Format booleans explicitly
                    if "is_active" in user:
                        user["is_active"] = bool(user["is_active"])
                    if "must_change_password" in user:
                        user["must_change_password"] = bool(
                            user["must_change_password"]
                        )

                    # Handle potential nulls
                    if not user.get("email"):
                        user["email"] = ""
                    if not user.get("warehouse"):
                        user["warehouse"] = ""

                    users_list.append(user)
                return {"users": users_list}
        except Exception as e:
            logger.error(f"SQL User Load Error: {e}")
            return {"users": []}

    def _load_json_fallback(self) -> Dict[str, Any]:
        """Load users from JSON file when SQL is unavailable (dev mode)."""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"JSON fallback load error: {e}")
        return {"users": []}

    def _save_data(self, data: Dict[str, Any]):
        """Save users to SQL database. Also exports a JSON backup."""
        # 1. Write JSON as a one-way disaster-recovery backup
        self._export_json_backup(data)

        # 2. Write to SQL (authoritative)
        if self.sql_engine is None:
            logger.error("SQL engine unavailable — cannot save users")
            return

        from sqlalchemy import text

        try:
            users_data = data.get("users", [])
            if not users_data:
                return

            with self.sql_engine.begin() as conn:
                db_users = conn.execute(
                    text("SELECT username FROM SGA_Users")
                ).fetchall()
                db_usernames = [row[0].lower() for row in db_users]

                for user in users_data:
                    username = user.get("username")

                    pwd = user.get("password_hash")
                    role = user.get("role", "viewer")
                    full_name = user.get("full_name", username)
                    email = user.get("email", "")
                    warehouse = user.get("warehouse", "")

                    created_at = user.get("created_at")
                    last_login = user.get("last_login")

                    is_active = 1 if user.get("is_active", True) else 0
                    must_change = 1 if user.get("must_change_password", False) else 0

                    params = {
                        "username": username,
                        "pwd": pwd,
                        "role": role,
                        "full_name": full_name,
                        "email": email,
                        "warehouse": warehouse,
                        "created_at": created_at,
                        "last_login": last_login,
                        "is_active": is_active,
                        "must_change": must_change,
                    }

                    if username.lower() not in db_usernames:
                        conn.execute(
                            text("""
                        INSERT INTO SGA_Users (username, password_hash, role, full_name, email, warehouse, created_at, last_login, is_active, must_change_password)
                        VALUES (:username, :pwd, :role, :full_name, :email, :warehouse, :created_at, :last_login, :is_active, :must_change)
                        """),
                            params,
                        )
                    else:
                        conn.execute(
                            text("""
                        UPDATE SGA_Users
                        SET password_hash=:pwd, role=:role, full_name=:full_name, email=:email,
                            warehouse=:warehouse, last_login=:last_login, is_active=:is_active, must_change_password=:must_change
                        WHERE username = :username
                        """),
                            params,
                        )
        except Exception as e:
            logger.error(f"SQL User Save Error: {e}")

    def _export_json_backup(self, data: Dict[str, Any]):
        """Write a JSON snapshot for disaster-recovery (never read for auth)."""
        try:
            backup_path = self.users_file
            os.makedirs(os.path.dirname(os.path.abspath(backup_path)), exist_ok=True)

            # Create .bak before overwriting
            if os.path.exists(backup_path):
                try:
                    import shutil

                    shutil.copy2(backup_path, f"{backup_path}.bak")
                except Exception:
                    pass

            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"JSON backup write error (non-critical): {e}")

    # ------------------------------------------------------------------
    # Password Hashing
    # ------------------------------------------------------------------

    def _hash_password(self, password: str, salt: Optional[str] = None) -> str:
        """Hash password with salt using SHA-256"""
        if salt is None:
            salt = secrets.token_hex(16)

        # Combine password and salt
        combined = f"{password}{salt}".encode("utf-8")
        hashed = hashlib.sha256(combined).hexdigest()

        # Return format: salt$hash
        return f"{salt}${hashed}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash"""
        try:
            # Legacy support for old format without salt
            if "$" not in stored_hash:
                return (
                    self._hash_password(password, "default_salt")
                    == f"default_salt${stored_hash}"
                )

            # New format: salt$hash
            salt, expected_hash = stored_hash.split("$", 1)
            actual_hash = self._hash_password(password, salt).split("$", 1)[1]
            return actual_hash == expected_hash
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate user with username and password

        Returns:
            bool: True if authentication successful, False otherwise
        """
        data = self._load_data()

        for user in data.get("users", []):
            if user["username"].lower() == username.lower() and user.get(
                "is_active", True
            ):
                if self._verify_password(password, user["password_hash"]):
                    # Update last login directly in SQL
                    self._update_last_login(username)

                    # Store current user (without sensitive data)
                    self._current_user = {
                        "username": user["username"],
                        "role": user["role"],
                        "full_name": user.get("full_name", user["username"]),
                        "warehouse": user.get("warehouse", ""),
                        "must_change_password": user.get("must_change_password", False),
                    }
                    return True

        return False

    def _update_last_login(self, username: str):
        """Update last_login timestamp directly in SQL (avoids full save cycle)."""
        if self.sql_engine is None:
            return
        from sqlalchemy import text

        try:
            with self.sql_engine.begin() as conn:
                conn.execute(
                    text("UPDATE SGA_Users SET last_login = :now WHERE username = :u"),
                    {"now": datetime.now().isoformat(), "u": username},
                )
        except Exception as e:
            logger.debug(f"Failed to update last_login for {username}: {e}")

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get currently logged-in user"""
        return self._current_user

    def logout(self):
        """Logout current user"""
        self._current_user = None

    def is_logged_in(self) -> bool:
        """Check if a user is logged in"""
        return self._current_user is not None

    def has_permission(
        self, required_role: UserRole, requesting_user: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if user has required permission level"""
        user_data = requesting_user

        if user_data is None:
            if not self.is_logged_in():
                return False
            user_data = self._current_user

        if user_data is None:
            return False

        user_role = UserRole(user_data["role"])

        # Admin has all permissions
        if user_role == UserRole.ADMIN:
            return True

        # Operator has operator and viewer permissions
        if user_role == UserRole.OPERATOR and required_role in [
            UserRole.OPERATOR,
            UserRole.VIEWER,
        ]:
            return True

        # Viewer only has viewer permissions
        if user_role == UserRole.VIEWER and required_role == UserRole.VIEWER:
            return True

        return False

    # ------------------------------------------------------------------
    # User CRUD
    # ------------------------------------------------------------------

    def create_user(
        self,
        username: str,
        password: str,
        role: UserRole,
        full_name: str = "",
        email: str = "",
        warehouse: str = "",
        requesting_user: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, str]:
        """
        Create a new user (admin only)

        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.has_permission(UserRole.ADMIN, requesting_user):
            return False, "Permission denied: Admin access required"

        # Validate username
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters"

        # Check if user exists
        data = self._load_data()
        for user in data["users"]:
            if user["username"].lower() == username.lower():
                return False, "Username already exists"

        # Validate password
        if len(password) < 6:
            return False, "Password must be at least 6 characters"

        # Create new user
        new_user = {
            "username": username,
            "password_hash": self._hash_password(password),
            "role": role.value,
            "full_name": full_name or username,
            "email": email,
            "warehouse": warehouse,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_active": True,
            "must_change_password": False,
        }

        data["users"].append(new_user)
        self._save_data(data)

        return True, f"User '{username}' created successfully"

    def update_user(
        self, username: str, requesting_user: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple[bool, str]:
        """
        Update user details (admin only, or self for password change)

        Allowed kwargs: password, role, full_name, email, is_active, warehouse
        """
        data = self._load_data()

        # Find user
        user_index = None
        for i, user in enumerate(data["users"]):
            if user["username"].lower() == username.lower():
                user_index = i
                break

        if user_index is None:
            return False, "User not found"

        # Determine who is requesting
        requester = (
            requesting_user
            if requesting_user
            else (self._current_user if self.is_logged_in() else None)
        )

        # Permission check
        is_self_password_change = (
            requester
            and requester["username"].lower() == username.lower()
            and len(kwargs) == 1
            and "password" in kwargs
        )

        if not is_self_password_change and not self.has_permission(
            UserRole.ADMIN, requesting_user
        ):
            return False, "Permission denied: Admin access required"

        # Update fields
        user = data["users"][user_index]

        if "password" in kwargs:
            if len(kwargs["password"]) < 6:
                return False, "Password must be at least 6 characters"
            user["password_hash"] = self._hash_password(kwargs["password"])
            user["must_change_password"] = False

        if "role" in kwargs and self.has_permission(UserRole.ADMIN, requesting_user):
            user["role"] = (
                kwargs["role"].value
                if isinstance(kwargs["role"], UserRole)
                else kwargs["role"]
            )

        if "full_name" in kwargs:
            user["full_name"] = kwargs["full_name"]

        if "email" in kwargs:
            user["email"] = kwargs["email"]

        if "warehouse" in kwargs:
            user["warehouse"] = kwargs["warehouse"]

        if "is_active" in kwargs and self.has_permission(
            UserRole.ADMIN, requesting_user
        ):
            user["is_active"] = kwargs["is_active"]

        self._save_data(data)

        # Update current user if it's self-update
        if (
            self._current_user
            and self._current_user["username"].lower() == username.lower()
        ):
            self._current_user["full_name"] = user.get("full_name", username)
            self._current_user["role"] = user["role"]

        return True, f"User '{username}' updated successfully"

    def delete_user(
        self, username: str, requesting_user: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, str]:
        """Delete a user (admin only, cannot delete self)"""
        if not self.has_permission(UserRole.ADMIN, requesting_user):
            return False, "Permission denied: Admin access required"

        requester = (
            requesting_user
            if requesting_user
            else (self._current_user if self.is_logged_in() else None)
        )

        if requester and requester["username"].lower() == username.lower():
            return False, "Cannot delete your own account"

        # Delete directly from SQL
        if self.sql_engine is None:
            return False, "SQL engine unavailable"

        from sqlalchemy import text

        try:
            with self.sql_engine.begin() as conn:
                result = conn.execute(
                    text("DELETE FROM SGA_Users WHERE LOWER(username) = :u"),
                    {"u": username.lower()},
                )

                if result.rowcount == 0:
                    return False, "User not found"

            # Refresh JSON backup
            data = self._load_data()
            self._export_json_backup(data)

            return True, f"User '{username}' deleted successfully"
        except Exception as e:
            logger.error(f"SQL User Delete Error: {e}")
            return False, f"Database error: {e}"

    # ------------------------------------------------------------------
    # User queries
    # ------------------------------------------------------------------

    def list_users(
        self, requesting_user: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """List all users (admin only, or current user for self)"""
        user_data = requesting_user if requesting_user else self._current_user

        if not user_data:
            return []

        data = self._load_data()
        users = data.get("users", [])

        # Remove sensitive data
        safe_users = []
        for user in users:
            safe_user = {
                "username": user["username"],
                "role": user["role"],
                "full_name": user.get("full_name", user["username"]),
                "email": user.get("email", ""),
                "warehouse": user.get("warehouse", ""),
                "created_at": user.get("created_at", ""),
                "last_login": user.get("last_login"),
                "is_active": user.get("is_active", True),
            }

            # Admin sees all, others see only themselves
            if self.has_permission(UserRole.ADMIN, requesting_user):
                safe_users.append(safe_user)
            elif user_data["username"].lower() == user["username"].lower():
                safe_users.append(safe_user)

        return safe_users

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Direct user retrieval for Flask-Login"""
        data = self._load_data()
        for user in data.get("users", []):
            if user["username"].lower() == username.lower():
                return {
                    "username": user["username"],
                    "role": user["role"],
                    "full_name": user.get("full_name", user["username"]),
                    "email": user.get("email", ""),
                    "warehouse": user.get("warehouse", ""),
                    "created_at": user.get("created_at", ""),
                    "last_login": user.get("last_login"),
                    "is_active": user.get("is_active", True),
                }
        return None

    def get_user_info(
        self,
        username: Optional[str] = None,
        requesting_user: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get user information (admin or self only)"""
        user_data = requesting_user if requesting_user else self._current_user

        if not user_data:
            return None

        # Default to current user
        if username is None:
            username = user_data["username"]

        if username is None:
            return None

        # Permission check
        is_self = user_data["username"].lower() == username.lower()
        if not is_self and not self.has_permission(UserRole.ADMIN, requesting_user):
            return None

        users = self.list_users()
        for user in users:
            if user["username"].lower() == username.lower():
                return user

        return None


if __name__ == "__main__":
    # Testing
    um = UserManager("test_users.json")

    print("Testing authentication...")
    if um.authenticate("admin", "admin123"):
        print("✓ Admin login successful")
        print(f"  Current user: {um.get_current_user()}")

        # Test user creation
        print("\nTesting user creation...")
        success, msg = um.create_user(
            "operator1", "pass123", UserRole.OPERATOR, "Juan Pérez"
        )
        print(f"  {msg}")

        success, msg = um.create_user(
            "viewer1", "pass123", UserRole.VIEWER, "María López"
        )
        print(f"  {msg}")

        # List users
        print("\nAll users:")
        for user in um.list_users():
            print(f"  - {user['username']} ({user['role']}): {user['full_name']}")
    else:
        print("✗ Login failed")
