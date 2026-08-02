import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.database import get_db
from app.models.schemas import Campaign, WorkspaceSetting
from app.schemas.campaigns import CampaignCreateSchema, CampaignResponseSchema, WorkspaceSettingUpdateSchema

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


def _settings_response(setting: WorkspaceSetting) -> dict:
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
            "exclude_weekends": setting.exclude_weekends,
            "dev_mode": setting.dev_mode,
            "icp_profile": setting.icp_profile,
            "qualification_config": setting.qualification_config,
        },
    }


@router.get("/settings", status_code=status.HTTP_200_OK)
async def get_workspace_settings(
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Sprint 6, item 2 (Dashboard Integration): reads the tenant's current
    workspace settings - the read half of the CRUD PUT /settings already
    supported. Returns built-in defaults (not persisted) if the tenant has
    never saved settings before, so the admin-settings UI always has
    something real to render instead of "Coming soon".
    """
    query = select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id)
    result = await db.execute(query)
    setting = result.scalar_one_or_none()
    if not setting:
        # A transient (never flushed) ORM object doesn't get its column
        # defaults applied by Python alone - those only fire at INSERT time
        # - so they're passed explicitly here to match WorkspaceSetting's
        # real column defaults exactly.
        setting = WorkspaceSetting(
            id="", tenant_id=tenant_id, follow_up_delay_hours=24, call_delay_hours=48,
            max_follow_ups=3, working_hours_start="09:00", working_hours_end="17:00",
            timezone="UTC", exclude_weekends=True, dev_mode=False,
            icp_profile={}, qualification_config={},
        )
    return _settings_response(setting)


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

    return _settings_response(setting)

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
