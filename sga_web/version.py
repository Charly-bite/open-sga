"""
SGA Version Module — Single source of truth for application version.

The version is read from git tags at import time.
Usage:
    git tag v2.0.0          # Tag the current commit
    git push origin v2.0.0  # Push the tag to GitHub

At runtime:
    from version import get_version, get_version_display
    get_version()         # "2.0.0"
    get_version_display() # "SGA v2.0.0"
    get_version_full()    # "2.0.0-3-g0985d5b" (includes commit distance)
"""

import os
import subprocess

# Hardcoded fallback — used when git is not available (e.g. deployed without .git)
_FALLBACK_VERSION = "2.0.0"

# Cache the version at module load time (called once, not per-request)
_cached_version = None
_cached_version_full = None


def _read_git_version():
    """Read version from git tags using `git describe --tags`."""
    global _cached_version, _cached_version_full
    try:
        # --tags: use any tag (not just annotated)
        # --always: fallback to short SHA if no tags exist
        raw = (
            subprocess.check_output(
                ["git", "describe", "--tags", "--always"],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )

        if raw.startswith("v"):
            raw = raw[1:]  # Strip leading 'v' → "2.0.0" or "2.0.0-3-g0985d5b"

        _cached_version_full = raw

        # Extract clean semver (everything before the first dash after the version)
        # "2.0.0-3-g0985d5b" → "2.0.0"
        # "2.0.0" → "2.0.0"
        parts = raw.split("-")
        _cached_version = parts[0]

    except Exception:
        _cached_version = _FALLBACK_VERSION
        _cached_version_full = _FALLBACK_VERSION


# Read version on import
_read_git_version()


def get_version():
    """Get the clean semantic version string (e.g. '2.0.0')."""
    return _cached_version


def get_version_full():
    """Get the full version with commit distance (e.g. '2.0.0-3-g0985d5b').
    Returns clean version if on an exact tag."""
    return _cached_version_full


def get_version_display():
    """Get the display string for UI (e.g. 'SGA v2.0.0')."""
    return f"SGA v{_cached_version}"


def get_git_sha():
    """Get the short git SHA for the current commit."""
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"
