import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.database import get_db
from app.models.schemas import ComplianceLog, DoNotContactList
from app.schemas.compliance import (
    ComplianceLogListResponse,
    ComplianceStatusResponse,
    DoNotContactCreate,
    DoNotContactResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance", tags=["Compliance"])

@router.get("/status", response_model=ComplianceStatusResponse)
async def get_compliance_status(tenant_id: str = Depends(verify_tenant)):
    """Returns the current configuration of the compliance engine."""
    return {
        "status": "success",
        "data": {
            "engine": "active",
            "enforced_policies": [
                "DO_NOT_CONTACT",
                "BUSINESS_HOURS"
            ]
        }
    }

@router.get("/violations", response_model=ComplianceLogListResponse)
async def get_compliance_violations(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Returns a list of recent compliance blocks."""
    query = (
        select(ComplianceLog)
        .where(ComplianceLog.tenant_id == tenant_id)
        .order_by(ComplianceLog.created_at.desc())
        .limit(50)
    )
    results = (await db.execute(query)).scalars().all()
    return {"status": "success", "data": results}

@router.post("/dnc", response_model=DoNotContactResponse)
async def add_to_dnc(dnc_data: DoNotContactCreate, tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Manually add an email, domain, or phone to the DNC list."""
    dnc = DoNotContactList(
        tenant_id=tenant_id,
        value=dnc_data.value,
        type=dnc_data.type,
        reason=dnc_data.reason,
        source=dnc_data.source
    )
    db.add(dnc)
    await db.commit()
    await db.refresh(dnc)
    return dnc
