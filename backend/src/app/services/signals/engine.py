import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import cache_get_or_set, make_cache_key
from app.database import redis_client
from app.models.schemas import BuyingSignal, MemoryType, Prospect, SignalStrength, SignalType
from app.services.memory.service import ConversationMemoryService
from app.services.signals.factory import get_signal_provider

logger = logging.getLogger(__name__)

class BuyingSignalEngine:
    """
    Centralized engine for collecting, scoring, and storing buying signals.
    """

    @staticmethod
    def _calculate_expiration(signal_type: SignalType) -> datetime:
        """
        Hard expiration dates based on signal type.
        """
        now = datetime.now(UTC)
        if signal_type in (SignalType.JOB_CHANGE, SignalType.FUNDING_EVENT):
            return now + timedelta(days=90)
        elif signal_type in (SignalType.COMPANY_HIRING, SignalType.PROMOTION, SignalType.NEWS_EVENT):
            return now + timedelta(days=30)
        elif signal_type in (SignalType.WEBSITE_VISIT, SignalType.EMAIL_CLICK):
            return now + timedelta(days=7)
        else:
            return now + timedelta(days=14)

    async def collect_and_process_signals(self, db: AsyncSession, prospect: Prospect) -> None:
        """
        Fetches signals via provider (read-through cached - Sprint 3, item
        6: the same prospect can be re-scanned repeatedly and vendor signal
        lookups are rate-limited/billed per call), deduplicates them, saves
        to BuyingSignal, and translates them into ConversationMemory entries.
        """
        provider = get_signal_provider(prospect.tenant_id)
        cache_key = make_cache_key("cache", "buying_signals", prospect.tenant_id, prospect.id)

        async def _fetch_serializable() -> list:
            raw = await provider.fetch_signals(prospect)
            return [self._serialize_raw_signal(r) for r in raw]

        serialized = await cache_get_or_set(
            redis_client, cache_key, settings.BUYING_SIGNALS_CACHE_TTL_SECONDS, _fetch_serializable
        )
        raw_signals = [self._deserialize_raw_signal(r) for r in serialized]

        if not raw_signals:
            return

        for raw in raw_signals:
            await self._process_single_signal(db, prospect, raw)

    @staticmethod
    def _serialize_raw_signal(raw: dict) -> dict:
        """Provider-returned raw signal dicts carry Enum members and
        (optionally) a datetime - neither is JSON-serializable, so cache
        storage needs its own explicit round-trip conversion."""
        out = dict(raw)
        out["signal_type"] = raw["signal_type"].value if isinstance(raw["signal_type"], SignalType) else raw["signal_type"]
        out["signal_strength"] = (
            raw["signal_strength"].value if isinstance(raw["signal_strength"], SignalStrength) else raw["signal_strength"]
        )
        expires_at = raw.get("expires_at")
        if expires_at is not None:
            out["expires_at"] = expires_at.isoformat() if hasattr(expires_at, "isoformat") else expires_at
        return out

    @staticmethod
    def _deserialize_raw_signal(raw: dict) -> dict:
        out = dict(raw)
        out["signal_type"] = SignalType(raw["signal_type"])
        out["signal_strength"] = SignalStrength(raw["signal_strength"])
        expires_at = raw.get("expires_at")
        if expires_at is not None:
            out["expires_at"] = datetime.fromisoformat(expires_at)
        return out

    async def _process_single_signal(self, db: AsyncSession, prospect: Prospect, raw: dict) -> None:
        # 1. Deduplication: check if an identical active signal exists in the last X days.
        sig_type = raw["signal_type"]
        sig_source = raw["signal_source"]
        
        query = select(BuyingSignal).where(
            BuyingSignal.tenant_id == prospect.tenant_id,
            BuyingSignal.prospect_id == prospect.id,
            BuyingSignal.signal_type == sig_type,
            BuyingSignal.signal_source == sig_source,
            BuyingSignal.is_active == True
        )
        existing = await db.execute(query)
        if existing.scalar_one_or_none():
            logger.debug(f"Signal {sig_type} from {sig_source} already exists for {prospect.id}. Skipping.")
            return

        # 2. Save BuyingSignal
        expires_at = raw.get("expires_at") or self._calculate_expiration(sig_type)
        signal = BuyingSignal(
            tenant_id=prospect.tenant_id,
            prospect_id=prospect.id,
            signal_type=sig_type,
            signal_source=sig_source,
            signal_strength=raw["signal_strength"],
            confidence=raw.get("confidence", 1.0),
            summary=raw["summary"],
            metadata_=raw.get("metadata_", {}),
            is_active=True,
            expires_at=expires_at,
            processed_at=datetime.now(UTC)
        )
        db.add(signal)
        
        # 3. Create structured ConversationMemory for the Decision Engine
        # The Decision Engine only evaluates structured memory.
        await ConversationMemoryService.add_memory(
            db=db,
            tenant_id=prospect.tenant_id,
            prospect_id=prospect.id,
            memory_type=MemoryType.BUYING_SIGNAL,
            content=f"[{sig_type.value}] {signal.summary}",
            importance_score=8 if raw["signal_strength"] in (SignalStrength.HIGH, SignalStrength.VERY_HIGH) else 4,
            source=sig_source,
            is_resolved=False,
            expires_at=expires_at,
            metadata_={"signal_type": sig_type.value, "signal_strength": raw["signal_strength"].value}
        )
        
        await db.flush()

    @staticmethod
    async def expire_old_signals(db: AsyncSession) -> int:
        """
        Sweeps the DB for signals that have passed expires_at and marks them inactive.
        Does NOT delete them (historical analytics).
        """
        now = datetime.now(UTC)
        stmt = (
            update(BuyingSignal)
            .where(
                BuyingSignal.is_active == True,
                BuyingSignal.expires_at <= now
            )
            .values(is_active=False)
            .returning(BuyingSignal.id)
        )
        result = await db.execute(stmt)
        expired_ids = result.scalars().all()
        await db.commit()
        
        # We must also expire the corresponding ConversationMemory entries if they share the same expires_at logic,
        # but the ConversationMemoryService.get_active_context() already filters out expired memories via SQL.
        return len(expired_ids)
