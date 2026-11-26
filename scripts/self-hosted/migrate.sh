#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE"
TEMP_ENV="$(mktemp "${TMPDIR:-/tmp}/retailo-migrate.XXXXXX")"
chmod 0600 "$TEMP_ENV"
trap 'rm -f "$TEMP_ENV"' EXIT
python3 - "$ENV_FILE" "$TEMP_ENV" <<'PY'
import sys
from pathlib import Path
source, destination = map(Path, sys.argv[1:])
lines = source.read_text(encoding="utf-8").splitlines()
values = {}
for line in lines:
    if line and not line.lstrip().startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
required = ("APP_DATABASE_USER", "APP_DATABASE_PASSWORD",
            "MIGRATION_DATABASE_USER", "MIGRATION_DATABASE_PASSWORD")
missing = [key for key in required if not values.get(key)]
if missing:
    raise SystemExit("Missing settings: " + ", ".join(missing))
replacements = {
    "APP_DATABASE_USER": values["MIGRATION_DATABASE_USER"],
    "APP_DATABASE_PASSWORD": values["MIGRATION_DATABASE_PASSWORD"],
}
output = []
seen = set()
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=", 1)[0].strip()
        if key in replacements:
            output.append(f"{key}={replacements[key]}")
            seen.add(key)
            continue
    output.append(line)
if seen != set(replacements):
    raise SystemExit("Expected APP_DATABASE_USER and APP_DATABASE_PASSWORD in .env.prod")
destination.write_text("\n".join(output) + "\n", encoding="utf-8")
PY
docker compose --env-file "$TEMP_ENV" -f "$COMPOSE_FILE" run --rm --no-deps api python manage.py migrate --noinput
