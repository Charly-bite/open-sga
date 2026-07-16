# Network Share Connection - Quick Reference

## 🔌 Current Status

The SGA system now has network share support infrastructure in place.

## 📋 What's Working

✅ **Configuration System**
   - `shared_config.json` - Configuration with server details
   - `SharedConfigManager` - Path resolution and mount checking
   - `SharedFileManager` - Thread-safe file operations with locking

✅ **Network Management Tools**
   - `network_share_manager.py` - CLI tool for diagnostics and mounting
   - `network_status_widget.py` - GUI widget for status monitoring
   - Auto-generated mount scripts

✅ **Diagnostics**
   - Server reachability testing
   - Mount point verification
   - Read/write access testing
   - Real-time status monitoring

## 🚀 Quick Start Guide

### 1. Check Current Status
```bash
python3 network_share_manager.py --diagnose
```

### 2. Generate Mount Scripts
```bash
python3 network_share_manager.py --generate-scripts
```

This creates:
- `mount_share.sh` - Script to mount the network share
- `sga-credentials.template` - Credentials file template

### 3. Configure Credentials
```bash
# Edit the credentials file
nano sga-credentials.template

# Add your password (replace YOUR_PASSWORD_HERE)
username=sga
password=YOUR_ACTUAL_PASSWORD
domain=WORKGROUP

# Copy to system location
sudo cp sga-credentials.template /etc/sga-credentials
sudo chmod 600 /etc/sga-credentials
```

### 4. Mount the Share
```bash
# Create mount point
sudo mkdir -p /mnt/sga_shared

# Mount the share
./mount_share.sh
```

### 5. Verify Connection
```bash
python3 network_share_manager.py --status
```

## 🔧 Configuration

Edit `shared_config.json`:

```json
{
  "deployment_type": "shared",
  "system_id": "admin1",
  "system_role": "administrator",
  
  "shared_base_path": "/mnt/sga_shared",
  
  "network": {
    "mount_check_enabled": true,
    "mount_path": "/mnt/sga_shared",
    "server_address": "20.0.1.9",
    "share_name": "sga_shared",
    "username": "sga",
    "fallback_to_local": false,
    "connection_timeout_seconds": 5
  }
}
```

### Key Configuration Options

- **server_address**: IP address or hostname of the file server
- **share_name**: Name of the SMB/CIFS share
- **mount_path**: Where to mount the share locally
- **fallback_to_local**: If true, use local files when share unavailable
- **mount_check_enabled**: Verify mount on startup

## 📊 Network Status Widget

The GUI includes a network status indicator:

```python
from network_status_widget import NetworkStatusWidget
from network_share_manager import NetworkShareManager

# Create manager
manager = NetworkShareManager('shared_config.json')

# Create widget (shows colored indicator)
widget = NetworkStatusWidget(parent, manager, on_click=show_details_dialog)
widget.pack()
```

**Status Colors:**
- 🟢 Green: Connected and working
- 🔴 Red: Not connected
- 🟡 Yellow: Connected but has issues
- 🔵 Blue: Checking status
- ⚪ Gray: Monitoring disabled

## 🖥️ Command Reference

### Diagnostics
```bash
# Full diagnostics report
python3 network_share_manager.py --diagnose

# Brief status check
python3 network_share_manager.py --status
```

### Mount Operations
```bash
# Mount the network share
python3 network_share_manager.py --mount

# Mount with custom credentials
python3 network_share_manager.py --mount --credentials /path/to/credentials

# Unmount the share
python3 network_share_manager.py --unmount
```

### Script Generation
```bash
# Generate mount script and credentials template
python3 network_share_manager.py --generate-scripts

# Use custom config file
python3 network_share_manager.py --config custom_config.json --diagnose
```

## 🔐 Security

### Credentials File
The credentials file should have restricted permissions:

```bash
sudo chmod 600 /etc/sga-credentials
sudo chown root:root /etc/sga-credentials
```

### File Permissions on Share
Recommended mount options:
```
rw,file_mode=0664,dir_mode=0775,uid=1000,gid=1000
```

## 🐛 Troubleshooting

### Mount Failed
```bash
# Check if server is reachable
ping 20.0.1.9

# Check if SMB port is open
telnet 20.0.1.9 445

# Install required packages
sudo apt install cifs-utils

# Check system logs
sudo dmesg | grep -i cifs
```

### Permission Denied
```bash
# Check credentials file
cat /etc/sga-credentials

# Test mount manually
sudo mount -t cifs //20.0.1.9/sga_shared /mnt/sga_shared \
  -o credentials=/etc/sga-credentials,rw
```

### Share Becomes Unresponsive
```bash
# Force unmount
sudo umount -l /mnt/sga_shared

# Remount
./mount_share.sh
```

## 📝 Auto-Mount on Boot

Add to `/etc/fstab`:

```
//20.0.1.9/sga_shared /mnt/sga_shared cifs credentials=/etc/sga-credentials,rw,file_mode=0664,dir_mode=0775,uid=1000,gid=1000,_netdev 0 0
```

The `_netdev` option ensures the mount waits for network.

## 🔄 Integration with SGA App

### Automatic Mode (Recommended)
The app automatically uses `SharedConfigManager` when:
1. `shared_config.json` exists
2. `deployment_type` is set to "shared"
3. Network share is mounted

### Manual Mode
For testing without network share:
```python
# Use local configuration
os.rename('shared_config.json', 'shared_config.json.disabled')
```

## 📚 Related Files

- `shared_config.json` - Main configuration
- `shared_config_manager.py` - Configuration handler
- `shared_file_manager.py` - File operations with locking
- `network_share_manager.py` - Network management CLI
- `network_status_widget.py` - GUI status widget
- `mount_share.sh` - Generated mount script
- `sga-credentials.template` - Credentials template

## 🎯 Next Steps

1. **Server Setup**: Run `setup_server.sh` on file server
2. **Data Migration**: Run `migrate_to_shared.py` to copy data
3. **Client Setup**: Run `setup_client.sh` on each client
4. **Testing**: Use diagnostic tools to verify connection
5. **Production**: Enable auto-mount in `/etc/fstab`

## 💡 Tips

- **Test locally first**: Verify the system works with local files
- **One system at a time**: Set up and test each client individually
- **Monitor logs**: Check `/var/log/syslog` for mount issues
- **Backup first**: Always backup data before migration
- **Document passwords**: Store credentials securely

## ❓ Getting Help

Run diagnostics and include output when reporting issues:
```bash
python3 network_share_manager.py --diagnose > network_status.txt
```
