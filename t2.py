import requests
import re

s = requests.Session()
r = s.get("http://127.0.0.2:5001/login")
print("GET /login status:", r.status_code)
content = r.text
match = re.search(r'<meta name="csrf-token" content="([^"]+)">', content)
if match:
    tok = match.group(1)
    print("Found CSRF:", len(tok))
    r2 = s.post("http://127.0.0.2:5001/api/sap/connect", headers={"X-CSRFToken": tok})
    print("POST /api/sap/connect status:", r2.status_code)
else:
    print("NO CSRF META TAG!")
