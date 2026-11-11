# Retailo role-based access control (RBAC)

This matrix describes the API routes currently registered in `config/urls.py` and the role checks implemented by their views. It is not a specification for unimplemented sales, reporting, or administration endpoints.

## Role definitions

- **OWNER** — full tenant operational access; owner-only administration may be added explicitly.
- **ADMIN** — tenant operational access, except owner-only actions where introduced.
- **MANAGER** — day-to-day catalogue, inventory, and purchasing operations.
- **CASHIER** — read access to currently available catalogue/inventory/supplier lists, and may post sales (`POST /api/v1/sales`); no other write endpoint grants cashier mutation access.
- **ACCOUNTANT** — read-only access to currently available catalogue/inventory/supplier lists; no current write endpoint grants accountant mutation access.

## Tenant API role matrix

| Endpoint | OWNER | ADMIN | MANAGER | CASHIER | ACCOUNTANT | Additional server-side scope |
|---|---|---|---|---|---|---|
| `GET /api/v1/products` | Read | Read | Read | Read | Read | Active tenant |
| `POST /api/v1/products` | Allow | Allow | Allow | Deny | Deny | Active tenant |
| `GET /api/v1/inventory/balances` | Read | Read | Read | Read | Read | Active tenant and active branch grant |
| `POST /api/v1/inventory/adjustments` | Allow | Allow | Allow | Deny | Deny | Active tenant and active branch grant |
| `GET /api/v1/inventory/suppliers` | Read | Read | Read | Read | Read | Active tenant |
| `POST /api/v1/inventory/suppliers` | Allow | Allow | Allow | Deny | Deny | Active tenant |
| `POST /api/v1/inventory/receipts` | Allow | Allow | Allow | Deny | Deny | Active tenant and active branch grant |
| `POST /api/v1/inventory/returns` | Allow | Allow | Allow | Deny | Deny | Active tenant and receipt's active branch grant |
| `POST /api/v1/sales` | Allow | Allow | Allow | Allow | Deny | Active tenant and active branch grant. `allow_negative_stock` (sell below on-hand stock) additionally requires owner, admin or manager; cashiers receive 403 |
| `GET /api/v1/sales` | Read | Read | Read | Read | Read | Only sales of branches granted to the membership; `branch_id` outside the grants returns 403 |
| `GET /api/v1/sales/{id}` | Read | Read | Read | Read | Read | Active tenant and active branch grant; others receive 404 |
| `POST /api/v1/sales/{id}/returns` | Allow | Allow | Allow | Allow | Deny | Active tenant and active branch grant on the sale; others receive 404. Refunds are cash only |
| `GET /api/v1/branches` | Read | Read | Read | Read | Read | Only active branches granted to the membership |
| `PATCH /api/v1/branches/{id}` | Allow | Allow | Deny | Deny | Deny | Active tenant and active branch grant; others receive 404 |
| `GET /api/v1/auth/me` | Read | Read | Read | Read | Read | Authenticated active membership |

The write decisions above are enforced by the endpoint role checks. Read routes require an authenticated active tenant membership; the branch-scoped routes additionally verify an active `BranchAccess`. A supplied branch identifier is never authorization by itself.

## Authentication and public routes

The following routes intentionally use public authentication flows rather than tenant membership role checks:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/password-reset/request`
- `POST /api/v1/auth/password-reset/confirm`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

`refresh` and `logout` additionally validate request Origin when supplied and use the refresh-token cookie. `GET /api/v1/health`, `GET /api/v1/schema/`, and `GET /api/v1/docs/` are operational/schema routes, not tenant-role endpoints.

## Enforcement and tests

- Membership must be active and belong to the authenticated user, JWT-selected tenant, and active tenant.
- Tenant-owned reads must use tenant-scoped querysets.
- Branch selection must be checked server-side against active `BranchAccess`; inactive grants and inactive branches do not authorize access.
- Every tenant API method must have an explicit role decision and endpoint tests for allowed and denied roles.
- Cross-tenant object identifiers must be rejected; never trust a tenant or branch identifier supplied by the client without validating it against the authenticated membership.
- Accountant remains read-only; do not grant write access through broad role defaults.

## Coverage notes

The role matrix is backed by endpoint tests for product create/list, inventory adjustment/balance list, supplier create/list, purchase receipt create, and purchase return create. Branch access and cross-tenant rejection are covered by endpoint-specific tests. Public authentication routes have separate authentication-flow tests.
