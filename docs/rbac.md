# Retailo role-based access control (RBAC)

This matrix documents the currently implemented API surface. Tenant membership and tenant-scoped querysets are required for tenant data. Branch-scoped operations additionally require an active branch grant; a client-selected branch is never authorization by itself.

## Role definitions

- **OWNER** — full tenant administration and operational access.
- **ADMIN** — tenant administration and operational access, except owner-only actions where introduced.
- **MANAGER** — day-to-day catalogue and store operations.
- **CASHIER** — sales-counter role; access is limited to explicitly granted sales operations as those endpoints are implemented.
- **ACCOUNTANT** — read-only operational access for reviewing catalogue and inventory data. Cannot create or change catalogue/inventory records.

## Current endpoint matrix

| Endpoint | OWNER | ADMIN | MANAGER | CASHIER | ACCOUNTANT |
|---|---|---|---|---|---|
| `GET /api/v1/products` | Read | Read | Read | Read | Read |
| `POST /api/v1/products` | Allow | Allow | Allow | Deny | Deny |
| `GET /api/v1/inventory/balances` | Read, branch grant required | Read, branch grant required | Read, branch grant required | Read, branch grant required | Read, branch grant required |
| `POST /api/v1/inventory/adjustments` | Allow, branch grant required | Allow, branch grant required | Allow, branch grant required | Deny | Deny |

**Important:** This is the implemented endpoint matrix, not a claim that every planned Retailo endpoint already exists. For any new endpoint, add an explicit role decision and endpoint permission tests before shipping. A role not explicitly allowed to mutate data must be denied mutation access. Every branch-scoped request must be validated server-side against active `BranchAccess`.

## Enforcement and testing

- Membership must be active and belong to the authenticated user, selected tenant, and active tenant.
- Tenant-owned reads must use tenant-scoped querysets.
- Branch selection must be checked against active branch access on the server.
- Add tests for each endpoint/method and each role, including denied writes and cross-tenant/unauthorized-branch access.
- The accountant role is intentionally read-only; do not grant write permissions by broad role defaults.
