# Authentication API contract (v1)

Base path: `/api/v1/auth/`.

## Endpoints

| Method | Path | Success response | Notes |
|---|---|---|---|
| POST | `register` | `202 Accepted` with generic detail | Body: `store_name`, `email`, `password`. Creates an inactive user, tenant, owner membership, and initial `MAIN` branch transactionally; sends email verification. |
| POST | `verify-email` | `200 OK` | Body: `token`. Signed token expires after 24 hours and cannot be reused after activation. |
| POST | `password-reset/request` | `202 Accepted` with generic detail | Body: `email`. Sends reset link for active accounts without confirming whether the address exists. |
| POST | `password-reset/confirm` | `200 OK` | Body: `uid`, `token`, `password`. Django's password-reset token is invalidated after password change. |
| POST | `login` | `{ "access": "<JWT>" }` | Body: `email`, `password`. Refresh token is set in an HttpOnly cookie. |
| POST | `refresh` | `{ "access": "<JWT>" }` | Uses the HttpOnly `retailo_refresh` cookie; validates active tenant membership. |
| POST | `logout` | `204 No Content` | Revokes refresh token when possible and clears the cookie. |
| GET | `me` | User, tenant, and role summary | Requires bearer access token. |

## Email configuration

Set these deployment environment variables; never commit credentials:

- `FRONTEND_BASE_URL`: public frontend origin used to construct verification/reset links.
- `DEFAULT_FROM_EMAIL`: verified sender address.
- `EMAIL_BACKEND`: production email backend (defaults to Django SMTP backend).
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`.
- `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, and optionally `EMAIL_TIMEOUT`.
- `AUTH_REFRESH_COOKIE_SAMESITE`: `Lax` by default; deployment-specific cross-origin setup needs deliberate review.

The CI settings use Django's in-memory email backend and a non-production example frontend URL.

## Security and rollout notes

- Keep access tokens in memory only; do not put them in local storage.
- Refresh tokens are stored in an HttpOnly cookie scoped to `/api/v1/auth/`.
- The refresh/logout Origin check currently permits same-origin requests; review carefully if the frontend and API use different origins.
- Configure HTTPS, a stable secret signing key, allowed hosts, rate limiting, monitoring, and mail delivery before public deployment.
- Email delivery is synchronous for now. A durable queue/retry system should be added when background-job infrastructure is justified.
- Login currently selects the first active membership. Explicit tenant/store switching is a separate feature.
- This is an implementation milestone, not a production security certification. Validate SMTP failure behavior, throttling, token lifetimes, deployment CORS/CSRF policy, and migrations in CI/staging before public exposure.
