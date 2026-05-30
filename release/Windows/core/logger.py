"""
NetTool - Network Toolbox
Version: V100R008C00SPC700
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Application-wide logging with file output and in-memory UI buffer.
"""

import logging
import logging.handlers
import os
import sys
import threading
import traceback
from datetime import datetime


class _MemoryHandler(logging.Handler):
    """Keeps the last N log records in memory for the UI to display."""

    def __init__(self, capacity=500):
        super().__init__()
        self.capacity = capacity
        self._records = []
        self._lock = threading.Lock()

    def emit(self, record):
        with self._lock:
            self._records.append(self.format(record))
            if len(self._records) > self.capacity:
                self._records.pop(0)

    def get_lines(self):
        with self._lock:
            return list(self._records)

    def clear(self):
        with self._lock:
            self._records.clear()


class AppLogger:
    """Singleton-style logger for the application.

    Usage:
        from core.logger import logger
        logger.info("something happened")
        logger.error("something broke", exc_info=True)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(self._log_dir, exist_ok=True)
        self._log_path = os.path.join(self._log_dir, "app.log")

        self._logger = logging.getLogger("network_toolbox")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()

        # File handler (rotating, max 5MB x 5 backups)
        fh = logging.handlers.RotatingFileHandler(
            self._log_path, maxBytes=5 * 1024 * 1024, backupCount=5,
            encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self._logger.addHandler(fh)

        # Memory handler for UI
        self._mem = _MemoryHandler(capacity=2000)
        self._mem.setLevel(logging.DEBUG)
        self._mem.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        ))
        self._logger.addHandler(self._mem)

        # Also log to stderr when running from terminal
        if sys.stderr and sys.stderr.isatty():
            ch = logging.StreamHandler(sys.stderr)
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S"
            ))
            self._logger.addHandler(ch)

        self._install_hooks()
        self.info("=" * 40)
        self.info("NetTool 启动")
        self.info(f"日志路径: {self._log_path}")
        self.info("=" * 40)

    # -- public API --

    def debug(self, msg, *a, **kw):
        self._logger.debug(msg, *a, **kw)

    def info(self, msg, *a, **kw):
        self._logger.info(msg, *a, **kw)

    def warning(self, msg, *a, **kw):
        self._logger.warning(msg, *a, **kw)

    def error(self, msg, *a, **kw):
        self._logger.error(msg, *a, **kw)

    def exception(self, msg, *a, **kw):
        self._logger.exception(msg, *a, **kw)

    @property
    def log_path(self):
        return self._log_path

    def get_recent_lines(self, n=200):
        """Return the last N log lines from memory."""
        lines = self._mem.get_lines()
        return lines[-n:] if n < len(lines) else lines

    def clear_memory(self):
        self._mem.clear()

    # -- exception hooks --

    def _install_hooks(self):
        """Capture unhandled exceptions in main thread and threads."""

        original_excepthook = sys.excepthook

        def _hook(exc_type, exc_value, exc_tb):
            self._logger.error(
                "未捕获的异常 (主线程):\n%s",
                "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            )
            original_excepthook(exc_type, exc_value, exc_tb)

        sys.excepthook = _hook

        # threading.excepthook (Python 3.8+)
        if hasattr(threading, "excepthook"):
            original_thread_hook = threading.excepthook

            def _thread_hook(args):
                self._logger.error(
                    "未捕获的异常 (线程 %s):\n%s",
                    args.thread.name if args.thread else "?",
                    "".join(traceback.format_exception(args.exc_type,
                                                        args.exc_value,
                                                        args.exc_traceback))
                )
                original_thread_hook(args)

            threading.excepthook = _thread_hook


# Global singleton
logger = AppLogger()
