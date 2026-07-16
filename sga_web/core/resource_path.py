#!/usr/bin/env python3
"""
Resource path helper for PyInstaller bundled applications.

When running as a bundled .exe, resources are extracted to a temp folder.
This module provides cross-platform resource path resolution.

Usage:
    from resource_path import get_resource_path, BASE_DIR

    # Get path to an asset
    logo_path = get_resource_path('assets', 'logo.png')

    # Get path to database
    db_path = get_resource_path('unified_db', 'products_master.csv')
"""

import os
import sys


def is_frozen():
    """Check if running as a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_base_dir():
    """Get the base directory for resources."""
    if is_frozen():
        # Running as bundled exe - resources in temp folder
        return sys._MEIPASS
    else:
        # Running as script - resources relative to the project root
        return os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )


def get_app_dir():
    """Get the directory where the application/exe is located.

    Use this for user data files (configs, logs, generated labels)
    that should persist between runs.
    """
    if is_frozen():
        # Running as bundled exe - use exe's directory
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(*path_parts):
    """Get the absolute path to a bundled resource.

    Args:
        *path_parts: Path components (e.g., 'assets', 'logo.png')

    Returns:
        Absolute path to the resource

    Example:
        get_resource_path('assets', 'pictograms', 'llama.png')
    """
    return os.path.join(get_base_dir(), *path_parts)


def get_data_path(*path_parts):
    """Get the absolute path for user data files.

    Use this for files that the user creates/modifies:
    - Generated labels
    - Configuration overrides
    - History files
    - Log files

    Args:
        *path_parts: Path components

    Returns:
        Absolute path in the app directory
    """
    return os.path.join(get_app_dir(), *path_parts)


def ensure_data_dir(*path_parts):
    """Ensure a data directory exists and return its path.

    Args:
        *path_parts: Path components for the directory

    Returns:
        Absolute path to the directory (created if needed)
    """
    path = get_data_path(*path_parts)
    os.makedirs(path, exist_ok=True)
    return path


# Module-level constants for convenience
BASE_DIR = get_base_dir()
APP_DIR = get_app_dir()


# Resource locations
ASSETS_DIR = get_resource_path("assets")
PICTOGRAMS_DIR = get_resource_path("assets", "pictograms")
UNIFIED_DB_DIR = get_resource_path("unified_db")
ORIGINAL_DATA_DIR = get_resource_path("original_data")
IMAGES_DIR = get_resource_path("images")


def get_poppler_path():
    """Get the path to Poppler binaries for pdf2image.

    Searches multiple locations to find Poppler binaries:
    1. Bundled in _MEIPASS/poppler/bin (frozen exe)
    2. Local poppler-24.08.0/Library/bin (development)
    3. poppler/bin relative to executable

    Returns:
        Path to Poppler bin directory, or None if not found
    """
    # Build list of candidate paths
    candidates = []

    if is_frozen():
        # Primary location when bundled as exe
        candidates.append(get_resource_path("poppler", "bin"))
        # Also check relative to executable
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "poppler", "bin"))
        candidates.append(os.path.join(exe_dir, "_internal", "poppler", "bin"))

    # Development paths
    base = get_base_dir()
    candidates.extend(
        [
            os.path.join(base, "poppler-24.08.0", "Library", "bin"),
            os.path.join(base, "poppler", "Library", "bin"),
            os.path.join(base, "poppler", "bin"),
        ]
    )

    # Check each candidate
    for candidate in candidates:
        if os.path.exists(candidate):
            # Verify pdftoppm exists
            pdftoppm = os.path.join(candidate, "pdftoppm.exe")
            if os.path.exists(pdftoppm) or os.path.exists(pdftoppm.replace(".exe", "")):
                return candidate

    return None


# Data locations (user-writable)
GENERATED_LABELS_DIR = ensure_data_dir("generated_labels")
LOGS_DIR = ensure_data_dir("logs")


if __name__ == "__main__":
    # Test the module
    print("=" * 50)
    print("Resource Path Helper - Test")
    print("=" * 50)
    print(f"\nRunning as frozen bundle: {is_frozen()}")
    print(f"\nBase directory (resources): {BASE_DIR}")
    print(f"App directory (user data):  {APP_DIR}")
    print("\nResource paths:")
    print(f"  Assets:      {ASSETS_DIR}")
    print(f"  Pictograms:  {PICTOGRAMS_DIR}")
    print(f"  Unified DB:  {UNIFIED_DB_DIR}")
    print(f"  Images:      {IMAGES_DIR}")
    print("\nData paths:")
    print(f"  Labels:      {GENERATED_LABELS_DIR}")
    print(f"  Logs:        {LOGS_DIR}")

    # Check if key files exist
    print("\nChecking key resources:")
    test_files = [
        ("assets", "logo.png"),
        ("assets", "pictograms", "llama.png"),
        ("unified_db", "products_master.csv"),
    ]
    for parts in test_files:
        path = get_resource_path(*parts)
        exists = "✅" if os.path.exists(path) else "❌"
        print(f"  {exists} {'/'.join(parts)}")
