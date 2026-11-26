# Store server power, startup, and failure handling

## Automatic startup

Docker must start at boot so Compose restart policies can bring Retailo back after a host reboot.

```sh
sudo systemctl enable --now docker.service
sudo systemctl is-enabled docker.service
sudo systemctl status docker.service --no-pager
```

All production Compose services use `restart: unless-stopped`. Do not manually stop a service and expect it to restart automatically until it is explicitly started again.

After Docker is running, verify the stack:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T api python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/api/v1/ready', timeout=5).status)"
```

The reverse proxy health check and API readiness check should return healthy. Do not open POS access until the SQL Server and Redis dependencies are ready.

## Graceful shutdown

The Compose file defines per-service stop grace periods: SQL Server 60 seconds, API 45 seconds, and Caddy 30 seconds. Docker sends the normal stop signal and allows the configured grace period before forcing termination.

For a host expected to shut down under UPS control, set a Docker daemon shutdown timeout that exceeds the longest container grace period. Merge this setting into the existing `/etc/docker/daemon.json`; do not overwrite other daemon configuration:

```json
{
  "shutdown-timeout": 120
}
```

Validate the JSON before restarting Docker:

```sh
sudo dockerd --validate --config-file=/etc/docker/daemon.json
sudo systemctl restart docker
```

Perform a planned shutdown test before pilot use. Confirm the host powers off cleanly, volumes are intact, and the stack returns healthy after boot. Do not pull power to test shutdown.

## UPS recommendation

Use a line-interactive or online UPS sized for the server, network switch/router, and any required external storage. Select capacity based on measured load and the runtime needed to finish writes and perform a controlled shutdown; have an electrician/UPS vendor validate sizing. Enable USB or network management and configure a host UPS daemon (for example, Network UPS Tools/NUT) to initiate `systemctl poweroff` while battery remains, before the UPS reaches cutoff.

The UPS must protect the network equipment too; otherwise the server may stay powered while POS clients lose connectivity. Test the UPS's low-battery shutdown behavior and automatic power restoration with the hardware vendor's recommended procedure.

## Capacity alerts

The monitor checks:

- Allocated SQL Server Express ROWS data-file size (warning 7.0 GiB, critical 8.5 GiB by default; Express ceiling 10 GiB per database).
- Host/system disk usage (warning 80%, critical 90%).
- SQL backup filesystem usage.
- External backup drive mount and usage.

Install the monitor timer:

```sh
sudo install -D -m 0644 deploy/systemd/retailo-monitor.service /etc/systemd/system/retailo-monitor.service
sudo install -D -m 0644 deploy/systemd/retailo-monitor.timer /etc/systemd/system/retailo-monitor.timer
sudo systemctl daemon-reload
sudo systemctl enable --now retailo-monitor.timer
sudo systemctl list-timers retailo-monitor.timer
```

Add optional email delivery to the protected `/etc/retailo/backup.env` (the host must have a working local `mail` command/MTA):

```ini
ALERT_EMAIL=store-owner@example.invalid
DB_WARNING_GB=7.0
DB_CRITICAL_GB=8.5
DISK_WARNING_PERCENT=80
DISK_CRITICAL_PERCENT=90
```

Use a real operational mailbox locally; the example address is intentionally non-routable. Alerts are also written to the system journal/syslog:

```sh
sudo systemctl start retailo-monitor.service
sudo systemctl status retailo-monitor.service --no-pager
sudo journalctl -t retailo-monitor -n 100 --no-pager
```

A warning exits with status 1 and a critical condition exits with status 2. Configure monitoring of the systemd unit failures so the owner is notified even if email delivery itself fails. Verify alert delivery during commissioning.

## What to do after a power cut

1. Wait for stable mains power and confirm the UPS has recovered. Do not repeatedly power-cycle the server.
2. Start the server and check that the filesystem mounted cleanly. If the OS reports filesystem errors, stop and follow the OS recovery procedure before starting Docker.
3. Check external-drive mounts before running backups. If the drive is missing, do not allow backup jobs to write into the empty mount directory.
4. Check Docker and the Compose stack:

   ```sh
   sudo systemctl status docker --no-pager
   docker compose --env-file .env.prod -f docker-compose.prod.yml ps
   docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 db api proxy
   ```

5. Wait for SQL Server recovery and Redis health checks. Then verify `/api/v1/ready` from a trusted LAN device.
6. If the database is unavailable or consistency errors appear, stop writes and contact the database/operator owner. Do not delete SQL Server files or recreate the database volume.
7. Once service is healthy, run a fresh backup and confirm both copies. Record the outage and any lost transactions.

## What to do after a disk failure

1. Stop POS writes and take the application offline. Do not continue selling against an unstable database disk.
2. Preserve the failed disk for recovery; avoid filesystem repair commands that write to it until an operator has decided whether forensic recovery is needed.
3. Replace the failed disk and reinstall/repair the host OS and Docker using the documented install process.
4. Restore the latest verified backup to a clean SQL Server instance following [the restore drill](backup-restore-drill.md). Obtain the rclone crypt recovery material from the approved password manager if offsite recovery is needed.
5. Run `DBCC CHECKDB`, application smoke tests, and business reconciliation before reopening the store.
6. Record the recovered backup timestamp and estimate the data-loss window from the last successful backup. Escalate if it exceeds the agreed RPO.

Never initialize a new empty production database over a failed volume and assume data has recovered. Keep at least one known-good backup copy disconnected/offsite.
