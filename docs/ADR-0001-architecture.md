# ADR-0001: Retailo Architecture

- Status: Accepted as the initial architecture baseline
- Date: 2026-10-30

## Context

Retailo is a GST-compliant retail POS and inventory platform for
Indian SMB and mid-market retailers. It must support multiple
tenants, branch-level operations, reliable financial records,
and resilient retail workflows.

## Decisions

- Use a modular monolith for the initial product.
- Backend: Django and Django REST Framework.
- Database: Microsoft SQL Server, with SQL Server used in
  development and testing through the approved Django integration.
- Frontend: Angular standalone components, signals, and PWA support.
- Offline client data and synchronization outbox use IndexedDB.
- Use Docker Compose for local development and nginx as the
  reverse proxy.
- Version APIs under /api/v1 and publish an OpenAPI schema.
- Keep money and tax calculations on the server using decimal
  arithmetic; never use binary floating-point for financial values.
- Scope tenant-owned data by tenant_id and apply branch scope
  wherever the domain requires it.
- Treat posted financial records and stock movements as
  append-only; correct them with explicit reversals or adjustment
  records.
- Make retryable mutations idempotent. Sale creation must use
  an Idempotency-Key.
- Keep external service calls outside the atomic sale transaction.
- Keep secrets out of source control; commit only .env.example.
- Record security-sensitive and business-critical mutations
  in an auditable event trail.

## Consequences

- Enforce tenant isolation in querysets and test cross-tenant
  access negatively.
- Add transaction, concurrency, and idempotency tests for sales,
  invoice numbering, and inventory movements.
- Use short-lived access tokens and securely rotated/revocable
  refresh tokens, with HttpOnly cookies and CSRF protection.
- The server is authoritative for official invoices, taxes,
  permissions, and stock.
- Offline invoice issuance and numbering remain unresolved until
  the blueprint's legal review is completed. Do not assume that
  a disconnected device may issue a final GST invoice.

## Source of truth

The approved Retailo Architecture Blueprint v1.0 governs detailed
requirements. If this ADR conflicts with the blueprint, stop and
resolve the discrepancy before implementation.
