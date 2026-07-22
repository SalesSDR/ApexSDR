from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models.schemas import SequenceRule, SequenceStep

router = APIRouter(prefix="/sequences", tags=["sequences"])

# --- Pydantic Schemas ---
class SequenceRuleResponse(BaseModel):
    id: str
    tenant_id: str
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

    class Config:
        from_attributes = True

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

    if not active_rule:
        # Seed default SequenceRule
        active_rule = SequenceRule(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            max_linkedin_msgs=3,
            linkedin_interval_days=2,
            max_emails=4,
            email_interval_days=3,
            max_calls=2,
            call_interval_days=4,
            response_handling_action="PAUSE_AND_NOTIFY",
            ai_guided_calls=True,
            call_mode="MANUAL",
            auto_handover_to_admin=True
        )
        db.add(active_rule)
        await db.commit()
        await db.refresh(active_rule)

    steps_res = await db.execute(
        select(SequenceStep).where(SequenceStep.sequence_rule_id == active_rule.id).order_by(SequenceStep.step_number)
    )
    steps = steps_res.scalars().all()

    return SequenceCurrentResponse(
        rule=SequenceRuleResponse.model_validate(active_rule),
        steps=[SequenceStepSchema.model_validate(s) for s in steps]
    )


@router.put("/rules", response_model=SequenceRuleResponse)
async def update_sequence_rules(payload: SequenceRuleUpdate, tenant_id: str = "tenant_1", db: AsyncSession = Depends(get_db)):
    """
    Updates the rules panel configuration for the active sequence.
    """
    rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
    active_rule = rule_res.scalar_one_or_none()
    
    if not active_rule:
        raise HTTPException(status_code=404, detail="SequenceRule not found for this tenant.")

    for key, value in payload.model_dump().items():
        setattr(active_rule, key, value)
        
    await db.commit()
    await db.refresh(active_rule)
    return SequenceRuleResponse.model_validate(active_rule)


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
