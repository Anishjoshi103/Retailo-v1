#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
DATABASE_NAME="${DATABASE_NAME:-Retailo}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/var/backups/sqlserver}"
EXTERNAL_BACKUP_DIR="${EXTERNAL_BACKUP_DIR:-}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
BACKUP_CONTAINER_DIR="/var/opt/mssql/backup"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE"
[[ -d "$BACKUP_DIR" ]] || fail "Create $BACKUP_DIR and grant SQL Server container UID 10001 write access"
[[ -n "$EXTERNAL_BACKUP_DIR" ]] || fail "Set EXTERNAL_BACKUP_DIR to the mounted external-drive destination"
[[ -d "$EXTERNAL_BACKUP_DIR" ]] || fail "External backup destination is not mounted: $EXTERNAL_BACKUP_DIR"
mountpoint -q "$EXTERNAL_BACKUP_DIR" || fail "External backup destination is not a mounted filesystem"
[[ -n "$RCLONE_REMOTE" ]] || fail "Set RCLONE_REMOTE to an rclone crypt remote path"
command -v rclone >/dev/null || fail "Install rclone and configure an encrypted crypt remote"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="${DATABASE_NAME}_full_${STAMP}.bak"
CONTAINER_FILE="$BACKUP_CONTAINER_DIR/$FILE"
HOST_FILE="$BACKUP_DIR/$FILE"
DB_IDENT="${DATABASE_NAME//]/]]}"

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

compose exec -T db bash -lc '/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -b -Q "$1"' _ \
  "BACKUP DATABASE [$DB_IDENT] TO DISK = N'$CONTAINER_FILE' WITH CHECKSUM, COMPRESSION, STATS = 10;"

[[ -s "$HOST_FILE" ]] || fail "SQL Server did not create $HOST_FILE"
compose exec -T db bash -lc '/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -b -Q "$1"' _ \
  "RESTORE VERIFYONLY FROM DISK = N'$CONTAINER_FILE' WITH CHECKSUM;"

# Require both independent copies to complete. Never silently skip either target.
install -m 0600 "$HOST_FILE" "$EXTERNAL_BACKUP_DIR/$FILE"
sync "$EXTERNAL_BACKUP_DIR/$FILE"
rclone copyto "$HOST_FILE" "$RCLONE_REMOTE/$FILE" --immutable --checksum
rclone check "$BACKUP_DIR" "$RCLONE_REMOTE" --one-way --include "$FILE"

printf 'BACKUP_OK file=%s bytes=%s\n' "$FILE" "$(stat -c '%s' "$HOST_FILE")"
printf 'Local:    %s\n' "$HOST_FILE"
printf 'External: %s\n' "$EXTERNAL_BACKUP_DIR/$FILE"
printf 'Offsite:  %s/%s\n' "$RCLONE_REMOTE" "$FILE"
