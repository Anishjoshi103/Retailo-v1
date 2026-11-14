import os
import tempfile
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
# simplejwt's token_blacklist migrations retype the primary-key columns (AutoField -> BigAutoField)
# in a later migration, which SQL Server rejects ("object ... is dependent on column 'token_id'").
# This app uses a single generated migration that creates the final schema directly instead.
# Regenerate it if simplejwt changes its models:
#   MIGRATION_MODULES points at an empty package, then `manage.py makemigrations token_blacklist`.
MIGRATION_MODULES = {"token_blacklist": "apps.accounts.token_blacklist_migrations"}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "apps.tenancy",
    "apps.accounts",
    "apps.catalog",
    "apps.inventory",
    "apps.sales",
    "apps.gst",
    "rest_framework_simplejwt.token_blacklist",
    "rest_framework",
    "drf_spectacular",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "config.middleware.CorrelationIdMiddleware",
]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DATABASE_ENGINE", "mssql"),
        "NAME": os.environ.get("DATABASE_NAME", "Retailo"),
        "USER": os.environ.get("DATABASE_USER", "sa"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", ""),
        "HOST": os.environ.get("DATABASE_HOST", "db"),
        "PORT": os.environ.get("DATABASE_PORT", "1433"),
        "OPTIONS": {"driver": os.environ.get("DATABASE_DRIVER", "ODBC Driver 18 for SQL Server"), "extra_params": os.environ.get("DATABASE_EXTRA_PARAMS", "")},
    }
}
# Request limits for the endpoints attackers target (see docs/rate-limiting.md and apps/accounts/throttles.py).
THROTTLE_RATES = {
    "login_ip_email": "10/min",   # guessing one account's password from one address
    "login_ip": "60/min",         # one address trying many accounts
    "register_ip": "10/hour",     # each registration creates a store and sends an email
    "reset_email": "3/hour",      # stops mailbox bombing through password reset
    "reset_ip": "20/hour",
    "token_ip": "30/hour",        # guessing email-verification and reset tokens
    "staff_invite": "30/hour",    # per signed-in user; each invitation sends an email
}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": THROTTLE_RATES,
    # How many trusted reverse proxies (for example nginx) sit in front of the app. The client address is
    # read from the right end of X-Forwarded-For, where a client cannot spoof it. 0 ignores the header.
    "NUM_PROXIES": int(os.environ.get("TRUSTED_PROXY_COUNT", "0")),
}
# Rate-limit counters live in a cache that all gunicorn workers share (a per-process cache would let
# each worker count separately). Files in one directory work for a single container; use a database or
# Redis cache if the app is scaled across several containers.
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "throttle": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.environ.get("THROTTLE_CACHE_DIR", os.path.join(tempfile.gettempdir(), "retailo-throttle")),
        # The default of 300 entries would cull counters at random once exceeded.
        "OPTIONS": {"MAX_ENTRIES": 100000},
    },
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
AUTH_REFRESH_COOKIE_SAMESITE = os.environ.get("AUTH_REFRESH_COOKIE_SAMESITE", "Lax")
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "").rstrip("/")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "")
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "false").lower() == "true"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
SPECTACULAR_SETTINGS = {
    "TITLE": "Retailo API",
    "DESCRIPTION": "Versioned API for the Retailo retail POS and inventory platform.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"structured": {"()": "config.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "structured"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
