#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
NEW_API_IMAGE="${1:-}"
LOCK_FILE="${UPDATE_LOCK_FILE:-/var/lock/retailo-update.lock}"
HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-30}"
HEALTH_DELAY_SECONDS="${HEALTH_DELAY_SECONDS:-5}"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE"
[[ -n "$NEW_API_IMAGE" ]] || fail "Usage: $0 <new-api-image@sha256:digest>"
[[ "$NEW_API_IMAGE" =~ ^ghcr\.io/anishjoshi103/retailo-api:[A-Za-z0-9_.-]+@sha256:[a-f0-9]{64}$ ]] \
  || fail "API image must be the approved GHCR Retailo image pinned by a full sha256 digest"
command -v flock >/dev/null || fail "flock is required"
command -v python3 >/dev/null || fail "python3 is required"

exec 9>"$LOCK_FILE"
flock -n 9 || fail "Another Retailo update is already running"

compose() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }

OLD_API_IMAGE="$(sed -n 's/^API_IMAGE=//p' "$ENV_FILE" | head -n 1)"
[[ -n "$OLD_API_IMAGE" ]] || fail "API_IMAGE is missing from $ENV_FILE"
[[ "$OLD_API_IMAGE" =~ @sha256:[a-f0-9]{64}$ ]] || fail "Current API_IMAGE is not digest-pinned"

set_api_image() {
  python3 - "$ENV_FILE" "$1" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
value = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
matches = [i for i, line in enumerate(lines) if line.startswith("API_IMAGE=")]
if len(matches) != 1:
    raise SystemExit("Expected exactly one API_IMAGE entry in .env.prod")
lines[matches[0]] = f"API_IMAGE={value}"
temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(temporary, 0o600)
os.replace(temporary, path)
PY
}

wait_for_health() {
  local attempt
  for ((attempt=1; attempt<=HEALTH_ATTEMPTS; attempt++)); do
    if compose exec -T api python -c \
      "from urllib.request import Request, urlopen; req=Request('http://127.0.0.1:8000/api/v1/ready', headers={'X-Forwarded-Proto': 'https'}); r=urlopen(req, timeout=5); raise SystemExit(0 if r.status == 200 else 1)" \
      >/dev/null 2>&1; then
      if compose exec -T proxy wget -q -O /dev/null --no-check-certificate https://127.0.0.1/api/v1/health \
        >/dev/null 2>&1; then
        return 0
      fi
    fi
    sleep "$HEALTH_DELAY_SECONDS"
  done
  return 1
}

UPDATED=0
ROLLBACK_IN_PROGRESS=0
rollback_on_failure() {
  local status=$?
  trap - EXIT
  if (( status != 0 && UPDATED == 1 && ROLLBACK_IN_PROGRESS == 0 )); then
    ROLLBACK_IN_PROGRESS=1
    printf 'Update failed; restoring previous API image %s\n' "$OLD_API_IMAGE" >&2
    if set_api_image "$OLD_API_IMAGE" && compose config --quiet && compose pull api && compose up -d --no-deps api; then
      if wait_for_health; then
        printf 'APP_ROLLBACK_OK previous API image is healthy.\n' >&2
      else
        printf 'CRITICAL: previous API image was redeployed but readiness did not recover. Keep POS writes stopped and follow the recovery runbook.\n' >&2
      fi
    else
      printf 'CRITICAL: automatic application rollback failed. Keep POS writes stopped and follow the recovery runbook.\n' >&2
    fi
  fi
  exit "$status"
}
trap rollback_on_failure EXIT

printf 'Step 1/5: create and verify a full backup plus external/offsite copies.\n'
BACKUP_OUTPUT="$(bash "$ROOT_DIR/scripts/self-hosted/backup.sh")"
printf '%s\n' "$BACKUP_OUTPUT"
grep -q '^BACKUP_OK ' <<<"$BACKUP_OUTPUT" || fail "Backup script did not report BACKUP_OK"

printf 'Step 2/5: record the previous image and configure the new digest.\n'
set_api_image "$NEW_API_IMAGE"
UPDATED=1
compose config --quiet

printf 'Step 3/5: pull the pinned release images.\n'
compose pull

printf 'Step 4/5: run database migrations as a one-off release task.\n'
compose run --rm --no-deps api python manage.py migrate --noinput

printf 'Step 5/5: activate the new API image and verify API readiness and proxy health.\n'
compose up -d --no-deps api
wait_for_health || fail "New release did not become healthy within the configured window"

UPDATED=0
trap - EXIT
printf 'UPDATE_OK image=%s\n' "$NEW_API_IMAGE"
printf 'Previous image remains pinned in the update log/terminal output for manual recovery if needed: %s\n' "$OLD_API_IMAGE"
