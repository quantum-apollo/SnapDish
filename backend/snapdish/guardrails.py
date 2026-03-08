"""
SnapDish Guardrails — code-level enforcement, server-side only.

This module is the single source of truth for what the system is and is not
allowed to do. Guardrail rules are loaded from the database at startup (and
cached in memory), so operators can update rules without a code deploy.
Client requests CANNOT modify, disable, or inspect these rules.

Design:
  1. GuardrailEngine.check_input()    — called before any model API call
  2. GuardrailEngine.check_output()   — called after model returns text
  3. GuardrailEngine.check_search_query() — called before any web search
  4. All violations raise GuardrailViolation (HTTP 400 to client, logged)
  5. Rules are seeded once into the DB; DB rows are read-only from the API.

Food-domain enforcement:
  - Input text is checked against a regex bank of non-food topics; blocked immediately.
  - Web search queries are additionally checked — no free-text passes through.
  - Output text is scanned for off-topic disclosure (e.g. if model hallucinates
    outside its domain).

Secrets / sensitive data:
  - Guardrail rules are stored in `guardrail_rules` DB table with `enabled` flag.
  - The seed list below is the authoritative default; DB overrides at runtime.
  - No rule text is ever returned to the client.
"""

from __future__ import annotations

import re
import threading
import time
from typing import TYPE_CHECKING

from .config import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Exception raised on violation
# ---------------------------------------------------------------------------


class GuardrailViolation(Exception):
    """Raised when a request or response violates a guardrail rule."""

    def __init__(self, rule_name: str, message: str) -> None:
        self.rule_name = rule_name
        self.message = message
        super().__init__(f"[{rule_name}] {message}")


# ---------------------------------------------------------------------------
# Seed rules — defaults seeded into DB on first startup
# Organised as (name, scope, pattern, description)
#   scope: "input" | "output" | "search"
# ---------------------------------------------------------------------------

_SEED_RULES: list[tuple[str, str, str, str]] = [
    # ── INPUT guardrails ────────────────────────────────────────────────────
    (
        "block_political",
        "input",
        r"\b(politics|democrat|republican|election|vote|congress|senate|president|prime.?minister|parliament|manifesto|political.?party)\b",
        "Block political topics — food-only app",
    ),
    (
        "block_financial",
        "input",
        r"\b(stock.?market|crypto|bitcoin|invest|forex|trading|shares|portfolio|hedge.?fund|ipo)\b",
        "Block financial advice requests",
    ),
    (
        "block_medical_treatment",
        "input",
        r"\b(diagnose|prescribe|dosage|medication|drug|pill|antidepressant|chemotherapy|insulin.?dose|surgery|treat.?my)\b",
        "Block medical treatment requests (dietary notes allowed; prescriptions blocked)",
    ),
    (
        "block_legal",
        "input",
        r"\b(legal.?advice|sue|lawsuit|attorney|lawyer|court|litigation|contract.?law)\b",
        "Block legal advice",
    ),
    (
        "block_weapons",
        "input",
        r"\b(weapon|gun|firearm|bomb|explosive|knife.?fight|how.?to.?kill|violence|murder)\b",
        "Block weapons and violence",
    ),
    (
        "block_adult",
        "input",
        r"\b(pornography|sex.?act|nude|erotic|xxx|adult.?content|sexual.?explicit)\b",
        "Block adult content",
    ),
    (
        "block_personal_data",
        "input",
        r"\b(social.?security|ssn|credit.?card.?number|passport.?number|bank.?account.?number)\b",
        "Block requests containing sensitive personal identifiers",
    ),
    (
        "block_hacking",
        "input",
        r"\b(sql.?inject|xss|csrf|buffer.?overflow|exploit|zero.?day|malware|ransomware|hack.?into)\b",
        "Block hacking and exploitation requests",
    ),
    # ── SEARCH guardrails (extra strict — applies to web search queries only)
    (
        "search_food_only",
        "search",
        r"^(?!.*(recipe|ingredient|food|meal|dish|restaurant|grocery|nutrition|cuisine|cook|bake|fry|boil|spice|sauce|vegan|gluten|halal|kosher|allergy|substitute|alternative|where.?to.?buy|near.?me|supermarket|farm|produce|organic|diet|calorie|protein|carb|fat|fiber|flavor|taste|chef|kitchen|pantry|herb|fruit|vegetable|meat|fish|seafood|dairy|egg|nuts|seed|grain|bread|pasta|rice|salad|soup|stew|dessert|snack|beverage|drink|juice|tea|coffee|beer|wine|oil|vinegar|seasoning|marinade|portion|serving|meal.?plan))).+",
        "Reject search queries that are not clearly food-related",
    ),
    # ── OUTPUT guardrails ─────────────────────────────────────────────────--
    (
        "output_no_medical_prescriptions",
        "output",
        r"\b(take \d+ mg|prescribed|your dosage|medical prescription|consult a doctor for dosage)\b",
        "Flag model outputs that include medication dosage advice",
    ),
    (
        "output_no_harmful_instructions",
        "output",
        r"\b(how to make a bomb|step.?by.?step.?to.?kill|instructions.?for.?(violence|weapon))\b",
        "Flag harmful instruction outputs",
    ),
]

# ---------------------------------------------------------------------------
# In-memory rule store (refreshed from DB every 5 minutes)
# ---------------------------------------------------------------------------

_RULES_LOCK = threading.Lock()
_rules_cache: list[dict] = []
_rules_loaded_at: float = 0.0
_RULES_TTL_SECONDS = 300  # 5 minutes


def _compile_rules(raw_rules: list[dict]) -> list[dict]:
    compiled = []
    for r in raw_rules:
        if not r.get("enabled", True):
            continue
        try:
            compiled.append(
                {
                    "name": r["name"],
                    "scope": r["scope"],
                    "pattern": re.compile(r["pattern"], re.IGNORECASE | re.DOTALL),
                    "description": r.get("description", ""),
                }
            )
        except re.error as exc:
            logger.warning("guardrail_pattern_invalid", extra={"name": r.get("name"), "error": str(exc)})
    return compiled


def _load_rules_from_db() -> list[dict]:
    """Load rules from the guardrail_rules table. Falls back to seed rules on error."""
    try:
        from .db import get_db_session, is_db_available
        from .models import GuardrailRule

        if not is_db_available():
            return _seed_as_dicts()

        with get_db_session() as session:
            rows = session.query(GuardrailRule).filter_by(enabled=True).all()
            if not rows:
                return _seed_as_dicts()
            return [
                {
                    "name": row.name,
                    "scope": row.scope,
                    "pattern": row.pattern,
                    "enabled": row.enabled,
                    "description": row.description,
                }
                for row in rows
            ]
    except Exception as exc:
        logger.warning("guardrail_rules_load_failed", extra={"error": str(exc)})
        return _seed_as_dicts()


def _seed_as_dicts() -> list[dict]:
    return [
        {"name": name, "scope": scope, "pattern": pattern, "enabled": True, "description": desc}
        for name, scope, pattern, desc in _SEED_RULES
    ]


def _get_compiled_rules() -> list[dict]:
    global _rules_cache, _rules_loaded_at
    now = time.monotonic()
    with _RULES_LOCK:
        if now - _rules_loaded_at > _RULES_TTL_SECONDS or not _rules_cache:
            raw = _load_rules_from_db()
            _rules_cache = _compile_rules(raw)
            _rules_loaded_at = now
    return _rules_cache


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def seed_guardrail_rules() -> None:
    """
    Insert default rules into guardrail_rules table if the table is empty.
    Called once at application startup. Safe to call multiple times (idempotent).
    """
    try:
        from .db import get_db_session, is_db_available
        from .models import GuardrailRule

        if not is_db_available():
            logger.info("guardrail_seed_skipped", extra={"reason": "DB not available"})
            return

        with get_db_session() as session:
            existing = session.query(GuardrailRule).count()
            if existing > 0:
                logger.info("guardrail_seed_skipped", extra={"reason": "rules already seeded", "count": existing})
                return
            for name, scope, pattern, desc in _SEED_RULES:
                session.add(
                    GuardrailRule(
                        name=name,
                        scope=scope,
                        pattern=pattern,
                        description=desc,
                        enabled=True,
                    )
                )
            session.commit()
            logger.info("guardrail_seed_ok", extra={"rules": len(_SEED_RULES)})
    except Exception as exc:
        logger.warning("guardrail_seed_failed", extra={"error": str(exc)})


def _check_with_openai_moderation(text: str) -> None:
    """
    Primary guardrail layer: OpenAI omni-moderation-latest model.

    Flags hate speech, violence, self-harm, sexual content, harassment, and
    other harmful categories as defined by the OpenAI Moderation API.
    Falls through silently if the Moderation API is unavailable — the regex
    rules in check_input() still run as a backup layer.

    OpenAI docs: https://platform.openai.com/docs/api-reference/moderations
    """
    try:
        from .openai_client import get_client
        result = get_client().moderations.create(
            input=text,
            model="omni-moderation-latest",
        )
        for output in result.results:
            if output.flagged:
                # Identify which category triggered the flag for logging only
                cats = output.categories.model_dump() if hasattr(output.categories, "model_dump") else vars(output.categories)
                flagged_cats = [k for k, v in cats.items() if v]
                logger.warning(
                    "guardrail_openai_moderation_flagged",
                    extra={"text_preview": text[:80], "categories": flagged_cats},
                )
                raise GuardrailViolation(
                    "openai_moderation",
                    "I can only help with food and cooking topics. "
                    "Please ask me something food-related!",
                )
    except GuardrailViolation:
        raise  # re-raise our own violation, do not swallow
    except Exception as exc:
        # Moderation API temporarily unavailable — fall through to regex checks
        logger.warning("openai_moderation_unavailable", extra={"error": str(exc)})


def check_input(text: str) -> None:
    """
    Validate user input text.

    Layers (fastest to slowest):
      1. OpenAI omni-moderation-latest — semantic harmful-content detection
      2. Regex rules loaded from the guardrail_rules DB table — domain enforcement

    Raises GuardrailViolation if any layer matches.
    Never leaks rule details to the caller.
    """
    if not text or not text.strip():
        return

    # Layer 1: OpenAI Moderation API (primary, semantic)
    _check_with_openai_moderation(text)

    # Layer 2: Regex rules from DB (secondary, food-domain enforcement)
    rules = _get_compiled_rules()
    for rule in rules:
        if rule["scope"] != "input":
            continue
        if rule["pattern"].search(text):
            logger.warning(
                "guardrail_input_blocked",
                extra={"rule": rule["name"], "text_preview": text[:80]},
            )
            raise GuardrailViolation(
                rule["name"],
                "I can only help with food, cooking, and nutrition topics. "
                "Please ask me something food-related!",
            )


def check_output(text: str, context: str = "") -> str:
    """
    Scan model output text for policy violations.
    If a violation is found, the output is replaced with a safe fallback.
    Returns (possibly replaced) safe text.
    """
    if not text:
        return text
    rules = _get_compiled_rules()
    for rule in rules:
        if rule["scope"] != "output":
            continue
        if rule["pattern"].search(text):
            logger.warning(
                "guardrail_output_blocked",
                extra={"rule": rule["name"], "context": context, "text_preview": text[:80]},
            )
            return (
                "I'm here to help with food and cooking! "
                "For medical or safety questions, please consult a qualified professional."
            )
    return text


def check_search_query(query: str) -> None:
    """
    Validate a web search query before it is submitted.
    Raises GuardrailViolation for non-food queries.

    IMPORTANT: This is checked in Python code — the model cannot bypass it
    by generating a search query indirectly.
    """
    if not query or not query.strip():
        raise GuardrailViolation("empty_search", "Search query must not be empty.")

    q = query.strip().lower()

    # Positive allowlist: must contain at least one food-domain keyword
    _FOOD_KEYWORDS = re.compile(
        r"\b(recipe|ingredient|food|meal|dish|restaurant|grocery|nutrition|cuisine|"
        r"cook|bake|fry|boil|grill|steam|saute|roast|spice|sauce|vegan|gluten|halal|"
        r"kosher|allergy|allerg|substitute|alternative|buy|supermarket|farm|produce|"
        r"organic|diet|calorie|protein|carb|fat|fiber|flavor|taste|chef|kitchen|"
        r"pantry|herb|fruit|vegetable|meat|fish|seafood|dairy|egg|nuts|grain|bread|"
        r"pasta|rice|salad|soup|stew|dessert|snack|beverage|drink|juice|tea|coffee|"
        r"oil|vinegar|seasoning|marinade|portion|serving|meal.plan|where.to.find|"
        r"near.me|open.now|food.store|health.food|whole.food|farmers.market)\b",
        re.IGNORECASE,
    )
    if not _FOOD_KEYWORDS.search(q):
        logger.warning("guardrail_search_blocked", extra={"query": query[:80], "reason": "not_food_related"})
        raise GuardrailViolation(
            "search_food_only",
            "Web search is restricted to food, cooking, and nutrition topics. "
            "Please ask me something food-related!",
        )

    # Denylist patterns also checked for search
    rules = _get_compiled_rules()
    for rule in rules:
        if rule["scope"] != "search":
            continue
        if rule["pattern"].search(q):
            logger.warning("guardrail_search_blocked", extra={"query": query[:80], "rule": rule["name"]})
            raise GuardrailViolation(
                rule["name"],
                "Web search is restricted to food, cooking, and nutrition topics.",
            )
