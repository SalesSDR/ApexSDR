
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant as get_current_tenant
from app.database import get_db
from app.models.schemas import MemoryType, Prospect
from app.schemas.memory import ConversationMemoryCreate, ConversationMemoryListResponse, ConversationMemoryResponse
from app.services.memory.service import ConversationMemoryService

router = APIRouter(prefix="/prospects/{prospect_id}/memory", tags=["Memory"])

async def get_prospect_or_404(db: AsyncSession, tenant_id: str, prospect_id: str) -> Prospect:
    result = await db.execute(select(Prospect).where(
        Prospect.id == prospect_id,
        Prospect.tenant_id == tenant_id
    ))
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prospect not found")
    return prospect

@router.post("", response_model=ConversationMemoryResponse)
async def create_memory(
    prospect_id: str,
    payload: ConversationMemoryCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant)
):
    await get_prospect_or_404(db, tenant_id, prospect_id)
    memory = await ConversationMemoryService.add_memory(
        db=db,
        tenant_id=tenant_id,
        prospect_id=prospect_id,
        memory_type=payload.memory_type,
        content=payload.content,
        importance_score=payload.importance_score,
        source=payload.source,
        is_resolved=payload.is_resolved,
        created_by=payload.created_by,
        expires_at=payload.expires_at,
        metadata_=payload.metadata_
    )
    return memory

@router.get("", response_model=ConversationMemoryListResponse)
async def list_memories(
    prospect_id: str,
    memory_type: MemoryType | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant)
):
    await get_prospect_or_404(db, tenant_id, prospect_id)
    
    # We pass the memory_type as a string and let SQLAlchemy coerce to Enum if provided, 
    # but to be strict, we'd cast it to the Enum.
    # To keep routes thin, we just pass it to the service.
    
    memories = await ConversationMemoryService.get_memories(
        db=db,
        tenant_id=tenant_id,
        prospect_id=prospect_id,
        memory_type=memory_type,
        limit=limit
    )
    return {"status": "success", "data": memories}
