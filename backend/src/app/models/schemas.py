import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin


class WorkspaceSetting(Base, TenantMixin):
    __tablename__ = "workspace_settings"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    follow_up_delay_hours: Mapped[int] = mapped_column(Integer, default=24)
    call_delay_hours: Mapped[int] = mapped_column(Integer, default=48)
    max_follow_ups: Mapped[int] = mapped_column(Integer, default=3)
    working_hours_start: Mapped[str] = mapped_column(String(5), default="09:00")  # HH:MM
    working_hours_end: Mapped[str] = mapped_column(String(5), default="17:00")    # HH:MM
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    exclude_weekends: Mapped[bool] = mapped_column(Boolean, default=True)
    dev_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    # Module 13 (Lead Qualification): per-tenant ICP target profile -
    # {"target_industries": [...], "target_job_titles": [...],
    # "target_seniority": [...], "company_size_min": int, "company_size_max": int,
    # "target_tech_stack": [...]}. Missing/empty keys mean "no preference" for
    # that factor (its scoring function degrades to a neutral score rather
    # than penalizing), so a tenant can configure as few or as many criteria
    # as they want.
    icp_profile: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Module 13: overrides for the qualification scoring engine's default
    # factor weights and HOT/HIGH/MEDIUM/LOW thresholds (see
    # services/qualification/scoring.py) - {"weights": {factor: float},
    # "thresholds": {"hot": float, "high": float, "medium": float}}. Empty
    # dict means "use the engine's built-in defaults".
    qualification_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

class QualificationLevel(enum.Enum):
    """Module 13: both the qualification tier (item 1's qualification_level)
    and the lead-priority tier (item 2's HOT/HIGH/MEDIUM/LOW) - one taxonomy
    driven by the same qualification_score, not two parallel scales."""
    HOT = "HOT"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ProspectState(enum.Enum):
    # Pre-outreach qualification phase (Module 3)
    NEW = "NEW"
    ENRICHING = "ENRICHING"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"

    IDLE = "IDLE"
    LI_REQ_SENT = "LI_REQ_SENT"
    LI_ACCEPTED_NO_MSG = "LI_ACCEPTED_NO_MSG"
    LI_MSG_SENT = "LI_MSG_SENT"
    LINKEDIN_NO_RESPONSE = "LINKEDIN_NO_RESPONSE"
    LINKEDIN_REPLIED = "LINKEDIN_REPLIED"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_OPENED = "EMAIL_OPENED"
    EMAIL_CLICKED = "EMAIL_CLICKED"
    EMAIL_FAILED = "EMAIL_FAILED"
    EMAIL_REPLIED = "EMAIL_REPLIED"
    CALL_QUEUED = "CALL_QUEUED"
    CALL_IN_PROGRESS = "CALL_IN_PROGRESS"
    CALL_CONNECTED = "CALL_CONNECTED"
    CALL_NO_ANSWER_1 = "CALL_NO_ANSWER_1"
    CALL_NO_ANSWER_2 = "CALL_NO_ANSWER_2"
    CALL_FAILED = "CALL_FAILED"
    CALL_RETRY = "CALL_RETRY"
    MEETING_BOOKED = "MEETING_BOOKED"
    PAUSED_NUDGED = "PAUSED_NUDGED"
    # Sequence Engine (Module 11): channels 4-7 of the configurable 7-step
    # sequence (LinkedIn, LinkedIn Follow-up, Email 1, Email 2, Call,
    # Voicemail, Breakup Email) - see workers/tasks.py's
    # execute_sequence_step_task, which is the only place that decides which
    # of these to move a prospect into (never hardcoded by state name).
    EMAIL_2_SENT = "EMAIL_2_SENT"
    VOICEMAIL_LEFT = "VOICEMAIL_LEFT"
    BREAKUP_EMAIL_SENT = "BREAKUP_EMAIL_SENT"
    COMPLETED_DECLINED = "COMPLETED_DECLINED"
    UNRESPONSIVE_DEAD = "UNRESPONSIVE_DEAD"
    LOST = "LOST"
    ERROR_NEEDS_HUMAN = "ERROR_NEEDS_HUMAN"
    ENGAGED_ON_WEBSITE = "ENGAGED_ON_WEBSITE"
    # Module 14 (Revenue Attribution): a MEETING_BOOKED deal that actually
    # closed - distinct from COMPLETED_DECLINED/LOST, neither of which means
    # "won". Reached only via an explicit human/ops action (no automated
    # detection of deal-closing exists), see api/v1/prospects.py's
    # /mark-won.
    CLOSED_WON = "CLOSED_WON"

class Campaign(Base, TenantMixin):
    __tablename__ = "campaigns"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Relationships
    prospects = relationship("Prospect", back_populates="campaign")

class Prospect(Base, TenantMixin):
    __tablename__ = "prospects"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    linkedin_url: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_state: Mapped[str] = mapped_column(String(50), default="PROSPECT_CREATED", index=True, nullable=False)
    
    # New strict pipeline fields
    # name= pins the native Postgres enum type to its original name (created
    # when this enum was still called ProspectStatus) so the Python-side
    # rename to ProspectState needs no migration on already-deployed DBs.
    status: Mapped[ProspectState] = mapped_column(SQLEnum(ProspectState, name="prospectstatus"), default=ProspectState.NEW, nullable=False)
    call_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_call_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_status_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # CRM sync (Module 1)
    hubspot_contact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hubspot_deal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hubspot_company_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Sequence Engine (Module 11): index into the tenant's ordered
    # SequenceStep list (step_number ascending) - the next step
    # execute_sequence_step_task will run for this prospect. 0 = sequence
    # not yet started. This is the sole source of truth for "what channel
    # comes next" - never a hardcoded chain of task names.
    sequence_step_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    # Calendar sync (Module 2)
    google_calendar_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Company enrichment (Module 13) - populated by the enrichment
    # waterfall's company-data tier, fed into qualification scoring and AI
    # personalization. All nullable: any field may be unavailable for a
    # given company, and scoring/personalization degrade gracefully when so.
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue: Mapped[str | None] = mapped_column(String(100), nullable=True)  # bucketed, e.g. "$10M-$50M"
    hq_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    funding_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. SEED, SERIES_A, PUBLIC
    funding_amount: Mapped[float | None] = mapped_column(Float, nullable=True)  # total raised, USD
    tech_stack: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    company_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lead Qualification & Prioritization (Module 13) - replaces the old
    # binary "has email or phone" qualification gate with a configurable,
    # weighted score (see services/qualification/scoring.py). Nullable:
    # prospects not yet through qualification have none of these set.
    qualification_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualification_level: Mapped[QualificationLevel | None] = mapped_column(
        SQLEnum(QualificationLevel, name="qualificationlevel"), nullable=True
    )

    # Revenue Attribution (Module 14) - estimated value of this deal, used
    # to derive estimated_pipeline_value/meeting_value/won_value/lost_value
    # in analytics. Defaulted from company size during qualification (see
    # services/qualification/scoring.py::estimate_deal_value) when not
    # explicitly set; always overridable.
    estimated_deal_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Analytics (Module 5) - no created_at existed before; needed for
    # daily/weekly activity trends and prospect-age/response-time metrics.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)

    # Relationships
    campaign = relationship("Campaign", back_populates="prospects")
    workflow_state = relationship("WorkflowState", back_populates="prospect", cascade="all, delete-orphan", uselist=False)
    follow_ups = relationship("FollowUp", back_populates="prospect", cascade="all, delete-orphan")
    activity_timeline = relationship("ActivityTimeline", back_populates="prospect", cascade="all, delete-orphan")
    calendar_sync_logs = relationship("CalendarSyncLog", back_populates="prospect", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_prospects_tenant_state", "tenant_id", "current_state"),
    )

class WorkflowState(Base, TenantMixin):
    __tablename__ = "workflow_states"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), default=func.now(), nullable=False)
    
    # Relationships
    prospect = relationship("Prospect", back_populates="workflow_state")

class FollowUp(Base, TenantMixin):
    __tablename__ = "follow_ups"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="LINKEDIN", nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True, nullable=False)  # PENDING, EXECUTED, CANCELED
    
    # Relationships
    prospect = relationship("Prospect", back_populates="follow_ups")

    __table_args__ = (
        Index("idx_followups_status_scheduled", "status", "scheduled_for"),
    )

class ActivityTimeline(Base, TenantMixin):
    __tablename__ = "activity_timelines"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)        # LINKEDIN, EMAIL, CALL, SYSTEM
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)     # SENT, ACCEPTED, REPLY, FAILED
    description: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    prospect = relationship("Prospect", back_populates="activity_timeline")

class CalendarSyncStatus(enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"

class CalendarSyncLog(Base, TenantMixin):
    """Structured log of calendar operations, distinct from the free-text
    ActivityTimeline: dashboard queries (Calendar Sync Status, Failed Syncs,
    Last Calendar Sync) need a queryable status/timestamp per operation
    rather than parsing narrative descriptions."""
    __tablename__ = "calendar_sync_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)  # EVENT_CREATED, EVENT_UPDATED, EVENT_DELETED, API_FAILURE, RETRY_ATTEMPT
    status: Mapped[CalendarSyncStatus] = mapped_column(SQLEnum(CalendarSyncStatus, name="calendarsyncstatus"), nullable=False)
    google_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)

    prospect = relationship("Prospect", back_populates="calendar_sync_logs")

class CrmSyncStatus(enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

class CrmSyncLog(Base, TenantMixin):
    """Module 1: audit trail for every CRM sync attempt (contact, company,
    deal, meeting, note, or association) - records whether it succeeded,
    the provider's raw response (or the error on failure), and when. There
    was previously no queryable record of CRM sync outcomes at all."""
    __tablename__ = "crm_sync_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str | None] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. HUBSPOT
    sync_type: Mapped[str] = mapped_column(String(30), nullable=False)  # CONTACT, COMPANY, DEAL, MEETING, NOTE, ASSOCIATION
    status: Mapped[CrmSyncStatus] = mapped_column(SQLEnum(CrmSyncStatus, name="crmsyncstatus"), nullable=False)
    provider_response: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)

class LinkedInAccount(Base, TenantMixin):
    """One row per LinkedIn/Unipile sending account (Module 4). Multiple
    accounts per tenant are supported by this schema even though today
    exactly one is created per tenant, resolved from
    settings.UNIPILE_ACCOUNT_ID - the future multi-account path is just
    resolving a different account_id per campaign/sequence instead."""
    __tablename__ = "linkedin_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    daily_send_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_count_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paused_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_linkedin_accounts_tenant_account", "tenant_id", "account_id", unique=True),
    )

class DecisionType(enum.Enum):
    """Module 6: every value the AI Decision Engine can return."""
    WAIT = "WAIT"
    SEND_LINKEDIN = "SEND_LINKEDIN"
    SEND_FOLLOWUP = "SEND_FOLLOWUP"
    SEND_EMAIL = "SEND_EMAIL"
    SCHEDULE_CALL = "SCHEDULE_CALL"
    RETRY_LATER = "RETRY_LATER"
    BOOK_MEETING = "BOOK_MEETING"
    MARK_QUALIFIED = "MARK_QUALIFIED"
    MARK_DISQUALIFIED = "MARK_DISQUALIFIED"
    END_SEQUENCE = "END_SEQUENCE"
    # Module 14: the qualification score and active buying signals can now
    # override a would-be send into one of these two, instead of the old
    # binary QUALIFIED/DISQUALIFIED gate being the only lever (see
    # services/decision/engine.py's _apply_qualification_and_signal_policy).
    PAUSE = "PAUSE"
    HUMAN_REVIEW = "HUMAN_REVIEW"

class DecisionLog(Base, TenantMixin):
    """Audit trail of every decision the DecisionEngine has made - the
    "log every decision with timestamp and explanation" requirement.
    prospect_status_at_decision is a snapshot (not a FK-only lookup) so the
    log stays meaningful even if the prospect's status has since moved on."""
    __tablename__ = "decision_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    decision_type: Mapped[DecisionType] = mapped_column(SQLEnum(DecisionType, name="decisiontype"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    prospect_status_at_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    # Sprint 6, item 4 (Historical Analytics): the prospect's
    # qualification_level/score AT THE TIME of this decision - a true
    # snapshot, not a join to Prospect's current (possibly since-changed)
    # value. Nullable: decisions logged before this sprint, and decisions
    # for never-scored prospects, have neither.
    qualification_level_at_decision: Mapped[QualificationLevel | None] = mapped_column(
        SQLEnum(QualificationLevel, name="qualificationlevel"), nullable=True
    )
    qualification_score_at_decision: Mapped[float | None] = mapped_column(Float, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    # Deterministic ordering tiebreaker: created_at (default=func.now()) is
    # the transaction's start time in Postgres, so two decisions logged in
    # the same transaction can share an identical created_at - this
    # database-generated IDENTITY column is strictly monotonic per insert
    # (atomic, race-free even under concurrency) and is what
    # api/v1/decisions.py actually orders by, not created_at.
    sequence_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True, index=True)

class SequenceRule(Base, TenantMixin):
    __tablename__ = "sequence_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    
    # Limits & Intervals
    max_linkedin_msgs: Mapped[int] = mapped_column(Integer, default=3)
    linkedin_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    max_emails: Mapped[int] = mapped_column(Integer, default=4)
    email_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    max_calls: Mapped[int] = mapped_column(Integer, default=2)
    call_interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    
    # Rules Panel Configs
    response_handling_action: Mapped[str] = mapped_column(String(50), default="PAUSE_AND_NOTIFY") # PAUSE_AND_NOTIFY, CONTINUE
    ai_guided_calls: Mapped[bool] = mapped_column(Boolean, default=True)
    call_mode: Mapped[str] = mapped_column(String(20), default="MANUAL") # MANUAL, AUTOMATIC
    assigned_lead_owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    auto_handover_to_admin: Mapped[bool] = mapped_column(Boolean, default=True)

class SequenceStep(Base):
    __tablename__ = "sequence_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sequence_rule_id: Mapped[str] = mapped_column(ForeignKey("sequence_rules.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(20)) # LINKEDIN, EMAIL, CALL
    step_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(100)) # e.g. "Message 1 (AI-crafted connect)"
    delay_minutes: Mapped[int] = mapped_column(Integer, default=60)
    template_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

class MemoryType(enum.Enum):
    """Module 7: Classification of conversational memories."""
    LINKEDIN_MESSAGE = "LINKEDIN_MESSAGE"
    EMAIL_MESSAGE = "EMAIL_MESSAGE"
    CALL_SUMMARY = "CALL_SUMMARY"
    AI_NOTE = "AI_NOTE"
    OBJECTION = "OBJECTION"
    PREFERENCE = "PREFERENCE"
    MEETING_OUTCOME = "MEETING_OUTCOME"
    BUYING_SIGNAL = "BUYING_SIGNAL"

class ConversationMemory(Base, TenantMixin):
    """Module 7: Persistent storage for prospect interaction history."""
    __tablename__ = "conversation_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type: Mapped[MemoryType] = mapped_column(SQLEnum(MemoryType, name="memorytype"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance_score: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # e.g., 1-10
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # E.g., 'SYSTEM', 'EMAIL_WEBHOOK', 'USER'
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)     # ID or email of human user if manual
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)      # Store thread_id, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)

    prospect = relationship("Prospect", backref="memories")

class SignalType(enum.Enum):
    """Module 8: Types of buying signals."""
    WEBSITE_VISIT = "WEBSITE_VISIT"
    LINKEDIN_ACTIVITY = "LINKEDIN_ACTIVITY"
    JOB_CHANGE = "JOB_CHANGE"
    PROMOTION = "PROMOTION"
    COMPANY_HIRING = "COMPANY_HIRING"
    FUNDING_EVENT = "FUNDING_EVENT"
    NEWS_EVENT = "NEWS_EVENT"
    TECH_STACK_CHANGE = "TECH_STACK_CHANGE"
    EMAIL_OPEN = "EMAIL_OPEN"
    EMAIL_CLICK = "EMAIL_CLICK"
    CALLBACK_REQUEST = "CALLBACK_REQUEST"
    HIGH_INTENT_REPLY = "HIGH_INTENT_REPLY"
    NEGATIVE_REPLY = "NEGATIVE_REPLY"
    MEETING_REQUEST = "MEETING_REQUEST"
    MANUAL_SIGNAL = "MANUAL_SIGNAL"
    CUSTOM_SIGNAL = "CUSTOM_SIGNAL"

class SignalStrength(enum.Enum):
    """Module 8: Scored strength of buying signals."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

class BuyingSignal(Base, TenantMixin):
    """Module 8: Collected raw signals before they are translated into actionable Memory."""
    __tablename__ = "buying_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_type: Mapped[SignalType] = mapped_column(SQLEnum(SignalType, name="signaltype"), nullable=False, index=True)
    signal_source: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_strength: Mapped[SignalStrength] = mapped_column(SQLEnum(SignalStrength, name="signalstrength"), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prospect = relationship("Prospect", backref="buying_signals")

class CompliancePolicyType(enum.Enum):
    """Module 9: Types of compliance policies."""
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    BOUNCE = "BOUNCE"
    INVALID_EMAIL = "INVALID_EMAIL"
    DAILY_LIMIT = "DAILY_LIMIT"
    RATE_LIMIT = "RATE_LIMIT"
    BUSINESS_HOURS = "BUSINESS_HOURS"
    COOLDOWN = "COOLDOWN"
    DUPLICATE_PREVENTION = "DUPLICATE_PREVENTION"
    MEETING_BOOKED = "MEETING_BOOKED"
    DISQUALIFIED = "DISQUALIFIED"
    CONSENT_MISSING = "CONSENT_MISSING"

class PolicySeverity(enum.Enum):
    """Module 9: Action triggered by a policy block."""
    INFO = "INFO"
    WARNING = "WARNING"
    TEMPORARY_BLOCK = "TEMPORARY_BLOCK"
    PERMANENT_BLOCK = "PERMANENT_BLOCK"

class ComplianceLog(Base, TenantMixin):
    """Module 9: Audit trail for compliance engine evaluations."""
    __tablename__ = "compliance_logs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str | None] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=True, index=True)
    policy_type: Mapped[CompliancePolicyType] = mapped_column(SQLEnum(CompliancePolicyType, name="compliancepolicytype"), nullable=False, index=True)
    severity: Mapped[PolicySeverity] = mapped_column(SQLEnum(PolicySeverity, name="policyseverity"), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True) # e.g. LINKEDIN, EMAIL, CALL
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str] = mapped_column(String(50), nullable=False) # BLOCKED, DELAYED
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    metadata_: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)

class DoNotContactList(Base, TenantMixin):
    """Module 9: Global and tenant-specific DNC lists."""
    __tablename__ = "do_not_contact"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    value: Mapped[str] = mapped_column(String(255), nullable=False, index=True) # e.g., example@domain.com, domain.com, +1234567890
    type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., EMAIL, DOMAIN, PHONE
    reason: Mapped[str] = mapped_column(Text, nullable=True) # e.g., Unsubscribed, Legal
    source: Mapped[str] = mapped_column(String(100), nullable=False) # e.g., SYSTEM, USER_MANUAL, INBOUND_REPLY
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)

class CallTranscript(Base, TenantMixin):
    """Module 10: Metadata for a completed or ongoing voice conversation."""
    __tablename__ = "call_transcripts"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    call_sid: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_turns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="IN_PROGRESS", nullable=False) # IN_PROGRESS, COMPLETED, FAILED
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    incremental_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    
    lines = relationship("CallTranscriptLine", back_populates="transcript", cascade="all, delete-orphan", order_by="CallTranscriptLine.turn_index")

class CallTranscriptLine(Base, TenantMixin):
    """Module 10: Individual turns within a voice conversation."""
    __tablename__ = "call_transcript_lines"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transcript_id: Mapped[str] = mapped_column(ForeignKey("call_transcripts.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(20), nullable=False) # ASSISTANT or PROSPECT
    text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    transcript = relationship("CallTranscript", back_populates="lines")

class EmailVerificationStatus(enum.Enum):
    """Module 12: outcome of verifying a recipient address before first
    send. RISKY covers addresses that pass syntax but where the provider
    could not confirm deliverability (e.g. no MX records returned)."""
    VALID = "VALID"
    INVALID = "INVALID"
    RISKY = "RISKY"
    UNKNOWN = "UNKNOWN"

class EmailVerification(Base):
    """Module 12: cached verification result per email address, checked
    once before its first send rather than on every send. Not
    tenant-scoped - deliverability is a property of the address itself,
    not of which tenant is emailing it."""
    __tablename__ = "email_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[EmailVerificationStatus] = mapped_column(
        SQLEnum(EmailVerificationStatus, name="emailverificationstatus"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

class EmailBounceSuppression(Base):
    """Module 12: permanent send-suppression list populated from bounce/
    complaint webhook events. Checked before every send, ahead of
    verification - a previously-valid address that later bounces must
    never be sent to again."""
    __tablename__ = "email_bounce_suppressions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

