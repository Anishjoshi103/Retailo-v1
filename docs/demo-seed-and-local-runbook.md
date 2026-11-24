# Demo data and local Docker runbook

This runbook starts the existing Docker Compose development stack and creates an isolated demo tenant. The seed command is for development and product walkthroughs, not production provisioning.

## Prerequisites

- Docker Desktop or Docker Engine with the Compose plugin
- GNU Make, or the equivalent `docker compose` commands
- Ports `8080` and `1433` available locally

The backend image uses Python 3.12 and installs `backend/requirements.txt`.

## 1. Configure and start the stack

From the repository root:

```sh
cp .env.example .env
```

Edit `.env` and set a unique local `DJANGO_SECRET_KEY` and a strong local-only `DATABASE_PASSWORD`. Never commit `.env` or use production credentials.

```sh
make config
make build
make up
docker compose ps
```

Wait until services are healthy. Useful endpoints:

- API health: http://localhost:8080/api/v1/health
- nginx health: http://localhost:8080/healthz
- API docs: http://localhost:8080/api/v1/docs/
- SQL Server: `127.0.0.1:1433` (local machine only)

## 2. Apply migrations

Compose does not run migrations automatically. After SQL Server and the web container are healthy:

```sh
make migrate
```

## 3. Create the demo store

```sh
docker compose exec web python manage.py seed_demo
```

On first run, set and confirm a unique local password of at least 12 characters. Do not reuse a real account password. To change the owner email:

```sh
docker compose exec web python manage.py seed_demo --email demo-owner@example.test
```

The default GST state code is `27` (Maharashtra). Set another two-digit code if needed:

```sh
docker compose exec web python manage.py seed_demo --state-code 29
```

The command creates the reserved `retailo-demo` tenant, owner membership, branches `MAIN` and `WH`, five sample HSN/GST products, one supplier, and opening stock of 50 units per product in each branch. Default login: `owner@retailo-demo.local`.

For non-interactive local automation, set `RETAILO_DEMO_PASSWORD` in the web container process environment. Never put a real password in source control or logs.

### Idempotency and safety

- If the reserved tenant slug belongs to a different store name, the command aborts.
- Existing product definitions that conflict with demo SKUs are not overwritten.
- Existing users outside the demo tenant are not adopted; existing passwords are never reset.
- Opening stock uses deterministic idempotency keys. Reruns do not add the opening quantity again or reset a balance that has subsequently changed.
- A non-zero balance without the matching demo opening movement causes an abort instead of increasing stock.
- Existing branch GST state codes are not replaced. A mismatch aborts; a blank state code is filled.
- No GSTIN is created. Configure and verify a valid branch GSTIN before issuing invoices.
- Sample GST rates are demonstration values, not tax advice or an authoritative HSN/rate catalogue.
- The seed runs in one transaction; validation errors roll back its changes.

## 4. Sign in

Use the owner email and password with `POST /api/v1/auth/login` (body fields `email` and `password`), or use the frontend sign-in screen. The API returns a short-lived access token and sets the refresh token in an HttpOnly cookie.

The seed supports catalogue, branch, supplier, and inventory walkthroughs. It does not create sales, invoices, GSTINs, staff invitations, or payment records.

## 5. Stop the stack

```sh
make down
```

To permanently delete the local SQL Server volume, use the explicit confirmation command:

```sh
make clean-volumes
```

This removes local database data and is not needed for ordinary shutdowns.

## 6. Backend checks

Run from the backend container:

```sh
docker compose exec web sh -lc 'DJANGO_SETTINGS_MODULE=config.settings.ci python manage.py check'
docker compose exec web sh -lc 'DJANGO_SETTINGS_MODULE=config.settings.ci python manage.py test apps.tenancy.test_seed_demo'
```

Run the full project engineering gates before merge.
