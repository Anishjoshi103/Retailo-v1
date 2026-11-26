#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
SQL_FILE="$ROOT_DIR/scripts/sql/bootstrap-logins.sql"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE"
[[ -f "$SQL_FILE" ]] || fail "Missing $SQL_FILE"
# Credentials are passed from the protected Compose environment into SQLCMD.
# They are not placed in host command arguments or shell history.
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db bash -lc '
  set -euo pipefail
  : "${MSSQL_SA_PASSWORD:?SQL Server administrator password is not configured}"
  : "${RETAILO_DATABASE_NAME:?Database name is not configured}"
  : "${RETAILO_APP_LOGIN:?Runtime login is not configured}"
  : "${RETAILO_APP_PASSWORD:?Runtime password is not configured}"
  : "${RETAILO_MIGRATION_LOGIN:?Migration login is not configured}"
  : "${RETAILO_MIGRATION_PASSWORD:?Migration password is not configured}"
  /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -b -r 1 \
    -v DatabaseName="$RETAILO_DATABASE_NAME" \
       AppLogin="$RETAILO_APP_LOGIN" AppPassword="$RETAILO_APP_PASSWORD" \
       MigrationLogin="$RETAILO_MIGRATION_LOGIN" MigrationPassword="$RETAILO_MIGRATION_PASSWORD" \
    -i /opt/retailo-sql/bootstrap-logins.sql
'
