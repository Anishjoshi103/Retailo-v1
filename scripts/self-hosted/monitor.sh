#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
DATABASE_NAME="${DATABASE_NAME:-Retailo}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/var/backups/sqlserver}"
EXTERNAL_BACKUP_DIR="${EXTERNAL_BACKUP_DIR:-}"
DB_WARNING_GB="${DB_WARNING_GB:-7.0}"
DB_CRITICAL_GB="${DB_CRITICAL_GB:-8.5}"
DISK_WARNING_PERCENT="${DISK_WARNING_PERCENT:-80}"
DISK_CRITICAL_PERCENT="${DISK_CRITICAL_PERCENT:-90}"
ALERT_EMAIL="${ALERT_EMAIL:-}"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE"
command -v awk >/dev/null || fail "awk is required"

compose() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }
DB_IDENT="${DATABASE_NAME//]/]]}"
QUERY="SET NOCOUNT ON; USE [$DB_IDENT]; SELECT CAST(COALESCE(SUM(size),0)*8.0/1024/1024 AS decimal(10,2)) FROM sys.database_files WHERE type_desc = 'ROWS';"
DB_GB="$(compose exec -T db bash -lc '/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -h -1 -W -Q "$1"' _ "$QUERY" | tr -d '\r' | xargs)"
[[ "$DB_GB" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "Could not parse SQL Server data-file size: $DB_GB"

ALERTS=()
log_alert() {
  local severity="$1" message="$2"
  ALERTS+=("$severity: $message")
  if [[ "$severity" == "CRITICAL" ]]; then
    logger -p user.err -t retailo-monitor "$message" || true
  else
    logger -p user.warning -t retailo-monitor "$message" || true
  fi
}

if awk -v v="$DB_GB" -v t="$DB_CRITICAL_GB" 'BEGIN { exit !(v >= t) }'; then
  log_alert CRITICAL "SQL Server Express data files for $DATABASE_NAME are ${DB_GB} GiB; critical threshold ${DB_CRITICAL_GB} GiB (10 GiB edition ceiling)."
elif awk -v v="$DB_GB" -v t="$DB_WARNING_GB" 'BEGIN { exit !(v >= t) }'; then
  log_alert WARNING "SQL Server Express data files for $DATABASE_NAME are ${DB_GB} GiB; warning threshold ${DB_WARNING_GB} GiB."
fi

check_disk() {
  local path="$1" label="$2" percent
  [[ -e "$path" ]] || { log_alert CRITICAL "$label path does not exist: $path"; return; }
  percent="$(df -P "$path" | awk 'NR == 2 { gsub(/%/, "", $5); print $5 }')"
  [[ "$percent" =~ ^[0-9]+$ ]] || { log_alert CRITICAL "Could not read disk usage for $label ($path)."; return; }
  if (( percent >= DISK_CRITICAL_PERCENT )); then
    log_alert CRITICAL "$label disk usage is ${percent}% (critical ${DISK_CRITICAL_PERCENT}%)."
  elif (( percent >= DISK_WARNING_PERCENT )); then
    log_alert WARNING "$label disk usage is ${percent}% (warning ${DISK_WARNING_PERCENT}%)."
  fi
}

check_disk "$ROOT_DIR" "system"
check_disk "$BACKUP_DIR" "SQL backup"
if [[ -n "$EXTERNAL_BACKUP_DIR" ]]; then
  if mountpoint -q "$EXTERNAL_BACKUP_DIR"; then
    check_disk "$EXTERNAL_BACKUP_DIR" "external backup"
  else
    log_alert CRITICAL "External backup drive is not mounted at $EXTERNAL_BACKUP_DIR."
  fi
fi

if (("${#ALERTS[@]}" > 0)); then
  MESSAGE="$(printf '%s\n' "${ALERTS[@]}")"
  printf '%s\n' "$MESSAGE" >&2
  if [[ -n "$ALERT_EMAIL" ]]; then
    command -v mail >/dev/null || fail "ALERT_EMAIL is set but the mail command is unavailable"
    printf '%s\n' "$MESSAGE" | mail -s "[Retailo] Store server alert" "$ALERT_EMAIL"
  fi
  if printf '%s\n' "${ALERTS[@]}" | grep -q '^CRITICAL:'; then
    exit 2
  fi
  exit 1
fi

logger -p user.info -t retailo-monitor "OK: SQL data files ${DB_GB} GiB; monitored disks below warning thresholds." || true
printf 'MONITOR_OK database_data_gib=%s\n' "$DB_GB"
