# Django backend foundation

Settings modules:
- `config.settings.local`: local Docker development; SQL Server and development certificate trust.
- `config.settings.ci`: isolated unit tests with an in-memory SQLite database.
- `config.settings.production`: fail-fast secret/host validation and secure cookie defaults.

Run tests inside the backend container with `DJANGO_SETTINGS_MODULE=config.settings.ci python manage.py test`.
The liveness endpoint is `/api/v1/health` and intentionally does not probe SQL Server.
OpenAPI schema and Swagger UI are available at `/api/v1/schema/` and `/api/v1/docs/`.

Production deployment must supply its own secret, allowed hosts, SQL Server connection
settings, and certificate-validation settings. Do not use the local settings in production.
