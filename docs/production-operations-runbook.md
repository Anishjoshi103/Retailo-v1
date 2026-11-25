# Production operations runbook

This document describes operational checks for a deployed Retailo environment. It is intentionally provider-neutral: adapt service names, secret storage, backup destinations, access controls, retention, and recovery objectives to the hosting platform and DBA procedures. The Docker Compose stack in the demo runbook is for local development, not production deployment.

## 1. Required production configuration

Before deploying the application, confirm that the deployment platform supplies:

- A strong, unique `DJANGO_SECRET_KEY` through a secret manager.
- `DJANGO_SETTINGS_MODULE=config.settings.production`.
- `DEBUG=false` and an explicit `DJANGO_ALLOWED_HOSTS`.
- `REDIS_URL` for the shared throttle cache. Use TLS where supported and restrict network access.
- SQL Server connection settings and credentials through protected configuration.
- HTTPS termination at a trusted proxy/load balancer. Configure `TRUST_PROXY_SSL_HEADER=true` only when the application is reachable exclusively through that trusted proxy and it overwrites the forwarded-protocol header.
- Correct `TRUSTED_PROXY_COUNT` for the actual proxy chain.
- Persistent, centralized application logs and monitoring for HTTP 5xx responses, dependency failures, disk capacity, and database health.

Do not copy development credentials, demo seed data, or the local Compose configuration into production.

## 2. Deploy and verify

1. Confirm the target environment, release artifact, database target, and rollback plan.
2. Confirm SQL Server and Redis are reachable from the application network.
3. Back up the database and verify that the backup completed before applying schema changes.
4. Deploy the application release using the platform's normal rolling or blue/green procedure.
5. Run Django migrations once as a controlled release step, not independently from every application replica:

   ```sh
   python manage.py migrate --noinput
   ```

6. Verify:
   - `GET /api/v1/health` returns HTTP 200. This is a liveness check and does not prove that dependencies are available.
   - `GET /api/v1/ready` returns HTTP 200. This checks SQL Server and the configured throttle cache.
   - The public HTTPS route works and HTTP is redirected according to the deployment policy.
   - Authentication, store/branch selection, product lookup, and a non-financial smoke test work.
7. Monitor application errors, database connections, cache availability, and latency during rollout.

A readiness response of HTTP 503 means at least one required dependency check failed. The response intentionally does not disclose which dependency or its connection details; use the application logs and platform monitoring to diagnose it.

## 3. Failure response

### Readiness returns 503

1. Check application logs for the dependency name associated with the readiness failure.
2. Verify SQL Server availability, network route, credentials/secret version, connection limits, and database status.
3. Verify Redis availability, TLS settings, network access, credentials, and memory/connection limits.
4. Check whether a recent configuration or secret rotation was applied consistently to all replicas.
5. Restore the failed dependency or roll back the faulty configuration, then confirm `/api/v1/ready` returns HTTP 200.

Do not repeatedly restart all services before identifying the failing dependency; this can amplify connection pressure.

### Deployment or migration failure

- Stop further rollout and retain the previous known-good application artifact.
- Capture migration output and application logs.
- Determine whether the migration completed partially or committed. Inspect the migration state before retrying.
- Do not manually delete migration records or reverse schema changes without a reviewed recovery plan.
- If a database restore is required, use the approved recovery procedure below and coordinate the outage with the store owner/operations lead.

## 4. SQL Server backup procedure

The following is an illustrative SQL Server T-SQL pattern. Replace database and paths with approved values. The backup path is on the SQL Server host, not necessarily the application container.

### Full backup

```sql
BACKUP DATABASE [Retailo]
TO DISK = N'<BACKUP_DIRECTORY>\Retailo_full_<YYYYMMDD_HHMMSS>.bak'
WITH
    COPY_ONLY,
    CHECKSUM,
    COMPRESSION,
    STATS = 10;
GO
```

Use `COPY_ONLY` for an ad-hoc full backup that should not disrupt an existing differential backup chain. For a scheduled backup strategy, the DBA must define whether regular full, differential, and transaction-log backups are required and configure the recovery model and log-backup cadence accordingly.

### Verify the backup file

```sql
RESTORE VERIFYONLY
FROM DISK = N'<BACKUP_DIRECTORY>\Retailo_full_<YYYYMMDD_HHMMSS>.bak'
WITH CHECKSUM;
GO
```

A successful `RESTORE VERIFYONLY` is useful but does not replace a periodic test restore. Copy backups to an access-controlled off-host location, encrypt them at rest and in transit, apply retention rules, and monitor backup age and job failures. Keep encryption certificates/keys recoverable under the organization's key-management process.

## 5. Restore drill and recovery

Perform restore drills in an isolated non-production SQL Server instance. Never run the sample restore commands against production without an approved incident/change procedure and an explicit target confirmation.

1. Select the required backup set and confirm its timestamp, database identity, encryption key availability, and expected recovery point.
2. Restore to a separate recovery database name and separate data/log file paths.
3. Use `RESTORE FILELISTONLY` to identify logical file names before specifying `MOVE` targets:

   ```sql
   RESTORE FILELISTONLY
   FROM DISK = N'<BACKUP_DIRECTORY>\Retailo_full_<YYYYMMDD_HHMMSS>.bak';
   GO
   ```

4. Example isolated restore (replace logical names and paths using the previous output):

   ```sql
   RESTORE DATABASE [Retailo_RecoveryDrill]
   FROM DISK = N'<BACKUP_DIRECTORY>\Retailo_full_<YYYYMMDD_HHMMSS>.bak'
   WITH
       MOVE N'<LOGICAL_DATA_NAME>' TO N'<RECOVERY_DATA_PATH>\Retailo_RecoveryDrill.mdf',
       MOVE N'<LOGICAL_LOG_NAME>' TO N'<RECOVERY_LOG_PATH>\Retailo_RecoveryDrill_log.ldf',
       RECOVERY,
       CHECKSUM,
       STATS = 10;
   GO
   ```

5. Run database consistency checks and application-level validation against the isolated restored database. Confirm critical tenant, branch, inventory, sales, and GST records are present and internally consistent.
6. Record restore duration, achieved recovery point, issues, and corrective actions.

For point-in-time recovery, the DBA must restore the appropriate full backup, optional differential backup, and the complete transaction-log chain in sequence, using a reviewed `STOPAT` target. The exact procedure depends on the configured recovery model and backup schedule; it is not implied by the full-backup example above.

## 6. Operational ownership checklist

- [ ] Named owner for SQL Server backups and restore drills.
- [ ] Backup schedule, retention, off-host copy, encryption, and alerting documented.
- [ ] Restore drill completed and evidence retained.
- [ ] SQL Server and Redis monitoring/alerting configured.
- [ ] Production secrets stored and rotated through an approved secret manager.
- [ ] Deployment, migration, rollback, and incident contacts documented.
- [ ] Recovery time objective (RTO) and recovery point objective (RPO) approved by the business.
