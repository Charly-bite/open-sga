#!/usr/bin/env python3
"""
Start SGA development web server
Connects to database on 192.168.2.237 via SMB share
"""

import os
import sys


def check_dependencies():
    """Check if all required packages are installed"""
    print("🔍 Checking dependencies...")

    required = [
        "flask",
        "flask_login",
        "pandas",
        "reportlab",
        "PIL",
    ]

    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print("   Installing: pip install -r sga_web/requirements.txt")
        return False

    print("✅ All dependencies installed")
    return True


def check_database():
    """Check if database is accessible"""
    print("\n🔍 Checking database connection...")

    try:
        from database_client import DatabaseClient

        client = DatabaseClient()
        if client.connect():
            db_path = client.get_database_path()
            print(f"✅ Database accessible at: {db_path}")
            return True
        else:
            print("❌ Could not connect to database")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def start_web_server():
    """Start the Flask development server"""
    print("\n🚀 Starting SGA web server...")
    print("=" * 60)

    os.chdir(os.path.join(os.path.dirname(__file__), "sga_web"))
    sys.path.insert(0, os.getcwd())

    # Use Flask's development server
    # For production, use: gunicorn app:app
    try:
        import flask
        from app import create_app

        app = create_app()

        print("✅ Application created")
        print(f"📝 Environment: {app.config.get('ENV', 'development')}")
        print()
        print("=" * 60)
        print("🎉 Web Server Starting")
        print("=" * 60)
        print("Address: http://192.168.2.172:5004")
        print("Local:   http://localhost:5004")
        print()
        print("Press CTRL+C to stop the server")
        print("=" * 60)
        print()

        # Run with debug=True for development
        app.run(
            host="0.0.0.0",
            port=5004,
            debug=False,  # Set to True for auto-reload on code changes
            use_reloader=False,  # Disable reloader to avoid double initialization
        )

    except ImportError as e:
        print(f"❌ Error importing Flask: {e}")
        print("   Install dependencies: pip install -r sga_web/requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("SGA Development Web Server Startup")
    print("=" * 60)
    print("Machine: 192.168.2.172")
    print("Database: 192.168.2.187/SGA_Database (SQL)")
    print()

    # Check dependencies
    if not check_dependencies():
        return False

    # Check database
    if not check_database():
        print("\n⚠️  Database not available")
        print("    The application will start but may use local fallback")

    # Start server
    try:
        return start_web_server()
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
