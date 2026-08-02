import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ConversationMemory, MemoryType

logger = logging.getLogger(__name__)

class ConversationMemoryService:
    @staticmethod
    async def add_memory(
        db: AsyncSession,
        tenant_id: str,
        prospect_id: str,
        memory_type: MemoryType,
        content: str,
        importance_score: int = 1,
        source: str = "SYSTEM",
        is_resolved: bool = False,
        created_by: str | None = None,
        expires_at: datetime | None = None,
        metadata_: dict | None = None
    ) -> ConversationMemory:
        memory = ConversationMemory(
            tenant_id=tenant_id,
            prospect_id=prospect_id,
            memory_type=memory_type,
            content=content,
            importance_score=importance_score,
            source=source,
            is_resolved=is_resolved,
            created_by=created_by,
            expires_at=expires_at,
            metadata_=metadata_ or {}
        )
        db.add(memory)
        await db.flush()
        return memory

    @staticmethod
    async def get_memories(
        db: AsyncSession,
        tenant_id: str,
        prospect_id: str,
        memory_type: MemoryType | None = None,
        limit: int = 50
    ) -> list[ConversationMemory]:
        """Returns the timeline of memories for a prospect."""
        query = select(ConversationMemory).where(
            ConversationMemory.tenant_id == tenant_id,
            ConversationMemory.prospect_id == prospect_id
        )
        if memory_type:
            query = query.where(ConversationMemory.memory_type == memory_type)
            
        query = query.order_by(ConversationMemory.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_active_context(
        db: AsyncSession,
        tenant_id: str,
        prospect_id: str
    ) -> list[ConversationMemory]:
        """
        Returns a structured list of active (unresolved, unexpired) memories
        that the Decision Engine should consider for table-driven rules.
        """
        now = datetime.now(UTC)
        query = select(ConversationMemory).where(
            ConversationMemory.tenant_id == tenant_id,
            ConversationMemory.prospect_id == prospect_id,
            ConversationMemory.is_resolved == False,
            or_(
                ConversationMemory.expires_at == None,
                ConversationMemory.expires_at > now
            )
        ).order_by(ConversationMemory.importance_score.desc(), ConversationMemory.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())
