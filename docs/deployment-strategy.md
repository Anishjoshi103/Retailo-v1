# Retailo deployment strategy

This document defines the deployment direction for Retailo. It separates the first store pilot from the later cloud-hosting design so the application remains portable and uses the same published API image in both phases.

## Decision summary

| Phase | Target | Status | Scope |
|---|---|---|---|
| Phase 1 | Self-hosted single-store server using Docker Compose | Implementation | API, SQL Server Express, Redis, TLS reverse proxy, LAN-first access, backups, monitoring, controlled updates |
| Phase 2 | Azure Container Apps + Azure SQL | Design only | Architecture, compatibility assessment, cost/capacity model, migration and operations plan; no IaC or deployment automation yet |

The Phase 1 pilot is the immediate delivery target. Phase 2 must not add Azure dependencies to application business logic or block the self-hosted release.

## Portability principles

1. **One API artifact.** CI builds and publishes the Retailo API image. Both deployment targets consume the same immutable image digest. Do not build a store-specific or Azure-specific application image.
2. **Environment-driven configuration.** Hosts, database connection details, Redis URL, allowed hosts, CSRF origins, public frontend URL, proxy trust, logging, and secrets are injected at runtime.
3. **No host-specific business logic.** Application behavior must not branch on Docker Compose, Azure, store hardware, tunnel provider, or cloud identity.
4. **Explicit infrastructure boundaries.** Compose, reverse proxy, systemd, backup destinations, Azure resources, and cloud identity belong to deployment/operations configuration, not domain code.
5. **Migrations are a release task.** Run migrations once as a controlled step before routing traffic to a release. Do not run migrations independently in every API replica.
6. **Readiness gates traffic.** Liveness reports whether the process is alive; readiness checks required dependencies. Current endpoints are `GET /api/v1/health` (liveness) and `GET /api/v1/ready` (SQL Server and Redis readiness). Preserve these contracts unless a separately reviewed compatibility change adds aliases.
7. **Rollback is explicit.** Keep the previous immutable API image available. Application rollback does not imply database rollback. Schema migrations must use backward-compatible expand/contract changes; database restore is a separately approved recovery operation because it can lose writes after the backup.
8. **Secrets never enter source control.** Use protected local environment files for the store pilot and a managed secret store for a future cloud deployment. Operators must not paste credentials into chat, tickets, or command-line arguments.
9. **Backups are independently recoverable.** A successful backup command is insufficient. Keep a local staging copy, an external/off-host copy, and an encrypted offsite copy, and periodically prove that a restore works.
10. **Security is enforced at the edge and network.** Only the TLS reverse proxy is exposed to POS devices. SQL Server, Redis, and Gunicorn remain on private service networks.

## Phase 1 — self-hosted single-store pilot

### Runtime topology

- Docker Compose runs the API container built by CI, SQL Server Express, Redis, and Caddy (or another reviewed TLS reverse proxy).
- The API container runs Gunicorn as a non-root user, with a read-only root filesystem where supported, dropped capabilities, resource limits, health checks, and a graceful stop period.
- SQL Server and Redis are not published on the store LAN.
- The reverse proxy publishes HTTPS only on the server's LAN address.
- POS clients access the server over the store LAN using a trusted local CA certificate or a real domain with a tunnel-managed TLS route.
- Remote owner/support access is opt-in through a private Tailscale or equivalent tunnel. No inbound router port forwarding is required.

### Data protection and operations

- Schedule a nightly SQL Server full backup.
- Verify the backup, copy it to an external drive, and send an encrypted copy to an offsite target.
- Alert on backup failures, missed backup age, database size, and filesystem capacity.
- Run a restore proof in an isolated database and document a full restore drill.
- Configure host startup, container restart policies, UPS-assisted graceful shutdown, and a power/disk failure checklist.
- Updates take a verified backup, pull immutable image digests, run migrations as a separate step, activate the API, and check readiness. If the application health check fails, restore the prior API image automatically. Never automatically overwrite the live database during rollback.

### Pilot acceptance gates

- [ ] All images are pinned to reviewed immutable digests for the host architecture.
- [ ] Only HTTPS is reachable from the POS LAN; SQL Server, Redis, and Gunicorn are private.
- [ ] POS devices trust the TLS certificate and secure cookies work.
- [ ] Django host, CSRF, and proxy settings match the actual hostname and proxy chain.
- [ ] SQL Server Express size monitoring and disk alerts are delivered to an actively monitored owner.
- [ ] Nightly backup produces verified local, external, and encrypted offsite copies.
- [ ] A restore drill succeeds on an isolated SQL Server instance.
- [ ] UPS shutdown and restart-after-power-loss procedures have been tested.
- [ ] A failed application update returns to the previous image without an unapproved database restore.
- [ ] Store owner signs off on POS smoke tests and recovery ownership.

## Phase 2 — Azure Container Apps + Azure SQL (design only)

No Azure resources, IaC, cloud-specific application code, OIDC deployment workflow, or Azure secret-store integration are authorized by this phase. The following is a design target to validate after the store pilot provides real usage and capacity data.

### Target architecture

- Azure Container Apps hosts the same immutable Retailo API image digest published by CI.
- Azure SQL is the managed relational database target, subject to a compatibility assessment for the current Django ORM, migrations, SQL Server-specific behavior, ODBC driver, collation, isolation, and transaction semantics.
- A managed Redis-compatible service provides the shared Django throttle cache if the selected Azure topology requires it.
- Azure-managed ingress terminates TLS and routes only to healthy API revisions.
- Managed identity and a managed secret store are preferred for runtime access to database credentials and other secrets.
- CI publishes the artifact; a separately approved deployment identity and release workflow would deploy it. The identity should use short-lived federation rather than long-lived client secrets.
- Database backup retention, point-in-time restore, geo-redundancy, and recovery objectives are designed and tested separately from API revision rollback.

### Compatibility questions to resolve before implementation

1. **Database compatibility:** validate Azure SQL support for all schema migrations, constraints, indexes, raw SQL, stored procedures, SQL Server driver options, and test coverage. Identify any unsupported SQL Server instance-level feature or behavior.
2. **Connection management:** size Django/Gunicorn workers and database connection limits against Azure SQL limits; define connection timeouts and retry behavior without retrying non-idempotent writes blindly.
3. **Network/security:** choose private endpoint/VNet integration or a documented restricted public endpoint; define ingress, egress, DNS, and administrator access.
4. **Identity/secrets:** define managed identity permissions, secret rotation, and emergency access.
5. **Scaling:** choose minimum/maximum replicas and scaling signals while ensuring migrations remain a single release task.
6. **Operations:** define logs, metrics, alerts, deployment approvals, maintenance windows, and incident ownership.
7. **Recovery:** define RPO/RTO, retention, restore validation, region recovery, and how application revisions align with database schema compatibility.
8. **Cost:** estimate Container Apps compute, Azure SQL tier/storage/backup, Redis, networking, logging, egress, and non-production environments using measured pilot traffic rather than guessed production load.

### Phase 2 implementation gate

Do not create Bicep/Terraform, Azure Container Apps manifests, Key Vault policies, Azure OIDC deployment workflows, or production Azure resources until the following are approved:

- [ ] Pilot traffic, data growth, and concurrency measurements are available.
- [ ] Azure SQL compatibility assessment and migration rehearsal pass.
- [ ] Availability, RPO/RTO, retention, and regional recovery targets are approved.
- [ ] Network topology and administrative access model are approved.
- [ ] Cost estimate and operating ownership are approved.
- [ ] Release approvals and federated deployment identity are designed.
- [ ] The same API image digest has passed the cloud-target verification gates.

## Release and migration policy

- Build once in CI and publish an immutable API image digest.
- Promote that same digest between environments; do not rebuild the application for the destination host.
- Keep environment-specific configuration and infrastructure definitions outside the application image.
- Run backup verification and migrations as explicit release stages before enabling traffic.
- Use expand/contract database migrations so the previous API image can remain compatible during rollout.
- Roll back the API revision/image automatically when readiness fails, but handle database recovery as a separate, owner-approved procedure.
- Record the deployed image digest, migration result, backup identifier, operator, and release time.

## Current implementation references

- [Self-hosting installation guide](self-hosting.md)
- [Production Compose stack](self-hosted-compose.md)
- [Network and remote access](self-hosted-network-access.md)
- [Backup and restore drill](backup-restore-drill.md)
- [Power and failure runbook](power-and-failure-runbook.md)
- [Safe update and rollback](self-hosted-updates.md)
- [Provider-neutral production operations runbook](production-operations-runbook.md)
