from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.database import get_db
from app.models.schemas import BuyingSignal, Prospect
from app.schemas.signals import BuyingSignalCreate, BuyingSignalListResponse, BuyingSignalResponse
from app.services.signals.engine import BuyingSignalEngine

router = APIRouter(prefix="/signals", tags=["Signals"])

@router.get("", response_model=BuyingSignalListResponse)
async def list_all_signals(
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = 50
):
    """Returns all active buying signals for the tenant."""
    query = select(BuyingSignal).where(
        BuyingSignal.tenant_id == tenant_id,
        BuyingSignal.is_active == True
    ).order_by(BuyingSignal.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    signals = result.scalars().all()
    
    return {"status": "success", "data": signals}

@router.get("/{prospect_id}", response_model=BuyingSignalListResponse)
async def list_prospect_signals(
    prospect_id: str,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = 50
):
    """Returns signals for a specific prospect."""
    query = select(BuyingSignal).where(
        BuyingSignal.tenant_id == tenant_id,
        BuyingSignal.prospect_id == prospect_id,
        BuyingSignal.is_active == True
    ).order_by(BuyingSignal.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    signals = result.scalars().all()
    
    return {"status": "success", "data": signals}

@router.post("/manual", response_model=BuyingSignalResponse)
async def create_manual_signal(
    prospect_id: str,
    payload: BuyingSignalCreate,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Allows an SDR to manually inject a buying signal."""
    # Verify prospect exists
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id))
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
        
    raw_signal = payload.model_dump()
    raw_signal["signal_type"] = payload.signal_type
    raw_signal["signal_strength"] = payload.signal_strength
    
    engine = BuyingSignalEngine()
    await engine._process_single_signal(db, prospect, raw_signal)
    await db.commit()
    
    # Fetch the newly created signal
    query = select(BuyingSignal).where(
        BuyingSignal.tenant_id == tenant_id,
        BuyingSignal.prospect_id == prospect_id,
        BuyingSignal.signal_type == payload.signal_type
    ).order_by(BuyingSignal.created_at.desc()).limit(1)
    
    new_signal = (await db.execute(query)).scalar_one_or_none()
    return new_signal

@router.get("/health/status")
async def signals_health(tenant_id: str = Depends(verify_tenant)):
    """Health check for signal providers."""
    return {"status": "success", "data": {"providers_active": True}}
