import sys
import os

# Set up paths
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database_client import get_shared_client
from sga_web.core.user_manager import UserManager
from sqlalchemy import text
from sqlalchemy import text

def migrate_users(dry_run=True):
    print(f"=== Starting Migration {'(DRY RUN)' if dry_run else ''} ===")
    
    # 1. Connect to the database
    client = get_shared_client()
    if not client.is_connected():
        print("Failed to connect to database.")
        return
        
    engine = client.get_sql_engine()
    if not engine:
        print("Failed to get SQL engine.")
        return
        
    # We will use UserManager for its hash function
    um = UserManager(users_file="users.json")
    
    # 2. Find the users file
    # We didn't find the JSON backup with actual users, but we found new_users_passwords.txt
    passwords_file = os.path.join(os.path.dirname(__file__), "new_users_passwords.txt")
    
    if not os.path.exists(passwords_file):
        print(f"File {passwords_file} not found!")
        return
        
    print(f"Found users in: {passwords_file}")
    
    # Parse the txt file
    users_to_insert = []
    with open(passwords_file, "r") as f:
        lines = f.readlines()
        current_user = {}
        for line in lines:
            line = line.strip()
            if line.startswith("Username:"):
                current_user["username"] = line.split(":", 1)[1].strip()
            elif line.startswith("Password:"):
                current_user["password"] = line.split(":", 1)[1].strip()
            elif line.startswith("Role:"):
                current_user["role"] = line.split(":", 1)[1].strip()
                if "username" in current_user and "password" in current_user:
                    users_to_insert.append(current_user)
                    current_user = {}

    print(f"Parsed {len(users_to_insert)} users to migrate.")
    
    # 3. Insert or update users in SQL
    with engine.begin() as conn:
        for u in users_to_insert:
            username = u["username"]
            pwd = u["password"]
            role = u["role"]
            
            pwd_hash = um._hash_password(pwd)
            
            # Check if user exists
            row = conn.execute(text("SELECT username FROM SGA_Users WHERE username = :u"), {"u": username}).fetchone()
            
            if row:
                print(f"User {username} already exists. Updating.")
                if not dry_run:
                    conn.execute(
                        text("""
                        UPDATE SGA_Users 
                        SET password_hash=:pwd, role=:role 
                        WHERE username=:u
                        """), 
                        {"pwd": pwd_hash, "role": role, "u": username}
                    )
            else:
                print(f"Inserting new user {username}.")
                if not dry_run:
                    from datetime import datetime
                    conn.execute(
                        text("""
                        INSERT INTO SGA_Users 
                        (username, password_hash, role, full_name, email, warehouse, created_at, is_active, must_change_password)
                        VALUES (:u, :pwd, :role, :fname, '', '', :now, 1, 0)
                        """),
                        {
                            "u": username,
                            "pwd": pwd_hash,
                            "role": role,
                            "fname": username,
                            "now": datetime.now().isoformat()
                        }
                    )
                    
    print("Migration completed.")

if __name__ == "__main__":
    # Dry run is set to True to prevent actual DB modifications
    migrate_users(dry_run=True)
