# Database Sharing Strategy for SGA System
## 4 Systems: 2 Admin + 2 Production

## Current Data Architecture

### Data Types
1. **Master Data (READ-MOSTLY)** - Product catalog, H/P statements, pictograms
   - `unified_db/*.csv` (~580 products)
   - Updated occasionally by admins
   - Read frequently by all systems

2. **Operational Data (READ-WRITE)** - Label queue, history
   - `label_queue.json` - Active print jobs
   - `history.json` - Print history log
   - Written/read by all systems

3. **Configuration Data (READ-WRITE)** - Users, settings
   - `users.json` - User accounts
   - `config_retail_sample.json` - System settings
   - Managed by admins, read by all

4. **Assets (READ-ONLY)** - Pictogram images
   - `assets/pictograms/*.png`
   - Static files, rarely change

---

## Recommended Solution: **Network Shared Folder (SMB/NFS)**

### Why This Approach?
✅ **Simplest** - No database server setup, just file sharing  
✅ **Reliable** - Linux SMB/NFS is battle-tested  
✅ **Low overhead** - CSV files work perfectly for 580 products  
✅ **Easy backup** - Just backup the folder  
✅ **No licensing** - Free, open-source  
✅ **Good for 4 systems** - Low concurrency, no scalability issues

### Architecture

```
Server (20.0.1.9 or new file server)
│
├── /shared/sga_data/
│   ├── unified_db/          (Master data - CSV files)
│   ├── assets/              (Pictograms - Images)
│   ├── operational/         (Queue & History - JSON)
│   ├── config/              (Users & Settings - JSON)
│   └── logs/                (Application logs)
│
└── Mounted on all 4 clients as:
    /mnt/sga_shared/  (or C:\sga_shared\ on Windows)
```

### Client Configuration
Each client:
- Mounts server share at boot
- Reads master data from shared folder
- Writes queue/history with file locking
- Local cache optional for performance

---

## Implementation Options

### Option 1: Network Folder (RECOMMENDED for 4 systems)

**Pros:**
- Simple setup (~30 min)
- Works with existing CSV/JSON files
- No code changes needed
- Built-in file locking
- Easy to debug

**Cons:**
- Network dependency
- Potential file lock conflicts (rare with 4 systems)
- No transactions

**Setup:**
```bash
# On server (Ubuntu/Linux)
sudo apt install samba
sudo mkdir -p /srv/sga_shared
sudo chown -R sga:sga /srv/sga_shared
# Configure SMB share in /etc/samba/smb.conf

# On each client
sudo mkdir /mnt/sga_shared
sudo mount -t cifs //server_ip/sga_shared /mnt/sga_shared -o credentials=/etc/sga-creds
```

---

### Option 2: SQLite with Network Share (HYBRID)

**Pros:**
- Single database file
- ACID transactions
- Better concurrency than CSV
- SQL queries available

**Cons:**
- SQLite on network share = risky (corruption possible)
- Requires schema migration
- More complex code changes

**Not recommended** for production over network.

---

### Option 3: Centralized PostgreSQL/MySQL (ENTERPRISE)

**Pros:**
- True multi-user database
- ACID guarantees
- Great concurrency
- Scales to 100+ users

**Cons:**
- Overkill for 4 systems
- Requires DBA setup
- More complex deployment
- Additional server resources

**Setup:**
```bash
# Server
sudo apt install postgresql
# Create database, users, tables
# Migrate CSV to SQL

# Each client
pip install psycopg2-binary
# Update code to use database instead of CSV
```

---

## Detailed Recommendation: Network Shared Folder

### File Structure
```
/mnt/sga_shared/
├── master_data/
│   ├── unified_db/
│   │   ├── products_master.csv
│   │   ├── h_statements.csv
│   │   ├── p_statements.csv
│   │   └── ... (all CSVs)
│   └── Unified_GHS_Database.csv
│
├── assets/
│   └── pictograms/
│       ├── llama.png
│       ├── calavera.png
│       └── ...
│
├── operational/
│   ├── label_queue.json       (with file locking)
│   ├── history.json           (append-only with rotation)
│   └── temp/                  (temp files)
│
├── config/
│   ├── users.json             (with backup)
│   ├── settings.json
│   └── mock_barcode_db.json
│
└── logs/
    ├── admin1_YYYYMMDD.log
    ├── admin2_YYYYMMDD.log
    ├── prod1_YYYYMMDD.log
    └── prod2_YYYYMMDD.log
```

### File Locking Strategy

For concurrent writes (label_queue.json, history.json):

```python
import fcntl
import json

class SharedJSONFile:
    """Thread-safe JSON file with file locking"""
    
    def __init__(self, filepath):
        self.filepath = filepath
    
    def read(self):
        with open(self.filepath, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock
            data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data
    
    def write(self, data):
        with open(self.filepath, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
            json.dump(data, f, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

---

## Migration Path

### Phase 1: Setup Server Share (Day 1)
1. Install Samba/NFS on server
2. Create shared folder structure
3. Copy current data to share
4. Test access from one client

### Phase 2: Update Code (Day 2)
1. Add configuration for shared paths
2. Implement file locking for queue/history
3. Add network error handling
4. Test with 2 clients simultaneously

### Phase 3: Deploy to All Systems (Day 3)
1. Mount share on all 4 systems
2. Update configuration files
3. Start admin systems first
4. Start production systems
5. Monitor for conflicts

### Phase 4: Monitoring & Optimization (Week 2)
1. Add logging for file access
2. Optimize caching if needed
3. Setup automated backups
4. Document procedures

---

## Alternative: Hybrid Local + Sync

If network reliability is a concern:

**Local Copy + Periodic Sync**
- Each system has local copy of master data
- Operational data on shared folder
- Rsync every 5 minutes for master data
- Best of both worlds (speed + redundancy)

```bash
# On each client (cron job)
*/5 * * * * rsync -avz /mnt/sga_shared/master_data/ /opt/sga/local_data/
```

---

## Cost Comparison

| Solution | Setup Time | Complexity | Cost | Best For |
|----------|-----------|------------|------|----------|
| **Network Share** | 2-4 hours | Low | $0 | 2-10 users |
| SQLite + Share | 1 day | Medium | $0 | Not recommended |
| PostgreSQL | 2-3 days | High | $0-500/mo | 10+ users |
| Cloud Database | 1-2 days | Medium | $50+/mo | Remote teams |

---

## Final Recommendation

**Use Network Shared Folder (SMB)** because:

1. Your server is already available (20.0.1.9)
2. Only 4 systems = low concurrency
3. CSV/JSON files work great for this scale
4. Zero additional infrastructure cost
5. Easy to backup and restore
6. Can upgrade later if needed

### Next Steps

1. **Setup Samba share** on your server
2. **Implement file locking** module (I can create this)
3. **Add path configuration** to support shared paths
4. **Test with 2 systems** before full rollout
5. **Create backup script** for the shared folder

Would you like me to:
- Create the file locking implementation?
- Write the server setup scripts?
- Build a path configuration system?
- Create a sync fallback solution?
