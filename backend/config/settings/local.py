import os
from .base import *  # noqa: F403

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
if not SECRET_KEY:
    SECRET_KEY = "unsafe-local-only-key-change-me"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,web,nginx"
    ).split(",")
    if host.strip()
]
DATABASES["default"]["OPTIONS"] = {  # noqa: F405
    "driver": "ODBC Driver 18 for SQL Server",
    "extra_params": "TrustServerCertificate=yes",
}
