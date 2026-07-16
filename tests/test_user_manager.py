"""Tests for user_manager.py - JSON fallback auth in dev mode."""

import json
import os
import tempfile
from unittest.mock import patch
from user_manager import UserManager, UserRole


def test_json_fallback_seeds_admin():
    """When SQL is unavailable, a users.json with admin/admin123 is created."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        um = UserManager(users_file=json_path)
        assert os.path.exists(json_path)
        with open(json_path, "r") as f:
            data = json.load(f)
        assert len(data["users"]) == 1
        assert data["users"][0]["username"] == "admin"
        assert "$" in data["users"][0]["password_hash"]


def test_json_fallback_login():
    """Admin can authenticate via JSON fallback when SQL is unavailable."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        um = UserManager(users_file=json_path)
        assert um.authenticate("admin", "admin123") is True
        assert um.get_current_user()["username"] == "admin"
        assert um.get_current_user()["role"] == "admin"


def test_json_fallback_wrong_password():
    """Wrong password is rejected with JSON fallback."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        um = UserManager(users_file=json_path)
        assert um.authenticate("admin", "wrong") is False
        assert um.get_current_user() is None


def test_json_fallback_nonexistent_user():
    """Non-existent user is rejected."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        um = UserManager(users_file=json_path)
        assert um.authenticate("nobody", "admin123") is False


def test_json_fallback_get_user():
    """get_user works with JSON fallback."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        um = UserManager(users_file=json_path)
        user = um.get_user("admin")
        assert user is not None
        assert user["username"] == "admin"
        assert user["role"] == "admin"


def test_json_fallback_get_user_not_found():
    """get_user returns None for non-existent user."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        um = UserManager(users_file=json_path)
        assert um.get_user("nobody") is None


def test_json_fallback_preserves_existing_hash():
    """If users.json already has a valid hash, it's not overwritten."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        # First init - creates the file
        um1 = UserManager(users_file=json_path)
        with open(json_path, "r") as f:
            original_hash = json.load(f)["users"][0]["password_hash"]

        # Second init - should not overwrite
        um2 = UserManager(users_file=json_path)
        with open(json_path, "r") as f:
            current_hash = json.load(f)["users"][0]["password_hash"]

        assert current_hash == original_hash


def test_json_fallback_replaces_placeholder_hash():
    """If users.json has a placeholder hash (xxx), it gets replaced."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        # Write a JSON with a placeholder hash
        data = {
            "users": [
                {
                    "username": "admin",
                    "password_hash": "xxx",
                    "role": "admin",
                    "full_name": "Admin",
                    "is_active": True,
                }
            ]
        }
        with open(json_path, "w") as f:
            json.dump(data, f)

        um = UserManager(users_file=json_path)
        # Now login should work with the new hash
        assert um.authenticate("admin", "admin123") is True


def test_password_hashing_roundtrip():
    """Password hash and verify are consistent."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        um = UserManager(users_file=json_path)
        h = um._hash_password("testpass123")
        assert "$" in h
        assert um._verify_password("testpass123", h) is True
        assert um._verify_password("wrong", h) is False


def test_logout():
    """Logout clears current user."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "users.json")
        um = UserManager(users_file=json_path)
        um.authenticate("admin", "admin123")
        assert um.is_logged_in() is True
        um.logout()
        assert um.is_logged_in() is False
        assert um.get_current_user() is None
