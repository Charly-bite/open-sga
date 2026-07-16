# Network Share Setup - Quick Start

## 🚀 Complete Setup Script Created!

I've created a comprehensive setup script that will configure everything automatically.

## 📋 What the Script Does

The script will guide you through:

1. **✓ Check Prerequisites** - Verify/install required packages (cifs-utils)
2. **✓ Create Mount Point** - Create `/mnt/sga_shared` directory
3. **✓ Configure Credentials** - Set up authentication securely
4. **✓ Mount Network Share** - Connect to server at 20.0.1.9
5. **✓ Test Permissions** - Verify read/write access
6. **✓ Run Diagnostics** - Python integration tests
7. **✓ GUI Integration Test** - Verify GUI can access the share
8. **✓ Auto-Mount Setup** (optional) - Configure mount on boot

## 🎯 How to Run

### Step 1: Make executable (if needed)
```bash
chmod +x setup_network_share.sh
```

### Step 2: Run the script
```bash
sudo ./setup_network_share.sh
```

### Step 3: Follow the prompts
The script will ask you for:
- Network share password (for user 'sga')
- Domain (default: WORKGROUP)
- Whether to configure auto-mount on boot

## 🔐 What You Need

Before running, make sure you have:
- ✓ Server IP: **20.0.1.9** (already configured)
- ✓ Share name: **sga_shared** (already configured)
- ✓ Username: **sga** (default, can change)
- ❓ **Password**: You'll need the actual password for the sga user

## ✨ Features

### Interactive & Safe
- Checks if already configured
- Asks before overwriting existing settings
- Creates backups of important files
- Validates each step before proceeding

### Comprehensive Testing
- Server reachability test (ping)
- Mount point creation and permissions
- Read/write access verification
- Python module integration test
- GUI compatibility check

### Error Handling
- Clear error messages
- Troubleshooting suggestions
- Safe rollback on failure

### Auto-Mount (Optional)
- Adds entry to /etc/fstab
- Creates backup before modifying
- Configures proper network wait (_netdev)

## 📊 Expected Output

```
╔════════════════════════════════════════════════════════════════╗
║     SGA Network Share Setup - Complete Configuration          ║
╚════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1: Checking Prerequisites
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ cifs-utils is installed
✓ Server 20.0.1.9 is reachable
✓ Credentials template found

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2: Creating Mount Point
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Mount point created
✓ Permissions set on mount point

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3: Configuring Credentials
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Credentials file created and secured

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4: Mounting Network Share
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Network share mounted successfully!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 5: Testing Mount and Permissions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Mount point is accessible
✓ Read access confirmed
✓ Write access confirmed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 6: Running Python Diagnostic Test
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Python integration test passed

╔════════════════════════════════════════════════════════════════╗
║                  ✅ SETUP COMPLETED SUCCESSFULLY!              ║
╚════════════════════════════════════════════════════════════════╝
```

## 🎯 After Setup

Once complete:
1. Open the SGA application
2. Go to **"Base de Datos"** tab
3. Click **"🌐 Estado de Red"** button
4. Click **"Refresh"** to see updated status
5. Status should show: **✅ Connected**

## 🔧 Useful Commands

After setup, you can use:

```bash
# Check current status
python3 network_share_manager.py --status

# Full diagnostics
python3 network_share_manager.py --diagnose

# Unmount share
sudo umount /mnt/sga_shared

# Remount share
./mount_share.sh

# Run setup again
sudo ./setup_network_share.sh
```

## ❓ Troubleshooting

### If mount fails:
1. Check password is correct
2. Verify server is accessible: `ping 20.0.1.9`
3. Check firewall allows port 445
4. Verify share exists on server

### If permission denied:
1. Check credentials in `/etc/sga-credentials`
2. Verify user 'sga' has access on server
3. Check share permissions on server

### To start over:
```bash
# Unmount if mounted
sudo umount /mnt/sga_shared

# Remove credentials
sudo rm /etc/sga-credentials

# Run setup again
sudo ./setup_network_share.sh
```

## 📚 Related Documentation

- [NETWORK_SHARE_GUIDE.md](NETWORK_SHARE_GUIDE.md) - Complete user guide
- [NETWORK_COMPLETE_PACKAGE.md](NETWORK_COMPLETE_PACKAGE.md) - Full package documentation
- [NETWORK_BUTTON_FEATURE.md](NETWORK_BUTTON_FEATURE.md) - GUI button documentation

---

**Ready to run?** Execute: `sudo ./setup_network_share.sh`
