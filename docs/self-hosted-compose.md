# Self-hosted production Compose stack

This stack is for a dedicated store server. It uses the same published Retailo API image built by CI; it does not build a different application image on the store server. All image references are required to include immutable SHA-256 digests.

## Included services

- **Caddy** terminates HTTPS using its internal CA. Only its HTTPS port is published, bound to the explicitly configured LAN IPv4 address.
- **API** runs the existing Gunicorn image as the non-root image user. The root filesystem is read-only, Linux capabilities are dropped, and only a small temporary filesystem is writable.
- **SQL Server Express 2022** stores the production database on a persistent named volume. No SQL port is published to the LAN.
- **Redis** provides the shared Django throttle cache required by production settings. It is private to the data network and persists its small AOF state.

All services restart with `unless-stopped`, have health checks, and declare CPU/memory limits. Compose's `deploy.resources.limits` is honored by current Docker Compose implementations; verify limits with `docker inspect` on the target host before relying on them.

## SQL Server Express capacity warning

SQL Server Express has a **10 GB maximum size per relational database data file** (the limit applies to each database, not to the sum of all databases on the instance). Express also has edition-specific compute and memory limits. The Compose configuration defaults to Express and caps the SQL Server container; it does not silently switch to Developer or Standard edition.

Monitor the Retailo database size and alert well before the limit (recommended pilot warning at 7 GB, critical at 8.5 GB). A database reaching 10 GB can stop normal growth and interrupt store operations. Plan a supported move to SQL Server Standard or a managed SQL Server service before the limit is reached. See the main self-hosting guide for the monitoring command and escalation steps.

## Configure image digests

The production Compose file intentionally refuses mutable image tags. For each image, resolve and record the platform-specific digest on a trusted machine with Docker Buildx:

```sh
docker buildx imagetools inspect ghcr.io/anishjoshi103/retailo-api:sha-COMMIT
docker buildx imagetools inspect mcr.microsoft.com/mssql/server:2022-latest
docker buildx imagetools inspect redis:7-alpine
docker buildx imagetools inspect caddy:2-alpine
```

Replace `COMMIT` with the actual commit-SHA tag from the published release. Copy the corresponding `Digest: sha256:...` value into each image variable in `.env.prod`, preserving the readable tag before `@sha256:`. Verify the architecture matches the store server (`linux/amd64` for the current API release workflow). Re-resolve and review digests deliberately when upgrading; do not use `:latest` or floating tags as the only pin.

## Install and start

1. Install Docker Engine and the Compose plugin on a supported 64-bit Linux host.
2. Clone the approved Retailo release or copy the deployment files from that release. Keep the application source tree owned by an administrator.
3. Copy `.env.prod.example` to `.env.prod`, fill in the image digests and unique secrets locally, and run `chmod 600 .env.prod`. Do not paste credentials into chat, tickets, or shell command history.
4. Set `LAN_BIND_IP` to the server's fixed LAN address and configure local DNS (or each POS device's hosts file) so `RETAILO_HOSTNAME` resolves to that address.
5. Validate and start:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

6. Trust Caddy's local root CA on each managed POS device before using the site. Caddy stores its CA under the persistent `retailo_caddy_data` volume. Export the root certificate through an administrator-controlled process and install it in the device's trusted root store. Never distribute the CA private key. Details and remote access options will be in the network/access section of the self-hosting guide.
7. Run the initial database migration as a separately approved step after the backup procedure is installed:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T api python manage.py migrate --noinput
```

Check `https://retailo.lan/api/v1/ready` from a trusted LAN client. A healthy liveness endpoint alone is not sufficient.

## Stop and inspect

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

Do not use `down -v`: it deletes the persistent SQL Server, Redis, and Caddy volumes.
