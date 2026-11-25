# Retailo API releases

This repository publishes the Django API container to GitHub Container Registry (GHCR). It does not deploy the image to a production host: the production hosting platform, runtime, secrets, network, and approval process have not been selected in this repository.

## Release prerequisites

Before creating a release tag:

1. Confirm the target commit is on \`main\` and all CI checks for that commit are green, including the container image build.
2. Review the changes and database migration plan. Migrations are a controlled release operation; the image publishing workflow does not run migrations against any database.
3. Confirm the release version follows Semantic Versioning: \`vMAJOR.MINOR.PATCH\`.
4. Confirm the release notes describe user-visible changes, operational changes, and any migration or configuration requirements.

Do not tag an unreviewed feature branch or a commit with failing checks.

## Publish an image

Create and push an annotated version tag from the verified \`main\` commit:

\`\`\`sh
git checkout main
git pull --ff-only
git tag -a v1.0.0 -m "Retailo API v1.0.0"
git push origin v1.0.0
\`\`\`

Replace \`v1.0.0\` with the approved release version. The tag push starts \`.github/workflows/release-api.yml\`.

The workflow builds the backend Dockerfile for \`linux/amd64\`, adds OCI metadata, and publishes:

- \`ghcr.io/anishjoshi103/retailo-api:MAJOR.MINOR.PATCH\`
- \`ghcr.io/anishjoshi103/retailo-api:MAJOR.MINOR\`
- \`ghcr.io/anishjoshi103/retailo-api:MAJOR\`
- \`ghcr.io/anishjoshi103/retailo-api:sha-COMMIT\`

It also publishes BuildKit provenance and an SBOM. Use the immutable commit-SHA tag for exact deployment pinning; major/minor tags are convenience aliases and move as later releases are published.

The workflow uses the repository-scoped \`GITHUB_TOKEN\` with \`packages: write\`; no long-lived registry password is required. GHCR package visibility and access must be reviewed in the package settings. The first publication may create a private package by default.

## Verify a published image

After the workflow succeeds:

1. Open the repository's Actions run and confirm the publish job succeeded.
2. Open the \`retailo-api\` package in GHCR and confirm the expected semantic-version and SHA tags exist.
3. Record the full commit SHA and image digest in the release record.
4. Pull the SHA-pinned image in a non-production environment and run the smoke checks before approving production rollout.

Example:

\`\`\`sh
docker pull ghcr.io/anishjoshi103/retailo-api:sha-COMMIT
\`\`\`

Replace \`COMMIT\` with the actual commit SHA tag published by the workflow.

## Deployment remains environment-specific

The following are intentionally not automated until the production target is defined:

- Provisioning or updating the application runtime.
- Injecting \`DJANGO_SECRET_KEY\`, SQL Server credentials, \`REDIS_URL\`, allowed hosts, and trusted-proxy settings.
- Database migration execution and rollback decisions.
- Traffic shifting, health-check policy, and application rollback.
- Production approval, monitoring, and incident ownership.

Use the [production operations runbook](production-operations-runbook.md) for dependency readiness, migrations, backup verification, and restore drills. The local Docker Compose stack is for development only and is not a production deployment target.

## Rollback

Do not overwrite or retag a published SHA image. Roll back by redeploying the previously approved SHA-pinned image through the hosting platform's release procedure. Database rollback is a separate operation and must follow the migration's reviewed recovery plan; restoring an older application image does not automatically reverse database schema changes.
