from .base import *  # noqa: F403

SECRET_KEY = "ci-only-not-for-deployment"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "test@retailo.invalid"
FRONTEND_BASE_URL = "https://retailo.example.test"
IS_TEST_ENV = True
# The suite signs in and registers far more often than any real client; throttling has its own tests.
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {scope: "100000/min" for scope in THROTTLE_RATES}}  # noqa: F405
CACHES = {**CACHES, "throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "throttle"}}  # noqa: F405
