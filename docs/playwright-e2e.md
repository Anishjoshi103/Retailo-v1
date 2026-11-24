# Playwright end-to-end tests

The browser suite exercises critical retail workflows against the real Angular application and Django API. It uses an isolated file-backed SQLite database; it does not connect to a developer's SQL Server or production database.

## Run locally

Prerequisites: Python 3.12, Node.js 22, and the backend/frontend dependencies installed.

From the repository root:

```sh
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd frontend
npm ci
npm install --no-save --package-lock=false @playwright/test
npx playwright install chromium
cd ..
```

Prepare the isolated database and demo owner:

```sh
cd backend
DJANGO_SETTINGS_MODULE=config.settings.ci_e2e RETAILO_DEMO_PASSWORD='Use-a-local-test-password-12' python manage.py migrate
DJANGO_SETTINGS_MODULE=config.settings.ci_e2e RETAILO_DEMO_PASSWORD='Use-a-local-test-password-12' python manage.py seed_demo
DJANGO_SETTINGS_MODULE=config.settings.ci_e2e python manage.py runserver 127.0.0.1:8000
```

In another terminal:

```sh
cd frontend
npm start -- --proxy-config proxy.conf.json
```

In a third terminal:

```sh
cd frontend
npx playwright test
```

The demo owner's email is `owner@retailo-demo.local`; use the same local test password supplied to the seed command. Do not use a real account or production password.

## Coverage

- Registration request and its privacy-preserving response
- Owner login and branch GST state configuration
- Product creation through the catalogue
- Goods receipt for the newly-created product
- Split cash/UPI sale, invoice detail and print action
- Partial return and credit note detail
- GST register and CSV download
- Staff invitation

The browser suite uses one serial owner workflow because later steps depend on data created earlier. CI uploads Playwright traces, screenshots and videos on completion for diagnosis.

## Database and environment safety

`config.settings.ci_e2e` derives from the CI settings and overrides only the database to a file-backed SQLite database at the repository root (`.e2e.sqlite3`). Keep this database local and disposable. Never point the E2E job at a production or shared database. The CI workflow seeds the dedicated demo tenant and starts isolated local processes for the API and Angular dev server.
