from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .base import *  # noqa: F403,F401


DEBUG = False

# Use fast, self-contained SQLite for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Isolate media/log outputs
TEST_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="test_media_"))
MEDIA_ROOT = TEST_MEDIA_ROOT

TEST_LOG_DIR = Path(tempfile.mkdtemp(prefix="test_logs_"))
os.environ["LOG_DIR"] = str(TEST_LOG_DIR)
LOG_DIR = TEST_LOG_DIR

from config.logging_config import build_logging_config  # noqa: E402

LOGGING = build_logging_config(BASE_DIR)  # noqa: F405
