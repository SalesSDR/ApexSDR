import logging
from datetime import UTC, datetime, timedelta

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.state_machine import TERMINAL_STATES
from app.models.schemas import (
    BuyingSignal,
    CalendarSyncLog,
    CalendarSyncStatus,
    CallTranscript,
    CallTranscriptLine,
    ComplianceLog,
    DecisionLog,
    DecisionType,
    DoNotContactList,
    EmailBounceSuppression,
    EmailVerification,
    EmailVerificationStatus,
    LinkedInAccount,
    Prospect,
    ProspectState,
    QualificationLevel,
)
from app.services.crm.service import DEAL_STAGE_BY_STATE
from app.services.qualification.scoring import PRIORITY_ORDER

logger = logging.getLogger(__name__)

LINKEDIN_STATES = (
    ProspectState.LI_REQ_SENT, ProspectState.LI_ACCEPTED_NO_MSG, ProspectState.LI_MSG_SENT,
    ProspectState.LINKEDIN_NO_RESPONSE, ProspectState.LINKEDIN_REPLIED,
)
EMAIL_STATES = (
    ProspectState.EMAIL_SENT, ProspectState.EMAIL_OPENED, ProspectState.EMAIL_CLICKED,
    ProspectState.EMAIL_FAILED, ProspectState.EMAIL_REPLIED,
    # Sequence Engine steps 4 and 7 - Email #2 and the Breakup Email.
    ProspectState.EMAIL_2_SENT, ProspectState.BREAKUP_EMAIL_SENT,
)
CALL_STATES = (
    ProspectState.CALL_QUEUED, ProspectState.CALL_IN_PROGRESS, ProspectState.CALL_CONNECTED,
    ProspectState.CALL_NO_ANSWER_1, ProspectState.CALL_NO_ANSWER_2, ProspectState.CALL_FAILED, ProspectState.CALL_RETRY,
    ProspectState.VOICEMAIL_LEFT,  # Sequence Engine step 6
)
REPLY_OR_BOOKED_STATES = (ProspectState.LINKEDIN_REPLIED, ProspectState.EMAIL_REPLIED, ProspectState.MEETING_BOOKED)

# Dashboard KPI cards (LinkedIn Responses / Meetings Booked / Invalid Data):
# states only reachable after a prospect has accepted the LinkedIn connection
# request - i.e. "has responded on LinkedIn at least once". LINKEDIN_REPLIED
# itself is excluded from this snapshot: webhooks.py's handle_unipile_webhook
# transitions a LINKEDIN_REPLIED prospect straight on to MEETING_BOOKED or
# PAUSED_NUDGED within the same request/transaction, so it is never actually
# persisted as a resting status (see that function's docstring/code).
LINKEDIN_RESPONDED_STATES = (
    ProspectState.LI_ACCEPTED_NO_MSG, ProspectState.LI_MSG_SENT, ProspectState.LINKEDIN_NO_RESPONSE,
)
# CLOSED_WON's only legal predecessor is MEETING_BOOKED (see
# core/state_machine.py's ALLOWED_TRANSITIONS), so counting both - not just
# the current MEETING_BOOKED snapshot - avoids undercounting deals that have
# since closed. COMPLETED_DECLINED/LOST are deliberately excluded: both are
# also reachable from several non-meeting paths (PAUSED_NUDGED,
# BREAKUP_EMAIL_SENT, ...), so folding them in would overcount.
MEETING_BOOKED_STATES = (ProspectState.MEETING_BOOKED, ProspectState.CLOSED_WON)

# Maps every ProspectState to exactly one funnel bucket, so a pipeline funnel
# query can GROUP BY status once and fold results into mutually-exclusive
# stages without double-counting or a second query per stage.
FUNNEL_STAGE_BY_STATUS: dict[ProspectState, str] = {
    ProspectState.NEW: "new",
    ProspectState.ENRICHING: "enriching",
    ProspectState.DISQUALIFIED: "disqualified",
    ProspectState.QUALIFIED: "qualified_ready",  # transient in practice, included for completeness
    ProspectState.IDLE: "qualified_ready",
    **{s: "outreach_in_progress" for s in LINKEDIN_STATES if s != ProspectState.LINKEDIN_REPLIED},
    **{s: "outreach_in_progress" for s in EMAIL_STATES if s != ProspectState.EMAIL_REPLIED},
    **{s: "outreach_in_progress" for s in CALL_STATES},
    ProspectState.LINKEDIN_REPLIED: "engaged",
    ProspectState.EMAIL_REPLIED: "engaged",
    ProspectState.PAUSED_NUDGED: "engaged",
    ProspectState.ENGAGED_ON_WEBSITE: "engaged",
    ProspectState.MEETING_BOOKED: "meeting_booked",
    ProspectState.CLOSED_WON: "closed_won",
    ProspectState.COMPLETED_DECLINED: "closed_declined",
    ProspectState.UNRESPONSIVE_DEAD: "closed_unresponsive",
    ProspectState.LOST: "closed_lost",
    ProspectState.ERROR_NEEDS_HUMAN: "needs_human",
}
FUNNEL_STAGE_ORDER = [
    "new", "enriching", "disqualified", "qualified_ready", "outreach_in_progress",
    "engaged", "meeting_booked", "closed_won", "closed_declined", "closed_unresponsive", "closed_lost", "needs_human",
]


def _pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator * 100), 1) if denominator else 0.0


class AnalyticsService:
    """Read-only aggregation layer over existing pipeline data (Prospect,
    CalendarSyncLog, LinkedInAccount, ARQ's own queue). Never mutates state
    and never re-implements pipeline/transition logic - it only counts and
    groups what core/state_machine.py, the CRM/Calendar/LinkedIn services,
    and the ARQ workers have already produced. Routes must go through this
    service rather than building queries inline."""

    def __init__(self, db: AsyncSession, tenant_id: str, arq_pool: ArqRedis | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self._status_counts_cache: dict[str, int] | None = None
        # Optional: the shared app-wide ARQ pool (see app.database.get_arq_pool).
        # Falls back to a short-lived ad hoc pool if not supplied, so
        # existing callers/tests that construct AnalyticsService(db, tenant_id)
        # without it keep working unchanged.
        self._arq_pool = arq_pool

    async def _status_counts(self) -> dict[str, int]:
        """Single GROUP BY query, cached for the lifetime of this instance
        (one per request) so every metric method that needs a status
        breakdown reuses it instead of re-querying."""
        if self._status_counts_cache is None:
            query = (
                select(Prospect.status, func.count())
                .where(Prospect.tenant_id == self.tenant_id)
                .group_by(Prospect.status)
            )
            rows = (await self.db.execute(query)).all()
            self._status_counts_cache = {status.value: count for status, count in rows}
        return self._status_counts_cache

    async def pipeline_funnel(self) -> dict:
        counts = await self._status_counts()
        stage_counts = {stage: 0 for stage in FUNNEL_STAGE_ORDER}
        for status_value, count in counts.items():
            stage = FUNNEL_STAGE_BY_STATUS.get(ProspectState(status_value), "other")
            stage_counts[stage] = stage_counts.get(stage, 0) + count
        return {
            "total_prospects": sum(counts.values()),
            "stages": [{"stage": s, "count": stage_counts[s]} for s in FUNNEL_STAGE_ORDER],
        }

    async def prospects_by_state(self) -> dict:
        counts = await self._status_counts()
        return {"by_state": {s.value: counts.get(s.value, 0) for s in ProspectState}}

    async def outreach_metrics(self) -> dict:
        counts = await self._status_counts()
        return {
            "currently_in_linkedin_outreach": sum(counts.get(s.value, 0) for s in LINKEDIN_STATES),
            "currently_in_email_outreach": sum(counts.get(s.value, 0) for s in EMAIL_STATES),
            "currently_in_call_outreach": sum(counts.get(s.value, 0) for s in CALL_STATES),
            "currently_engaged": counts.get(ProspectState.LINKEDIN_REPLIED.value, 0) + counts.get(ProspectState.EMAIL_REPLIED.value, 0),
            "meetings_booked": counts.get(ProspectState.MEETING_BOOKED.value, 0),
        }

    async def linkedin_metrics(self) -> dict:
        counts = await self._status_counts()
        accounts_query = select(LinkedInAccount).where(LinkedInAccount.tenant_id == self.tenant_id)
        accounts = (await self.db.execute(accounts_query)).scalars().all()
        return {
            "by_state": {s.value: counts.get(s.value, 0) for s in LINKEDIN_STATES},
            "accounts": [
                {
                    "account_id": a.account_id,
                    "daily_send_count": a.daily_send_count,
                    "daily_limit": a.daily_limit,
                    "is_paused": a.is_paused,
                    "paused_reason": a.paused_reason,
                }
                for a in accounts
            ],
        }

    async def email_metrics(self) -> dict:
        counts = await self._status_counts()
        return {"by_state": {s.value: counts.get(s.value, 0) for s in EMAIL_STATES}}

    async def call_metrics(self) -> dict:
        counts = await self._status_counts()
        query = select(
            func.count(case((Prospect.call_attempts == 0, 1))).label("zero"),
            func.count(case((Prospect.call_attempts == 1, 1))).label("one"),
            func.count(case((Prospect.call_attempts >= 2, 1))).label("two_plus"),
        ).where(Prospect.tenant_id == self.tenant_id)
        row = (await self.db.execute(query)).one()
        return {
            "by_state": {s.value: counts.get(s.value, 0) for s in CALL_STATES},
            "call_attempts_distribution": {"0": row.zero, "1": row.one, "2+": row.two_plus},
        }

    async def crm_sync_metrics(self) -> dict:
        totals_query = select(
            func.count().label("total"),
            func.count(Prospect.hubspot_contact_id).label("contacts_synced"),
            func.count(Prospect.hubspot_deal_id).label("deals_created"),
        ).where(Prospect.tenant_id == self.tenant_id)
        totals = (await self.db.execute(totals_query)).one()

        deal_stage_query = (
            select(Prospect.status, func.count())
            .where(Prospect.tenant_id == self.tenant_id, Prospect.hubspot_deal_id.isnot(None))
            .group_by(Prospect.status)
        )
        deals_by_stage: dict[str, int] = {}
        for status, count in (await self.db.execute(deal_stage_query)).all():
            stage = DEAL_STAGE_BY_STATE.get(status, "unmapped")
            deals_by_stage[stage] = deals_by_stage.get(stage, 0) + count

        return {
            "total_prospects": totals.total,
            "contacts_synced": totals.contacts_synced,
            "deals_created": totals.deals_created,
            "sync_coverage_pct": _pct(totals.contacts_synced, totals.total),
            "deals_by_stage": deals_by_stage,
        }

    async def calendar_metrics(self) -> dict:
        status_query = (
            select(CalendarSyncLog.status, func.count())
            .where(CalendarSyncLog.tenant_id == self.tenant_id)
            .group_by(CalendarSyncLog.status)
        )
        by_status = {s.value: 0 for s in CalendarSyncStatus}
        for status, count in (await self.db.execute(status_query)).all():
            by_status[status.value] = count

        event_type_query = (
            select(CalendarSyncLog.event_type, func.count())
            .where(CalendarSyncLog.tenant_id == self.tenant_id)
            .group_by(CalendarSyncLog.event_type)
        )
        by_event_type = dict((await self.db.execute(event_type_query)).all())

        counts = await self._status_counts()
        return {
            "meetings_booked": counts.get(ProspectState.MEETING_BOOKED.value, 0),
            "sync_by_status": by_status,
            "sync_by_event_type": by_event_type,
        }

    async def queue_metrics(self) -> dict:
        accounts_query = select(LinkedInAccount).where(LinkedInAccount.tenant_id == self.tenant_id)
        accounts = (await self.db.execute(accounts_query)).scalars().all()
        linkedin_queue = {
            "accounts": len(accounts),
            "paused_accounts": sum(1 for a in accounts if a.is_paused),
            "total_daily_capacity": sum(a.daily_limit for a in accounts),
            "total_sent_today": sum(a.daily_send_count for a in accounts),
        }

        # ARQ has no tenant concept - pending job counts are system-wide,
        # read via ARQ's own public queued_jobs() API (reused, not
        # hand-parsed from Redis keys).
        pending_jobs = []
        try:
            if self._arq_pool is not None:
                pending_jobs = await self._arq_pool.queued_jobs()
            else:
                arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
                try:
                    pending_jobs = await arq_pool.queued_jobs()
                finally:
                    await arq_pool.close()
        except Exception as e:
            logger.warning(f"Failed to read ARQ queue depth: {e}")

        by_function: dict[str, int] = {}
        for job in pending_jobs:
            by_function[job.function] = by_function.get(job.function, 0) + 1

        return {
            "linkedin_queue": linkedin_queue,
            "arq_pending_jobs_total": len(pending_jobs),
            "arq_pending_jobs_by_function": by_function,
        }

    async def retry_metrics(self) -> dict:
        query = select(
            func.count(case((Prospect.retry_count == 0, 1))).label("zero"),
            func.count(case((Prospect.retry_count == 1, 1))).label("one"),
            func.count(case((Prospect.retry_count == 2, 1))).label("two"),
            func.count(case((Prospect.retry_count >= 3, 1))).label("three_plus"),
        ).where(Prospect.tenant_id == self.tenant_id)
        row = (await self.db.execute(query)).one()

        counts = await self._status_counts()
        return {
            "retry_count_distribution": {"0": row.zero, "1": row.one, "2": row.two, "3+": row.three_plus},
            "retries_exhausted_needs_human": counts.get(ProspectState.ERROR_NEEDS_HUMAN.value, 0),
        }

    async def daily_weekly_activity(self, period: str = "daily", days: int = 30) -> dict:
        if period not in ("daily", "weekly"):
            raise ValueError("period must be 'daily' or 'weekly'")
        trunc_unit = "day" if period == "daily" else "week"
        since = datetime.now(UTC) - timedelta(days=days if period == "daily" else days * 7)

        bucket = func.date_trunc(trunc_unit, Prospect.created_at).label("bucket")
        query = (
            select(bucket, func.count().label("count"))
            .where(Prospect.tenant_id == self.tenant_id, Prospect.created_at >= since)
            .group_by(bucket)
            .order_by(bucket)
        )
        rows = (await self.db.execute(query)).all()
        return {
            "period": period,
            "buckets": [{"date": b.isoformat(), "new_prospects": c} for b, c in rows],
        }

    async def failed_jobs(self) -> dict:
        needs_human_query = (
            select(Prospect.id, Prospect.first_name, Prospect.last_name, Prospect.last_status_change_at)
            .where(Prospect.tenant_id == self.tenant_id, Prospect.status == ProspectState.ERROR_NEEDS_HUMAN)
            .order_by(Prospect.last_status_change_at.desc())
            .limit(100)
        )
        needs_human_rows = (await self.db.execute(needs_human_query)).all()

        calendar_failures_query = (
            select(CalendarSyncLog)
            .where(CalendarSyncLog.tenant_id == self.tenant_id, CalendarSyncLog.status == CalendarSyncStatus.FAILED)
            .order_by(CalendarSyncLog.created_at.desc())
            .limit(100)
        )
        calendar_failures = (await self.db.execute(calendar_failures_query)).scalars().all()

        return {
            "total_pipeline_failures": len(needs_human_rows),
            "total_calendar_failures": len(calendar_failures),
            "pipeline_failures_needing_human": [
                {
                    "prospect_id": r.id,
                    "name": f"{r.first_name} {r.last_name}",
                    "failed_at": r.last_status_change_at.isoformat() if r.last_status_change_at else None,
                }
                for r in needs_human_rows
            ],
            "calendar_sync_failures": [
                {
                    "prospect_id": f.prospect_id,
                    "event_type": f.event_type,
                    "error_message": f.error_message,
                    "created_at": f.created_at.isoformat(),
                }
                for f in calendar_failures
            ],
        }

    async def conversion_rates(self) -> dict:
        """Computed from the current status snapshot, not cumulative
        lifetime totals - there's no per-event history table (see
        ActivityTimeline note in the Module 5 report)."""
        counts = await self._status_counts()
        total = sum(counts.values())
        disqualified = counts.get(ProspectState.DISQUALIFIED.value, 0)
        still_qualifying = counts.get(ProspectState.NEW.value, 0) + counts.get(ProspectState.ENRICHING.value, 0)
        qualified = total - disqualified - still_qualifying
        meetings_booked = counts.get(ProspectState.MEETING_BOOKED.value, 0)
        replied = counts.get(ProspectState.LINKEDIN_REPLIED.value, 0) + counts.get(ProspectState.EMAIL_REPLIED.value, 0)

        return {
            "total_prospects": total,
            "qualification_rate_pct": _pct(qualified, qualified + disqualified),
            "reply_rate_pct": _pct(replied, total),
            "meeting_conversion_rate_pct": _pct(meetings_booked, total),
        }

    async def response_times(self) -> dict:
        """Approximation: last_status_change_at - created_at for prospects
        currently at a reply/booked state. Not a true per-event log (see
        Module 5 report's technical debt notes)."""
        query = select(
            func.avg(func.extract("epoch", Prospect.last_status_change_at - Prospect.created_at)).label("avg_seconds"),
            func.count().label("sample_size"),
        ).where(Prospect.tenant_id == self.tenant_id, Prospect.status.in_(REPLY_OR_BOOKED_STATES))
        row = (await self.db.execute(query)).one()
        return {
            "avg_time_to_first_response_hours": round(row.avg_seconds / 3600, 2) if row.avg_seconds is not None else None,
            "sample_size": row.sample_size,
        }

    async def signal_metrics(self) -> dict:
        """
        Aggregate buying signal counts and trends.
        """
        # Active vs Expired count
        active_query = select(func.count()).where(BuyingSignal.tenant_id == self.tenant_id, BuyingSignal.is_active == True)
        expired_query = select(func.count()).where(BuyingSignal.tenant_id == self.tenant_id, BuyingSignal.is_active == False)
        
        active_count = (await self.db.execute(active_query)).scalar() or 0
        expired_count = (await self.db.execute(expired_query)).scalar() or 0
        
        # Count by type (active only)
        by_type_query = (
            select(BuyingSignal.signal_type, func.count())
            .where(BuyingSignal.tenant_id == self.tenant_id, BuyingSignal.is_active == True)
            .group_by(BuyingSignal.signal_type)
        )
        by_type_rows = (await self.db.execute(by_type_query)).all()
        by_type = {row[0].value: row[1] for row in by_type_rows}
        
        # Count by source (active only)
        by_source_query = (
            select(BuyingSignal.signal_source, func.count())
            .where(BuyingSignal.tenant_id == self.tenant_id, BuyingSignal.is_active == True)
            .group_by(BuyingSignal.signal_source)
        )
        by_source_rows = (await self.db.execute(by_source_query)).all()
        by_source = {row[0]: row[1] for row in by_source_rows}
        
        return {
            "total_active_signals": active_count,
            "total_expired_signals": expired_count,
            "by_type": by_type,
            "by_source": by_source
        }

    async def qualification_metrics(self, top_n: int = 10) -> dict:
        """Module 13: qualification/priority distribution (one taxonomy,
        HOT/HIGH/MEDIUM/LOW, drives both per services/qualification/scoring.py),
        average score, and the top ICP matches by score."""
        level_query = (
            select(Prospect.qualification_level, func.count())
            .where(Prospect.tenant_id == self.tenant_id)
            .group_by(Prospect.qualification_level)
        )
        level_rows = (await self.db.execute(level_query)).all()
        distribution = {level.value: 0 for level in QualificationLevel}
        not_yet_scored = 0
        for level, count in level_rows:
            if level is None:
                not_yet_scored += count
            else:
                distribution[level.value] = count

        avg_query = select(
            func.avg(Prospect.qualification_score), func.count(Prospect.qualification_score)
        ).where(Prospect.tenant_id == self.tenant_id)
        avg_row = (await self.db.execute(avg_query)).one()
        average_score = round(avg_row[0], 2) if avg_row[0] is not None else None

        top_query = (
            select(Prospect)
            .where(Prospect.tenant_id == self.tenant_id, Prospect.qualification_score.isnot(None))
            .order_by(Prospect.qualification_score.desc())
            .limit(top_n)
        )
        top_prospects = (await self.db.execute(top_query)).scalars().all()

        return {
            "qualification_distribution": distribution,
            "priority_distribution": distribution,
            "not_yet_scored": not_yet_scored,
            "average_score": average_score,
            "scored_count": avg_row[1],
            "top_icp_matches": [
                {
                    "prospect_id": p.id,
                    "name": f"{p.first_name} {p.last_name}",
                    "company_name": p.company_name,
                    "qualification_score": p.qualification_score,
                    "qualification_level": p.qualification_level.value if p.qualification_level else None,
                    "qualification_reason": p.qualification_reason,
                }
                for p in top_prospects
            ],
        }

    async def messages_by_priority(self) -> dict:
        """Sprint 6, item 4 (Historical Analytics): count of outbound
        send-decisions, grouped by DecisionLog.qualification_level_at_decision
        - the priority tier the prospect was ACTUALLY at when each decision
        was made, not a join to Prospect's current (possibly since-changed)
        value. No Prospect join needed at all now."""
        send_types = [
            DecisionType.SEND_LINKEDIN, DecisionType.SEND_FOLLOWUP,
            DecisionType.SEND_EMAIL, DecisionType.SCHEDULE_CALL,
        ]
        query = (
            select(DecisionLog.qualification_level_at_decision, func.count(DecisionLog.id))
            .where(DecisionLog.tenant_id == self.tenant_id, DecisionLog.decision_type.in_(send_types))
            .group_by(DecisionLog.qualification_level_at_decision)
        )
        rows = (await self.db.execute(query)).all()
        distribution = {level.value: 0 for level in QualificationLevel}
        not_yet_scored = 0
        for level, count in rows:
            if level is None:
                not_yet_scored += count
            else:
                distribution[level.value] = count
        return {"messages_sent_by_priority": distribution, "not_yet_scored": not_yet_scored}

    def _latest_decision_level_subquery(self):
        """Sprint 6, item 4: each prospect's MOST RECENT logged
        qualification_level_at_decision - the historical snapshot
        conversion_by_priority()/qualification_accuracy() group by, instead
        of Prospect's current qualification_level."""
        ranked = (
            select(
                DecisionLog.prospect_id,
                DecisionLog.qualification_level_at_decision.label("level"),
                func.row_number().over(
                    partition_by=DecisionLog.prospect_id,
                    order_by=DecisionLog.sequence_number.desc(),
                ).label("rn"),
            )
            .where(DecisionLog.tenant_id == self.tenant_id)
            .subquery()
        )
        return select(ranked.c.prospect_id, ranked.c.level).where(ranked.c.rn == 1).subquery()

    async def conversion_by_priority(self) -> dict:
        """Sprint 5, item 4 / Sprint 6, item 4: per-priority-tier totals and
        meeting/reply/won rates - does a HOT lead actually convert better
        than a MEDIUM one? Grouped by each prospect's most recently logged
        qualification_level_at_decision (a historical snapshot), not
        Prospect's current value."""
        latest_level = self._latest_decision_level_subquery()
        query = (
            select(
                latest_level.c.level,
                func.count().label("total"),
                func.count(case((Prospect.status == ProspectState.MEETING_BOOKED, 1))).label("meetings"),
                func.count(case((Prospect.status == ProspectState.CLOSED_WON, 1))).label("won"),
                func.count(case((Prospect.status.in_([ProspectState.LINKEDIN_REPLIED, ProspectState.EMAIL_REPLIED]), 1))).label("replied"),
            )
            .select_from(Prospect)
            .join(latest_level, latest_level.c.prospect_id == Prospect.id)
            .where(Prospect.tenant_id == self.tenant_id, latest_level.c.level.isnot(None))
            .group_by(latest_level.c.level)
        )
        rows = (await self.db.execute(query)).all()
        result = {}
        for level, total, meetings, won, replied in rows:
            result[level.value] = {
                "total": total,
                "meetings_booked": meetings,
                "won": won,
                "replied": replied,
                "meeting_rate_pct": _pct(meetings, total),
                "reply_rate_pct": _pct(replied, total),
            }
        return {"conversion_by_priority": result}

    async def qualification_accuracy(self) -> dict:
        """Sprint 5, item 4 / Sprint 6, item 4: correlates qualification
        tier with actual pipeline outcomes - the empirical check on whether
        the scoring model's priority ordering matches reality (HOT should
        convert at least as well as LOW, not worse). Grouped by each
        prospect's most recently logged qualification_level_at_decision."""
        latest_level = self._latest_decision_level_subquery()
        query = (
            select(
                latest_level.c.level,
                func.count().label("total"),
                func.count(case((Prospect.status.in_([ProspectState.MEETING_BOOKED, ProspectState.CLOSED_WON]), 1))).label("positive"),
                func.count(case((Prospect.status.in_(
                    [ProspectState.COMPLETED_DECLINED, ProspectState.UNRESPONSIVE_DEAD, ProspectState.LOST]
                ), 1))).label("negative"),
            )
            .select_from(Prospect)
            .join(latest_level, latest_level.c.prospect_id == Prospect.id)
            .where(Prospect.tenant_id == self.tenant_id, latest_level.c.level.isnot(None))
            .group_by(latest_level.c.level)
        )
        rows = (await self.db.execute(query)).all()
        by_level = {}
        for level, total, positive, negative in rows:
            resolved = positive + negative
            by_level[level.value] = {
                "total": total,
                "positive_outcomes": positive,
                "negative_outcomes": negative,
                "positive_rate_pct": _pct(positive, resolved),
            }

        ordered_rates = [
            by_level[level.value]["positive_rate_pct"]
            for level in PRIORITY_ORDER
            if level.value in by_level and by_level[level.value]["total"] > 0
        ]
        priority_order_matches_outcomes = (
            all(ordered_rates[i] >= ordered_rates[i + 1] for i in range(len(ordered_rates) - 1))
            if len(ordered_rates) > 1 else None
        )
        return {
            "qualification_accuracy_by_level": by_level,
            "priority_order_matches_outcomes": priority_order_matches_outcomes,
        }

    async def channel_performance(self) -> dict:
        """Sprint 5, item 4: reply/connect rate per outbound channel -
        a current-snapshot view (no per-event history table exists)."""
        counts = await self._status_counts()

        def bucket_total(states) -> int:
            return sum(counts.get(s.value, 0) for s in states)

        linkedin_total = bucket_total(LINKEDIN_STATES)
        email_total = bucket_total(EMAIL_STATES)
        call_total = bucket_total(CALL_STATES)
        linkedin_replied = counts.get(ProspectState.LINKEDIN_REPLIED.value, 0)
        email_replied = counts.get(ProspectState.EMAIL_REPLIED.value, 0)
        call_connected = counts.get(ProspectState.CALL_CONNECTED.value, 0)

        return {
            "linkedin": {
                "total": linkedin_total, "replied": linkedin_replied,
                "reply_rate_pct": _pct(linkedin_replied, linkedin_total),
            },
            "email": {
                "total": email_total, "replied": email_replied,
                "reply_rate_pct": _pct(email_replied, email_total),
            },
            "call": {
                "total": call_total, "connected": call_connected,
                "connect_rate_pct": _pct(call_connected, call_total),
            },
        }

    # --- Dashboard KPI cards: LinkedIn Responses / Meetings Booked / Invalid
    # Data. All three are computed entirely from existing tables (Prospect,
    # EmailVerification, EmailBounceSuppression, DoNotContactList) - no new
    # columns or tables were added for this feature. ---

    async def linkedin_response_metrics(self) -> dict:
        """"LinkedIn Responses" KPI. Caveat, same as channel_performance()
        above: a current-status snapshot, not a cumulative event count -
        there is no per-event history table, and a prospect who responded
        and has since moved on to MEETING_BOOKED/PAUSED_NUDGED (shared with
        the email channel) is not counted here, since channel attribution
        isn't preserved past that point in the current schema."""
        counts = await self._status_counts()
        total = sum(counts.get(s.value, 0) for s in LINKEDIN_RESPONDED_STATES)

        since = datetime.now(UTC) - timedelta(days=1)
        today_query = select(func.count()).where(
            Prospect.tenant_id == self.tenant_id,
            Prospect.status.in_(LINKEDIN_RESPONDED_STATES),
            Prospect.last_status_change_at >= since,
        )
        today = (await self.db.execute(today_query)).scalar() or 0
        return {"linkedin_responses": total, "linkedin_responses_today": today}

    async def meetings_booked_metrics(self) -> dict:
        """"Meetings Booked" KPI - see MEETING_BOOKED_STATES above for why
        CLOSED_WON is folded in and COMPLETED_DECLINED/LOST are not."""
        counts = await self._status_counts()
        total = sum(counts.get(s.value, 0) for s in MEETING_BOOKED_STATES)

        since = datetime.now(UTC) - timedelta(days=1)
        today_query = select(func.count()).where(
            Prospect.tenant_id == self.tenant_id,
            Prospect.status.in_(MEETING_BOOKED_STATES),
            Prospect.last_status_change_at >= since,
        )
        today = (await self.db.execute(today_query)).scalar() or 0
        return {"meetings_booked": total, "meetings_booked_today": today}

    async def invalid_data_metrics(self) -> dict:
        """"Invalid Data" KPI - counts distinct prospects with at least one
        data-quality issue, aggregated from existing tables only: a prospect
        counts if its email is flagged INVALID/RISKY in EmailVerification,
        has ever bounced (EmailBounceSuppression), matches a DoNotContactList
        entry by email or phone, has no company_name, has no email at all,
        or shares its email with another prospect in the same tenant
        (create_prospect()'s own duplicate check is currently disabled - see
        that route's comment - so duplicates by email can and do occur).
        `missing_linkedin_url` is always 0: Prospect.linkedin_url is NOT
        NULL at the DB level, so no existing row can lack one - kept as an
        explicit bucket for forward compatibility only. Reasons overlap, so
        `invalid_data` is a DISTINCT prospect count, not a sum of `by_reason`."""
        dup_emails = (
            select(Prospect.email)
            .where(Prospect.tenant_id == self.tenant_id, Prospect.email.isnot(None))
            .group_by(Prospect.email)
            .having(func.count() > 1)
        ).subquery()

        invalid_email_query = (
            select(func.count(func.distinct(Prospect.id)))
            .select_from(Prospect)
            .join(EmailVerification, EmailVerification.email == Prospect.email)
            .where(
                Prospect.tenant_id == self.tenant_id,
                EmailVerification.status.in_([EmailVerificationStatus.INVALID, EmailVerificationStatus.RISKY]),
            )
        )
        bounced_query = (
            select(func.count(func.distinct(Prospect.id)))
            .select_from(Prospect)
            .join(EmailBounceSuppression, EmailBounceSuppression.email == Prospect.email)
            .where(Prospect.tenant_id == self.tenant_id)
        )
        blacklisted_query = (
            select(func.count(func.distinct(Prospect.id)))
            .select_from(Prospect)
            .join(
                DoNotContactList,
                (DoNotContactList.tenant_id == self.tenant_id)
                & (
                    ((DoNotContactList.type == "EMAIL") & (DoNotContactList.value == Prospect.email))
                    | ((DoNotContactList.type == "PHONE") & (DoNotContactList.value == Prospect.phone_number))
                ),
            )
            .where(Prospect.tenant_id == self.tenant_id)
        )
        missing_company_query = select(func.count()).where(
            Prospect.tenant_id == self.tenant_id, Prospect.company_name.is_(None)
        )
        missing_email_query = select(func.count()).where(
            Prospect.tenant_id == self.tenant_id, Prospect.email.is_(None)
        )
        duplicate_query = select(func.count()).where(
            Prospect.tenant_id == self.tenant_id, Prospect.email.in_(select(dup_emails.c.email)),
        )

        invalid_email = (await self.db.execute(invalid_email_query)).scalar() or 0
        bounced = (await self.db.execute(bounced_query)).scalar() or 0
        blacklisted = (await self.db.execute(blacklisted_query)).scalar() or 0
        missing_company = (await self.db.execute(missing_company_query)).scalar() or 0
        missing_email = (await self.db.execute(missing_email_query)).scalar() or 0
        duplicate = (await self.db.execute(duplicate_query)).scalar() or 0

        total_query = (
            select(func.count(func.distinct(Prospect.id)))
            .select_from(Prospect)
            .outerjoin(EmailVerification, EmailVerification.email == Prospect.email)
            .outerjoin(EmailBounceSuppression, EmailBounceSuppression.email == Prospect.email)
            .outerjoin(
                DoNotContactList,
                (DoNotContactList.tenant_id == self.tenant_id)
                & (
                    ((DoNotContactList.type == "EMAIL") & (DoNotContactList.value == Prospect.email))
                    | ((DoNotContactList.type == "PHONE") & (DoNotContactList.value == Prospect.phone_number))
                ),
            )
            .where(
                Prospect.tenant_id == self.tenant_id,
                (
                    EmailVerification.status.in_([EmailVerificationStatus.INVALID, EmailVerificationStatus.RISKY])
                    | EmailBounceSuppression.id.isnot(None)
                    | DoNotContactList.id.isnot(None)
                    | Prospect.company_name.is_(None)
                    | Prospect.email.is_(None)
                    | Prospect.email.in_(select(dup_emails.c.email))
                ),
            )
        )
        total = (await self.db.execute(total_query)).scalar() or 0

        return {
            "invalid_data": total,
            "by_reason": {
                "invalid_or_risky_email": invalid_email,
                "bounced_email": bounced,
                "blacklisted_contact": blacklisted,
                "missing_company": missing_company,
                "missing_email": missing_email,
                "duplicate_lead": duplicate,
                "missing_linkedin_url": 0,
            },
        }

    async def dashboard_kpi_metrics(self) -> dict:
        """Bundles the three new dashboard KPI cards (LinkedIn Responses,
        Meetings Booked, Invalid Data) into a single response so the
        frontend can fetch them in one request instead of three."""
        linkedin = await self.linkedin_response_metrics()
        meetings = await self.meetings_booked_metrics()
        invalid = await self.invalid_data_metrics()
        return {
            "linkedinResponses": linkedin["linkedin_responses"],
            "linkedinResponsesToday": linkedin["linkedin_responses_today"],
            "meetingsBooked": meetings["meetings_booked"],
            "meetingsBookedToday": meetings["meetings_booked_today"],
            "invalidData": invalid["invalid_data"],
            "invalidDataByReason": invalid["by_reason"],
        }

    async def revenue_metrics(self) -> dict:
        """Sprint 5, item 5 (Revenue Attribution): estimated_pipeline_value
        (still-open deals), meeting_value (currently at MEETING_BOOKED),
        won_value (CLOSED_WON), and lost_value (COMPLETED_DECLINED/LOST/
        UNRESPONSIVE_DEAD combined) - all summed from
        Prospect.estimated_deal_value."""
        async def _sum_where(*conditions) -> float:
            query = select(func.coalesce(func.sum(Prospect.estimated_deal_value), 0.0)).where(
                Prospect.tenant_id == self.tenant_id, *conditions
            )
            return float((await self.db.execute(query)).scalar_one())

        estimated_pipeline_value = await _sum_where(Prospect.status.notin_(TERMINAL_STATES))
        meeting_value = await _sum_where(Prospect.status == ProspectState.MEETING_BOOKED)
        won_value = await _sum_where(Prospect.status == ProspectState.CLOSED_WON)
        lost_value = await _sum_where(Prospect.status.in_(
            [ProspectState.COMPLETED_DECLINED, ProspectState.LOST, ProspectState.UNRESPONSIVE_DEAD]
        ))

        return {
            "estimated_pipeline_value": round(estimated_pipeline_value, 2),
            "meeting_value": round(meeting_value, 2),
            "won_value": round(won_value, 2),
            "lost_value": round(lost_value, 2),
        }

    @classmethod
    async def compliance_metrics(cls, db: AsyncSession, tenant_id: str) -> dict:
        """Module 9: Compliance Engine metrics."""
        # Total blocks
        total_query = select(func.count(ComplianceLog.id)).where(ComplianceLog.tenant_id == tenant_id)
        total_blocks = (await db.execute(total_query)).scalar_one()
        
        # Top policies
        policy_query = (
            select(ComplianceLog.policy_type, func.count(ComplianceLog.id))
            .where(ComplianceLog.tenant_id == tenant_id)
            .group_by(ComplianceLog.policy_type)
            .order_by(func.count(ComplianceLog.id).desc())
            .limit(5)
        )
        top_policies = {row[0].value: row[1] for row in (await db.execute(policy_query)).all()}
        
        # Permanent vs Temporary
        severity_query = (
            select(ComplianceLog.severity, func.count(ComplianceLog.id))
            .where(ComplianceLog.tenant_id == tenant_id)
            .group_by(ComplianceLog.severity)
        )
        severity_counts = {row[0].value: row[1] for row in (await db.execute(severity_query)).all()}
        
        return {
            "total_blocks": total_blocks,
            "top_policies": top_policies,
            "severity_counts": severity_counts
        }

    @classmethod
    async def voice_metrics(cls, db: AsyncSession, tenant_id: str) -> dict:
        """Module 10: Voice Engine metrics."""
        
        # Total conversations
        total_query = select(func.count(CallTranscript.id)).where(CallTranscript.tenant_id == tenant_id)
        total_calls = (await db.execute(total_query)).scalar_one()
        
        # Average duration and turns
        avg_query = (
            select(
                func.avg(CallTranscript.duration_seconds),
                func.avg(CallTranscript.total_turns)
            )
            .where(CallTranscript.tenant_id == tenant_id, CallTranscript.status == "COMPLETED")
        )
        avg_res = (await db.execute(avg_query)).first()
        avg_duration = float(avg_res[0] or 0)
        avg_turns = float(avg_res[1] or 0)
        
        # Intent distribution
        intent_query = (
            select(CallTranscriptLine.intent, func.count(CallTranscriptLine.id))
            .where(CallTranscriptLine.tenant_id == tenant_id, CallTranscriptLine.speaker == "ASSISTANT", CallTranscriptLine.intent.is_not(None))
            .group_by(CallTranscriptLine.intent)
        )
        intent_counts = {row[0]: row[1] for row in (await db.execute(intent_query)).all()}
        
        return {
            "total_calls": total_calls,
            "average_duration_seconds": avg_duration,
            "average_turns": avg_turns,
            "intent_distribution": intent_counts
        }
