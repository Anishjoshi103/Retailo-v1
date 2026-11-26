# SQL Server backup, offsite copy, and restore drill

## Backup design

The scheduled job creates a SQL Server native full backup with `CHECKSUM` and `COMPRESSION`, then:

1. Runs `RESTORE VERIFYONLY ... WITH CHECKSUM` inside SQL Server.
2. Copies the backup to a mounted external drive.
3. Copies it to an rclone **crypt** remote. The remote encrypts both file contents and names before sending data to the offsite storage provider.
4. Verifies the offsite copy with `rclone check`.

The job fails if the external drive is not mounted or if the encrypted offsite copy cannot be verified. A successful SQL backup alone is not treated as a successful backup job.

The SQL Server container writes to `var/backups/sqlserver` on the host. The host directory is mounted at `/var/opt/mssql/backup` in the database container. Create it with the SQL Server container's UID (the current SQL Server Linux image uses UID 10001):

```sh
sudo install -d -o 10001 -g 0 -m 0700 var/backups/sqlserver
```

Confirm the UID against the exact pinned SQL Server image before first use.

## Prepare the external drive

Use a dedicated external SSD/HDD. Prefer full-disk encryption (for example, LUKS on Linux) and store its recovery key separately from the drive. Mount it at a stable path such as `/mnt/retailo-backup`. Configure a filesystem UUID mount in `/etc/fstab` so the drive is available after reboot. Do not rely on a transient `/media/<user>` desktop mount.

Check the mount before running the backup:

```sh
mountpoint /mnt/retailo-backup
df -h /mnt/retailo-backup
```

The backup script refuses to copy into an ordinary directory when the drive is absent. Keep the external drive physically disconnected or locked away when not in use where practical; rotate a second drive if continuous attachment is operationally required.

## Configure encrypted offsite storage with rclone

Install rclone from its official distribution channel. Configure a backend remote for the selected offsite provider, then configure a second remote of type **crypt** that wraps a dedicated folder on that backend. Example names:

- Backend remote: `offsite-store`
- Crypt remote: `retailo-offsite`
- Wrapped path: `offsite-store:retailo-backups/store-001`

Run `rclone config` locally on the store server and follow its prompts. Generate a strong crypt password and salt; store them in an approved password manager and keep a separately protected recovery copy. Enable filename encryption and directory-name encryption. Do not paste provider credentials, crypt passwords, or recovery keys into chat or commit rclone configuration. The script uses the root account's rclone configuration when run by the supplied systemd unit.

Test the crypt remote before scheduling:

```sh
sudo rclone lsd retailo-offsite:
sudo rclone about retailo-offsite:
```

If the selected backend does not support `about`, a small test upload/download through the crypt remote is sufficient. Confirm that the remote is configured as type `crypt`, not as the raw backend.

Create `/etc/retailo/backup.env` with restricted permissions:

```sh
sudo install -d -m 0700 /etc/retailo
sudo install -m 0600 /dev/null /etc/retailo/backup.env
sudoedit /etc/retailo/backup.env
```

Add only non-secret operational paths:

```ini
EXTERNAL_BACKUP_DIR=/mnt/retailo-backup
RCLONE_REMOTE=retailo-offsite:/
DATABASE_NAME=Retailo
```

The rclone crypt password is held by rclone's protected configuration, not this file.

## Run a backup manually

From the deployment checkout:

```sh
sudo EXTERNAL_BACKUP_DIR=/mnt/retailo-backup RCLONE_REMOTE=retailo-offsite:/ scripts/self-hosted/backup.sh
```

For routine operation, use the protected `/etc/retailo/backup.env` through systemd below. Check that the output lists all three copies and ends with `BACKUP_OK`. Confirm the file exists on the external drive and the encrypted remote.

## Schedule nightly backups

The included systemd timer runs daily at 01:30 local server time with a small randomized delay and catches up a missed run after boot.

Install the unit files (adjust `/opt/retailo` if the deployment checkout is elsewhere):

```sh
sudo install -D -m 0644 deploy/systemd/retailo-backup.service /etc/systemd/system/retailo-backup.service
sudo install -D -m 0644 deploy/systemd/retailo-backup.timer /etc/systemd/system/retailo-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now retailo-backup.timer
sudo systemctl list-timers retailo-backup.timer
```

The service runs as root because it needs the Docker socket and the root-owned rclone configuration. The backup script does not print secrets. Review the last run:

```sh
sudo systemctl start retailo-backup.service
sudo systemctl status retailo-backup.service --no-pager
sudo journalctl -u retailo-backup.service -n 100 --no-pager
```

## Restore proof script

A backup is not proven recoverable until SQL Server restores it. The script restores the selected backup to a uniquely named temporary database, runs `DBCC CHECKDB`, and drops that temporary database after a successful check. It never overwrites the live `Retailo` database.

Copy the chosen backup into `var/backups/sqlserver` if it is currently only on the external drive. Then run during a quiet period with sufficient free disk space:

```sh
sudo scripts/self-hosted/restore-proof.sh Retailo_full_YYYYMMDDTHHMMSSZ.bak
```

The script uses the SQL Server instance's data volume for temporary restored files. It requires additional free space approximately equal to the restored database size. A failed restore or consistency check exits non-zero and leaves the temporary database for investigation; do not delete it until the failure has been reviewed.

For a more isolated drill, restore to a separate SQL Server instance with the manual steps below. Never restore over production `Retailo` during a drill.

## Manual isolated restore drill

If the restore-proof script reports an unsupported file type (for example FILESTREAM), or if the drill is performed on a separate recovery server:

1. Run `RESTORE VERIFYONLY` with checksum.
2. Run `RESTORE FILELISTONLY` and note all logical file names.
3. Restore under a new database name and use `MOVE` to new data/log paths.
4. Run `DBCC CHECKDB` on the restored database.
5. Connect the application to the isolated database in a non-production environment and validate store/tenant, branch, product, stock, sales, and GST records.
6. Record the backup timestamp, restore start/end time, validation result, achieved recovery point, and any issues.
7. Drop the temporary recovery database only after evidence has been recorded.

## Monthly drill and retention

- Confirm the latest scheduled job succeeded and both external and offsite copies exist.
- Restore at least one backup in an isolated environment and run consistency checks.
- Verify the crypt password/salt recovery procedure without exposing the keys.
- Confirm retention and deletion policies on the external drive and offsite backend.
- Monitor backup age; alert if the last successful backup is older than 26 hours.
- Retain enough generations to cover the business's agreed recovery point and retention requirements. Do not delete the only known-good backup after a failed run.

A full backup-only schedule does not provide point-in-time recovery between nightly backups. If the store requires a smaller RPO, configure SQL Server recovery model and transaction-log backups with a DBA-reviewed schedule.
