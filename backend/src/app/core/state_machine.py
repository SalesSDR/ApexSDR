import uuid
import pytz
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.schemas import Prospect, WorkflowState, ActivityTimeline, FollowUp, WorkspaceSetting

logger = logging.getLogger(__name__)

# State transitions map: Source State -> Allowed Destination States
ALLOWED_TRANSITIONS = {
    "PROSPECT_CREATED": ["LINKEDIN_REQ_SENT", "PENDING_ACCEPTANCE", "EMAIL_QUEUED", "CLOSED"],
    "LINKEDIN_REQ_SENT": ["PENDING_ACCEPTANCE", "CONNECTION_ACCEPTED", "CLOSED"],
    "PENDING_ACCEPTANCE": ["CONNECTION_ACCEPTED", "EMAIL_QUEUED", "PAUSED_RATE_LIMITED", "FAILED_INVALID_PROFILE", "PAUSED_ERROR", "CLOSED"],
    "PAUSED_RATE_LIMITED": ["PENDING_ACCEPTANCE", "EMAIL_QUEUED", "CLOSED"],
    "FAILED_INVALID_PROFILE": ["EMAIL_QUEUED", "CLOSED"],
    "PAUSED_ERROR": ["PENDING_ACCEPTANCE", "EMAIL_QUEUED", "CLOSED"],
    "CONNECTION_ACCEPTED": ["INITIAL_MSG_SENT", "LINKEDIN_SENT", "CLOSED"],
    "INITIAL_MSG_SENT": ["WAITING_FOR_REPLY", "CLOSED"],
    "LINKEDIN_SENT": ["FOLLOW_UP_SCHEDULED", "LINKEDIN_SENT", "EMAIL_SENT", "WAITING_FOR_REPLY", "CONVERSATION_ACTIVE", "CALL_QUEUED", "CLOSED"],
    "EMAIL_SENT": ["FOLLOW_UP_SCHEDULED", "LINKEDIN_SENT", "EMAIL_SENT", "WAITING_FOR_REPLY", "CONVERSATION_ACTIVE", "CALL_QUEUED", "CLOSED"],
    "WAITING_FOR_REPLY": ["FOLLOW_UP_SCHEDULED", "CONVERSATION_ACTIVE", "CALL_QUEUED", "CLOSED"],
    "FOLLOW_UP_SCHEDULED": ["FOLLOW_UP_SENT", "LINKEDIN_SENT", "EMAIL_SENT", "CONVERSATION_ACTIVE", "CALL_QUEUED", "CLOSED"],
    "FOLLOW_UP_SENT": ["CALL_SCHEDULED", "WAITING_FOR_REPLY", "CONVERSATION_ACTIVE", "CALL_QUEUED", "CLOSED"],
    "CALL_SCHEDULED": ["CALL_QUEUED", "IN_CALL", "CALL_COMPLETED", "CONVERSATION_ACTIVE", "CLOSED"],
    "CALL_QUEUED": ["CALL_QUEUED", "IN_CALL", "CALL_COMPLETED", "CONVERSATION_ACTIVE", "CLOSED"],
    "IN_CALL": ["CALL_COMPLETED", "CONVERSATION_ACTIVE", "CLOSED"],
    "CALL_COMPLETED": ["CLOSED", "CONVERSATION_ACTIVE"],
    "CONVERSATION_ACTIVE": ["CALL_QUEUED", "CLOSED"],
    "CLOSED": [],  # Terminal state
    "EMAIL_QUEUED": ["EMAIL_SENT", "EMAIL_FAILED", "CLOSED"],
    "EMAIL_FAILED": ["CLOSED"]
}

class StateMachineError(Exception):
    """Raised when an invalid state transition is requested."""
    pass

class StateMachine:
    @staticmethod
    def calculate_next_execution(base_time: datetime, delay_hours: int, settings: WorkspaceSetting) -> datetime:
        """
        Computes exact execution times while respecting configured work hours and weekend flags.
        Ensures outbound interactions land naturally in the prospect's active time frame.
        """
        # Ensure base_time is timezone-aware and in UTC
        if base_time.tzinfo is None:
            base_time = pytz.utc.localize(base_time)
        else:
            base_time = base_time.astimezone(pytz.utc)

        target_time = base_time + timedelta(hours=delay_hours)
        tz = pytz.timezone(settings.timezone)
        target_localized = target_time.astimezone(tz)

        # Evaluate Weekend adjustments
        if settings.exclude_weekends:
            while target_localized.weekday() >= 5:  # Saturday=5, Sunday=6
                target_localized += timedelta(days=1)
                # Reset to beginning of workspace shift hours
                h, m = map(int, settings.working_hours_start.split(":"))
                target_localized = target_localized.replace(hour=h, minute=m, second=0, microsecond=0)

        # Evaluate Intraday bounds adjustment
        start_h, start_m = map(int, settings.working_hours_start.split(":"))
        end_h, end_m = map(int, settings.working_hours_end.split(":"))

        current_h = target_localized.hour
        current_m = target_localized.minute

        # Calculate time as minutes since midnight to make comparison robust
        current_minutes = current_h * 60 + current_m
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m

        if current_minutes < start_minutes:
            target_localized = target_localized.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        elif current_minutes >= end_minutes:
            # Push to next calendar day window
            target_localized += timedelta(days=1)
            target_localized = target_localized.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            # Re-evaluate weekend rules recursively in case we pushed into a weekend
            if settings.exclude_weekends and target_localized.weekday() >= 5:
                return StateMachine.calculate_next_execution(target_localized, 0, settings)

        return target_localized.astimezone(pytz.utc)

    @staticmethod
    async def check_idempotency(redis: Redis, token: str) -> bool:
        """
        Checks if token exists in Redis. If not, registers it with 24h TTL.
        Returns True if the token is unique and registered, False if it is a duplicate.
        """
        if not token:
            return True
        key = f"idempotency:{token}"
        # Set with 24 hour TTL if it doesn't exist
        acquired = await redis.set(key, "processed", ex=86400, nx=True)
        return bool(acquired)

    @staticmethod
    async def transition(
        db: AsyncSession,
        redis: Redis,
        prospect_id: str,
        new_state: str,
        event_trigger: str,
        payload_updates: Optional[Dict[str, Any]] = None,
        idempotency_token: Optional[str] = None,
        force: bool = False
    ) -> Tuple[Prospect, WorkflowState]:
        """
        Transition a prospect's state, tracking historical events and ensuring idempotency.
        """
        # 1. High-speed Redis Idempotency Guard
        if idempotency_token:
            is_unique = await StateMachine.check_idempotency(redis, idempotency_token)
            if not is_unique:
                logger.warning(f"Duplicate task execution blocked by Redis idempotency guard: {idempotency_token}")
                # Load and return current state
                p_res = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
                prospect = p_res.scalar_one()
                w_res = await db.execute(select(WorkflowState).where(WorkflowState.prospect_id == prospect_id))
                wf_state = w_res.scalar_one()
                return prospect, wf_state

        # Use explicit atomic database ledger
        async with db.begin_nested() if db.in_transaction() else db.begin():
            # Fetch entities
            p_res = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
            prospect = p_res.scalar_one_or_none()
            if not prospect:
                raise StateMachineError(f"Prospect with ID {prospect_id} not found.")

            w_res = await db.execute(select(WorkflowState).where(WorkflowState.prospect_id == prospect_id))
            wf_state = w_res.scalar_one_or_none()
            if not wf_state:
                wf_state = WorkflowState(
                    id=str(uuid.uuid4()),
                    prospect_id=prospect.id,
                    tenant_id=prospect.tenant_id,
                    state=prospect.current_state,
                    payload={}
                )
                db.add(wf_state)

            # 2. Database level idempotency guard: check in payload
            if idempotency_token and wf_state.payload.get("processed_tokens", {}).get(idempotency_token):
                logger.warning(f"Duplicate task execution blocked by DB payload check: {idempotency_token}")
                return prospect, wf_state

            # Validate transition path (Any state is allowed to shift to CLOSED or CONVERSATION_ACTIVE)
            current = prospect.current_state
            if current != new_state and not force:
                allowed = ALLOWED_TRANSITIONS.get(current, [])
                if new_state not in allowed and new_state not in ["CLOSED", "CONVERSATION_ACTIVE"]:
                    raise StateMachineError(f"Illegal state transition from {current} to {new_state}.")

            # Shift states
            prospect.current_state = new_state
            wf_state.state = new_state

            # Merge payload updates
            if not wf_state.payload:
                wf_state.payload = {}
            if payload_updates:
                wf_state.payload.update(payload_updates)

            # Record idempotency token in the DB payload
            if idempotency_token:
                if "processed_tokens" not in wf_state.payload:
                    wf_state.payload["processed_tokens"] = {}
                wf_state.payload["processed_tokens"][idempotency_token] = datetime.utcnow().isoformat()

            # Log to ActivityTimeline
            timeline_event = ActivityTimeline(
                id=str(uuid.uuid4()),
                tenant_id=prospect.tenant_id,
                prospect_id=prospect.id,
                channel=StateMachine._get_channel_for_state(new_state),
                event_type=StateMachine._get_event_type_for_trigger(event_trigger),
                description=f"State transitioned from {current} to {new_state}. Trigger: {event_trigger}"
            )
            db.add(timeline_event)

            # Side effects
            if new_state in ["CONVERSATION_ACTIVE", "CLOSED"]:
                # Cancel all downstream pending FollowUp entities
                await db.execute(
                    update(FollowUp)
                    .where(FollowUp.prospect_id == prospect_id, FollowUp.status == "PENDING")
                    .values(status="CANCELED")
                )
                logger.info(f"Cancelled downstream pending follow-ups for prospect {prospect_id} due to state {new_state}")

            await db.flush()
            return prospect, wf_state

    @staticmethod
    def _get_channel_for_state(state: str) -> str:
        if "LINKEDIN" in state:
            return "LINKEDIN"
        elif "EMAIL" in state or "FOLLOW_UP" in state:
            return "EMAIL"
        elif "CALL" in state:
            return "CALL"
        else:
            return "SYSTEM"

    @staticmethod
    def _get_event_type_for_trigger(trigger: str) -> str:
        t_upper = trigger.upper()
        if "SENT" in t_upper or "INITIAL" in t_upper:
            return "SENT"
        elif "ACCEPT" in t_upper:
            return "ACCEPTED"
        elif "REPLY" in t_upper:
            return "REPLY"
        elif "FAIL" in t_upper:
            return "FAILED"
        else:
            return "SYSTEM_EVENT"
