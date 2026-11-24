import os

from .base import *  # noqa: F403

if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be configured in production.")
if DEBUG:
    raise RuntimeError("DEBUG must be disabled in production.")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
if not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be configured in production.")

# Production throttling must use a shared service: file and in-memory caches are
# local to a container and allow limits to be bypassed across replicas.
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if not REDIS_URL:
    raise RuntimeError("REDIS_URL must be configured in production.")

CACHES["throttle"] = {  # noqa: F405
    "BACKEND": "django.core.cache.backends.redis.RedisCache",
    "LOCATION": REDIS_URL,
    "KEY_PREFIX": os.environ.get("THROTTLE_CACHE_KEY_PREFIX", "retailo:throttle"),
    "TIMEOUT": 3600,
}

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# TLS is expected to terminate at the edge proxy/load balancer. Keep redirect
# enabled by default; configure the proxy header only when the app is reachable
# exclusively through that trusted proxy.
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() == "true"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "false").lower() == "true"
if os.environ.get("TRUST_PROXY_SSL_HEADER", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
