# Django production settings for the store server

The self-hosted Compose stack selects `config.settings.production`. Configure these values in the protected local `.env.prod` file; do not commit real values.

| Variable | Required value / purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `DJANGO_SECRET_KEY` | Unique high-entropy secret, generated locally and stored with file permissions restricted to the deployment administrator |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames used by browsers, e.g. `retailo.lan`; no scheme or port |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated full origins including scheme, e.g. `https://retailo.lan` |
| `TRUST_PROXY_SSL_HEADER` | `true` only because the API is reachable through the trusted Caddy reverse proxy |
| `TRUSTED_PROXY_COUNT` | `1` for the single Caddy hop; keep aligned with the actual proxy chain |
| `SECURE_SSL_REDIRECT` | `true`; TLS terminates at Caddy |
| `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_SECURE` | Always enabled by production settings |
| `REDIS_URL` | Supplied internally by Compose for the shared throttle cache |

Production settings fail fast if the secret key, allowed hosts, CSRF trusted origins, or shared Redis URL are missing. CSRF origins are normalized by trimming whitespace and trailing slashes. Do not put `https://` in `DJANGO_ALLOWED_HOSTS`; do include it in `DJANGO_CSRF_TRUSTED_ORIGINS`.

## Proxy trust boundary

Caddy is the only container publishing an application port. It overwrites the forwarded protocol and client-address headers before proxying to Gunicorn. The API port is not published on the host. Do not expose Gunicorn directly or add another proxy without revisiting `TRUSTED_PROXY_COUNT`, `SECURE_PROXY_SSL_HEADER`, and the forwarded-header policy.

The `SECURE_PROXY_SSL_HEADER` setting is enabled only by the explicit `TRUST_PROXY_SSL_HEADER=true` environment value. Never enable it if clients can reach the API directly or supply their own forwarded-protocol header.

## Verify locally on the store host

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T api python -c "from django.conf import settings; print(settings.ALLOWED_HOSTS); print(settings.CSRF_TRUSTED_ORIGINS); print(settings.CSRF_COOKIE_SECURE, settings.SESSION_COOKIE_SECURE); print(settings.SECURE_PROXY_SSL_HEADER)"
```

The output should contain only the intended hostnames/origins and secure-cookie values. Do not print or share the secret key or database password.
