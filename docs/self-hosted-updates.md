# Safe self-hosted application updates

## Release input

The update script accepts only the Retailo GHCR API image with a full immutable digest. Obtain the exact image digest from the approved GitHub release and verify it against the release commit before running the update.

Example image reference shape (replace both placeholders locally):

```text
ghcr.io/anishjoshi103/retailo-api:sha-COMMIT@sha256:FULL_64_CHARACTER_DIGEST
```

Do not use a floating `:latest`, major, or minor tag for a production update.

## Before updating

- Schedule a quiet maintenance window and stop POS writes.
- Confirm the latest backup timer succeeded and both copies are available.
- Confirm the external drive is mounted and the rclone crypt remote is reachable.
- Check disk free space for the backup and temporary migration/container work.
- Review the release notes and every migration included in the release.
- Ensure migrations follow an expand/contract strategy and remain compatible with the previous API image until the new image is healthy.

## Run the single update script

Run from the deployment checkout. The backup script requires the external drive and encrypted offsite remote to be configured. Use local environment variables or the protected operations environment file; never put credentials on the command line.

```sh
sudo env EXTERNAL_BACKUP_DIR=/mnt/retailo-backup RCLONE_REMOTE=retailo-offsite:store-001 \
  bash scripts/self-hosted/update.sh \
  'ghcr.io/anishjoshi103/retailo-api:sha-COMMIT@sha256:FULL_64_CHARACTER_DIGEST'
```

The script performs these stages in order:

1. Creates a full SQL backup, verifies it, and confirms the external-drive and encrypted offsite copies.
2. Saves the currently deployed API digest in memory and updates only `API_IMAGE` in the protected `.env.prod`.
3. Validates Compose configuration and pulls all pinned images.
4. Runs `manage.py migrate --noinput` in a one-off API container using the dedicated migration login; the long-running API container retains its restricted runtime login.
5. Recreates the API container and checks both Django readiness (SQL Server + Redis) and the reverse proxy health endpoint.

A lock prevents concurrent updates. The script does not print or read secrets from `.env.prod` into logs.

## Automatic rollback behavior

If image pulling, migration execution, container activation, or health checks fail after the new image is selected, the script automatically:

- Restores the previous API image reference in `.env.prod`.
- Pulls that previous digest if needed.
- Recreates the API container with the previous image.
- Checks readiness and proxy health, then reports whether application rollback recovered.

If the old application image does not become healthy, keep POS writes stopped and follow the incident/restore runbook.

**Database schema is not automatically rolled back.** A database restore can discard sales or inventory writes made after the backup, so the script deliberately does not overwrite the live database automatically. Migrations must be backward-compatible with the previous image. If a migration has already changed the schema and the old image cannot run, stop the application and follow the approved restore procedure in [backup and restore](backup-restore-drill.md), with the store owner authorizing the recovery point.

## After update

- Confirm the script prints `UPDATE_OK`.
- Check `docker compose ... ps` and recent API logs.
- Sign in from a POS device; verify store/branch selection, product search, stock view, and a controlled non-financial workflow.
- Reconcile that no pending sales/stock operations were lost during maintenance.
- Keep the pre-update backup and old image digest through the agreed observation period.
- Record the deployed digest, migration result, backup filename, and operator/time in the release log.

## Manual rollback

If the host is interrupted after the update script exits but before the release is accepted, restore the prior approved `API_IMAGE` digest in `.env.prod`, then run:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml pull api
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --no-deps api
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Database recovery remains a separate decision and procedure.
