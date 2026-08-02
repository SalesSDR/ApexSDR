"""Sprint 4, item 3: unit coverage for build_prospect_context, which
assembles the rich personalization fields generate_outreach_message's
`context` parameter consumes."""
from app.models.schemas import BuyingSignal, ConversationMemory, MemoryType, Prospect, SignalStrength, SignalType
from app.services.personalization import build_prospect_context


def _prospect(**overrides) -> Prospect:
    defaults = dict(tenant_id="t1", first_name="Ada", last_name="Lovelace", linkedin_url="https://linkedin.com/in/ada")
    defaults.update(overrides)
    return Prospect(**defaults)


def test_context_surfaces_enrichment_fields():
    prospect = _prospect(
        job_title="VP of Engineering",
        industry="Fintech",
        company_description="Builds payment infrastructure.",
        company_website="https://acme.io",
        tech_stack=["Python", "Kubernetes"],
        funding_stage="SERIES_B",
        funding_amount=25_000_000,
    )
    context = build_prospect_context(prospect)
    assert context["job_title"] == "VP of Engineering"
    assert context["role"] == "VP of Engineering"
    assert context["industry"] == "Fintech"
    assert context["company_description"] == "Builds payment infrastructure."
    assert context["company_website"] == "https://acme.io"
    assert context["tech_stack"] == "Python, Kubernetes"
    assert "Series B" in context["funding_info"]
    assert "$25,000,000" in context["funding_info"]


def test_context_is_all_none_for_a_bare_prospect():
    context = build_prospect_context(_prospect())
    assert context["job_title"] is None
    assert context["tech_stack"] is None
    assert context["funding_info"] is None
    assert context["recent_news"] is None
    assert context["hiring_signals"] is None
    assert context["conversation_memory"] is None
    assert context["buying_signals"] is None


def test_context_includes_conversation_memory_content():
    memories = [
        ConversationMemory(
            tenant_id="t1", prospect_id="p1", memory_type=MemoryType.OBJECTION,
            content="Said pricing was a concern.", source="EMAIL_WEBHOOK",
        ),
        ConversationMemory(
            tenant_id="t1", prospect_id="p1", memory_type=MemoryType.PREFERENCE,
            content="Prefers async communication.", source="SYSTEM",
        ),
    ]
    context = build_prospect_context(_prospect(), memories=memories)
    assert "Said pricing was a concern." in context["conversation_memory"]
    assert "Prefers async communication." in context["conversation_memory"]


def test_context_separates_hiring_and_news_signals_from_generic_buying_signals():
    signals = [
        BuyingSignal(
            tenant_id="t1", prospect_id="p1", signal_type=SignalType.COMPANY_HIRING,
            signal_source="test", signal_strength=SignalStrength.HIGH, summary="Hiring 10 engineers",
        ),
        BuyingSignal(
            tenant_id="t1", prospect_id="p1", signal_type=SignalType.FUNDING_EVENT,
            signal_source="test", signal_strength=SignalStrength.HIGH, summary="Raised a new round",
        ),
        BuyingSignal(
            tenant_id="t1", prospect_id="p1", signal_type=SignalType.EMAIL_OPEN,
            signal_source="test", signal_strength=SignalStrength.LOW, summary="Opened outreach email",
        ),
    ]
    context = build_prospect_context(_prospect(), buying_signals=signals)
    assert "Hiring 10 engineers" in context["hiring_signals"]
    assert "Raised a new round" in context["recent_news"]
    # The generic buying_signals field aggregates every signal regardless of type.
    assert "Opened outreach email" in context["buying_signals"]
    assert "Hiring 10 engineers" in context["buying_signals"]
