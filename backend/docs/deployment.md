# ApexSDR Deployment Guide

## Prerequisites
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

## Environment Variables
Ensure `.env.production` is populated securely:
- `ENVIRONMENT="production"`
- `DATABASE_URL` (Standard postgres:// URL for Alembic sync)
- `DATABASE_ASYNC_URL` (postgresql+asyncpg:// URL for FastAPI async sessions)
- `REDIS_URL` (redis:// connection string for ARQ)
- External API Keys: `GEMINI_API_KEY`, `HUBSPOT_API_KEY`, `TWILIO_ACCOUNT_SID`, etc.
- Authentication/webhook secrets - see below. **All authenticated routes fail
  closed (401) if these are unset**, so a fresh production environment must
  set them before traffic is routed to it.

## Authentication & Secrets

All non-webhook API routes are protected by `app.api.v1.auth.verify_tenant`,
which resolves the caller's tenant **only** from a verified bearer
credential - never from a header, query parameter, or request body. It
supports two credential types, tried in this order based on shape:

### JWT signing (primary credential type)
- Config: `SECRET_KEY` - the HS256 signing key. **No insecure default is
  provided**; if unset, every JWT is rejected.
- A valid token must carry a `tenant_id` claim (a non-empty string) and an
  `exp` claim (tokens without an expiration are rejected outright, not just
  ones that have already expired).
- Tokens are verified in `app.core.security.JWTAuthProvider`. There is no
  token-issuance/login endpoint in this codebase - `SECRET_KEY` is meant to
  be shared with whatever service actually authenticates end users and
  mints their session JWTs. For local development only, see "Development
  Authentication" below.
- Generate `SECRET_KEY` with something like `openssl rand -hex 32` and keep
  it out of version control (`.env.production` is gitignored).

### API key configuration (secondary credential type)
- Config: `TENANT_API_KEYS` - a comma-separated `key:tenant_id` list, e.g.
  `TENANT_API_KEYS="sk_live_abc123:tenant_acme,sk_live_def456:tenant_globex"`.
- Intended for server-to-server callers (internal scripts, other backend
  services) that shouldn't need a JWT. Any credential that isn't
  JWT-shaped (i.e. doesn't parse as three dot-separated segments) is looked
  up against this registry with a constant-time comparison; an unrecognized
  key is rejected the same as an invalid JWT.
- There is no expiry or rotation mechanism for these keys beyond editing
  the environment variable and redeploying - rotate by replacing the value
  and restarting the app.
- Empty/unset `TENANT_API_KEYS` means no API key is ever accepted, which is
  the correct default until you deliberately provision one.

### Webhook secrets
Inbound webhooks are a separate trust boundary from the tenant-auth model
above - they're validated against a provider-specific signature, not a
bearer token:

| Provider | Config | Mechanism |
|---|---|---|
| Twilio (call-status webhook) | `TWILIO_AUTH_TOKEN` | `X-Twilio-Signature` header, verified via `twilio.request_validator.RequestValidator` against the full posted form and `PUBLIC_BASE_URL` + request path. |
| Unipile (LinkedIn events) | `UNIPILE_WEBHOOK_SECRET` | Shared secret returned verbatim in the `Unipile-Auth` header (configured when the webhook is created in Unipile), compared with `hmac.compare_digest`. |
| Resend (inbound email replies) | `RESEND_WEBHOOK_SECRET` (format `whsec_...`) | Resend delivers webhooks through Svix: HMAC-SHA256 over `"{svix-id}.{svix-timestamp}.{raw body}"` using the base64-decoded secret as the key, checked against the (possibly multi-valued) `svix-signature` header. The `svix-timestamp` must also be within 5 minutes of the current time. |

All three fail closed with `401` if their secret is unset, the signature is
missing/invalid, or (for Resend) the timestamp is stale - never with a
silent pass-through.

### Development authentication
There is intentionally no user-management system. The **one** supported
way to get a working bearer token for local development is
`backend/scripts/generate_dev_jwt.py`:

```bash
python scripts/generate_dev_jwt.py --tenant-id acme_corp
# prints the token to stdout, and a ready-to-paste
# "Authorization: Bearer <token>" line to stderr
```

It signs with the same `SECRET_KEY` the running app verifies against, so
the token is accepted exactly like a real one. It **refuses to run when
`ENVIRONMENT=production`** and again if `SECRET_KEY` is unset - it is a
local developer convenience, not a second auth backend, and is never
imported by application/route code.

## Docker Build & Run
ApexSDR runs in a single optimized container holding both the FastAPI web server and the ARQ worker (spawned natively via `asyncio.create_task` during FastAPI startup).

Local development (hot reload, bind-mounted source):
```bash
docker compose up -d --build api_gateway
```

Production image - what Render actually builds and runs (`Dockerfile.prod` +
`start.sh`, no reload, no bind mount):
```bash
docker build -f Dockerfile.prod -t apex-sdr-backend-prod .
docker run --env-file .env.production -p 8000:8000 apex-sdr-backend-prod bash start.sh
```

## Database Migrations
Database migrations are automatically applied on application boot via a safely guarded Postgres advisory lock in `src/app/main.py`. This ensures zero race conditions if multiple containers are scaled horizontally.

## Scaling
To handle high background task load, scale the API Gateway horizontally. Each container spins up its own internal ARQ worker connected to the shared Redis queue, seamlessly distributing load.
