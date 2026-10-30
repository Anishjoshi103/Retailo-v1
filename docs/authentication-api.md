# Authentication API contract (v1)

Base path: `/api/v1/auth/`.

## Current endpoints

| Method | Path | Success response | Notes |
|---|---|---|---|
| POST | `login` | `{ "access": "<JWT>" }` | Body: `email`, `password`. Refresh token is set in an HttpOnly cookie. |
| POST | `refresh` | `{ "access": "<JWT>" }` | Uses the HttpOnly `retailo_refresh` cookie; validates active tenant membership. |
| POST | `logout` | `204 No Content` | Revokes refresh token when possible and clears the cookie. |
| GET | `me` | User, tenant, and role summary | Requires bearer access token. |

## Not implemented yet

Registration and password recovery are not available backend endpoints yet. The frontend currently has forms that call these routes; until the backend flows exist, they will fail and must not be advertised as working. Registration must verify email before activating the account and must create the tenant, owner membership, and initial branch transactionally. Password recovery must use single-use, expiring tokens and a configured email delivery channel, with a generic response that does not disclose whether an account exists.

## Security/deployment notes

- Keep access tokens in memory only; do not put them in local storage.
- Refresh tokens are stored in an HttpOnly cookie scoped to `/api/v1/auth/`.
- The current origin check only allows same-origin requests and needs review if the frontend and API are deployed on different origins.
- Configure HTTPS, a stable secret signing key, allowed hosts, rate limiting, monitoring, and the appropriate cookie SameSite policy before public deployment.
- A user's first active membership is selected at login. Multi-tenant account switching is not implemented yet.
