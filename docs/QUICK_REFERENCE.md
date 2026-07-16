# SGA Multi-System Quick Reference

## 📁 File Structure
```
/mnt/sga_shared/              (Network mounted folder)
├── master_data/              Product database (read-mostly)
│   ├── unified_db/           Normalized CSV files
│   └── original_data/        Legacy data
├── assets/                   Pictogram images
├── operational/              Active operations (read-write)
│   ├── label_queue.json      Print queue
│   └── history.json          Print history
├── config/                   Configuration (admin-managed)
│   ├── users.json            User accounts
│   └── settings.json         System settings  
├── logs/                     Application logs
└── generated_labels/         PDF outputs
```

## 🖥️ System IDs

| ID | Role | Location |
|----|------|----------|
| admin1 | Administrator | Main office |
| admin2 | Administrator | Secondary office |
| prod1 | Production | Warehouse 1 |
| prod2 | Production | Warehouse 2 |

## 🔧 Common Commands

### Check Mount Status
```bash
mount | grep sga_shared
ls -la /mnt/sga_shared/
```

### Manually Mount/Unmount
```bash
# Mount
sudo mount -a

# Unmount
sudo umount /mnt/sga_shared

# Remount
sudo umount /mnt/sga_shared && sudo mount -a
```

### View Shared Files
```bash
# Check operational files
cat /mnt/sga_shared/operational/label_queue.json | jq
tail -20 /mnt/sga_shared/operational/history.json

# Check logs
ls -lht /mnt/sga_shared/logs/ | head
tail -f /mnt/sga_shared/logs/admin1_$(date +%Y%m%d).log
```

### Test File Access
```bash
# Read test
cat /mnt/sga_shared/config/users.json

# Write test
echo "test" > /mnt/sga_shared/operational/test_$(hostname).txt
rm /mnt/sga_shared/operational/test_$(hostname).txt
```

### Check Who's Connected
```bash
# On server
sudo smbstatus

# Expected output shows connected clients
```

## 🐛 Troubleshooting

### Mount Issues
```bash
# Check server reachable
ping 20.0.1.9

# Check Samba port open
nc -zv 20.0.1.9 445

# Check credentials
sudo cat /etc/sga-cifs-credentials

# Try manual mount with debug
sudo mount.cifs //20.0.1.9/sga_shared /mnt/sga_shared \
  -o credentials=/etc/sga-cifs-credentials,vers=3.0 -v
```

### File Lock Issues
```bash
# Check what processes have file open
sudo lsof /mnt/sga_shared/operational/label_queue.json

# Kill stuck process
sudo pkill -f "python.*ghs_label_gui"

# Check file permissions
ls -l /mnt/sga_shared/operational/
```

### Application Won't Start
```bash
# Check configuration
cd /opt/sga
python3 -c "
from shared_config_manager import SharedConfigManager
config = SharedConfigManager()
print('System ID:', config.get_system_id())
print('Paths OK:', all(config.get_all_paths().values()))
"

# Check dependencies
python3 -c "
from shared_file_manager import SharedFileManager
from shared_config_manager import SharedConfigManager
print('✓ All modules load successfully')
"

# Check mount
ls /mnt/sga_shared/ || echo "Mount missing!"
```

### Network Performance
```bash
# Test read speed (should be < 1 second)
time head -100 /mnt/sga_shared/master_data/unified_db/products_master.csv

# Test write speed
time dd if=/dev/zero of=/mnt/sga_shared/test.bin bs=1M count=10
rm /mnt/sga_shared/test.bin
```

## 🔄 Backup & Restore

### Manual Backup
```bash
# Full backup
sudo rsync -avz /mnt/sga_shared/ /backup/sga_$(date +%Y%m%d)/

# Operational files only
sudo cp /mnt/sga_shared/operational/*.json /backup/operational_$(date +%Y%m%d)/
```

### Restore
```bash
# Restore single file
sudo cp /backup/sga_20260118/operational/label_queue.json \
       /mnt/sga_shared/operational/

# Restore all
sudo rsync -avz /backup/sga_20260118/ /mnt/sga_shared/
```

## 🚀 Restart Procedures

### Restart Single Client
```bash
# Kill application
sudo pkill -f "python.*ghs_label_gui"

# Verify mount
mount | grep sga_shared || sudo mount -a

# Restart application
cd /opt/sga
python3 ghs_label_gui.py &
```

### Restart Server
```bash
# On server (will disconnect all clients)
sudo systemctl restart smbd

# Verify service
sudo systemctl status smbd

# Clients will reconnect automatically
```

### Emergency: Switch to Local Mode
```bash
# Unmount shared folder
sudo umount /mnt/sga_shared

# Disable shared config
mv shared_config.json shared_config.json.disabled

# Application will use local files
python3 ghs_label_gui.py
```

## 📊 Monitoring

### Daily Checks
- [ ] All systems can access /mnt/sga_shared
- [ ] No file lock errors in logs
- [ ] Backup completed successfully
- [ ] Disk space > 20% free

### Check Disk Space
```bash
df -h /mnt/sga_shared
# Warning if > 80% full
```

### Check Log Size
```bash
du -sh /mnt/sga_shared/logs/
# Rotate if > 100MB
```

### View Recent Activity
```bash
# Recent label prints
tail -20 /mnt/sga_shared/operational/history.json | jq

# Active queue
cat /mnt/sga_shared/operational/label_queue.json | jq '.queue | length'
```

## 📞 Emergency Contacts

| Role | Contact |
|------|---------|
| System Admin | [Your contact] |
| Network Admin | [IT contact] |
| Vendor Support | [Vendor contact] |

## 🔑 Important Paths

| Purpose | Path |
|---------|------|
| Application | `/opt/sga/` |
| Shared Data | `/mnt/sga_shared/` |
| Config File | `/opt/sga/shared_config.json` |
| Credentials | `/etc/sga-cifs-credentials` |
| Mount Config | `/etc/fstab` (line with sga_shared) |
| Logs | `/mnt/sga_shared/logs/` |
| Backups | `/backup/sga_*` |

---

**Print this page and keep near each workstation**  
**Version:** 1.0 | **Date:** 2026-01-19
