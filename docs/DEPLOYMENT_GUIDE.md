# SGA Multi-System Deployment Guide
## Complete Setup for 4 Systems (2 Admin + 2 Production)

---

## Overview

This guide walks you through setting up a shared database environment for SGA across 4 systems using network file sharing (Samba/CIFS).

### Architecture
```
┌─────────────────────────────────────────────────┐
│         File Server (20.0.1.9 or dedicated)     │
│                                                 │
│  /srv/sga_shared/                              │
│  ├── master_data/      (Product catalog)       │
│  ├── assets/           (Pictograms)            │
│  ├── operational/      (Queue, History)        │
│  ├── config/           (Users, Settings)       │
│  └── logs/             (Application logs)      │
└─────────────────────────────────────────────────┘
         │         │         │         │
         ▼         ▼         ▼         ▼
    ┌────────┬────────┬────────┬────────┐
    │ Admin1 │ Admin2 │ Prod1  │ Prod2  │
    └────────┴────────┴────────┴────────┘
     Mounted at: /mnt/sga_shared
```

---

## Prerequisites

- [ ] Linux server for file sharing (Ubuntu 20.04+ recommended)
- [ ] Network connectivity between all systems
- [ ] Root/sudo access on all systems
- [ ] Current SGA installation with data

---

## Phase 1: Server Setup (30 minutes)

### Step 1: Prepare Server

SSH into your server:
```bash
ssh user@20.0.1.9
```

### Step 2: Run Server Setup Script

```bash
# Copy setup_server.sh to the server
scp setup_server.sh user@20.0.1.9:/tmp/

# On the server
cd /tmp
sudo bash setup_server.sh
```

**What it does:**
- Installs Samba file server
- Creates shared directory structure
- Creates `sga` user and group
- Configures file permissions
- Sets up Samba share with proper locking

**You'll be prompted for:**
- Samba password for `sga` user (choose a strong password)

**Note the output:**
- Server IP address
- Share name (usually `sga_shared`)
- Share path (usually `/srv/sga_shared`)

### Step 3: Migrate Data to Server

On your current SGA system:
```bash
# First, do a dry run to see what will be copied
python3 migrate_to_shared.py \
  --source /path/to/current/sga \
  --dest /srv/sga_shared

# If everything looks good, do the actual migration
sudo python3 migrate_to_shared.py \
  --source /path/to/current/sga \
  --dest /srv/sga_shared \
  --live
```

### Step 4: Verify Server Setup

```bash
# Check shared folder structure
ls -la /srv/sga_shared/

# Should see:
# master_data/
# assets/
# operational/
# config/
# logs/
# generated_labels/

# Check Samba status
sudo systemctl status smbd

# View Samba configuration
sudo testparm
```

---

## Phase 2: Client Setup (15 minutes per client)

Repeat these steps for each of the 4 systems.

### System Configuration Values

| System ID | Role           | Purpose              |
|-----------|----------------|----------------------|
| admin1    | administrator  | Primary admin desk   |
| admin2    | administrator  | Secondary admin desk |
| prod1     | production     | Warehouse station 1  |
| prod2     | production     | Warehouse station 2  |

### Step 1: Edit Client Setup Script

Before running, edit `setup_client.sh` for each system:

```bash
# Edit these values:
SERVER_IP="20.0.1.9"          # Your server IP
SYSTEM_ID="admin1"            # Change for each: admin1, admin2, prod1, prod2
SYSTEM_ROLE="administrator"   # Or "production" for prod1/prod2
```

### Step 2: Run Client Setup

```bash
# Copy setup script to client
scp setup_client.sh user@client-system:/tmp/

# On each client system
cd /tmp
sudo bash setup_client.sh
```

**You'll be prompted for:**
- Confirm configuration
- Samba password (use the password you set on server)

**What it does:**
- Installs CIFS utilities
- Creates mount point at `/mnt/sga_shared`
- Mounts the network share
- Adds to `/etc/fstab` for automatic mount on boot
- Creates system-specific configuration

### Step 3: Verify Client Mount

```bash
# Check if mounted
mount | grep sga_shared

# Should show:
# //20.0.1.9/sga_shared on /mnt/sga_shared type cifs (...)

# Check access
ls -la /mnt/sga_shared/

# Test write permission
touch /mnt/sga_shared/operational/test_$(hostname).txt
rm /mnt/sga_shared/operational/test_$(hostname).txt
```

### Step 4: Install SGA Application

On each client:
```bash
# Create application directory
sudo mkdir -p /opt/sga
sudo chown $USER:$USER /opt/sga

# Copy SGA application files
cd /opt/sga
# ... copy your Python files, or clone from git ...

# Install Python dependencies
pip3 install -r requirements.txt

# Copy shared configuration
cp /opt/sga/shared_config.json ./

# Verify configuration
python3 shared_config_manager.py
```

---

## Phase 3: Testing (30 minutes)

### Test 1: Configuration Check

On each client:
```bash
cd /opt/sga
python3 -c "
from shared_config_manager import SharedConfigManager
config = SharedConfigManager('shared_config.json')
print(f'System: {config.get_system_id()}')
print(f'Role: {config.get(\"system_role\")}')
print(f'Shared mode: {config.is_shared_mode()}')
print(f'Base path: {config.get_path(\"base\")}')
"
```

Expected output:
```
System: admin1  (or admin2, prod1, prod2)
Role: administrator  (or production)
Shared mode: True
Base path: /mnt/sga_shared
```

### Test 2: File Locking

On **two different clients** simultaneously:

**Terminal 1 (admin1):**
```bash
cd /opt/sga
python3 shared_file_manager.py
# Should show: "✓ All tests passed!"
```

**Terminal 2 (admin2):**
```bash
cd /opt/sga
python3 shared_file_manager.py
# Should also pass without conflicts
```

### Test 3: Application Start

Start on **one** client first:
```bash
cd /opt/sga
python3 ghs_label_gui.py
```

**Verify:**
- [ ] Login works
- [ ] Product database loads
- [ ] Can create a label
- [ ] History is recorded
- [ ] No error messages

### Test 4: Multi-Client Operation

1. Start application on **admin1**
2. Create a test label
3. Check history on **admin2**
4. Verify both see the same data

```bash
# On admin2, check shared history
python3 -c "
from shared_file_manager import SharedFileManager
mgr = SharedFileManager('/mnt/sga_shared')
history = mgr.read_json('operational/history.json', [])
print(f'History entries: {len(history)}')
if history:
    print(f'Latest: {history[-1]}')
"
```

### Test 5: Failover Test

1. Start application on **admin1**
2. Simulate network issue: `sudo umount /mnt/sga_shared`
3. Application should show error
4. Remount: `sudo mount -a`
5. Application should recover

---

## Phase 4: Production Deployment

### Deployment Checklist

- [ ] All 4 systems successfully tested
- [ ] No file lock conflicts observed
- [ ] Network performance is acceptable
- [ ] Backup procedures in place
- [ ] Users trained on new system

### Deployment Order

1. **Day 1 Morning**: Deploy to admin1 (primary admin)
2. **Day 1 Afternoon**: Deploy to admin2 (if admin1 stable)
3. **Day 2**: Deploy to prod1 and prod2
4. **Week 1**: Monitor closely, gather feedback

### Rollback Plan

If issues arise:

```bash
# On affected client
sudo umount /mnt/sga_shared

# Rename shared_config.json
mv shared_config.json shared_config.json.disabled

# Application will fall back to local mode
python3 ghs_label_gui.py
```

---

## Ongoing Maintenance

### Daily Tasks

**Automated via cron:**
```bash
# Add to /etc/cron.daily/sga-backup
#!/bin/bash
rsync -avz /mnt/sga_shared/ /backup/sga_shared_$(date +%Y%m%d)/
find /backup/sga_shared_* -mtime +7 -delete
```

### Weekly Tasks

- Check disk space: `df -h /mnt/sga_shared`
- Review logs: `ls -lh /mnt/sga_shared/logs/`
- Verify backups exist
- Check Samba status: `sudo smbstatus`

### Monthly Tasks

- Review and rotate logs
- Update product database
- Test restore from backup
- Review user access logs

---

## Troubleshooting

### Issue: Mount Failed

**Symptoms:** Client can't mount shared folder

**Diagnosis:**
```bash
# Test network connectivity
ping 20.0.1.9

# Test Samba port
nc -zv 20.0.1.9 445

# Check credentials
cat /etc/sga-cifs-credentials

# Try manual mount
sudo mount -t cifs //20.0.1.9/sga_shared /mnt/sga_shared \
  -o credentials=/etc/sga-cifs-credentials,vers=3.0
```

**Solutions:**
- Verify server is running: `sudo systemctl status smbd`
- Check firewall: `sudo ufw status`
- Verify Samba user: `sudo pdbedit -L`
- Check credentials file permissions: `ls -l /etc/sga-cifs-credentials`

### Issue: File Lock Timeout

**Symptoms:** "FileLockTimeout" errors

**Diagnosis:**
```bash
# Check who has files open
sudo lsof /mnt/sga_shared/operational/label_queue.json

# Check Samba connections
sudo smbstatus
```

**Solutions:**
- Increase lock timeout in `shared_config.json`
- Restart stuck processes
- Check network latency: `ping -c 10 20.0.1.9`

### Issue: Slow Performance

**Symptoms:** Application feels sluggish

**Diagnosis:**
```bash
# Test read speed
time cat /mnt/sga_shared/master_data/unified_db/products_master.csv > /dev/null

# Test write speed
time dd if=/dev/zero of=/mnt/sga_shared/test.tmp bs=1M count=10
rm /mnt/sga_shared/test.tmp
```

**Solutions:**
- Enable local caching in `shared_config.json`:
  ```json
  "local_cache": {
    "enabled": true,
    "cache_master_data": true
  }
  ```
- Upgrade network (use Gigabit Ethernet)
- Check server load: `top` on server

### Issue: Data Corruption

**Symptoms:** JSON files malformed, CSV errors

**Recovery:**
```bash
# Restore from backup
sudo cp /mnt/sga_shared/operational/label_queue.json.bak \
       /mnt/sga_shared/operational/label_queue.json

# Or from daily backup
sudo cp /backup/sga_shared_20260118/operational/label_queue.json \
       /mnt/sga_shared/operational/
```

---

## Appendix: Configuration Reference

### Complete shared_config.json

```json
{
  "deployment_type": "shared",
  "system_id": "admin1",
  "system_role": "administrator",
  "shared_base_path": "/mnt/sga_shared",
  
  "network": {
    "mount_check_enabled": true,
    "mount_path": "/mnt/sga_shared",
    "fallback_to_local": false,
    "connection_timeout_seconds": 5
  },
  
  "file_locking": {
    "enabled": true,
    "lock_timeout_seconds": 10,
    "retry_delay_seconds": 0.1
  },
  
  "local_cache": {
    "enabled": false,
    "path": "/opt/sga/cache",
    "sync_interval_seconds": 300
  }
}
```

### Samba Configuration (/etc/samba/smb.conf)

```ini
[sga_shared]
    path = /srv/sga_shared
    browseable = yes
    writable = yes
    valid users = @sga
    create mask = 0664
    directory mask = 0775
    strict locking = yes
    oplocks = no
```

---

## Support & Contact

For issues or questions:
1. Check logs: `/mnt/sga_shared/logs/`
2. Review this guide
3. Contact system administrator

---

**Document Version:** 1.0  
**Last Updated:** January 19, 2026  
**Next Review:** February 19, 2026
