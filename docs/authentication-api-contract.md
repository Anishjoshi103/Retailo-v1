# Authentication API contract (v1)

## Status and scope

This document is the proposed contract for the first authenticated API slice. It is deliberately not a claim that the endpoints already exist. The current backend scaffold exposes health, schema, and API documentation routes only; it does not yet install Django's authentication apps or define tenant/store models.

The contract must be implemented alongside the tenant identity model and tested before the sign-in UI is considered production-ready.

## Endpoints

All paths are relative to `/api/v1`.

| Method | Path | Intended result |
| --- | --- | --- |
| POST | `/auth/login` | Validate credentials and return a short-lived access token; set a rotating refresh token in a Secure, HttpOnly cookie in production. |
| POST | `/auth/refresh` | Rotate the refresh cookie and return a new access token. Reject missing, expired, revoked, or invalid refresh tokens. |
| POST | `/auth/logout` | Revoke/blacklist the refresh token where supported, clear the cookie, and return 204. |
| POST | `/auth/register` | Accept a registration request only when tenant/store creation and verification are implemented atomically. Do not create an unowned user or silently assign an arbitrary tenant. |
| POST | `/auth/password-reset/request` | Return the same generic response regardless of whether the email exists; send a time-limited, single-use reset message through a configured email provider. |

## Response shape

Successful login and refresh:

```json
{ "access": "<short-lived bearer access token>" }
```

Authentication failures use the shared API error envelope and must not reveal whether an account exists. The frontend must not persist access or refresh tokens in localStorage/sessionStorage. The access token remains in memory; the refresh token is HttpOnly and cookie-based.

## Security requirements

- Use Django's maintained authentication/password hashing facilities. Never store or log raw passwords or tokens.
- Require TLS in production; mark refresh cookies `Secure`, `HttpOnly`, and `SameSite=Lax` or stricter where deployment topology permits.
- Validate CSRF/origin protections for cookie-authenticated state-changing endpoints; `SameSite` alone is not the only CSRF control.
- Rate-limit login, registration, and reset requests at the application edge or a deliberately selected backend mechanism before public launch.
- Use short-lived access tokens and rotating, revocable refresh tokens; reject token reuse after rotation.
- Normalize email consistently and enforce uniqueness at the database layer.
- Registration must establish tenant ownership transactionally and must not let the client choose a tenant ID or role.
- Password reset must use random, single-use, expiring tokens and avoid account enumeration.
- Never return a success response for an operation that was not actually accepted or persisted. A generic reset response is the intentional exception for enumeration resistance.

## Dependencies and implementation gate

Before implementation, select and pin a supported JWT implementation (or explicitly choose Django sessions), define refresh-token revocation/rotation, and settle frontend/backend origin and CSRF behavior. The current `backend/requirements.txt` does not include a JWT package. No new authentication dependency should be added without reviewing its maintenance/security posture.

The current backend has no tenant/store model or account app. Therefore registration cannot safely provision a retailer yet. Implement the tenant identity model and account ownership rules before enabling public registration. Email delivery must also be configured before password reset is advertised as operational.

## Acceptance tests

- Correct credentials produce an access token; incorrect, inactive, or unknown users receive the same generic authentication failure.
- Expired, malformed, revoked, and reused refresh tokens are rejected.
- Refresh rotates the cookie and cannot be used cross-site without the configured CSRF/origin protection.
- Logout clears and revokes refresh credentials.
- Registration cannot choose a tenant or role; duplicate email handling does not disclose account existence.
- Password-reset responses are non-enumerating; valid reset tokens expire and can be consumed only once.
- Every authenticated request is tenant-scoped on the server. Cross-tenant access is denied by negative tests.
