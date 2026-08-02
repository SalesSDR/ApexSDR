import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.database import get_db
from app.models.schemas import SequenceRule, SequenceStep, WorkspaceSetting

router = APIRouter(prefix="/sequences", tags=["sequences"])

# --- Pydantic Schemas ---
class SequenceRuleResponse(BaseModel):
    id: str
    tenant_id: str
    max_linkedin_msgs: int
    linkedin_interval_days: int  # Exposed as days in UI; stored as minutes internally
    max_emails: int
    email_interval_days: int
    max_calls: int
    call_interval_days: int
    response_handling_action: str
    ai_guided_calls: bool
    call_mode: str
    assigned_lead_owner_id: str | None
    auto_handover_to_admin: bool
    dev_mode: bool = False

    class Config:
        from_attributes = True

    @classmethod
    def from_db(cls, rule: "SequenceRule") -> "SequenceRuleResponse":
        """Convert minutes-based DB model to days-based API response."""
        return cls(
            id=rule.id,
            tenant_id=rule.tenant_id,
            max_linkedin_msgs=rule.max_linkedin_msgs,
            linkedin_interval_days=max(1, rule.linkedin_interval_minutes // 60),
            max_emails=rule.max_emails,
            email_interval_days=max(1, rule.email_interval_minutes // 60),
            max_calls=rule.max_calls,
            call_interval_days=max(1, rule.call_interval_minutes // 1440),
            response_handling_action=rule.response_handling_action,
            ai_guided_calls=rule.ai_guided_calls,
            call_mode=rule.call_mode,
            assigned_lead_owner_id=rule.assigned_lead_owner_id,
            auto_handover_to_admin=rule.auto_handover_to_admin,
            dev_mode=getattr(rule, '_dev_mode_temp', False)
        )

class SequenceRuleUpdate(BaseModel):
    max_linkedin_msgs: int
    linkedin_interval_days: int
    max_emails: int
    email_interval_days: int
    max_calls: int
    call_interval_days: int
    response_handling_action: str
    ai_guided_calls: bool
    call_mode: str
    assigned_lead_owner_id: str | None
    auto_handover_to_admin: bool
    dev_mode: bool = False

class SequenceStepSchema(BaseModel):
    id: str
    channel: str
    step_number: int
    title: str
    delay_days: int  # Exposed as days in UI; stored as minutes internally (SequenceStep.delay_minutes)
    template_prompt: str | None = None

    class Config:
        from_attributes = True

    @classmethod
    def from_db(cls, step: "SequenceStep") -> "SequenceStepSchema":
        """Convert minutes-based DB model to days-based API response - the
        step-level equivalent of SequenceRuleResponse.from_db above.
        SequenceStep has no `delay_days` attribute (only `delay_minutes`),
        so a bare model_validate(step, from_attributes=True) would raise."""
        return cls(
            id=step.id,
            channel=step.channel,
            step_number=step.step_number,
            title=step.title,
            delay_days=max(0, (step.delay_minutes or 0) // 1440),
            template_prompt=step.template_prompt,
        )

class SequenceStepCreate(BaseModel):
    channel: str
    step_number: int
    title: str
    delay_days: int
    template_prompt: str | None = None

class SequenceCurrentResponse(BaseModel):
    rule: SequenceRuleResponse
    steps: list[SequenceStepSchema]

# The 7 channels the Sequence Engine (workers/tasks.py's
# execute_sequence_step_task) knows how to run, in the spec's recommended
# default order. This is only a *default* seeded once per tenant - the
# actual order that governs execution is whatever step_number order exists
# in the sequence_steps table at run time, fully editable via POST
# /sequences/steps; nothing in the worker is hardcoded to this list.
_DEFAULT_SEQUENCE_STEPS = [
    ("LINKEDIN", "LinkedIn Connection Request", 2),
    ("LINKEDIN_FOLLOWUP", "LinkedIn Follow-up Message", 2),
    ("EMAIL_1", "Email #1", 2),
    ("EMAIL_2", "Email #2", 3),
    ("CALL", "Phone Call", 1),
    ("VOICEMAIL", "Voicemail Drop", 1),
    ("BREAKUP_EMAIL", "Breakup Email", 0),
]


async def _seed_default_steps(db: AsyncSession, sequence_rule_id: str) -> None:
    for step_number, (channel, title, delay_days) in enumerate(_DEFAULT_SEQUENCE_STEPS, start=1):
        db.add(SequenceStep(
            id=str(uuid.uuid4()),
            sequence_rule_id=sequence_rule_id,
            channel=channel,
            step_number=step_number,
            title=title,
            delay_minutes=delay_days * 1440,
        ))

# --- Endpoints ---

@router.get("/current", response_model=SequenceCurrentResponse)
async def get_current_sequence(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """
    Fetches the active sequence rule and steps for the tenant.
    If none exists, automatically seeds and returns a default rule.
    """
    rule = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
    active_rule = rule.scalar_one_or_none()
    
    ws = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
    workspace = ws.scalar_one_or_none()
    if not workspace:
        workspace = WorkspaceSetting(tenant_id=tenant_id, dev_mode=False)
        db.add(workspace)
        
    if not active_rule:
        # Seed default SequenceRule using correct minute-based fields
        active_rule = SequenceRule(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            max_linkedin_msgs=2,
            linkedin_interval_minutes=1,   # 1 minute for testing
            max_emails=2,
            email_interval_minutes=1,      # 1 minute for testing
            max_calls=1,
            call_interval_minutes=1,       # 1 minute for testing
            response_handling_action="PAUSE_AND_NOTIFY",
            ai_guided_calls=True,
            call_mode="AUTOMATIC",
            auto_handover_to_admin=True
        )
        db.add(active_rule)
        await db.flush()
        await _seed_default_steps(db, active_rule.id)
        await db.commit()
        await db.refresh(active_rule)

    steps_res = await db.execute(
        select(SequenceStep).where(SequenceStep.sequence_rule_id == active_rule.id).order_by(SequenceStep.step_number)
    )
    steps = steps_res.scalars().all()

    active_rule._dev_mode_temp = workspace.dev_mode

    return SequenceCurrentResponse(
        rule=SequenceRuleResponse.from_db(active_rule),
        steps=[SequenceStepSchema.from_db(s) for s in steps]
    )


@router.put("/rules", response_model=SequenceRuleResponse)
async def update_sequence_rules(payload: SequenceRuleUpdate, tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """
    Updates the rules panel configuration for the active sequence.
    Converts days-based UI values to minutes-based DB storage.
    """
    rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
    active_rule = rule_res.scalar_one_or_none()
    
    if not active_rule:
        # Auto-seed if missing instead of throwing 404
        active_rule = SequenceRule(id=str(uuid.uuid4()), tenant_id=tenant_id)
        db.add(active_rule)
        
    ws_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
    workspace = ws_res.scalar_one_or_none()
    if not workspace:
        workspace = WorkspaceSetting(tenant_id=tenant_id)
        db.add(workspace)
        
    workspace.dev_mode = payload.dev_mode

    # Map days→minutes for storage
    active_rule.max_linkedin_msgs = payload.max_linkedin_msgs
    active_rule.linkedin_interval_minutes = payload.linkedin_interval_days * 60
    active_rule.max_emails = payload.max_emails
    active_rule.email_interval_minutes = payload.email_interval_days * 60
    active_rule.max_calls = payload.max_calls
    active_rule.call_interval_minutes = payload.call_interval_days * 1440
    active_rule.response_handling_action = payload.response_handling_action
    active_rule.ai_guided_calls = payload.ai_guided_calls
    active_rule.call_mode = payload.call_mode
    active_rule.assigned_lead_owner_id = payload.assigned_lead_owner_id
    active_rule.auto_handover_to_admin = payload.auto_handover_to_admin
        
    await db.commit()
    await db.refresh(active_rule)
    active_rule._dev_mode_temp = workspace.dev_mode
    return SequenceRuleResponse.from_db(active_rule)


@router.post("/steps", response_model=list[SequenceStepSchema])
async def update_sequence_steps(payload: list[SequenceStepCreate], tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """
    Replaces all sequence steps for the active rule.
    """
    rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
    active_rule = rule_res.scalar_one_or_none()
    
    if not active_rule:
        raise HTTPException(status_code=404, detail="SequenceRule not found. Please load /current first.")

    # Delete existing steps
    await db.execute(delete(SequenceStep).where(SequenceStep.sequence_rule_id == active_rule.id))
    
    new_steps = []
    for s in payload:
        step = SequenceStep(
            id=str(uuid.uuid4()),
            sequence_rule_id=active_rule.id,
            channel=s.channel,
            step_number=s.step_number,
            title=s.title,
            delay_minutes=s.delay_days * 1440,
            template_prompt=s.template_prompt
        )
        db.add(step)
        new_steps.append(step)

    await db.commit()

    return [SequenceStepSchema.from_db(s) for s in new_steps]
