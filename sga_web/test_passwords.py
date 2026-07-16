"""Check password hashes for all users in SQL vs JSON"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "core")))

from dotenv import load_dotenv
load_dotenv()

from database_client import get_shared_client
client = get_shared_client()

if client.get_sql_engine():
    from sqlalchemy import text
    engine = client.get_sql_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT username, password_hash, role, is_active FROM SGA_Users ORDER BY username")).fetchall()
        print(f"=== SQL Database Users ({len(rows)}) ===")
        for r in rows:
            h = r[1] if r[1] else ""
            has_dollar = "$" in h
            print(f"  {r[0]:15s} | role={r[2]:12s} | active={r[3]} | hash_format={'salt$hash' if has_dollar else 'OTHER'} | hash={h[:40]}...")

# Now check the JSON file
import json
users_file = os.path.join(os.path.dirname(__file__), "..", "users.json")
if os.path.exists(users_file):
    with open(users_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    users = data.get("users", [])
    print(f"\n=== JSON File Users ({len(users)}) ===")
    for u in users:
        h = u.get("password_hash", "")
        has_dollar = "$" in h
        print(f"  {u['username']:15s} | role={u.get('role','?'):12s} | active={u.get('is_active')} | hash_format={'salt$hash' if has_dollar else 'OTHER'} | hash={h[:40]}...")

# Test authentication for Alm01
print("\n=== Auth Tests ===")
from user_manager import UserManager
um = UserManager(users_file)
print(f"UM has SQL engine: {um.sql_engine is not None}")

# Test with the password from the screenshot
test_cases = [
    ("admin", "admin123"),
    ("Alm01", "NUswLTSWWa"),
    ("Alm01", "alm01"),
    ("Alm01", "Alm01"),
]
for user, pwd in test_cases:
    result = um.authenticate(user, pwd)
    print(f"  auth({user}, {pwd}) = {result}")

# Check if the password verification works directly
print("\n=== Direct Hash Verification ===")
if um.sql_engine:
    with um.sql_engine.connect() as conn:
        row = conn.execute(text("SELECT password_hash FROM SGA_Users WHERE username = 'Alm01'")).fetchone()
        if row:
            stored_hash = row[0]
            print(f"  Alm01 stored hash: {stored_hash}")
            verify_result = um._verify_password("NUswLTSWWa", stored_hash)
            print(f"  verify_password('NUswLTSWWa', stored_hash) = {verify_result}")
