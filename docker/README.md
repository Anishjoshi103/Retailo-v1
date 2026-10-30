# Local container stack

The development stack runs SQL Server 2022 Developer, Django/Gunicorn, and nginx.
SQL Server Developer is for local development/testing only; production should use a
managed SQL Server instance or separately operated database.

## Start

1. Copy `.env.example` to `.env`.
2. Replace the local-only Django secret and database password. SQL Server requires a strong SA password (typically at least 8 characters with uppercase, lowercase, digits, and symbols).
3. Run `make config`, `make build`, then `make up`.
4. Check `http://localhost:8080/api/v1/health` and `http://localhost:8080/healthz`.

Use `make logs` to inspect startup and `make down` to stop services. Database data
persists in the named Docker volume. `make clean-volumes` permanently deletes that
local database volume and asks for explicit confirmation.

The SQL Server port is bound to 127.0.0.1 only. Never commit `.env` or production
credentials. The local SQL Server connection trusts its development certificate;
production certificate validation must be configured explicitly.
