import os

log_path = r"C:\Users\QB_DESARROLLO\Desktop\DEVELOPMENT\logs\sga_app.log"
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        for line in lines[-50:]:
            print(line.strip().encode("ascii", "replace").decode("ascii"))
