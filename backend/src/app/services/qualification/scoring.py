"""Sprint 4, item 1/2: configurable, weighted lead-qualification scoring -
replaces the old binary "has an email or phone number" gate. Every factor
is a pure function of (Prospect, tenant ICP profile[, active BuyingSignal
rows]) returning a 0-100 sub-score; the final score is their weighted
average, and the resulting HOT/HIGH/MEDIUM/LOW level is both the
"qualification_level" (item 1) and the lead-priority tier (item 2) - one
number drives both.

Every factor degrades gracefully when its underlying data (enrichment,
ICP configuration) is missing - a partially-enriched prospect gets a
plausible neutral score for the factors it lacks data for, rather than a
crash or an automatic zero.
"""
from dataclasses import dataclass, field

from app.models.schemas import (
    BuyingSignal,
    Prospect,
    QualificationLevel,
    SignalStrength,
    SignalType,
    WorkspaceSetting,
)

FACTOR_NAMES = [
    "icp_fit", "company_size", "industry", "job_title", "seniority",
    "buying_signals", "email_quality", "company_website", "tech_stack",
    "funding", "hiring", "decision_maker_likelihood",
]

# Equal weighting by default - a tenant with an opinion about which factors
# matter most overrides via WorkspaceSetting.qualification_config["weights"].
DEFAULT_WEIGHTS: dict[str, float] = {name: 1.0 / len(FACTOR_NAMES) for name in FACTOR_NAMES}

# Below "medium" is LOW (disqualified); "medium" and up is qualified, with
# HOT/HIGH/MEDIUM as the priority tiers among qualified leads.
DEFAULT_THRESHOLDS: dict[str, float] = {"hot": 75.0, "high": 55.0, "medium": 35.0}

_FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com",
    "icloud.com", "live.com", "protonmail.com", "mail.com",
}

_SENIORITY_TABLE = [
    (("chief", "ceo", "cto", "cfo", "coo", "cmo", "cro", "founder", "co-founder", "owner", "president"), 100),
    (("vp", "vice president", "svp", "evp"), 90),
    (("director", "head of"), 75),
    (("manager", "lead"), 55),
]

_FUNDING_STAGE_SCORES = {
    "PUBLIC": 100, "IPO": 100,
    "SERIES_D": 90, "SERIES_C": 88, "SERIES_C_PLUS": 90,
    "SERIES_B": 80,
    "SERIES_A": 65,
    "SEED": 50,
    "PRE_SEED": 42,
    "BOOTSTRAPPED": 40,
}


@dataclass
class ScoreBreakdown:
    score: float
    level: QualificationLevel
    reason: str
    factor_scores: dict[str, float] = field(default_factory=dict)


def _icp_profile_of(workspace_setting: WorkspaceSetting | None) -> dict:
    return (getattr(workspace_setting, "icp_profile", None) or {}) if workspace_setting else {}


def _qualification_config_of(workspace_setting: WorkspaceSetting | None) -> dict:
    return (getattr(workspace_setting, "qualification_config", None) or {}) if workspace_setting else {}


def _matches_any(value: str | None, candidates: list[str]) -> bool:
    if not value or not candidates:
        return False
    value_lower = value.lower()
    return any(c.lower() in value_lower for c in candidates if c)


def _score_icp_fit(prospect: Prospect, icp: dict) -> float:
    """Composite match across every ICP criterion the tenant has actually
    configured - the denominator is how many criteria are configured, not
    a fixed 3, so a tenant using only one criterion isn't penalized for
    the others being unset."""
    checks = []
    target_industries = icp.get("target_industries") or []
    if target_industries:
        checks.append(bool(prospect.industry and prospect.industry.lower() in [i.lower() for i in target_industries]))
    target_titles = icp.get("target_job_titles") or []
    if target_titles:
        checks.append(_matches_any(prospect.job_title, target_titles))
    size_min, size_max = icp.get("company_size_min"), icp.get("company_size_max")
    if size_min is not None or size_max is not None:
        if prospect.employee_count is None:
            checks.append(False)
        else:
            ok = True
            if size_min is not None:
                ok = ok and prospect.employee_count >= size_min
            if size_max is not None:
                ok = ok and prospect.employee_count <= size_max
            checks.append(ok)
    target_tech = icp.get("target_tech_stack") or []
    if target_tech:
        stack = {t.lower() for t in (prospect.tech_stack or [])}
        checks.append(bool(stack & {t.lower() for t in target_tech}))

    if not checks:
        return 50.0  # no ICP profile configured - neutral, not penalized
    return round(100.0 * sum(checks) / len(checks), 2)


def _score_company_size(prospect: Prospect, icp: dict) -> float:
    size_min, size_max = icp.get("company_size_min"), icp.get("company_size_max")
    if prospect.employee_count is None:
        return 40.0
    if size_min is not None or size_max is not None:
        lo = size_min if size_min is not None else 0
        hi = size_max if size_max is not None else float("inf")
        if lo <= prospect.employee_count <= hi:
            return 100.0
        distance = min(abs(prospect.employee_count - lo), abs(prospect.employee_count - hi))
        return max(20.0, 80.0 - distance / 10.0)
    # No configured target range - a generic mid-market sweet spot.
    if 50 <= prospect.employee_count <= 1000:
        return 70.0
    if prospect.employee_count < 50:
        return 50.0
    return 60.0


def _score_industry(prospect: Prospect, icp: dict) -> float:
    target_industries = [i.lower() for i in (icp.get("target_industries") or [])]
    if target_industries:
        if not prospect.industry:
            return 30.0
        return 100.0 if prospect.industry.lower() in target_industries else 30.0
    return 60.0 if prospect.industry else 40.0


def _score_job_title(prospect: Prospect, icp: dict) -> float:
    target_titles = icp.get("target_job_titles") or []
    if target_titles:
        if not prospect.job_title:
            return 30.0
        return 100.0 if _matches_any(prospect.job_title, target_titles) else 30.0
    return 60.0 if prospect.job_title else 30.0


def _score_seniority(prospect: Prospect) -> float:
    if not prospect.job_title:
        return 30.0
    title_lower = prospect.job_title.lower()
    for keywords, score in _SENIORITY_TABLE:
        if any(k in title_lower for k in keywords):
            return float(score)
    return 40.0


def _score_buying_signals(signals: list[BuyingSignal]) -> float:
    if not signals:
        return 0.0
    points = 0.0
    for s in signals:
        if s.signal_strength in (SignalStrength.HIGH, SignalStrength.VERY_HIGH):
            points += 25.0
        elif s.signal_strength == SignalStrength.MEDIUM:
            points += 12.0
        else:
            points += 5.0
    return min(100.0, points)


def _score_email_quality(prospect: Prospect) -> float:
    if not prospect.email or "@" not in prospect.email:
        return 0.0
    domain = prospect.email.rsplit("@", 1)[-1].lower()
    return 50.0 if domain in _FREE_EMAIL_DOMAINS else 90.0


def _score_company_website(prospect: Prospect) -> float:
    return 80.0 if prospect.company_website else 20.0


def _score_tech_stack(prospect: Prospect, icp: dict) -> float:
    target_tech = [t.lower() for t in (icp.get("target_tech_stack") or [])]
    stack = [t.lower() for t in (prospect.tech_stack or [])]
    if target_tech:
        if not stack:
            return 20.0
        overlap = len(set(stack) & set(target_tech))
        return round(100.0 * overlap / len(target_tech), 2)
    return 60.0 if stack else 30.0


def _score_funding(prospect: Prospect) -> float:
    if not prospect.funding_stage:
        return 40.0
    base = _FUNDING_STAGE_SCORES.get(prospect.funding_stage.upper(), 45.0)
    if prospect.funding_amount and prospect.funding_amount >= 50_000_000:
        base = min(100.0, base + 5.0)
    return float(base)


def _score_hiring(signals: list[BuyingSignal]) -> float:
    return 100.0 if any(s.signal_type == SignalType.COMPANY_HIRING for s in signals) else 30.0


def _score_decision_maker_likelihood(prospect: Prospect) -> float:
    if not prospect.job_title:
        return 20.0
    title_lower = prospect.job_title.lower()
    if any(k in title_lower for k in ("founder", "co-founder", "owner", "chief", "ceo", "cto", "cfo", "coo", "cmo", "president")):
        return 100.0
    if any(k in title_lower for k in ("vp", "vice president", "director", "head of")):
        return 80.0
    if "manager" in title_lower:
        return 50.0
    return 20.0


def _level_for_score(score: float, thresholds: dict[str, float]) -> QualificationLevel:
    if score >= thresholds.get("hot", DEFAULT_THRESHOLDS["hot"]):
        return QualificationLevel.HOT
    if score >= thresholds.get("high", DEFAULT_THRESHOLDS["high"]):
        return QualificationLevel.HIGH
    if score >= thresholds.get("medium", DEFAULT_THRESHOLDS["medium"]):
        return QualificationLevel.MEDIUM
    return QualificationLevel.LOW


def score_prospect(
    prospect: Prospect,
    workspace_setting: WorkspaceSetting | None = None,
    buying_signals: list[BuyingSignal] | None = None,
) -> ScoreBreakdown:
    """Pure - no I/O. Callers fetch workspace_setting/buying_signals
    themselves (see decision/engine.py's decide_qualification)."""
    icp = _icp_profile_of(workspace_setting)
    qual_config = _qualification_config_of(workspace_setting)
    weights = {**DEFAULT_WEIGHTS, **(qual_config.get("weights") or {})}
    thresholds = {**DEFAULT_THRESHOLDS, **(qual_config.get("thresholds") or {})}
    signals = buying_signals or []

    factor_scores = {
        "icp_fit": _score_icp_fit(prospect, icp),
        "company_size": _score_company_size(prospect, icp),
        "industry": _score_industry(prospect, icp),
        "job_title": _score_job_title(prospect, icp),
        "seniority": _score_seniority(prospect),
        "buying_signals": _score_buying_signals(signals),
        "email_quality": _score_email_quality(prospect),
        "company_website": _score_company_website(prospect),
        "tech_stack": _score_tech_stack(prospect, icp),
        "funding": _score_funding(prospect),
        "hiring": _score_hiring(signals),
        "decision_maker_likelihood": _score_decision_maker_likelihood(prospect),
    }

    total_weight = sum(weights.get(f, 0.0) for f in FACTOR_NAMES) or 1.0
    weighted = sum(factor_scores[f] * weights.get(f, 0.0) for f in FACTOR_NAMES) / total_weight
    score = round(weighted, 2)
    level = _level_for_score(score, thresholds)

    ranked = sorted(factor_scores.items(), key=lambda kv: kv[1], reverse=True)
    strongest = ranked[:3]
    weakest = ranked[-2:]
    reason = (
        f"Score {score}/100 ({level.value}). "
        f"Strongest factors: {', '.join(f'{name} ({val:.0f})' for name, val in strongest)}. "
        f"Weakest factors: {', '.join(f'{name} ({val:.0f})' for name, val in weakest)}."
    )

    return ScoreBreakdown(score=score, level=level, reason=reason, factor_scores=factor_scores)


# Sprint 5, item 2 (Priority Queue): lower rank = processed first. Also
# doubles as the SQL CASE ordering key (see priority_rank_case()) so the
# Sequence Engine's due-prospect query and any Python-side sort agree on
# the exact same order.
PRIORITY_ORDER = [QualificationLevel.HOT, QualificationLevel.HIGH, QualificationLevel.MEDIUM, QualificationLevel.LOW]
PRIORITY_RANK: dict[QualificationLevel | None, int] = {level: i for i, level in enumerate(PRIORITY_ORDER)}
# Not-yet-scored prospects (NEW/ENRICHING, qualification_level is NULL)
# sort after every scored tier - they have no priority signal yet.
_UNSCORED_RANK = len(PRIORITY_ORDER)


def priority_rank(level: QualificationLevel | None) -> int:
    return PRIORITY_RANK.get(level, _UNSCORED_RANK)


def priority_rank_case():
    """A SQLAlchemy CASE expression ranking Prospect.qualification_level in
    priority order (HOT=0 ... LOW=3, NULL/unscored=4) - ORDER BY this,
    then created_at ascending, is "HOT first, oldest first within a tier"
    (Sprint 5, item 2)."""
    from sqlalchemy import case

    return case(
        *[(Prospect.qualification_level == level, rank) for level, rank in PRIORITY_RANK.items()],
        else_=_UNSCORED_RANK,
    )


# Sprint 5, item 2: prospects at a lower priority tier get a longer gap
# before their next sequence step - HOT leads move through the sequence
# faster, LOW-priority ones slower. Applied as a multiplier on the
# configured step delay (see workers/tasks.py's execute_sequence_step_task).
PRIORITY_DELAY_MULTIPLIER: dict[QualificationLevel | None, float] = {
    QualificationLevel.HOT: 0.75,
    QualificationLevel.HIGH: 1.0,
    QualificationLevel.MEDIUM: 1.5,
    QualificationLevel.LOW: 2.0,
}


def delay_multiplier_for(level: QualificationLevel | None) -> float:
    return PRIORITY_DELAY_MULTIPLIER.get(level, 1.0)


# Sprint 5, item 5 (Revenue Attribution): a simple, transparent estimate of
# deal value used to seed Prospect.estimated_deal_value when not already
# set (e.g. by a human/CRM). Company size is the only enrichment signal
# reliably available pre-close, so this is deliberately a single-factor
# heuristic rather than a second scoring model - it's a starting estimate,
# always overridable, not a prediction the rest of the system depends on.
_DEFAULT_DEAL_VALUE = 5000.0
_PER_EMPLOYEE_VALUE = 400.0
_MAX_EMPLOYEE_COUNT_FOR_ESTIMATE = 5000


def estimate_deal_value(prospect: Prospect) -> float:
    if prospect.employee_count:
        capped = min(prospect.employee_count, _MAX_EMPLOYEE_COUNT_FOR_ESTIMATE)
        return round(capped * _PER_EMPLOYEE_VALUE, 2)
    return _DEFAULT_DEAL_VALUE
