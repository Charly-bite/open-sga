"""
SGA Web Application - Main Entry Point
GHS Label System for Warehouse Operations
"""

import os
import sys
import io
import logging

# ── Fix Windows encoding FIRST (before any logging or print) ──────────
# When running under NSSM, stdout/stderr are file handles in cp1252.
# Emojis and Unicode in print()/logging crash without this fix.
if sys.platform == "win32" and "pytest" not in sys.modules:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )
    except Exception:
        pass  # Ignore if already wrapped or buffer unavailable

# Central application logging unconditionally
os.makedirs(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"),
    exist_ok=True,
)
log_file = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "sga_app.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
    force=True,  # Override random configs from other imported files
)

# Add parent directory to path so we can import shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Add core directory to path to fix missing sap_connector import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "core")))

from tara_weight_manager import get_tara_manager
from template_manager import TemplateManager
from order_status_manager import OrderStatusManager, OrderStatus
from history_manager import HistoryManager
from user_manager import UserManager, UserRole
from generate_ghs_label import GHSLabelGenerator
from smart_label import SmartLabelManager
from extensions import limiter as _limiter
from version import get_version, get_version_display, get_version_full, get_git_sha
from sga_web.config import config
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_login import LoginManager
from flask import Flask, render_template, jsonify, request, flash, redirect, url_for

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path for importing existing modules
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PARENT_DIR)


# Import existing backend modules


# Optional SAP connector (with dev throttle wrapper)
try:
    from sap_connector import SAPHanaConnector
    from sap_dev_wrapper import SAPDevThrottle

    SAP_AVAILABLE = True
    print("✅ SAP connector available (hdbcli installed)")
    print("🔒 SAP Dev Throttle wrapper loaded (1 conn, 2s cooldown)")
except ImportError:
    SAPHanaConnector = None
    SAPDevThrottle = None
    SAP_AVAILABLE = False
    print("⚠️ SAP connector not available (hdbcli missing)")


def create_app(config_name="default"):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize CSRF protection with graceful error handling.
    # In Flask 3.x + Werkzeug 3.x, HTTPExceptions (including CSRFError)
    # are handled as WSGI responses and bypass Flask's error handlers.
    # We override protect() to catch the error at its source.
    csrf = CSRFProtect(app)
    app.csrf = csrf

    _original_protect = csrf.protect

    def _graceful_protect(**kwargs):
        try:
            _original_protect(**kwargs)
        except CSRFError:
            from flask import session as flask_session

            flask_session.pop("csrf_token", None)
            flash("Su sesión expiró. Por favor intente de nuevo.", "warning")
            # Use abort with a 302 redirect response — not RequestRedirect (308)
            response = redirect(url_for("auth.login"))
            from werkzeug.exceptions import HTTPException

            exc = HTTPException(response=response)
            exc.code = 302
            raise exc

    csrf.protect = _graceful_protect

    # Initialize rate limiter (brute-force protection)
    _limiter.init_app(app)
    app.limiter = _limiter

    # Add zip to jinja globals
    app.jinja_env.globals.update(zip=zip)

    # Ensure directories exist
    os.makedirs(app.config["GENERATED_LABELS_PATH"], exist_ok=True)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Por favor inicie sesión para acceder."
    login_manager.login_message_category = "warning"

    @login_manager.unauthorized_handler
    def unauthorized():
        """Return JSON 401 for AJAX/API requests so fetch() doesn't silently
        follow the redirect and deliver an HTML login page as if it were JSON."""
        is_ajax = (
            request.accept_mimetypes.accept_json
            and not request.accept_mimetypes.accept_html
        ) or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        # Only treat explicit /api/ sub-paths as API calls, not page URLs
        is_api_path = "/api/" in request.path
        if is_ajax or is_api_path:
            return (
                jsonify(
                    {
                        "error": "session_expired",
                        "message": "Sesión expirada. Por favor recargue la página.",
                    }
                ),
                401,
            )
        # Regular page request — redirect to login as normal
        from flask import flash as _flash

        _flash("Por favor inicie sesión para acceder.", "warning")
        return redirect(url_for("auth.login", next=request.path))

    # Initialize managers
    app.user_manager = UserManager(app.config["USERS_FILE"])
    app.smart_label = SmartLabelManager()
    app.history_mgr = HistoryManager()
    app.order_status_mgr = OrderStatusManager()
    app.template_manager = TemplateManager()

    # Cache GHSLabelGenerator at startup (avoids re-reading CSVs per request)
    app.label_generator = GHSLabelGenerator(
        app.config["UNIFIED_DB_PATH"], manager=app.smart_label
    )
    print("✅ GHSLabelGenerator cached at startup")

    # Initialize Tara Weight Manager
    tara_csv = os.path.join(
        PARENT_DIR, "original_data", "Sample DataBase Tectronic QBR.csv"
    )
    app.tara_manager = get_tara_manager(tara_csv)
    print("✅ TaraWeightManager initialized")

    # Auto-import CLASIFICACION.xlsx rules (product types + per-product NETO→TARA overrides)
    excel_path = os.path.join(PARENT_DIR, "original_data", "CLASIFICACION.xlsx")
    if os.path.exists(excel_path):
        try:
            result = app.tara_manager.import_from_excel(excel_path)
            print(
                f"✅ CLASIFICACION.xlsx imported: {result.get('imported', 0)} products, "
                f"{result.get('tara_overrides_added', 0)} tara overrides"
            )
        except Exception as _e:
            print(f"⚠️ CLASIFICACION.xlsx import warning: {_e}")
    else:
        print("⚠️ CLASIFICACION.xlsx not found — skipping auto-import")

    # ── Eager startup: initialize classifications & lote recovery ──────
    # This runs the expensive work (SQL loads, lote recovery) at boot time
    # so the first user search is instant instead of waiting ~13s.
    try:
        import time as _boot_time

        _t0 = _boot_time.time()
        app.tara_manager.initialize_classifications(smart_label_manager=app.smart_label)
        # Run the one-time lote recovery that was previously inline in api_products()
        from routes.control_interno import run_startup_lote_recovery

        run_startup_lote_recovery(app)
        _elapsed = _boot_time.time() - _t0
        print(f"✅ Control Interno ready ({_elapsed:.1f}s startup)")
    except Exception as _e:
        print(f"⚠️ Control Interno startup init warning: {_e}")

    # Initialize SAP connector (optional)
    app.sap_connector = None
    app.sap_available = SAP_AVAILABLE

    # Initialize connector if available (with DEV THROTTLE wrapper)
    if SAP_AVAILABLE:
        sap_user = os.environ.get("SAP_USER")
        sap_pass = os.environ.get("SAP_PASS")
        if sap_user and sap_pass:
            try:
                _base_connector = SAPHanaConnector(
                    host=os.environ.get("SAP_HOST", "20.0.1.9"),
                    port=int(os.environ.get("SAP_PORT", 30015)),
                    username=sap_user,
                    password=sap_pass,
                    schema=os.environ.get("SAP_SCHEMA", "SBO_QUIMICABOSS"),
                )
                # Wrap with dev throttle to limit SAP load
                if SAPDevThrottle:
                    app.sap_connector = SAPDevThrottle(_base_connector)
                    print("✅ SAP Connector initialized (DEV THROTTLED mode)")
                else:
                    app.sap_connector = _base_connector
                    print("✅ SAP Connector initialized (Lazy connection mode)")
            except Exception as e:
                print(f"⚠️ SAP Connector initialization error: {e}")
                app.sap_connector = None

    # User loader with in-memory cache (avoids reading users.json on every request)
    # _user_cache = {}  # {user_id: (User, timestamp)}
    # _USER_CACHE_TTL = 60  # seconds

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        import logging as _logging
        _log = _logging.getLogger("user_loader")

        _log.info(f"[USER_LOADER] Called with user_id={user_id!r}")

        # Use the SQL-backed UserManager to get user details
        user_data = app.user_manager.get_user(user_id)
        if user_data:
            _log.info(f"[USER_LOADER] Found user {user_id!r} in DB, is_active={user_data.get('is_active')}")
            return User(user_data)
        # ── TEMPORARY BYPASS fallback ──────────────────────────────
        # The login route allows any username (even unknown ones) to
        # create a session.  If the user is not in the DB, build a
        # minimal User so the session is still recognised.
        _log.warning(f"[USER_LOADER] User {user_id!r} NOT in DB — creating temp bypass user")
        return User({
            "username": user_id,
            "role": "operator",
            "full_name": user_id,
            "warehouse": "",
            "must_change_password": False,
        })

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.labels import labels_bp
    from routes.products import products_bp
    from routes.orders import orders_bp
    from routes.users import users_bp
    from routes.api import api_bp
    from routes.templates import templates_bp
    from routes.control_interno import control_bp
    from routes.monitor import monitor_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(labels_bp, url_prefix="/labels")
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(orders_bp, url_prefix="/orders")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(templates_bp, url_prefix="/templates")
    app.register_blueprint(control_bp, url_prefix="/control")
    app.register_blueprint(monitor_bp, url_prefix="/api")

    # Initialize request logging middleware (structured HTTP access logs)
    from middleware.request_logger import init_request_logger

    init_request_logger(app)

    # CSRF Token validation ENFORCED per developer policy
    # Removed standard csrf_exempt directives to validate CSRF properly.

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        if (
            request.path.startswith("/api/")
            or request.is_json
            or request.headers.get("Accept", "") == "application/json"
        ):
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        if (
            request.path.startswith("/api/")
            or request.path.startswith("/labels/")
            or request.path.startswith("/orders/")
            or request.is_json
            or request.headers.get("Accept", "") == "application/json"
        ):
            return (
                jsonify({"error": "Internal server error", "message": str(error)}),
                500,
            )
        return render_template("errors/500.html"), 500

    # Context processor for templates
    @app.route("/favicon.ico")
    def favicon():
        return app.send_static_file("images/logo_vertical.2.png")

    @app.context_processor
    def utility_processor():
        return {
            "sap_available": SAP_AVAILABLE,
            "UserRole": UserRole,
            "OrderStatus": OrderStatus,
            "sga_version": get_version(),
            "sga_version_display": get_version_display(),
        }

    # Resolve and cache poppler path once at startup (avoids repeated filesystem scans)
    app.config["POPPLER_PATH"] = _find_poppler_path(app)

    # Register cleanup task for temp files (runs every 30 min)
    _register_temp_cleanup(app)

    # Register background SAP sync has been moved to sync_orders_job.py to prevent threading issues

    # Health check endpoint for CI/CD pipeline monitoring
    @app.route("/health")
    def health_check():
        smart_label = app.smart_label
        # Diagnostic: check UserManager state
        um = app.user_manager
        um_has_sql = um.sql_engine is not None
        try:
            um_data = um._load_data()
            um_user_count = len(um_data.get("users", []))
            um_usernames = [u["username"] for u in um_data.get("users", [])]
        except Exception:
            um_user_count = -1
            um_usernames = []
        return jsonify(
            {
                "status": "ok",
                "version": get_version(),
                "version_full": get_version_full(),
                "git_sha": get_git_sha(),
                "environment": os.environ.get("SGA_ENV", "development"),
                "db_connected": smart_label.df_products is not None,
                "sap_available": SAP_AVAILABLE,
                "products_loaded": (
                    len(smart_label.df_products)
                    if smart_label.df_products is not None
                    else 0
                ),
                "auth_sql_engine": um_has_sql,
                "auth_user_count": um_user_count,
                "auth_users": um_usernames,
            }
        )

    # Note: Database connection is handled by connect_db.bat and database_client module.
    # db_connector is only used for config path resolution (in config.py).

    return app


def _find_poppler_path(app):
    """Resolve poppler binary path once at startup."""
    # app.root_path = .../sga_web → one level up = project root
    project_root = os.path.dirname(app.root_path)
    # Also check PARENT_DIR as fallback
    _search_dirs = [project_root, os.path.dirname(project_root)]
    try:
        poppler_dirs = [d for d in os.listdir(project_root) if "poppler" in d.lower()]
        for d in poppler_dirs:
            candidate = os.path.join(project_root, d, "Library", "bin")
            if os.path.exists(candidate) and os.path.exists(
                os.path.join(candidate, "pdftoppm.exe")
            ):
                print(f"✅ Poppler found at {candidate}")
                return candidate
            candidate = os.path.join(project_root, d, "bin")
            if os.path.exists(candidate) and os.path.exists(
                os.path.join(candidate, "pdftoppm.exe")
            ):
                print(f"✅ Poppler found at {candidate}")
                return candidate
    except Exception:
        pass
    # Fallback: try resource_path helper
    try:
        from resource_path import get_poppler_path

        pp = get_poppler_path()
        if pp:
            print(f"✅ Poppler found via resource_path: {pp}")
            return pp
    except Exception:
        pass
    print("⚠️ Poppler not found — PDF-to-image conversion may fail")
    return None


def _register_temp_cleanup(app):
    """Register periodic cleanup of temp files older than 1 hour."""
    import threading
    import time as _time
    import glob

    MAX_AGE_SECONDS = 3600  # 1 hour
    CLEANUP_INTERVAL = 1800  # 30 minutes

    def _cleanup_loop():
        while True:
            _time.sleep(CLEANUP_INTERVAL)
            try:
                now = _time.time()
                # Clean static/tmp
                tmp_dir = os.path.join(app.root_path, "static", "tmp")
                if os.path.exists(tmp_dir):
                    for f in glob.glob(os.path.join(tmp_dir, "*")):
                        if (
                            os.path.isfile(f)
                            and (now - os.path.getmtime(f)) > MAX_AGE_SECONDS
                        ):
                            try:
                                os.remove(f)
                            except Exception:
                                pass
                # Clean generated_labels older than 24h
                labels_dir = app.config.get("GENERATED_LABELS_PATH", "")
                if labels_dir and os.path.exists(labels_dir):
                    for f in glob.glob(os.path.join(labels_dir, "*.pdf")):
                        if os.path.isfile(f) and (now - os.path.getmtime(f)) > 86400:
                            try:
                                os.remove(f)
                            except Exception:
                                pass
            except Exception:
                pass

    # Prevent running twice in Flask debug mode
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and app.debug:
        return

    t = threading.Thread(target=_cleanup_loop, daemon=True, name="temp-cleanup")
    t.start()


# Create app instance — DEVELOPMENT environment
app = create_app("development")


if __name__ == "__main__":
    print("=" * 60)
    print("🏷️  SGA Web Application - GHS Label System")
    print("=" * 60)
    print(f"📂 Database: {app.config['UNIFIED_DB_PATH']}")
    print(f"🔌 SAP Available: {SAP_AVAILABLE}")
    print("=" * 60)

    # Run development server
    app.run(
        host=os.environ.get("DEV_HOST", "0.0.0.0"),  # nosec B104
        port=int(os.environ.get("DEV_PORT", "5000")),
        debug=True,  # nosec B201
    )
