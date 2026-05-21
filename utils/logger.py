"""
Centralized logging system for PLC Decoder.
Supports file + console output with configurable log levels.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class AppLogger:
    """
    Singleton logger that writes to both console and rotating log file.
    Provides structured log output with timestamp, level, and module context.
    """

    _instance: Optional["AppLogger"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._setup_logger()

    def _setup_logger(self):
        """Configure handlers for console and file logging."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"plc_decoder_{datetime.now().strftime('%Y%m%d')}.log"

        self.logger = logging.getLogger("PLCDecoder")
        self.logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers when re-imported
        if self.logger.handlers:
            return

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(module)s:%(lineno)d — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler (DEBUG+)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)

        # Console handler (INFO+)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        # In-memory log store for GUI log panel
        self._log_records: list[dict] = []

        # Custom handler to capture records for GUI
        gui_handler = _GUILogHandler(self._log_records)
        gui_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(gui_handler)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

    def get_records(self) -> list[dict]:
        """Return in-memory log records for GUI display."""
        return list(self._log_records)

    def clear_records(self):
        """Clear in-memory records (e.g., on new file load)."""
        self._log_records.clear()


class _GUILogHandler(logging.Handler):
    """Custom handler that stores formatted records for GUI consumption."""

    def __init__(self, store: list):
        super().__init__()
        self._store = store

    def emit(self, record: logging.LogRecord):
        try:
            self._store.append(
                {
                    "time": datetime.fromtimestamp(record.created).strftime(
                        "%H:%M:%S"
                    ),
                    "level": record.levelname,
                    "module": record.module,
                    "message": self.format(record).split("—", 1)[-1].strip(),
                }
            )
            # Keep only last 2000 records
            if len(self._store) > 2000:
                self._store.pop(0)
        except Exception:
            pass
