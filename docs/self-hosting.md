# Retailo self-hosted store server — pilot guide

This is the end-to-end installation and operating guide for one Retailo store server. See [deployment strategy](deployment-strategy.md) for the Phase 1 portable-hosting decision and the Phase 2 Azure design-only boundary. It is intentionally environment-driven: the API image is the same immutable GHCR image built by CI, and database/network/secret settings are supplied at runtime. No cloud-specific application code is required.

The deployment is a single-server pilot, not a high-availability architecture. A server, SSD, UPS, or store-network failure can interrupt POS operations. Backups and tested recovery are mandatory before the store goes live.

## 1. Recommended hardware

The current API release workflow publishes `linux/amd64`; use a 64-bit Intel/AMD x86-64 server for this pilot.

| Component | Pilot minimum | Recommended |
|---|---|---|
| CPU | Modern x86-64, 4 physical cores / 8 threads | 6–8 physical cores |
| RAM | 16 GB | 32 GB |
| Internal storage | 2 × 512 GB SSD in mirror/RAID1 | 2 × 1 TB enterprise TLC NVMe SSD in mirror/RAID1 |
| Backup storage | 1 × external USB 3 SSD/HDD, 2 TB | 2 × encrypted external 2 TB drives, rotated |
| Network | Wired Gigabit Ethernet | Dedicated POS VLAN + separate admin access |
| UPS | Sized for measured server + router + switch load | Line-interactive/online UPS with USB/network signalling and enough runtime for orderly shutdown |

**Do not treat one SSD as a backup.** Mirroring helps with a single drive failure but does not protect against deletion, ransomware, theft, fire, or database corruption. Keep an external copy and an encrypted offsite copy.

For the UPS, measure actual wall power under load and size it for at least 15–30 minutes of runtime or enough time for a controlled shutdown. The VA rating depends on the server, switch, router, and monitor load; have the UPS supplier validate the final model. A starting 1000–1500 VA unit may suit a small server/network stack, but it is not a substitute for measuring watts and runtime.

### SQL Server Express capacity planning

SQL Server 2022 Express has a **10 GB maximum relational database size** and a **1,410 MB maximum buffer-pool memory per Database Engine instance**; the Database Engine compute ceiling is the lesser of one socket or four cores. The Compose container memory limit does not remove SQL Express edition limits. See Microsoft's [SQL Server 2022 edition scale limits](https://learn.microsoft.com/en-us/sql/sql-server/editions-and-components-of-sql-server-2022/).

The monitor warns at 7.0 GiB and becomes critical at 8.5 GiB. Start planning a database edition upgrade or migration before 8.5 GiB; do not wait until the 10 GB ceiling interrupts growth.

## 2. Operating system

Use **Ubuntu Server 24.04 LTS, 64-bit amd64, minimal installation** for this pilot. It is an established LTS baseline and Docker Engine officially supports Ubuntu 24.04 and 26.04. Keep the OS on a supported security-update channel. See [Ubuntu 24.04 release notes](https://documentation.ubuntu.com/release-notes/24.04/) and [Docker's Ubuntu installation requirements](https://docs.docker.com/engine/install/ubuntu/).

During OS installation:

- Use a dedicated server hostname such as `retailo-store-01`.
- Use a non-root administrator account with sudo.
- Enable full-disk encryption if recovery procedures for unattended boot are understood and tested.
- Use mirrored internal SSDs where supported.
- Configure a fixed LAN address or DHCP reservation.
- Enable automatic security updates, but schedule Docker/image updates through the Retailo update procedure.
- Do not install a desktop environment unless there is a documented operational need.

## 3. Install Docker Engine and Compose

Run on a fresh Ubuntu Server host. These commands use Docker's official apt repository, not the convenience install script.

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker.service
sudo docker run --rm hello-world
docker compose version
```

Keep Docker Engine and Compose patched. Avoid adding ordinary users to the `docker` group: Docker socket access is effectively root-level access. Use `sudo docker` for administration.

**Firewall note:** Docker-published ports can bypass UFW/firewalld rules depending on the host's packet-filtering configuration. Follow Docker's [packet filtering and firewall guidance](https://docs.docker.com/engine/network/packet-filtering-firewalls/) and enforce source restrictions in the appropriate `DOCKER-USER`/host firewall path. Verify reachability from another device; do not assume a UFW rule alone protects every published container port.

## 4. Prepare the deployment directory

Clone the approved release after PRs #101–#106 and this guide have been reviewed and merged. Use the same Git checkout for the Compose files and scripts.

```sh
sudo git clone https://github.com/Anishjoshi103/Retailo-v1.git /opt/retailo
sudo chown -R root:root /opt/retailo
sudo chmod -R go-w /opt/retailo
cd /opt/retailo
```

Use a reviewed release/tag rather than deploying arbitrary main commits. Keep the deployment checkout writable only by administrators.

Create the SQL backup mount directory. Confirm the UID against the exact pinned SQL Server image before changing ownership:

```sh
sudo install -d -o 10001 -g 0 -m 0700 /opt/retailo/var/backups/sqlserver
```

Prepare an external drive, preferably encrypted, and mount it at a stable path such as `/mnt/retailo-backup`. Configure a filesystem UUID in `/etc/fstab` and verify the mount after reboot.

## 5. Configure environment and image digests

Copy the example file and protect it:

```sh
sudo cp .env.prod.example .env.prod
sudo chmod 600 .env.prod
sudoedit .env.prod
```

Generate secrets locally and enter them directly into `.env.prod`; never paste credentials into chat, tickets, Git, or shell command arguments. Use `openssl rand -base64 48` for `DJANGO_SECRET_KEY` and `openssl rand -hex 32` separately for `SA_PASSWORD`, `APP_DATABASE_PASSWORD`, and `MIGRATION_DATABASE_PASSWORD`. Hex passwords avoid quoting issues in the SQLCMD bootstrap script. Keep `.env.prod` mode `0600`.

Set at least:

- `DJANGO_SECRET_KEY`: unique secret, not the example placeholder.
- `DJANGO_ALLOWED_HOSTS=retailo.lan`: hostname only, no scheme.
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://retailo.lan`: full HTTPS origin.
- `RETAILO_HOSTNAME=retailo.lan`.
- `LAN_BIND_IP`: the server's actual fixed LAN IPv4 address.
- `SA_PASSWORD`: SQL Server administrator password, used only by the SQL Server container and admin-only backup/bootstrap operations.
- `APP_DATABASE_USER` / `APP_DATABASE_PASSWORD`: restricted Django runtime login.
- `MIGRATION_DATABASE_USER` / `MIGRATION_DATABASE_PASSWORD`: separate elevated login used only by the one-off migration task.
- Four image references with full immutable digests: `API_IMAGE`, `SQLSERVER_IMAGE`, `REDIS_IMAGE`, and `CADDY_IMAGE`.

The API image is published by the existing CI release workflow to GHCR. Resolve its digest from the release's commit-SHA tag. Resolve the SQL Server, Redis, and Caddy digests deliberately from the image versions you have reviewed:

```sh
docker buildx imagetools inspect ghcr.io/anishjoshi103/retailo-api:sha-COMMIT
docker buildx imagetools inspect mcr.microsoft.com/mssql/server:2022-latest
docker buildx imagetools inspect redis:7-alpine
docker buildx imagetools inspect caddy:2-alpine
```

Use the immutable form `repository:tag@sha256:64_HEX_CHARACTERS`. The current CI API release workflow targets `linux/amd64`; ensure the server architecture matches. Do not copy example digest placeholders into production. If GHCR package access is private, authenticate on the store server interactively with a least-privilege package-read token; do not put a token in a command argument or repository file.

Validate without starting services:

```sh
sudo docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet
```

## 6. Start and initialize Retailo

1. Configure local DNS so `retailo.lan` resolves to the store server LAN address. Add the Caddy local root CA to every managed POS device as described in [network access](self-hosted-network-access.md).
2. Ensure the external backup drive and encrypted rclone crypt remote are ready. Follow [backup and restore](backup-restore-drill.md).
3. Pull and start the pinned stack:

   ```sh
   sudo docker compose --env-file .env.prod -f docker-compose.prod.yml pull
   sudo docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
   sudo docker compose --env-file .env.prod -f docker-compose.prod.yml ps
   ```

4. Confirm SQL Server, Redis, API, and Caddy health checks pass.
5. Complete the first backup and verify the external and encrypted offsite copies.
6. Provision the database and separate logins once, after SQL Server is healthy:

   ```sh
   sudo bash scripts/self-hosted/bootstrap-db-users.sh
   ```

   This creates the database if absent, a runtime login limited to data read/write and stored-procedure execution, and a separate migration login for schema changes. It is safe to rerun.

7. Run migrations as a one-off task using the migration login; the long-running API continues to use only the restricted runtime login:

   ```sh
   sudo bash scripts/self-hosted/migrate.sh
   ```

8. Verify `https://retailo.lan/api/v1/ready` from a managed POS device.
9. Complete a controlled pilot smoke test: sign in, select the correct store/branch, search a product, inspect stock, and perform only approved test transactions. Reconcile the resulting records before live trading.

Do not open SQL Server, Redis, or Gunicorn ports to the LAN. Do not configure router port forwarding. Remote support is optional and must follow the Tailscale procedure in [network access](self-hosted-network-access.md).

## 7. Install scheduled operations

Follow the full [backup and restore runbook](backup-restore-drill.md), then configure:

- `retailo-backup.timer`: nightly full backup at 01:30 local server time, external copy, encrypted offsite copy.
- `retailo-monitor.timer`: SQL database size and disk capacity checks every 15 minutes.
- Docker auto-start: `sudo systemctl enable --now docker.service`.
- UPS-controlled graceful shutdown: configure the UPS vendor's service or NUT and test a controlled shutdown before live operation.

The supplied systemd units assume the checkout path `/opt/retailo`. If you install elsewhere, update their `WorkingDirectory` and `ExecStart` values.

Set up a working local mail transport if email alerts are required. Confirm an actual warning/critical test reaches the owner's operational mailbox. Journal-only alerts are not a substitute for an actively monitored alert channel.

## 8. Monthly maintenance checklist

- [ ] Review Docker/OS security updates; schedule them in a maintenance window.
- [ ] Confirm all containers are healthy and review API/SQL logs for repeated errors.
- [ ] Check database allocated data-file size; review 7 GiB warning / 8.5 GiB critical thresholds.
- [ ] Check root, SQL data, backup, and external-drive free space.
- [ ] Confirm the previous night's backup has local, external, and encrypted offsite copies.
- [ ] Perform a restore proof or isolated restore drill and record the result.
- [ ] Verify the external drive mount and rotate/disconnect the drive as planned.
- [ ] Check UPS battery health and test its alert path; schedule a controlled shutdown test.
- [ ] Review Tailscale users/devices and ACLs if remote support is enabled; remove obsolete devices.
- [ ] Review administrator accounts, SSH access, firewall rules, TLS expiry/trust, and secret access.
- [ ] Confirm the deployed API image digest matches the approved release record.
- [ ] Record capacity trends and the date when SQL Express will need an upgrade.

## 9. Security checklist before live transactions

- [ ] Ubuntu Server is supported and security updates are enabled.
- [ ] Docker Engine/Compose are installed from the official repository and patched.
- [ ] Deployment directory and `.env.prod` are administrator-only; no secrets are committed.
- [ ] Every container image uses an approved immutable SHA-256 digest.
- [ ] API runs non-root, read-only, with dropped capabilities and no-new-privileges.
- [ ] SQL Server and Redis have no host-published ports.
- [ ] HTTPS is valid on every POS device; Caddy root CA is trusted and its private key is protected.
- [ ] Django allowed hosts, CSRF trusted origins, secure cookies, and trusted proxy settings are correct.
- [ ] LAN access is restricted to the POS subnet; remote access is disabled unless explicitly approved.
- [ ] No router port forwarding, DMZ, UPnP, or Tailscale Funnel is enabled.
- [ ] Nightly backup, external copy, encrypted offsite copy, and restore proof have all succeeded.
- [ ] SQL and disk alerts are delivered to a monitored owner.
- [ ] UPS shutdown and post-power-cut recovery have been tested.
- [ ] A named person owns backup checks, restore drills, security updates, and incident response.

## 10. When to move beyond this pilot

### Upgrade SQL Server Express

Start the migration plan when the database reaches 7 GiB; treat 8.5 GiB as a critical trigger. Move to SQL Server Standard or another supported SQL Server edition before reaching 10 GB. Rehearse the database migration and restore process using a copy before the store depends on it.

### Move to a managed database or cloud host

Consider a managed SQL Server service or cloud-hosted runtime when one or more are true:

- The store requires higher availability than one physical server can provide.
- Database growth, transaction volume, memory, or concurrency exceeds Express or the server's tested capacity.
- The business needs point-in-time recovery, stronger backup retention, and a staffed recovery SLA.
- Multiple stores need centralized access or remote administration beyond a small tailnet.
- Hardware replacement, UPS maintenance, OS patching, and physical security are becoming operational burdens.
- The agreed RTO/RPO cannot be met with one on-site server and nightly backups.

The application remains environment-driven: a later host can supply the same API image with different database host/credentials, Redis URL, allowed hosts, CSRF origins, and trusted proxy settings. Replace the self-hosted Compose runtime and backup/monitoring services with the target platform's equivalents; do not introduce cloud SDK dependencies into business logic merely to move hosting.

A cloud migration still requires a planned SQL Server compatibility, network, secret-management, backup, and data-migration exercise. Moving the API container alone does not migrate the database or provide high availability automatically.
