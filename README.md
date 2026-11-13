# KP ETSIP Release 1

An internal portfolio and application inventory platform with role-scoped access, an executive dashboard, reports, CSV export and audit history. The frontend is React/TypeScript with Vite; the API is FastAPI backed by MongoDB using PyMongo's asynchronous client.

## Run with Docker Compose

Install Docker Compose. Supply private values in your shell or an untracked root `.env` file before starting:

```sh
export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export SEED_ADMIN_PASSWORD='a-private-admin-password'
export SEED_DEMO_PASSWORD='a-private-demo-password'
docker compose up --build -d
```

Passwords must contain at least 12 characters; the signing key must be private and at least 32 characters. Preserve the signing key across restarts: changing it invalidates existing sessions. Open `http://localhost:3000`; `http://localhost:3000/api/health` should return `{"status":"ok"}`. Nginx forwards `/api/` to the backend service. Mongo's `mongo-data` volume is persistent. `docker compose down` stops the services without deleting data. Local Compose MongoDB is unauthenticated and intended only for development; production requires secured MongoDB, TLS, secret management and appropriate network isolation.

Seeding creates six roles, demonstration accounts, three portfolios and ten sample applications idempotently. The administrator account is `admin@ketsip.local` and its initial password is supplied by `SEED_ADMIN_PASSWORD`; first sign-in requires changing it. Other demonstration accounts use `SEED_DEMO_PASSWORD`. Disable `SEED_ON_STARTUP` and avoid demonstration accounts in production. Idempotent seeding does not reset previously changed credentials.

## Local development

Start MongoDB and install Python 3.12 and Node 22.12 or later. Create a virtual environment outside the project, install `backend/requirements.txt`, and configure `backend/.env` using `backend/.env.example` as a field reference. Replace the example JWT value with a generated private secret; that example is intentionally rejected. Start the API from `backend/` with `uvicorn app.main:app --host 127.0.0.1 --port 8000`. Install frontend dependencies with `npm ci` in `frontend/`, then start Vite. Its development proxy forwards `/api` to the API; the client uses same-origin requests unless `VITE_API_BASE_URL` is configured at build time. Do not commit `.env` files.

## Features and security

- JWT sign-in, self-service password change and landing preference; current account and permissions are reloaded from MongoDB.
- Administrator user/role management, soft deactivation and audit history; Auditor access is read-only.
- Scoped portfolio and application inventories with administrator portfolio management, application validation and reference-safe portfolio deletion.
- Dashboard metrics calculated from visible source data and two scoped reports with CSV download. CSV values beginning with spreadsheet formula characters are neutralized. Successful exports are audited.
- APIs are under `/api`; interactive OpenAPI documentation is available at `/docs`. Client-side guards do not replace backend authorization.

Audit persistence is required for a successful audited operation, but local standalone MongoDB does not provide multi-document transactions: an audit failure after a domain write can leave the write persisted while returning an error. Review the operational audit/rollback policy before production. Empty dashboard averages are null; linked portfolios cannot be deleted until references are removed. Deployment to AWS and a secured managed MongoDB service are outside this local setup.

## Tests

Backend tests use an isolated real Mongo database named `ketsip_test`; run from `backend/` with `PYTHONPATH=. python -m pytest -q`. Frontend tests run from `frontend/` with `node node_modules/vitest/vitest.mjs run`; build with `npm run build`. Browser tests use the frontend's Playwright package and isolated local MongoDB, API and Vite servers. From the repository root:

```sh
NODE_PATH="$PWD/frontend/node_modules" node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.ts --grep-invert 'capture representative accessible UI structure'
```

The browser suite uses a fresh randomly named `ketsip_e2e_*` database per invocation. These test databases are not automatically dropped; remove only the test databases you own when no longer needed. See `test_report.yaml` in the pipeline workspace for this run's results and caveats.
