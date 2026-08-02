# ApexSDR Runbook

This runbook outlines operational procedures for the ApexSDR application, intended for on-call engineers and platform operators.

## 1. System Health Monitoring

- **API Health**: `GET /api/v1/health`
- **Kubernetes Liveness**: `GET /api/v1/health/liveness`
- **Kubernetes Readiness**: `GET /api/v1/health/readiness` (Checks PostgreSQL and Redis)
- **Metrics Dashboard**: `GET /metrics` (Prometheus text format)

## 2. Common Alerts and Mitigation

### High `background_queue_depth`
**Symptoms**: Enqueued tasks in ARQ are not being processed; latency for decision updates spikes.
**Mitigation**:
1. Check if the worker process is running: `docker logs apex_sdr_api_gateway | grep "Worker starting"`.
2. Ensure Redis is reachable and not out of memory.
3. Scale up worker instances if CPU bound.

### High `crm_sync_failures_total`
**Symptoms**: Prospects aren't being reflected in HubSpot.
**Mitigation**:
1. Check `ActivityTimeline` for a specific tenant to identify API quota errors.
2. Verify HubSpot API keys in production configuration.
3. If HubSpot is experiencing an outage, the system will continue outreach but CRM syncs will fail; monitor until HubSpot recovers, then force a manual sync via the CRM dashboard if needed.

### Database Connection Saturation
**Symptoms**: `503 Service Unavailable` on `/health/readiness` with `db: down`.
**Mitigation**:
1. Check active connections on PostgreSQL (`pg_stat_activity`).
2. Verify `DATABASE_ASYNC_URL` max connections pool size (default in SQLAlchemy asyncpg pool is often 5-15).
3. If saturated, kill idle transactions or increase max pool size in `app/database.py`.

### Every API request returns 401
**Symptoms**: Authenticated-looking requests to `/api/v1/*` (Prospects, Analytics, Apollo, ICP, etc.) all return `401 Missing authentication credentials.` or `Invalid token`/`Unrecognized API key`.
**Mitigation**:
1. Confirm `SECRET_KEY` is set in the running environment - if unset, every JWT is rejected (fail-closed, not a bug). See `docs/deployment.md` § Authentication & Secrets.
2. If the caller is using an API key rather than a JWT, confirm it's present in `TENANT_API_KEYS` in the exact `key:tenant_id` format.
3. Tenant identity comes **only** from the verified credential now - a caller cannot fix this by passing `?tenant_id=` or an `X-Tenant-ID` header; those are ignored.
4. For local reproduction, mint a known-good token with `python scripts/generate_dev_jwt.py --tenant-id <id>` and retry with it before escalating.

### Webhooks (Twilio / Unipile / Resend) always return 401
**Symptoms**: Inbound call-status, LinkedIn, or email-reply webhooks are rejected instead of processed.
**Mitigation**:
1. Check which secret backs the failing provider: `TWILIO_AUTH_TOKEN` (call-status), `UNIPILE_WEBHOOK_SECRET` (LinkedIn events), `RESEND_WEBHOOK_SECRET` (inbound email, format `whsec_...`). An unset secret fails closed by design.
2. For Resend specifically, also check the request isn't stale - `svix-timestamp` more than 5 minutes old is rejected as a replay-protection measure, even with a correct signature.
3. If the provider recently rotated its signing secret/token, update the corresponding environment variable and restart - there's no dual-secret grace period for Twilio/Unipile (Resend's `svix-signature` header does tolerate multiple space-delimited signatures during a provider-side rotation).

## 3. Deployment Verification

After a deployment, check:
1. `GET /api/v1/health/readiness` returns 200 OK.
2. Migrations successfully applied via the startup event (`docker logs` for "Database migrations applied successfully").
3. Submit a test webhook to `/api/v1/voice/webhook/incoming` (or using Mock Voice UI) to ensure the LLM connects properly.
