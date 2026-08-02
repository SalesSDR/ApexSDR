# ApexSDR Disaster Recovery Plan

## 1. Database Failure (PostgreSQL)

If the primary PostgreSQL database drops offline, the web API will return `503 Service Unavailable` on read/write endpoints, and ARQ background tasks will fail, bubbling exceptions up to the retry engine.

**Recovery Steps**:
- Identify the root cause via the hosting provider (OOM, Disk Full, Network Partition).
- If transient, ARQ's built-in exponential backoff will automatically resume tasks without data loss.
- If permanent, restore the database from the latest PITR (Point in Time Recovery) snapshot. Re-point the `DATABASE_URL` environment variables to the new instance and restart containers.

## 2. Queue Failure (Redis)

If Redis drops, the system cannot enqueue new tasks, and running tasks may drop their result futures.

**Recovery Steps**:
- Redis in this architecture acts purely as an ephemeral task queue (no persistent business state is stored in Redis; the source of truth is Postgres).
- Restart Redis.
- Once Redis is healthy, the Decision Engine's evaluation loop (triggered manually or by schedule) will naturally pick up prospects that were stuck in processing states and re-enqueue them based on their `next_action_at` timestamp.

## 3. External API Outages (LLM, CRM, Calendar)

**Recovery Steps**:
- **LLM Outage (Gemini)**: Voice webhooks gracefully fallback to pre-recorded/canned safe statements to end the call elegantly. Outbound sequences will hit standard retry backoffs in ARQ. Monitor the provider's status page.
- **CRM Outage (HubSpot)**: Sync tasks fail gracefully, logging to Prometheus (`crm_sync_failures_total`) but they do not block outbound engagement. You must run a manual batch sync script once HubSpot recovers.
- **Calendar Outage (Google)**: Meeting booking requests will fail and `calendar_sync_failures_total` will increment. The system prompts the prospect to attempt again later.

## 4. Total Container Failure

**Recovery Steps**:
- Because state is externalized to Postgres and Redis, you can safely kill and replace any API/Worker container.
- Ensure Docker orchestration (Kubernetes / ECS / Swarm) is configured with Healthchecks targeting `/api/v1/health/readiness` to automatically replace unhealthy pods.
