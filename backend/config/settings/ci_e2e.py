from pathlib import Path

from .ci import *  # noqa: F403

# A file-backed SQLite database is shared by the migration/seed commands and the
# long-running Django server in the Playwright job.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(Path(__file__).resolve().parents[3] / ".e2e.sqlite3"),
    }
}
