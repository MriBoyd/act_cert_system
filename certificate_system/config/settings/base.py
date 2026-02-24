import os
from pathlib import Path

from dotenv import load_dotenv

from config.logging_config import build_logging_config

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key-change-me")
DEBUG = False
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.users.apps.UsersConfig",
    "apps.certificates.apps.CertificatesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.RequestContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.certificates.context_processors.feature_flags_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "certificate_db"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "http://127.0.0.1:8000")

LOG_DIR = Path(os.getenv("LOG_DIR", str(BASE_DIR / "logs")))

FEATURE_FLAGS = {
    "admin_dashboard": _env_bool("FF_ADMIN_DASHBOARD", True),
    "template_management": _env_bool("FF_TEMPLATE_MANAGEMENT", True),
    "certificate_generation": _env_bool("FF_CERTIFICATE_GENERATION", True),
    "bulk_generation": _env_bool("FF_BULK_GENERATION", True),
    "certificate_management": _env_bool("FF_CERTIFICATE_MANAGEMENT", True),
    "certificate_detail": _env_bool("FF_CERTIFICATE_DETAIL", True),
    "certificate_download": _env_bool("FF_CERTIFICATE_DOWNLOAD", True),
    "public_verification": _env_bool("FF_PUBLIC_VERIFICATION", True),
    "qr_scanner": _env_bool("FF_QR_SCANNER", True),
    "verification_api": _env_bool("FF_VERIFICATION_API", True),
    "verification_animation": _env_bool("FF_VERIFICATION_ANIMATION", True),
    "log_management": _env_bool("FF_LOG_MANAGEMENT", True),
    "integration_api": _env_bool("FF_INTEGRATION_API", True),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "admin-dashboard"
LOGOUT_REDIRECT_URL = "public-verify"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = build_logging_config(BASE_DIR)
