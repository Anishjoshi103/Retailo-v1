# Retailo

GST-compliant retail POS and inventory platform for Indian retailers.

## Architecture

See `docs/ADR-0001-architecture.md` for the agreed architecture and constraints.

## Local development

Requirements: Docker Engine/Desktop with the Compose plugin, and GNU Make (or run the
equivalent `docker compose` commands directly).

```sh
cp .env.example .env
```

Edit `.env` before starting the stack:
- Set `DJANGO_SECRET_KEY` to a unique local development secret.
- Set `DATABASE_PASSWORD` to a strong local-only password that satisfies SQL Server's password policy.

Then run:

```sh
make config
make build
make up
docker compose ps
```

The API health endpoint is `http://localhost:8080/api/v1/health`; nginx health is
`http://localhost:8080/healthz`. SQL Server is available on `127.0.0.1:1433` for
local database tools. Do not expose this development database publicly.

Useful commands: `make logs`, `make down`, `make migrate`, and `make test`.
For an isolated sample store and demo-data walkthrough, see
[`docs/demo-seed-and-local-runbook.md`](docs/demo-seed-and-local-runbook.md).
To delete the local database volume, use `make clean-volumes` and confirm the prompt.
This permanently removes local SQL Server data.

Never commit `.env`, access tokens, or real credentials. Production database and
secret configuration must be managed outside this development Compose stack.

For the store-server pilot deployment, see the [self-hosting guide](docs/self-hosting.md), [network/access setup](docs/self-hosted-network-access.md), and [backup/restore runbook](docs/backup-restore-drill.md).
