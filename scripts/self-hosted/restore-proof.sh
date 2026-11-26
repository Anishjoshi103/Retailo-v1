#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
BACKUP_FILE="${1:-}"
RESTORE_DB="${RESTORE_DB:-Retailo_RestoreProof_$(date -u +%Y%m%d%H%M%S)}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/var/backups/sqlserver}"
SQL_FILE="$ROOT_DIR/scripts/sql/restore-proof.sql"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ -n "$BACKUP_FILE" ]] || fail "Usage: $0 <backup-file-name-or-path>"
[[ "$RESTORE_DB" =~ ^[A-Za-z][A-Za-z0-9_]{0,127}$ ]] || fail "RESTORE_DB must be a simple SQL identifier (letters, digits, underscore; max 128 characters)"
[[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE"
[[ -f "$SQL_FILE" ]] || fail "Missing restore SQL script"

if [[ "$BACKUP_FILE" = /* ]]; then
  HOST_FILE="$BACKUP_FILE"
  FILE_NAME="$(basename "$BACKUP_FILE")"
else
  FILE_NAME="$(basename "$BACKUP_FILE")"
  HOST_FILE="$BACKUP_DIR/$FILE_NAME"
fi
[[ -s "$HOST_FILE" ]] || fail "Backup file not found or empty: $HOST_FILE"
[[ "$FILE_NAME" =~ ^[A-Za-z0-9_.-]+\.bak$ ]] || fail "Backup filename contains unsupported characters"

# The backup must also exist in the SQL Server container's mounted backup directory.
CONTAINER_FILE="/var/opt/mssql/backup/$FILE_NAME"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db test -s "$CONTAINER_FILE" \
  || fail "Backup is not available inside SQL Server container at $CONTAINER_FILE"

printf 'Restoring %s to isolated database %s; this uses additional SQL Server disk space.\n' "$HOST_FILE" "$RESTORE_DB"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db bash -lc \
  '/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -b -r 1 -v BackupFile="$1" RestoreDb="$2" -i /dev/stdin' \
  _ "$CONTAINER_FILE" "$RESTORE_DB" < "$SQL_FILE"

printf 'RESTORE_PROOF_PASSED backup=%s restored_database=%s (temporary database removed after DBCC CHECKDB)\n' "$FILE_NAME" "$RESTORE_DB"
