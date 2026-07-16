#!/usr/bin/env python3
"""
SGA Server Watchdog
===================
Monitors the database SMB share and the SGA web server.
Automatically attempts to reconnect the SMB share and restart
the web server when they become unavailable.

Usage:
    python watchdog.py              # Run with defaults from db_client_config.json
    python watchdog.py --interval 60  # Check every 60 seconds
    python watchdog.py --no-web     # Only monitor the SMB share
    python watchdog.py --no-smb     # Only monitor the web server

Logs are written to:
    logs/watchdog.log       (rolling log)
    logs/watchdog_stats.json  (live status)
"""

import os
import sys
import io
import time
import json

# Fix Windows encoding FIRST (before any logging or print)
if sys.platform == "win32":
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
        pass
import threading
import socket
import logging
import argparse
import subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(BASE_DIR, "db_client_config.json")
STATS_FILE = os.path.join(LOG_DIR, "watchdog_stats.json")
LOG_FILE = os.path.join(LOG_DIR, "watchdog.log")


# ──────────────────────────────────────────────
# Logging - console + rotating file (5 MB × 3)
# ──────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger("SGA-Watchdog")
    logger.setLevel(logging.DEBUG)

    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


logger = _setup_logging()


# ──────────────────────────────────────────────
# Config loader
# ──────────────────────────────────────────────
def load_config() -> dict:
    """
    Load configuration from db_client_config.json.
    Fills in sensible defaults for missing keys.
    """
    defaults: dict = {
        "server": {
            "ip_address": "192.168.2.237",
            "hostname": "ServerWebQB",
            "share_name": "SGA_Database",
        },
        "watchdog": {
            "check_interval": 30,  # seconds between health checks
            "smb_reconnect_retries": 3,  # attempts before giving up on one cycle
            "web_restart_threshold": 2,  # consecutive fails before restarting web
            "web_server_host": "localhost",
            "web_server_port": 5000,
            "web_app_script": "sga_web/app.py",
        },
    }

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            file_cfg = json.load(f)
        # Shallow-merge each section
        for section in ("server", "watchdog"):
            defaults[section].update(file_cfg.get(section, {}))
        logger.info(f"Configuracion cargada desde {CONFIG_FILE}")
    except FileNotFoundError:
        logger.warning(
            f"Archivo de configuracion no encontrado ({CONFIG_FILE}), usando valores por defecto."
        )
    except Exception as e:
        logger.error(f"Error al cargar configuracion: {e}")

    return defaults


# ──────────────────────────────────────────────
# SMB share watchdog
# ──────────────────────────────────────────────
class SMBWatchdog:
    """Checks and restores the network SMB share."""

    def __init__(self, cfg: dict):
        s = cfg["server"]
        self.ip = s["ip_address"]
        self.hostname = s.get("hostname", "")
        self.share_name = s["share_name"]
        self.share_path = f"\\\\{self.ip}\\{self.share_name}"
        self.retries = cfg["watchdog"].get("smb_reconnect_retries", 3)
        self.consecutive_failures = 0

    # ----------------------------------------------------------
    def is_accessible(self) -> bool:
        """Return True when the share root directory is reachable."""
        try:
            return os.path.exists(self.share_path)
        except Exception:
            return False

    def can_ping(self) -> bool:
        """TCP probe on port 445 (SMB) — fast reachability check."""
        try:
            with socket.create_connection((self.ip, 445), timeout=5):
                return True
        except Exception:
            return False

    def reconnect(self) -> bool:
        """
        Drop the stale session with 'net use /delete' and re-establish it.
        Returns True if the share becomes accessible again.
        """
        logger.info(f"Desconectando sesion existente: {self.share_path}  ...")
        try:
            subprocess.run(
                ["net", "use", self.share_path, "/delete", "/yes"],
                capture_output=True,
                timeout=15,
            )
        except Exception:
            pass  # Ignore if it was not mounted

        time.sleep(2)

        for attempt in range(1, self.retries + 1):
            logger.info(
                f"  Intento {attempt}/{self.retries}: net use {self.share_path}"
            )
            try:
                result = subprocess.run(
                    ["net", "use", self.share_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    logger.info("  ✅ Share SMB reconectado exitosamente.")
                    return True
                logger.warning(
                    f"  net use fallo rc={result.returncode}: "
                    f"{result.stderr.strip()}"
                )
            except subprocess.TimeoutExpired:
                logger.warning("  net use timeout.")
            except Exception as e:
                logger.error(f"  Error: {e}")

            if attempt < self.retries:
                time.sleep(5)

        logger.error(
            f"❌ No se pudo reconectar el share SMB tras {self.retries} intentos."
        )
        return False


# ──────────────────────────────────────────────
# Web server watchdog
# ──────────────────────────────────────────────
class WebServerWatchdog:
    """Checks and restarts the Flask web server process."""

    def __init__(self, cfg: dict):
        wd = cfg["watchdog"]
        self.host = wd.get("web_server_host", "localhost")
        self.port = int(wd.get("web_server_port", 5000))
        rel_script = wd.get("web_app_script", "sga_web/app.py")
        self.app_script = os.path.join(BASE_DIR, rel_script)
        self.web_dir = os.path.dirname(self.app_script)
        self.threshold = int(wd.get("web_restart_threshold", 2))

        self.process: subprocess.Popen | None = None
        self.consecutive_failures = 0

    # ----------------------------------------------------------
    def is_up(self) -> bool:
        """Return True when the web server is listening on its port."""
        try:
            with socket.create_connection((self.host, self.port), timeout=5):
                return True
        except Exception:
            return False

    def restart(self) -> bool:
        """Stop any existing process and launch a fresh one."""
        self._stop_existing()
        self._kill_port()
        time.sleep(3)

        if not os.path.exists(self.app_script):
            logger.error(f"❌ Script del servidor web no encontrado: {self.app_script}")
            return False

        log_path = os.path.join(LOG_DIR, "web_server.log")
        logger.info(f"Iniciando servidor web: {self.app_script} ...")

        try:
            flags = (
                subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(
                    f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                    f"--- Watchdog restart ---\n"
                )
                self.process = subprocess.Popen(
                    [sys.executable, self.app_script],
                    cwd=self.web_dir,
                    stdout=lf,
                    stderr=lf,
                    creationflags=flags,
                )

            # Give it a moment to bind the port
            for i in range(30):
                time.sleep(2)
                if self.is_up():
                    logger.info(
                        f"✅ Servidor web iniciado (PID {self.process.pid}) "
                        f"en {self.host}:{self.port}"
                    )
                    return True
                logger.debug(f"  Esperando que el servidor inicie... ({i+1}/30)")

            logger.warning("[WARNING] El servidor inicio pero aun no responde en el puerto.")
            return False

        except Exception as e:
            logger.error(f"❌ Error al iniciar el servidor web: {e}")
            return False

    # ----------------------------------------------------------
    def _stop_existing(self):
        if self.process and self.process.poll() is None:
            logger.info(f"Deteniendo proceso existente (PID {self.process.pid})...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def _kill_port(self):
        """Kill any process already listening on self.port (Windows)."""
        if sys.platform != "win32":
            return
        try:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if f":{self.port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        subprocess.run(
                            ["taskkill", "/PID", pid, "/F"],
                            capture_output=True,
                            timeout=5,
                        )
                        logger.info(
                            f"Proceso en puerto {self.port} terminado (PID {pid})"
                        )
        except Exception:
            pass


# ──────────────────────────────────────────────
# Main watchdog loop
# ──────────────────────────────────────────────
class Watchdog:
    def __init__(
        self,
        monitor_smb: bool = True,
        monitor_web: bool = True,
        monitor_sap: bool = True,
        interval_override: int | None = None,
    ):
        self.cfg = load_config()
        self.interval = interval_override or self.cfg["watchdog"].get(
            "check_interval", 30
        )
        self.monitor_smb = monitor_smb
        self.monitor_web = monitor_web
        self.monitor_sap = monitor_sap
        self.last_sap_sync = 0

        self.smb = SMBWatchdog(self.cfg) if monitor_smb else None
        self.web = WebServerWatchdog(self.cfg) if monitor_web else None

        self.stats: dict = {
            "watchdog_start": datetime.now().isoformat(),
            "last_check": None,
            "sap_sync": {
                "enabled": monitor_sap,
                "last_sync": None,
                "status": "unknown",
            },
            "smb": {
                "target": self.smb.share_path if self.smb else "disabled",
                "status": "unknown",
                "consecutive_fails": 0,
                "total_disconnects": 0,
                "total_reconnects": 0,
                "last_ok": None,
                "last_fail": None,
            },
            "web": {
                "target": (
                    f"{self.web.host}:{self.web.port}" if self.web else "disabled"
                ),
                "status": "unknown",
                "consecutive_fails": 0,
                "total_restarts": 0,
                "last_ok": None,
                "last_fail": None,
            },
        }

    # ----------------------------------------------------------
    def run(self):
        self._print_banner()
        try:
            while True:
                now = datetime.now().isoformat()
                self.stats["last_check"] = now

                if self.smb:
                    self._check_smb()
                if self.web:
                    self._check_web()
                if self.monitor_sap:
                    self._check_sap_sync()

                self._save_stats()
                logger.debug(f"Siguiente comprobacion en {self.interval}s ...")
                time.sleep(self.interval)

        except KeyboardInterrupt:
            logger.info("Watchdog detenido por el usuario (Ctrl+C).")
        except Exception as e:
            logger.critical(f"Error fatal en el watchdog: {e}", exc_info=True)

    # ----------------------------------------------------------
    def _run_sap_sync_thread(self):
        try:
            import sync_sap_to_db

            logger.info(
                "Iniciando sincronizacion horaria con SAP (en segundo plano)..."
            )
            stats = sync_sap_to_db.run_sync()
            logger.info(f"✅ Sincronizacion SAP completada: {stats}")
            self.stats["sap_sync"]["status"] = "ok"
            self.stats["sap_sync"]["last_sync"] = datetime.now().isoformat()

            # If products were added or updated, we should notify the web server.
            # Easiest way in this architecture is to briefly restart it so it reloads CSV.
            if self.web and stats.get("added", 0) + stats.get("updated", 0) > 0:
                logger.info(
                    "Nuevos productos sincronizados. Reiniciando servidor web para recargar caché..."
                )
                self.web.restart()

        except Exception as e:
            logger.error(f"❌ Error en sincronizacion SAP: {e}")
            self.stats["sap_sync"]["status"] = "error"

    def _check_sap_sync(self):
        # 3600 seconds = 1 hour
        now = time.time()
        if now - self.last_sap_sync >= 3600:
            self.last_sap_sync = now
            # Run in a separate thread to prevent blocking web/smb restart checks
            sync_thread = threading.Thread(
                target=self._run_sap_sync_thread, daemon=True
            )
            sync_thread.start()

    # ----------------------------------------------------------
    def _check_smb(self):
        s = self.stats["smb"]
        if self.smb.is_accessible():
            if self.smb.consecutive_failures > 0:
                logger.info(f"✅ SMB restaurado: {self.smb.share_path}")
            self.smb.consecutive_failures = 0
            s["status"] = "ok"
            s["consecutive_fails"] = 0
            s["last_ok"] = datetime.now().isoformat()
            logger.debug(f"SMB OK: {self.smb.share_path}")
        else:
            self.smb.consecutive_failures += 1
            s["consecutive_fails"] = self.smb.consecutive_failures
            s["total_disconnects"] += 1
            s["status"] = "down"
            s["last_fail"] = datetime.now().isoformat()
            logger.warning(
                f"[WARNING]  SMB no disponible (fallo #{self.smb.consecutive_failures}): "
                f"{self.smb.share_path}"
            )

            if self.smb.can_ping():
                logger.info(
                    "   Servidor alcanzable en el puerto 445 — reconectando share ..."
                )
                if self.smb.reconnect():
                    s["total_reconnects"] += 1
                    s["status"] = "ok"
                    self.smb.consecutive_failures = 0
                    s["consecutive_fails"] = 0
                    s["last_ok"] = datetime.now().isoformat()
            else:
                logger.error(
                    f"   Servidor {self.smb.ip} no responde en el puerto 445."
                    f" La red puede estar caida."
                )

    def _check_web(self):
        w = self.stats["web"]
        if self.web.is_up():
            if self.web.consecutive_failures > 0:
                logger.info(
                    f"✅ Servidor web restaurado en {self.web.host}:{self.web.port}"
                )
            self.web.consecutive_failures = 0
            w["status"] = "ok"
            w["consecutive_fails"] = 0
            w["last_ok"] = datetime.now().isoformat()
            logger.debug(f"Web OK: {self.web.host}:{self.web.port}")
        else:
            self.web.consecutive_failures += 1
            w["consecutive_fails"] = self.web.consecutive_failures
            w["status"] = "down"
            w["last_fail"] = datetime.now().isoformat()
            logger.warning(
                f"[WARNING]  Servidor web no responde (fallo #{self.web.consecutive_failures}/"
                f"{self.web.threshold}) en {self.web.host}:{self.web.port}"
            )

            if self.web.consecutive_failures >= self.web.threshold:
                logger.info("🔄 Reiniciando servidor web ...")
                if self.web.restart():
                    w["total_restarts"] += 1
                    w["status"] = "ok"
                    self.web.consecutive_failures = 0
                    w["consecutive_fails"] = 0
                    w["last_ok"] = datetime.now().isoformat()

    # ----------------------------------------------------------
    def _save_stats(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _print_banner(self):
        logger.info("=" * 62)
        logger.info("  SGA Server Watchdog")
        logger.info("=" * 62)
        if self.smb:
            logger.info(f"  SMB share  : {self.smb.share_path}")
        else:
            logger.info("  SMB share  : deshabilitado")
        if self.web:
            logger.info(f"  Web server : http://{self.web.host}:{self.web.port}")
        else:
            logger.info("  Web server : deshabilitado")
        if self.monitor_sap:
            logger.info("  SAP Sync   : habilitado (1 vez por hora)")
        else:
            logger.info("  SAP Sync   : deshabilitado")
        logger.info(f"  Intervalo  : {self.interval}s")
        logger.info(f"  Log        : {LOG_FILE}")
        logger.info(f"  Stats      : {STATS_FILE}")
        logger.info("=" * 62)


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="SGA Server Watchdog — monitorea el share SMB y el servidor web."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Segundos entre comprobaciones (sobreescribe db_client_config.json).",
    )
    parser.add_argument(
        "--no-smb", action="store_true", help="Deshabilitar monitoreo del share SMB."
    )
    parser.add_argument(
        "--no-web", action="store_true", help="Deshabilitar monitoreo del servidor web."
    )
    parser.add_argument(
        "--no-sap",
        action="store_true",
        help="Deshabilitar la sincronizacion horaria de productos con SAP.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    watchdog = Watchdog(
        monitor_smb=not args.no_smb,
        monitor_web=not args.no_web,
        monitor_sap=not args.no_sap,
        interval_override=args.interval,
    )
    watchdog.run()
