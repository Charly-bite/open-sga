import os
import sys
import logging
import traceback

# Setup basic crash logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/sga_app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# Ensure the root directory is in the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Enter sga_web so Flask templates/static resolve correctly
# But prevent reloader restart errors by disabling reloader or doing it properly
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import app

if __name__ == "__main__":
    # Dedicated development bind to avoid collisions with pre-production services.
    # Override with DEV_HOST / DEV_PORT when needed.
    dev_host = os.environ.get("DEV_HOST", "192.168.2.218")
    dev_port = int(os.environ.get("DEV_PORT", "5000"))

    try:
        logging.info("Starting SGA Developer Server...")
        # Start the Flask app using the native configuration found in app.py
        # use_reloader=False prevents the "sga_web/run_development.py" pathing error
        app.run(host=dev_host, port=dev_port, debug=True, use_reloader=False)
    except Exception as e:
        logging.critical(f"FATAL SERVER CRASH: {e}\n{traceback.format_exc()}")
        with open("logs/crash.log", "a", encoding="utf-8") as f:
            f.write(f"FATAL SERVER CRASH: {e}\n{traceback.format_exc()}\n\n")
        raise
