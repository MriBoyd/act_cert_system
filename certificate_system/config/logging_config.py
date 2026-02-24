from __future__ import annotations

import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _level(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().upper()
    # be forgiving for common typos
    if value == "WARN":
        return "WARNING"
    return value


def build_logging_config(base_dir: Path) -> dict:
    log_dir = Path(os.getenv("LOG_DIR", str(base_dir / "logs")))
    log_dir.mkdir(parents=True, exist_ok=True)

    base_level = _level("LOG_LEVEL", "INFO")
    django_level = _level("DJANGO_LOG_LEVEL", base_level)
    audit_level = _level("AUDIT_LOG_LEVEL", base_level)
    security_level = _level("SECURITY_LOG_LEVEL", base_level)

    log_json = _env_bool("LOG_JSON", False)

    formatters: dict = {
        "plain": {
            "format": (
                "%(levelname)s %(asctime)s %(name)s "
                "[rid=%(request_id)s uid=%(user_id)s ip=%(ip)s] "
                "%(method)s %(path)s - %(message)s"
            )
        }
    }

    if log_json:
        # Requires `python-json-logger`
        formatters["json"] = {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": (
                "%(levelname)s %(asctime)s %(name)s %(message)s "
                "%(request_id)s %(user_id)s %(username)s %(ip)s %(method)s %(path)s"
            ),
        }

    formatter_name = "json" if log_json else "plain"

    handlers: dict = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": formatter_name,
            "filters": ["request_context"],
        },
        "app_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(log_dir / "app.log"),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "delay": True,
            "formatter": formatter_name,
            "filters": ["request_context"],
        },
        "audit_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(log_dir / "audit.log"),
            "when": "midnight",
            "backupCount": 30,
            "encoding": "utf-8",
            "delay": True,
            "formatter": formatter_name,
            "filters": ["request_context"],
        },
        "security_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(log_dir / "security.log"),
            "when": "midnight",
            "backupCount": 30,
            "encoding": "utf-8",
            "delay": True,
            "formatter": formatter_name,
            "filters": ["request_context"],
        },
    }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_context": {"()": "config.logging_filters.RequestContextFilter"},
        },
        "formatters": formatters,
        "handlers": handlers,
        "root": {
            "handlers": ["console", "app_file"],
            "level": base_level,
        },
        "loggers": {
            "django": {
                "handlers": ["console", "app_file"],
                "level": django_level,
                "propagate": False,
            },
            "django.request": {
                "handlers": ["console", "app_file"],
                "level": "ERROR",
                "propagate": False,
            },
            "django.security": {
                "handlers": ["console", "security_file"],
                "level": "WARNING",
                "propagate": False,
            },
            "security": {
                "handlers": ["console", "security_file"],
                "level": security_level,
                "propagate": False,
            },
            "audit": {
                "handlers": ["audit_file"],
                "level": audit_level,
                "propagate": False,
            },
            "apps": {
                "handlers": ["console", "app_file"],
                "level": base_level,
                "propagate": False,
            },
            "django.db.backends": {
                "handlers": ["console", "app_file"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }
