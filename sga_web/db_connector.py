import os
import json
import subprocess
from dotenv import load_dotenv

# Load environment variables from predictable paths.
# This keeps SMB credentials available even when the app is launched from project root.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for env_path in (
    os.path.join(BASE_DIR, ".env"),
    os.path.join(os.path.dirname(BASE_DIR), ".env"),
):
    if os.path.exists(env_path):
        load_dotenv(env_path, override=False)


def load_server_config(config_path="server_config.json"):
    """Load server configuration from JSON file"""
    import os

    if os.environ.get("FLASK_ENV") == "development":
        print("[INFO] FLASK_ENV is development. Short-circuiting to local config.")
        return None

    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def ping_server(host):
    """
    Ping the server to check availability.
    Returns True if reachable, False otherwise.
    """
    try:
        # -n 1 for count, -w 1000 for timeout in ms
        cmd = f"ping -n 1 -w 1000 {host}"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5  # nosec B602
        )
        return result.returncode == 0
    except (Exception, subprocess.TimeoutExpired):
        return False


def _try_mount(share_path, db_user, db_password):
    """Helper to attempt mounting a specific path"""
    print(f"[CONN] Attempting to connect to {share_path}...")

    # Check if already connected
    try:
        check_cmd = f"net use {share_path}"
        result = subprocess.run(
            check_cmd, shell=True, capture_output=True, text=True, timeout=10  # nosec B602
        )
        if result.returncode == 0:
            print(f"[OK] Already connected to {share_path}")
            return True
    except Exception as e:
        print(f"[WARN] Error checking connection: {e}")

    # Try to connect
    try:
        cmd = f'net use "{share_path}" /user:{db_user} "{db_password}"'
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10  # nosec B602
        )

        if result.returncode == 0:
            print(f"[OK] Successfully mounted {share_path}")
            return True
        else:
            print(f"[ERROR] Failed to mount {share_path}: {result.stderr.strip()}")
            if "1219" in result.stderr:
                print("[WARN] Multiple connections detected. Attempting to clear...")
                subprocess.run(
                    f'net use "{share_path}" /delete /y', shell=True, timeout=10  # nosec B602
                )
                # Recursive retry logic should be handled by caller or simple retry here
                return False
            return False
    except Exception as e:
        print(f"[ERROR] Exception connecting to share: {e}")
        return False


def mount_share(config):
    """
    Mount the network share with automatic fallback (Hostname -> IP)
    Returns True if successful, False otherwise
    """
    if not config or not config.get("server") or not config.get("database"):
        print("[ERROR] Missing server or database configuration")
        return False

    server = config["server"]

    hostname = server.get("hostname")
    ip_address = server.get("ip_address")
    share_name = server.get("share_name")

    # Get credentials from env
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")

    if not db_user or not db_password:
        print("[ERROR] Missing DB_USER or DB_PASSWORD in .env")
        return False

    # 1. Ping Server by IP (Checks if online)
    if ip_address:
        print(f"[PING] Pinging server {ip_address}...")
        if ping_server(ip_address):
            print(f"[OK] Server {ip_address} is online")
        else:
            print(
                f"[WARN] Server {ip_address} did not respond to ping (might be unreachable or firewall blocking)"
            )
            # We continue anyway to try connecting, as ping might be blocked but SMB allowed

    # 2. Try connecting via Hostname
    if hostname and share_name:
        hostname_path = f"\\\\{hostname}\\{share_name}"
        if _try_mount(hostname_path, db_user, db_password):
            # Update config to use this path for get_db_path logic
            config["database"]["primary_path"] = f"//{hostname}/{share_name}"
            return True

    # 3. If that fails, try connecting via IP Address
    if ip_address and share_name:
        print(
            "[WARN] Hostname connection failed/skipped. Trying IP address fallback..."
        )
        ip_path = f"\\\\{ip_address}\\{share_name}"
        if _try_mount(ip_path, db_user, db_password):
            # Update config to use this path for get_db_path logic
            config["database"]["primary_path"] = f"//{ip_address}/{share_name}"
            return True

    print("[ERROR] All connection attempts failed.")
    return False


def get_db_path(config):
    """
    Get the database path based on configuration and availability
    Returns tuple (path, source)
    """
    import os

    if os.environ.get("FLASK_ENV") == "development":
        return "unified_db", "local_development"

    if not config:
        return "unified_db", "local_default"

    # Try server path
    if config.get("database", {}).get("primary_path"):
        # Convert //server/share to \\server\share format for Windows check
        server_path = config["database"]["primary_path"].replace("/", "\\")
        if not server_path.startswith("\\\\"):
            server_path = "\\\\" + server_path.lstrip("\\")

        # Check if we can access the path (assuming it's already mounted or accessible)
        # We append the actual db file name if it's a directory in the config,
        # but the config says "primary_path" is usually the share root.
        # Let's assume the DB folder is at that path.

        # NOTE: standard unified_db structure
        if os.path.exists(server_path):
            return server_path, "server"
        else:
            print(f"[WARN] Server path {server_path} not accessible")

    # Fallback to local
    if config.get("fallback", {}).get("enabled"):
        local_path = config["fallback"].get("local_database_path", "unified_db")
        print(f"[WARN] Using fallback local database: {local_path}")
        return local_path, "local_fallback"

    return "unified_db", "local_default"
