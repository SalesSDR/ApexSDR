import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.api.v1.auth import verify_tenant
from app.models.schemas import WorkspaceSetting, Campaign
from app.schemas.campaigns import WorkspaceSettingUpdateSchema, CampaignCreateSchema, CampaignResponseSchema

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.put("/settings", status_code=status.HTTP_200_OK)
async def update_workspace_settings(
    payload: WorkspaceSettingUpdateSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates workspace execution settings and constraints dynamically.
    These rules will apply to future calculations in the state transition workflow.
    """
    query = select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id)
    result = await db.execute(query)
    setting = result.scalar_one_or_none()

    if not setting:
        setting = WorkspaceSetting(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id
        )
        db.add(setting)

    # Apply modified properties dynamically
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(setting, field, value)

    await db.commit()
    await db.refresh(setting)
    
    return {
        "status": "success",
        "data": {
            "id": setting.id,
            "tenant_id": setting.tenant_id,
            "follow_up_delay_hours": setting.follow_up_delay_hours,
            "call_delay_hours": setting.call_delay_hours,
            "max_follow_ups": setting.max_follow_ups,
            "working_hours_start": setting.working_hours_start,
            "working_hours_end": setting.working_hours_end,
            "timezone": setting.timezone,
            "exclude_weekends": setting.exclude_weekends
        }
    }

@router.post("", status_code=status.HTTP_201_CREATED, response_model=CampaignResponseSchema)
async def create_campaign(
    payload: CampaignCreateSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new marketing/outbound Campaign sequence.
    """
    campaign = Campaign(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=payload.name
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign
