import logging

import httpx
from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.apollo import ApolloClient
from app.services.calendar.factory import get_calendar_adapter
from app.services.calendar.service import CalendarService
from app.services.crm.factory import get_crm_adapter
from app.services.crm.service import CRMService
from app.services.decision.engine import DecisionEngine
from app.services.linkedin.factory import get_linkedin_adapter
from app.services.linkedin.service import LinkedInQueueService
from app.services.voice.factory import get_voice_adapter
from app.workers.tasks import (
    autonomous_pipeline_supervisor_task,
    book_calendar_meeting_task,
    cancel_calendar_meeting_task,
    collect_buying_signals_task,
    execute_call_task,
    execute_email_dispatch_task,
    execute_sequence_step_task,
    expire_buying_signals_task,
    reschedule_calendar_meeting_task,
    run_waterfall_enrichment_task,
    send_email_nudge_task,
    send_linkedin_followup_task,
    start_outbound_sequence,
    start_voice_conversation_task,
    summarize_voice_conversation_task,
    sync_crm_contact_task,
    sync_crm_deal_stage_task,
)

logger = logging.getLogger(__name__)

async def on_startup(ctx):
    """
    ARQ lifecycle worker startup.
    Instantiates global singleton client integrations using a shared client.
    """
    logger.info("Initializing ARQ background worker and service connectors...")
    # Initialize global decoupled HTTP client
    ctx['http_client'] = httpx.AsyncClient()
    
    # Inject client adapters sharing the workspace socket connection pools
    ctx['linkedin_queue'] = LinkedInQueueService(get_linkedin_adapter(ctx['http_client']))
    ctx['apollo_client'] = ApolloClient(
        api_key=settings.APOLLO_API_KEY,
        http_client=ctx['http_client']
    )
    ctx['voice_adapter'] = get_voice_adapter()
    ctx['crm_service'] = CRMService(get_crm_adapter(ctx['http_client']))
    ctx['calendar_service'] = CalendarService(get_calendar_adapter(ctx['http_client']))
    ctx['decision_engine'] = DecisionEngine()
    ctx['sessionmaker'] = AsyncSessionLocal
    ctx['logger'] = logger

async def on_shutdown(ctx):
    """
    ARQ lifecycle worker shutdown.
    Closes the shared HTTP client to release all file descriptors.
    """
    logger.info("Closing ARQ background worker resource pools...")
    if 'http_client' in ctx:
        await ctx['http_client'].aclose()

async def on_task_error(ctx, job_id, error):
    """
    Intercepts execution faults, checks retry parameters,
    and logs critical anomalies to ensure tracing visibility.
    """
    log = ctx.get('logger', logger)
    log.error(f"Execution system fault encountered on Job {job_id}: {str(error)}")

class WorkerSettings:
    """
    ARQ worker configuration blueprint.
    """
    functions = [
        start_outbound_sequence,
        send_linkedin_followup_task,
        execute_email_dispatch_task,
        send_email_nudge_task,
        execute_call_task,
        execute_sequence_step_task,
        autonomous_pipeline_supervisor_task,
        run_waterfall_enrichment_task,
        sync_crm_contact_task,
        sync_crm_deal_stage_task,
        book_calendar_meeting_task,
        cancel_calendar_meeting_task,
        reschedule_calendar_meeting_task,
        collect_buying_signals_task,
        expire_buying_signals_task,
        start_voice_conversation_task,
        summarize_voice_conversation_task
    ]
    # Poll Unipile invitations queue every minute (second=0)
    # Poll Autonomous Supervisor every minute for testing (change to minute=set(range(0, 60, 5)) for production)
    cron_jobs = [
        cron(autonomous_pipeline_supervisor_task, second=0),
        cron(expire_buying_signals_task, hour=set(range(0, 24)), minute=0) # Every hour on the hour
    ]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_error = on_task_error
