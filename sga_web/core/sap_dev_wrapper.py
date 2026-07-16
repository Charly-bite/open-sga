"""
SAP Development Wrapper
=======================
Drop-in throttle wrapper around SAPHanaConnector for the development environment.
Limits SAP HANA load so dev work doesn't interfere with production.

Features:
    - Single concurrent connection (threading.Semaphore(1))
    - 2-second cooldown between queries
    - Auto-disconnect after 60 seconds of inactivity
    - Full query timing logs for debugging
    - Same API as SAPHanaConnector (transparent to calling code)
"""

import time
import threading
import logging
import functools
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class SAPDevThrottle:
    """
    Wraps SAPHanaConnector to throttle SAP HANA access in development.

    Usage:
        from sap_dev_wrapper import SAPDevThrottle
        from sap_connector import SAPHanaConnector

        base = SAPHanaConnector(...)
        sap = SAPDevThrottle(base)
        sap.connect()
        orders = sap.get_recent_orders(limit=10)
    """

    # Configuration
    MAX_CONCURRENT = 1  # Max simultaneous connections
    COOLDOWN_SECS = 2.0  # Seconds between queries
    IDLE_TIMEOUT = 60  # Auto-disconnect after N seconds idle

    def __init__(self, connector):
        """
        Args:
            connector: A SAPHanaConnector instance to wrap.
        """
        self._sap = connector
        self._semaphore = threading.Semaphore(self.MAX_CONCURRENT)
        self._last_query_time = 0.0
        self._lock = threading.Lock()
        self._idle_timer: Optional[threading.Timer] = None
        self._query_count = 0
        self._total_query_time = 0.0
        logger.info(
            f"[DEV-SAP] Throttle wrapper active: "
            f"max_concurrent={self.MAX_CONCURRENT}, "
            f"cooldown={self.COOLDOWN_SECS}s, "
            f"idle_timeout={self.IDLE_TIMEOUT}s"
        )

    # ------------------------------------------------------------------
    # Proxy all attributes to the underlying connector
    # ------------------------------------------------------------------
    def __getattr__(self, name):
        """Proxy attribute access to the underlying SAPHanaConnector."""
        attr = getattr(self._sap, name)

        # If it's a callable method, wrap it with throttling
        if callable(attr) and not name.startswith("_"):

            @functools.wraps(attr)
            def throttled_call(*args, **kwargs):
                return self._throttled_exec(name, attr, *args, **kwargs)

            return throttled_call

        return attr

    # ------------------------------------------------------------------
    # Core throttle logic
    # ------------------------------------------------------------------
    def _throttled_exec(self, method_name, method, *args, **kwargs):
        """Execute a SAP method with throttling."""
        # Skip throttle for connect/disconnect/simple property checks
        if method_name in ("connect", "disconnect", "test_connection"):
            return method(*args, **kwargs)

        self._semaphore.acquire()
        try:
            # Enforce cooldown
            with self._lock:
                elapsed = time.time() - self._last_query_time
                if elapsed < self.COOLDOWN_SECS:
                    wait = self.COOLDOWN_SECS - elapsed
                    logger.debug(
                        f"[DEV-SAP] Cooldown: waiting {wait:.1f}s before {method_name}"
                    )
                    time.sleep(wait)

            # Execute with timing
            start = time.time()
            logger.info(f"[DEV-SAP] ▶ {method_name}({self._format_args(args, kwargs)})")

            try:
                result = method(*args, **kwargs)
                duration = time.time() - start
                self._query_count += 1
                self._total_query_time += duration

                # Log result summary
                result_summary = self._summarize_result(result)
                logger.info(
                    f"[DEV-SAP] ✅ {method_name} completed in {duration:.2f}s "
                    f"({result_summary}) [query #{self._query_count}]"
                )

                return result

            except Exception as e:
                duration = time.time() - start
                logger.error(
                    f"[DEV-SAP] ❌ {method_name} failed after {duration:.2f}s: {e}"
                )
                raise

            finally:
                with self._lock:
                    self._last_query_time = time.time()
                self._reset_idle_timer()

        finally:
            self._semaphore.release()

    # ------------------------------------------------------------------
    # Idle auto-disconnect
    # ------------------------------------------------------------------
    def _reset_idle_timer(self):
        """Reset the idle disconnect timer."""
        if self._idle_timer:
            self._idle_timer.cancel()

        self._idle_timer = threading.Timer(self.IDLE_TIMEOUT, self._idle_disconnect)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _idle_disconnect(self):
        """Disconnect after idle timeout."""
        logger.info(
            f"[DEV-SAP] ⏰ Idle timeout ({self.IDLE_TIMEOUT}s) — auto-disconnecting. "
            f"Session stats: {self._query_count} queries, "
            f"{self._total_query_time:.1f}s total query time"
        )
        try:
            self._sap.disconnect()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Direct proxy for connect/disconnect (not throttled)
    # ------------------------------------------------------------------
    def connect(self, *args, **kwargs):
        """Connect to SAP HANA (not throttled, but logged)."""
        logger.info("[DEV-SAP] 🔌 Connecting to SAP HANA...")
        result = self._sap.connect(*args, **kwargs)
        if result:
            logger.info("[DEV-SAP] ✅ Connected")
            self._reset_idle_timer()
        return result

    def disconnect(self):
        """Disconnect from SAP HANA."""
        if self._idle_timer:
            self._idle_timer.cancel()
        logger.info(
            f"[DEV-SAP] 🔌 Disconnecting. "
            f"Session stats: {self._query_count} queries, "
            f"{self._total_query_time:.1f}s total query time"
        )
        return self._sap.disconnect()

    @property
    def connected(self):
        return self._sap.connected

    @property
    def connection(self):
        return self._sap.connection

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_args(args, kwargs):
        """Format method arguments for logging (truncated)."""
        parts = []
        for a in args:
            s = repr(a)
            parts.append(s[:50] + "..." if len(s) > 50 else s)
        for k, v in kwargs.items():
            s = repr(v)
            parts.append(f"{k}={s[:40]}{'...' if len(s) > 40 else ''}")
        return ", ".join(parts) if parts else ""

    @staticmethod
    def _summarize_result(result):
        """Create a brief summary of a query result for logging."""
        if result is None:
            return "None"
        if isinstance(result, dict):
            if "data" in result:
                return f"{len(result['data'])} items"
            if "header" in result:
                return f"order #{result['header'].get('order_number', '?')}"
            return f"dict({len(result)} keys)"
        if isinstance(result, list):
            return f"{len(result)} items"
        if hasattr(result, "__len__"):
            return f"{len(result)} rows"
        return str(type(result).__name__)

    def get_stats(self) -> Dict:
        """Return throttle statistics for monitoring."""
        return {
            "query_count": self._query_count,
            "total_query_time": round(self._total_query_time, 2),
            "avg_query_time": round(
                self._total_query_time / max(self._query_count, 1), 2
            ),
            "connected": self.connected,
            "cooldown_secs": self.COOLDOWN_SECS,
            "max_concurrent": self.MAX_CONCURRENT,
            "idle_timeout": self.IDLE_TIMEOUT,
        }
