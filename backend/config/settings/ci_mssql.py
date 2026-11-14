"""CI settings that run the test suite against a real SQL Server (the production database).

Everything else matches ``config.settings.ci``; only the database changes, so a failure here
is a SQL Server incompatibility that the default in-memory SQLite run cannot see.
"""

import os

from .ci import *  # noqa: F403

DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "mssql",
        "NAME": os.environ.get("DATABASE_NAME", "retailo_ci"),
        "USER": os.environ.get("DATABASE_USER", "sa"),
        "PASSWORD": os.environ["DATABASE_PASSWORD"],
        "HOST": os.environ.get("DATABASE_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DATABASE_PORT", "1433"),
        "OPTIONS": {
            "driver": os.environ.get("DATABASE_DRIVER", "ODBC Driver 18 for SQL Server"),
            # The CI container uses a self-signed certificate.
            "extra_params": "TrustServerCertificate=yes",
        },
    }
}
