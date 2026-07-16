#!/usr/bin/env python3
"""
Network Share Manager for SGA System
Provides diagnostics, mount/unmount, and connection testing
"""

import os
import sys
import json
import subprocess
import logging
from typing import Dict, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class NetworkShareManager:
    """Manages network share connections for SGA system"""

    def __init__(self, config_file: str = "shared_config.json"):
        """
        Initialize network share manager

        Args:
            config_file: Path to shared configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.mount_path = self.config.get("network", {}).get(
            "mount_path", "/mnt/sga_shared"
        )
        self.server_path = self._get_server_path()

    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            logger.warning(f"Config file not found: {self.config_file}")
            return {}

        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    def _get_server_path(self) -> Optional[str]:
        """Extract server path from shared_base_path"""
        base_path = self.config.get("shared_base_path", "")

        # If it starts with /mnt/, extract server info
        if base_path.startswith("/mnt/"):
            return base_path

        # Check if there's explicit server config
        network = self.config.get("network", {})
        server = network.get("server_address")
        share = network.get("share_name", "sga_shared")

        if server:
            return f"//{server}/{share}"

        return None

    def check_status(self) -> Dict:
        """
        Check current network share status

        Returns:
            Dictionary with status information
        """
        status = {
            "mount_point_exists": False,
            "is_mounted": False,
            "mount_type": None,
            "server_reachable": False,
            "can_read": False,
            "can_write": False,
            "config_valid": False,
            "mount_path": self.mount_path,
        }

        # Check if mount point directory exists
        status["mount_point_exists"] = os.path.exists(self.mount_path)

        # Check if actually mounted
        status["is_mounted"] = self._is_mounted(self.mount_path)

        if status["is_mounted"]:
            # Get mount type
            status["mount_type"] = self._get_mount_type(self.mount_path)

            # Test read access
            status["can_read"] = self._test_read_access(self.mount_path)

            # Test write access
            status["can_write"] = self._test_write_access(self.mount_path)

        # Check server reachability
        if self.server_path:
            status["server_reachable"] = self._test_server_reachable()
            status["config_valid"] = True

        return status

    def _is_mounted(self, path: str) -> bool:
        """Check if path is a mount point"""
        try:
            result = subprocess.run(
                ["mountpoint", "-q", path], capture_output=True, timeout=2
            )
            return result.returncode == 0
        except Exception:
            # Fallback method
            try:
                return os.path.ismount(path)
            except Exception:
                return False

    def _get_mount_type(self, path: str) -> Optional[str]:
        """Get filesystem type of mount"""
        try:
            result = subprocess.run(
                ["stat", "-f", "-c", "%T", path],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        # Fallback: check mount command
        try:
            result = subprocess.run(
                ["mount"], capture_output=True, text=True, timeout=2
            )
            for line in result.stdout.split("\n"):
                if path in line:
                    if "cifs" in line.lower():
                        return "cifs"
                    elif "nfs" in line.lower():
                        return "nfs"
        except Exception:
            pass

        return None

    def _test_read_access(self, path: str) -> bool:
        """Test if we can read from the mount"""
        try:
            os.listdir(path)
            return True
        except Exception:
            return False

    def _test_write_access(self, path: str) -> bool:
        """Test if we can write to the mount"""
        test_file = os.path.join(path, ".sga_write_test")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except Exception:
            return False

    def _test_server_reachable(self) -> bool:
        """Test if server is reachable"""
        network = self.config.get("network", {})
        server = network.get("server_address")

        if not server:
            return False

        # Remove protocol prefix if present
        server_ip = server.replace("//", "").split("/")[0]

        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", server_ip],
                capture_output=True,
                timeout=3,
            )
            return result.returncode == 0
        except Exception:
            return False

    def print_diagnostics(self):
        """Print detailed diagnostic information"""
        print("=" * 70)
        print("SGA NETWORK SHARE DIAGNOSTICS")
        print("=" * 70)

        status = self.check_status()

        print("\n📁 Mount Configuration:")
        print(f"   Config File: {self.config_file}")
        print(f"   Mount Point: {status['mount_path']}")
        print(f"   Server Path: {self.server_path or 'Not configured'}")

        print("\n🔍 Status Checks:")
        print(f"   ✓ Config Valid: {'YES' if status['config_valid'] else 'NO'}")
        print(
            f"   ✓ Mount Point Exists: {'YES' if status['mount_point_exists'] else 'NO'}"
        )
        print(f"   ✓ Currently Mounted: {'YES' if status['is_mounted'] else 'NO'}")

        if status["is_mounted"]:
            print(f"   ✓ Mount Type: {status['mount_type'] or 'Unknown'}")
            print(f"   ✓ Can Read: {'YES' if status['can_read'] else 'NO'}")
            print(f"   ✓ Can Write: {'YES' if status['can_write'] else 'NO'}")

        if status["config_valid"]:
            print(
                f"   ✓ Server Reachable: {'YES' if status['server_reachable'] else 'NO'}"
            )

        print("\n💡 Recommendations:")
        if not status["config_valid"]:
            print("   → Update shared_config.json with server details")
        elif not status["mount_point_exists"]:
            print(f"   → Create mount point: sudo mkdir -p {self.mount_path}")
        elif not status["is_mounted"]:
            if status["server_reachable"]:
                print("   → Mount the share: sudo ./mount_share.sh")
            else:
                print("   → Check network connection to server")
        elif not status["can_read"] or not status["can_write"]:
            print("   → Check file permissions on the share")
        else:
            print("   ✅ All checks passed! Network share is working properly.")

        print("\n" + "=" * 70)

    def mount_share(self, credentials_file: str = None) -> Tuple[bool, str]:
        """
        Mount the network share

        Args:
            credentials_file: Path to credentials file (optional)

        Returns:
            (success, message)
        """
        if self._is_mounted(self.mount_path):
            return True, "Share already mounted"

        network = self.config.get("network", {})
        server = network.get("server_address")
        share = network.get("share_name", "sga_shared")

        if not server:
            return False, "Server address not configured in shared_config.json"

        # Create mount point if needed
        if not os.path.exists(self.mount_path):
            try:
                os.makedirs(self.mount_path, exist_ok=True)
            except PermissionError:
                return False, f"Need sudo to create {self.mount_path}"

        # Build mount command
        mount_cmd = [
            "sudo",
            "mount",
            "-t",
            "cifs",
            f"//{server}/{share}",
            self.mount_path,
        ]

        # Add options
        options = ["rw", "file_mode=0664", "dir_mode=0775"]

        if credentials_file and os.path.exists(credentials_file):
            options.append(f"credentials={credentials_file}")

        mount_cmd.extend(["-o", ",".join(options)])

        try:
            result = subprocess.run(
                mount_cmd, capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                return True, "Share mounted successfully"
            else:
                return False, f"Mount failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Mount operation timed out"
        except Exception as e:
            return False, f"Mount error: {e}"

    def unmount_share(self) -> Tuple[bool, str]:
        """
        Unmount the network share

        Returns:
            (success, message)
        """
        if not self._is_mounted(self.mount_path):
            return True, "Share not mounted"

        try:
            result = subprocess.run(
                ["sudo", "umount", self.mount_path],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True, "Share unmounted successfully"
            else:
                return False, f"Unmount failed: {result.stderr}"

        except Exception as e:
            return False, f"Unmount error: {e}"

    def generate_mount_script(self, output_file: str = "mount_share.sh"):
        """Generate a shell script for mounting the share"""
        network = self.config.get("network", {})
        server = network.get("server_address", "SERVER_IP")
        share = network.get("share_name", "sga_shared")
        username = network.get("username", "sga")

        script = f"""#!/bin/bash
# SGA Network Share Mount Script
# Generated automatically - customize as needed

set -e

MOUNT_POINT="{self.mount_path}"
SERVER="{server}"
SHARE="{share}"
USERNAME="{username}"
CREDENTIALS_FILE="/etc/sga-credentials"

echo "Mounting SGA Network Share..."

# Check if already mounted
if mountpoint -q "$MOUNT_POINT"; then
    echo "✓ Share already mounted at $MOUNT_POINT"
    exit 0
fi

# Create mount point if needed
if [ ! -d "$MOUNT_POINT" ]; then
    echo "Creating mount point: $MOUNT_POINT"
    sudo mkdir -p "$MOUNT_POINT"
fi

# Check if credentials file exists
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "⚠️  Credentials file not found: $CREDENTIALS_FILE"
    echo "Creating template credentials file..."
    
    sudo tee "$CREDENTIALS_FILE" > /dev/null <<EOF
username=$USERNAME
password=YOUR_PASSWORD_HERE
domain=WORKGROUP
EOF
    sudo chmod 600 "$CREDENTIALS_FILE"
    
    echo "❌ Please edit $CREDENTIALS_FILE and add the correct password"
    echo "Then run this script again"
    exit 1
fi

# Mount the share
echo "Mounting //$SERVER/$SHARE to $MOUNT_POINT..."
sudo mount -t cifs "//$SERVER/$SHARE" "$MOUNT_POINT" \\
    -o credentials="$CREDENTIALS_FILE",rw,file_mode=0664,dir_mode=0775,uid=$(id -u),gid=$(id -g)

if mountpoint -q "$MOUNT_POINT"; then
    echo "✅ Share mounted successfully!"
    echo "Testing access..."
    ls -la "$MOUNT_POINT" | head -5
else
    echo "❌ Mount failed"
    exit 1
fi
"""

        try:
            with open(output_file, "w") as f:
                f.write(script)
            os.chmod(output_file, 0o755)
            return True, f"Created mount script: {output_file}"
        except Exception as e:
            return False, f"Error creating script: {e}"

    def generate_credentials_template(
        self, output_file: str = "sga-credentials.template"
    ):
        """Generate credentials file template"""
        network = self.config.get("network", {})
        username = network.get("username", "sga")

        template = f"""# SGA Network Share Credentials
# Copy this file to /etc/sga-credentials and set permissions:
# sudo cp {output_file} /etc/sga-credentials
# sudo chmod 600 /etc/sga-credentials

username={username}
password=YOUR_PASSWORD_HERE
domain=WORKGROUP
"""

        try:
            with open(output_file, "w") as f:
                f.write(template)
            return True, f"Created credentials template: {output_file}"
        except Exception as e:
            return False, f"Error creating template: {e}"


def main():
    """CLI interface for network share management"""
    import argparse

    parser = argparse.ArgumentParser(
        description="SGA Network Share Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --status              Show current status
  %(prog)s --diagnose            Run full diagnostics
  %(prog)s --mount               Mount the network share
  %(prog)s --unmount             Unmount the network share
  %(prog)s --generate-scripts    Create mount script and credentials template
        """,
    )

    parser.add_argument(
        "--config",
        default="shared_config.json",
        help="Configuration file (default: shared_config.json)",
    )
    parser.add_argument("--status", action="store_true", help="Show brief status")
    parser.add_argument("--diagnose", action="store_true", help="Run full diagnostics")
    parser.add_argument("--mount", action="store_true", help="Mount the network share")
    parser.add_argument(
        "--unmount", action="store_true", help="Unmount the network share"
    )
    parser.add_argument(
        "--generate-scripts",
        action="store_true",
        help="Generate mount script and credentials template",
    )
    parser.add_argument("--credentials", help="Path to credentials file (for --mount)")

    args = parser.parse_args()

    manager = NetworkShareManager(args.config)

    if args.diagnose:
        manager.print_diagnostics()

    elif args.status:
        status = manager.check_status()
        print(f"Mount Point: {status['mount_path']}")
        print(f"Mounted: {'YES' if status['is_mounted'] else 'NO'}")
        if status["is_mounted"]:
            print(f"Type: {status['mount_type']}")
            print(f"Read: {'OK' if status['can_read'] else 'FAIL'}")
            print(f"Write: {'OK' if status['can_write'] else 'FAIL'}")

    elif args.mount:
        success, message = manager.mount_share(args.credentials)
        print(message)
        sys.exit(0 if success else 1)

    elif args.unmount:
        success, message = manager.unmount_share()
        print(message)
        sys.exit(0 if success else 1)

    elif args.generate_scripts:
        success1, msg1 = manager.generate_mount_script()
        success2, msg2 = manager.generate_credentials_template()
        print(msg1)
        print(msg2)
        if success1 and success2:
            print("\n✅ Scripts generated successfully!")
            print("Next steps:")
            print("  1. Edit sga-credentials.template with your password")
            print("  2. sudo cp sga-credentials.template /etc/sga-credentials")
            print("  3. sudo chmod 600 /etc/sga-credentials")
            print("  4. ./mount_share.sh")
        sys.exit(0 if (success1 and success2) else 1)

    else:
        # Default: show diagnostics
        manager.print_diagnostics()


if __name__ == "__main__":
    main()
