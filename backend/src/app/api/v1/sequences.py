from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
import uuid

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
    assigned_lead_owner_id: Optional[str]
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
    assigned_lead_owner_id: Optional[str]
    auto_handover_to_admin: bool
    dev_mode: bool = False

class SequenceStepSchema(BaseModel):
    id: str
    channel: str
    step_number: int
    title: str
    delay_days: int
    template_prompt: Optional[str] = None

    class Config:
        from_attributes = True

class SequenceStepCreate(BaseModel):
    channel: str
    step_number: int
    title: str
    delay_days: int
    template_prompt: Optional[str] = None

class SequenceCurrentResponse(BaseModel):
    rule: SequenceRuleResponse
    steps: List[SequenceStepSchema]

# --- Endpoints ---

@router.get("/current", response_model=SequenceCurrentResponse)
async def get_current_sequence(tenant_id: str = "tenant_1", db: AsyncSession = Depends(get_db)):
    """
    Fetches the active sequence rule and steps for the tenant.
    If none exists, automatically seeds and returns a default rule.
    """
    # Using a hardcoded tenant_id="tenant_1" for demo purposes.
    # In production, this would come from a JWT auth dependency.
    
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
        await db.commit()
        await db.refresh(active_rule)

    steps_res = await db.execute(
        select(SequenceStep).where(SequenceStep.sequence_rule_id == active_rule.id).order_by(SequenceStep.step_number)
    )
    steps = steps_res.scalars().all()
    
    active_rule._dev_mode_temp = workspace.dev_mode

    return SequenceCurrentResponse(
        rule=SequenceRuleResponse.from_db(active_rule),
        steps=[SequenceStepSchema.model_validate(s) for s in steps]
    )


@router.put("/rules", response_model=SequenceRuleResponse)
async def update_sequence_rules(payload: SequenceRuleUpdate, tenant_id: str = "tenant_1", db: AsyncSession = Depends(get_db)):
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


@router.post("/steps", response_model=List[SequenceStepSchema])
async def update_sequence_steps(payload: List[SequenceStepCreate], tenant_id: str = "tenant_1", db: AsyncSession = Depends(get_db)):
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
            delay_days=s.delay_days,
            template_prompt=s.template_prompt
        )
        db.add(step)
        new_steps.append(step)
        
    await db.commit()
    
    return [SequenceStepSchema.model_validate(s) for s in new_steps]
