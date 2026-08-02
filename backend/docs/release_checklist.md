# Release Checklist

Run through this before every production deploy. See `deployment.md` for the
authentication model in depth and `runbook.md` for operational procedures.

## 1. Required secrets

`app/config.py`'s `validate_production_secrets()` makes the app refuse to
start with `ENVIRONMENT=production` if any of these six are missing - this
is enforced at process boot, not discovered later at first request:

| Secret | Used for |
|---|---|
| `SECRET_KEY` | JWT signing/verification for all authenticated API routes |
| `UNIPILE_WEBHOOK_SECRET` | Verifies the `Unipile-Auth` header on inbound LinkedIn webhooks |
| `RESEND_WEBHOOK_SECRET` | Verifies the Svix signature on inbound Resend email webhooks |
| `TWILIO_AUTH_TOKEN` | Verifies `X-Twilio-Signature` on inbound call-status webhooks |
| `GOOGLE_CLIENT_SECRET` | OAuth for Google Calendar meeting booking |
| `HUBSPOT_API_KEY` | CRM deal-stage sync on CLOSED_WON/CLOSED_LOST |

This check only runs when `ENVIRONMENT=production`; development and test
environments boot with any of these unset, and `USE_MOCK_CLIENTS=true`
remains fully supported for local/mock-mode work regardless.

Also required, unchecked by the startup validator (no safe default exists,
but missing them fails individual features rather than blocking boot):
`DATABASE_ASYNC_URL` / `DATABASE_URL`, `REDIS_URL`, `TWILIO_ACCOUNT_SID`,
`TWILIO_FROM_NUMBER`, `GOOGLE_CLIENT_ID`, `GOOGLE_REFRESH_TOKEN`,
`UNIPILE_API_KEY`, `APOLLO_API_KEY`, `GEMINI_API_KEY`, `RESEND_API_KEY`,
`ALLOWED_ORIGINS`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID` (the latter three gate the Voice AI conversation
pipeline's STT/TTS providers - like every other integration, mock mode via
`USE_MOCK_CLIENTS=true` doesn't need real values for them).

Set these in Render's dashboard (declared as `sync: false` in `render.yaml`
so Render prompts for them without the values ever touching git) or in
`backend/.env.production` for a local production-mode run - see
`.env.example` for the full annotated list.

**Frontend**: the deployed frontend needs a bearer credential configured -
either `NEXT_PUBLIC_API_CREDENTIAL` at build time, or an operator pastes one
into Admin Settings → API Credential (stored in that browser's
`localStorage`, sent as `Authorization: Bearer`). There is no tenant-ID
header and no login flow; a credential is a signed JWT or a key registered
in `TENANT_API_KEYS`, minted via `scripts/generate_dev_jwt.py` or an
equivalent internal tool.

## 2. Deployment order

1. Confirm `uv.lock` is committed and up to date (`uv lock --check` exits 0).
2. Confirm every required secret above is set in Render for `apex-sdr-api`.
3. Push/merge to the branch Render's blueprint deploys from.
4. Render builds `Dockerfile.prod`, then runs `bash start.sh`
   (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
5. On boot, before serving any request, the app (in order):
   - fails fast if a required production secret is missing (§1);
   - acquires a Postgres advisory lock and runs `alembic upgrade head`
     (safe under concurrent/scaled instances - only one applies migrations,
     the rest block briefly on the lock and proceed once it's released);
   - opens the shared ARQ Redis pool and starts the embedded ARQ worker in
     the same event loop (there is no separate worker service/dyno - see
     `architecture.md`).
6. Render's health check polls `GET /api/v1/health` (configured via
   `healthCheckPath` in `render.yaml`) before routing traffic to the new
   instance.
7. Confirm `GET /api/v1/health/readiness` reports `db: up` and `redis: up`.

## 3. Rollback

- Render: use "Rollback to this deploy" on the previous successful deploy in
  the Render dashboard. This redeploys the previous image; it does **not**
  revert database migrations.
- If the new release included a migration that the previous image's models
  are incompatible with, first run `alembic downgrade <previous_revision>`
  (via `scripts/`, a one-off Render shell, or locally against the prod DB
  with extreme care) before rolling back the image - deploy order (§2)
  reversed. Prefer additive, backward-compatible migrations so this is
  rarely necessary.
- The embedded worker means rolling back the web service also rolls back
  the worker - there is nothing else to coordinate.

## 4. Migration steps

- Migrations run automatically on boot (§2, step 5) - no manual step in the
  common case.
- To check the current/pending state without booting the full app:
  ```bash
  cd backend
  alembic current
  alembic history --indicate-current
  ```
- To apply manually (e.g. investigating a boot failure):
  ```bash
  DATABASE_ASYNC_URL=<prod-url> alembic upgrade head
  ```
- Every migration in `alembic/versions/` has been verified to `upgrade head`
  and `downgrade -1` cleanly from scratch (see Sprint 6 verification).

## 5. Smoke tests

Run immediately after a deploy reports healthy:

```bash
# 1. Health / readiness / liveness
curl -f https://<render-url>/api/v1/health
curl -f https://<render-url>/api/v1/health/readiness
curl -f https://<render-url>/api/v1/health/liveness

# 2. Auth is enforced (expect 401, not 200 or 500)
curl -s -o /dev/null -w "%{http_code}\n" https://<render-url>/api/v1/prospects

# 3. Auth succeeds with a real credential (expect 200)
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer <token>" \
  https://<render-url>/api/v1/prospects

# 4. Provider circuit-breaker status (confirms secrets loaded, integrations reachable)
curl -s -H "Authorization: Bearer <token>" https://<render-url>/api/v1/health/providers
```

Then, from the frontend: confirm the dashboard loads real metrics (not a
loading/error state), the active-queue and engage-queue lists render, and
the SSE prospect-stream connection in the browser devtools Network tab
shows `200` with `text/event-stream` (not repeated 401s).

## 6. Known pre-existing gaps (not blockers, tracked here for visibility)

- No self-service login/token-issuance endpoint; credentials are minted
  out-of-band (`scripts/generate_dev_jwt.py` or equivalent) and distributed
  to whoever operates the frontend.
- `backend/.env.production` (local-only, gitignored) previously used the
  wrong variable name for CORS (`CORS_ORIGINS` instead of `ALLOWED_ORIGINS`)
  and had 5 of the 6 now-required secrets entirely unset - both fixed this
  release, but real (non-placeholder) values still need to be provisioned
  in Render before this has ever run with real Unipile/Resend/Twilio/Google/
  HubSpot verification in production.
