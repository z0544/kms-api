"""הגדרת logging מרוכזת למערכת KMS."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False

DEFAULT_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DEFAULT_LEVEL = os.getenv("KMS_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("KMS_LOG_FILE")  # אופציונלי: אם הוגדר, כותב גם לקובץ עם rotation


def setup_logging(level: str | None = None) -> None:
    """מאתחל logging גלובלי. בטוח לקריאה חוזרת — לא מכפיל handlers."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = (level or DEFAULT_LEVEL).upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # ניקוי handlers קיימים (למשל מ-uvicorn) כדי למנוע פלט כפול
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    # מבטיח UTF-8 גם ב-Windows (אחרת cp1252 מפיל עברית בלוגים)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    if LOG_FILE:
        try:
            path = Path(LOG_FILE).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                path,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            root.warning("לא ניתן לפתוח קובץ לוג %s: %s", LOG_FILE, exc)

    # השתקת רעש מ-libs צד שלישי
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """מחזיר logger במרחב השמות של המודול. מבטיח שה-setup רץ."""
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)
