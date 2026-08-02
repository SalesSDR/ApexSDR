"""Sprint 4, item 3 (Advanced Personalization), extended in Sprint 5: builds
the rich context every outbound AI prompt draws on - company enrichment,
qualification, buying signals, conversation memory, industry, funding,
tech stack, news, and job title - replacing name/company-only prompts.

Deliberately separate from services/ai.py: this module only reads/shapes
data (Prospect, ConversationMemory, BuyingSignal), never talks to Gemini or
builds prompt strings itself - ai.py owns prompt construction and the
prompt-injection defenses (core/prompt_security.py) applied to every field
this module surfaces.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import BuyingSignal, ConversationMemory, Prospect

# Signal types whose summaries read naturally as "recent news" in a prompt,
# vs. purely internal engagement signals (email opens/clicks) that don't.
_NEWS_LIKE_SIGNAL_TYPES = {
    "FUNDING_EVENT", "NEWS_EVENT", "JOB_CHANGE", "PROMOTION", "TECH_STACK_CHANGE",
}


def build_prospect_context(
    prospect: Prospect,
    memories: list[ConversationMemory] | None = None,
    buying_signals: list[BuyingSignal] | None = None,
) -> dict:
    """Returns a dict of named context fields for generate_outreach_message's
    `context` parameter. Every value is plain text (or None) - ai.py is
    responsible for escaping/wrapping each one before it reaches a prompt."""
    memories = memories or []
    buying_signals = buying_signals or []

    hiring_signals = [s.summary for s in buying_signals if s.signal_type.value == "COMPANY_HIRING"]
    recent_news = [s.summary for s in buying_signals if s.signal_type.value in _NEWS_LIKE_SIGNAL_TYPES]

    return {
        "job_title": prospect.job_title,
        "role": prospect.job_title,
        "industry": prospect.industry,
        "company_description": prospect.company_description,
        "company_website": prospect.company_website,
        "tech_stack": ", ".join(prospect.tech_stack) if prospect.tech_stack else None,
        "funding_info": _format_funding(prospect),
        "recent_news": " | ".join(recent_news) if recent_news else None,
        "hiring_signals": " | ".join(hiring_signals) if hiring_signals else None,
        "conversation_memory": " | ".join(m.content for m in memories) if memories else None,
        "buying_signals": " | ".join(s.summary for s in buying_signals) if buying_signals else None,
        "qualification_summary": _format_qualification(prospect),
    }


def _format_funding(prospect: Prospect) -> str | None:
    if not prospect.funding_stage and not prospect.funding_amount:
        return None
    parts = []
    if prospect.funding_stage:
        parts.append(prospect.funding_stage.replace("_", " ").title())
    if prospect.funding_amount:
        parts.append(f"${prospect.funding_amount:,.0f} raised")
    return " - ".join(parts)


def _format_qualification(prospect: Prospect) -> str | None:
    if prospect.qualification_level is None:
        return None
    parts = [f"{prospect.qualification_level.value} priority lead"]
    if prospect.qualification_score is not None:
        parts.append(f"score {prospect.qualification_score:.0f}/100")
    if prospect.qualification_reason:
        parts.append(prospect.qualification_reason)
    return " - ".join(parts)


class PersonalizationService:
    """Sprint 5, item 1: the single entry point every outbound channel goes
    through to generate a message - LinkedIn request/follow-up, Email 1/2,
    breakup email, and the legacy follow-up/nudge tasks all call
    generate_message() rather than calling generate_outreach_message()
    directly with just a name and company. Centralizing the DB fetch
    (active conversation memory + active buying signals) here means every
    call site gets the same rich, real context with no risk of a channel
    quietly reverting to a minimal prompt."""

    @staticmethod
    async def build_context(db: AsyncSession, prospect: Prospect) -> dict:
        from app.services.memory.service import ConversationMemoryService

        memories = await ConversationMemoryService.get_active_context(db, prospect.tenant_id, prospect.id)
        signals_res = await db.execute(
            select(BuyingSignal).where(
                BuyingSignal.tenant_id == prospect.tenant_id,
                BuyingSignal.prospect_id == prospect.id,
                BuyingSignal.is_active == True,
            )
        )
        buying_signals = list(signals_res.scalars().all())
        return build_prospect_context(prospect, memories=memories, buying_signals=buying_signals)

    @staticmethod
    async def generate_message(db: AsyncSession, prospect: Prospect, prompt_type: str) -> str:
        from app.services.ai import generate_outreach_message

        context = await PersonalizationService.build_context(db, prospect)
        return await generate_outreach_message(
            prospect_name=prospect.first_name,
            company=prospect.company_name or "",
            prompt_type=prompt_type,
            context=context,
        )
