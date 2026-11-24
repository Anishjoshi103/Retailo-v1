# Rate limiting

The endpoints attackers go after are limited so that password guessing, mailbox bombing and token
guessing are slow and expensive. A limited request gets **429** with the usual error body
(`code: "throttled"`) and a `Retry-After` header (seconds).

| Scope | Applies to | Key | Default |
|---|---|---|---|
| `login_ip_email` | `POST /auth/login` | client address + email | 10 per minute |
| `login_ip` | `POST /auth/login` | client address | 60 per minute |
| `register_ip` | `POST /auth/register` | client address | 10 per hour |
| `reset_ip` | `POST /auth/password-reset/request` | client address | 20 per hour |
| `reset_email` | `POST /auth/password-reset/request` | the email | 3 per hour |
| `token_ip` | `POST /auth/verify-email`, `POST /auth/password-reset/confirm` | client address | 30 per hour |
| `staff_invite` | `POST /staff`, `POST /staff/{id}/resend-invite` | signed-in user | 30 per hour |

Rates live in `settings.THROTTLE_RATES`. Listing staff and everything after sign-in is not limited here.

## Design choices

- **Sign-in is keyed on address *and* email.** Someone hammering one account from one address is
  stopped, but cannot lock the real owner out from their own address. A second, looser per-address
  limit catches one address trying many accounts.
- **Emails are normalised** (trimmed, case-folded) so changing the case does not evade a limit.
- **Mailbox bombing** through password reset is limited per email, whatever address it comes from.
- **Bad requests are answered as before.** The email is read from the raw JSON body, so a malformed
  body is still a 400 from the view; the address limit is checked first so such requests still count.

## Client address behind a proxy

Behind nginx every connection arrives from the proxy, so the real client address is read from
`X-Forwarded-For`. nginx **appends** the address it saw (`$proxy_add_x_forwarded_for`), so the
right-most entry is trustworthy and anything the client put in front of it is not.

`TRUSTED_PROXY_COUNT` says how many proxies to trust:

- `1` for the bundled nginx (set in `docker-compose.yml`).
- `0` (the default) when the app is reached directly: the header is ignored.
- Too low makes every user share the proxy's address; too high lets clients spoof their address.
  Match it to the real number of proxies in your deployment.

## Where the counters live

- **Local development:** the `throttle` cache uses a file-based cache shared by Gunicorn workers
  inside one container. It is not shared across containers.
- **Production:** `config.settings.production` requires `REDIS_URL` and uses Django's Redis cache
  backend for throttle counters. All application replicas must point to the same Redis deployment
  and the same `THROTTLE_CACHE_KEY_PREFIX` namespace. Redis should be private-network-only, require
  authentication/TLS as appropriate, and have persistence/availability configured to match the
  service's operational requirements.
- Production fails fast if `REDIS_URL` is missing; it will not silently fall back to per-container
  rate limits.

## Production HTTPS and security headers

Production settings enable HTTPS redirects and one year of HSTS by default. TLS should terminate at
the trusted edge proxy/load balancer, which must forward the original scheme to Django. Set
`TRUST_PROXY_SSL_HEADER=true` only when the application cannot be reached except through that
trusted proxy and it overwrites `X-Forwarded-Proto`; otherwise a client could spoof the header.
HSTS subdomains and preload are opt-in because they affect every covered hostname and require
separate domain readiness checks. Set `SECURE_SSL_REDIRECT=false` only for a deliberately
TLS-terminating local/test topology, never as a general production workaround.

## Not covered

- No lockout or CAPTCHA after repeated failures, and no alerting on bursts of 429s.
- Limits on the authenticated API (for example sale posting) are not set; add scopes if abuse appears.
