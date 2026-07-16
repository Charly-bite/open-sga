#!/usr/bin/env python3
"""
Cross-platform build script for GHS Label System (SGA)
Can be run from Linux to prepare the Windows build, or directly on Windows.

Usage:
    python build_windows.py          # Prepare build (from any OS)
    python build_windows.py --build  # Actually build (must run on Windows)
"""

import os
import sys
import shutil
import subprocess
import argparse

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Files required for the application
REQUIRED_MODULES = [
    "ghs_label_gui.py",
    "smart_label.py",
    "settings_manager.py",
    "generate_ghs_label.py",
    "history_manager.py",
    "user_manager.py",
    "login_dialog.py",
    "user_management_dialog.py",
    "styled_dialogs.py",
    "sga_controller.py",
    "network_share_manager.py",
    "network_status_widget.py",
    "shared_config_manager.py",
    "shared_file_manager.py",
]

REQUIRED_FOLDERS = [
    "assets",
    "unified_db",
    "original_data",
    "images",
]

REQUIRED_CONFIGS = [
    "config_retail_sample.json",
    "mock_barcode_db.json",
    "users.json",
]


def check_prerequisites():
    """Check that all required files exist."""
    print("\n📋 Checking prerequisites...\n")

    missing = []

    # Check modules
    for module in REQUIRED_MODULES:
        path = os.path.join(BASE_DIR, module)
        if os.path.exists(path):
            print(f"  ✅ {module}")
        else:
            print(f"  ❌ {module} - MISSING")
            missing.append(module)

    # Check folders
    print()
    for folder in REQUIRED_FOLDERS:
        path = os.path.join(BASE_DIR, folder)
        if os.path.isdir(path):
            count = len(os.listdir(path))
            print(f"  ✅ {folder}/ ({count} items)")
        else:
            print(f"  ❌ {folder}/ - MISSING")
            missing.append(folder)

    # Check configs
    print()
    for config in REQUIRED_CONFIGS:
        path = os.path.join(BASE_DIR, config)
        if os.path.exists(path):
            print(f"  ✅ {config}")
        else:
            print(f"  ⚠️  {config} - Optional, will use defaults")

    if missing:
        print(f"\n❌ Missing {len(missing)} required files/folders!")
        return False

    print("\n✅ All prerequisites satisfied!")
    return True


def check_python_deps():
    """Check and install Python dependencies."""
    print("\n📦 Checking Python dependencies...\n")

    deps = ["pyinstaller", "pillow", "pandas", "reportlab", "openpyxl"]

    for dep in deps:
        try:
            __import__(dep.replace("-", "_"))
            print(f"  ✅ {dep}")
        except ImportError:
            print(f"  ⬇️  Installing {dep}...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", dep], capture_output=True
            )

    print("\n✅ Dependencies ready!")
    return True


def create_windows_package():
    """Create a folder with all files needed for Windows build."""
    print("\n📁 Creating Windows build package...\n")

    dist_dir = os.path.join(BASE_DIR, "windows_build_package")

    # Clean and create directory
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)

    # Copy Python files
    for module in REQUIRED_MODULES:
        src = os.path.join(BASE_DIR, module)
        if os.path.exists(src):
            shutil.copy2(src, dist_dir)
            print(f"  📄 {module}")

    # Copy folders
    for folder in REQUIRED_FOLDERS:
        src = os.path.join(BASE_DIR, folder)
        if os.path.isdir(src):
            dst = os.path.join(dist_dir, folder)
            shutil.copytree(src, dst)
            print(f"  📁 {folder}/")

    # Copy configs
    for config in REQUIRED_CONFIGS:
        src = os.path.join(BASE_DIR, config)
        if os.path.exists(src):
            shutil.copy2(src, dist_dir)
            print(f"  ⚙️  {config}")

    # Copy build files
    for build_file in ["sga_app.spec", "build_windows.bat", "requirements.txt"]:
        src = os.path.join(BASE_DIR, build_file)
        if os.path.exists(src):
            shutil.copy2(src, dist_dir)
            print(f"  🔧 {build_file}")

    print(f"\n✅ Package created at: {dist_dir}")
    print("\n📋 To build on Windows:")
    print("   1. Copy the 'windows_build_package' folder to a Windows machine")
    print("   2. Install Python 3.8+ from python.org")
    print("   3. Open Command Prompt in that folder")
    print("   4. Run: build_windows.bat")
    print("   5. Find SGA_GHS_Labels.exe in the dist folder")

    return dist_dir


def build_executable():
    """Run PyInstaller to create the executable."""
    print("\n🔨 Building executable...\n")

    if sys.platform != "win32":
        print("⚠️  Note: Building Windows .exe works best on Windows.")
        print("   The generated exe will only run on Windows.\n")

    # Run PyInstaller
    spec_file = os.path.join(BASE_DIR, "sga_app.spec")

    if not os.path.exists(spec_file):
        print("❌ sga_app.spec not found!")
        return False

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec_file, "--clean"], cwd=BASE_DIR
    )

    if result.returncode == 0:
        exe_path = os.path.join(BASE_DIR, "dist", "SGA_GHS_Labels.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print("\n✅ Build successful!")
            print(f"   📦 {exe_path}")
            print(f"   📏 Size: {size_mb:.1f} MB")
            return True

    print("\n❌ Build failed!")
    return False


def main():
    parser = argparse.ArgumentParser(description="Build GHS Label System for Windows")
    parser.add_argument(
        "--build",
        action="store_true",
        help="Actually build the executable (run on Windows)",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Create a package folder to transfer to Windows",
    )
    parser.add_argument("--check", action="store_true", help="Only check prerequisites")

    args = parser.parse_args()

    print("=" * 50)
    print("  GHS Label System - Windows Build Tool")
    print("=" * 50)

    # Always check prerequisites
    if not check_prerequisites():
        sys.exit(1)

    if args.check:
        sys.exit(0)

    if args.package or (not args.build and sys.platform != "win32"):
        # Create package for Windows
        create_windows_package()

    if args.build:
        check_python_deps()
        if not build_executable():
            sys.exit(1)

    if not args.build and not args.package and sys.platform != "win32":
        print("\n💡 Tip: Run with --build on Windows to create the .exe")


if __name__ == "__main__":
    main()
