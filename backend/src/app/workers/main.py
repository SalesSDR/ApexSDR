import logging
import httpx
from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.database import AsyncSessionLocal, redis_client
from app.services.unipile import UnipileClient
from app.services.apollo import ApolloClient
from app.services.twilio import TwilioClient
    start_outbound_sequence,
    send_linkedin_followup_task,
    execute_email_dispatch_task,
    execute_call_task,
    autonomous_pipeline_supervisor_task
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
    ctx['unipile_client'] = UnipileClient(
        api_key=settings.UNIPILE_API_KEY,
        base_url=settings.UNIPILE_BASE_URL,
        http_client=ctx['http_client']
    )
    ctx['apollo_client'] = ApolloClient(
        api_key=settings.APOLLO_API_KEY,
        http_client=ctx['http_client']
    )
    ctx['twilio_client'] = TwilioClient(
        account_sid=settings.TWILIO_ACCOUNT_SID,
        auth_token=settings.TWILIO_AUTH_TOKEN,
        from_number=settings.TWILIO_FROM_NUMBER,
        http_client=ctx['http_client']
    )
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
        execute_call_task,
        autonomous_pipeline_supervisor_task
    ]
    # Poll Unipile invitations queue every minute (second=0)
    # Poll Autonomous Supervisor every minute for testing (change to minute=set(range(0, 60, 5)) for production)
    cron_jobs = [
        cron(autonomous_pipeline_supervisor_task, second=0)
    ]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_error = on_task_error
