"""Extract a global SRS profile (locale/region/timezone/currency/formats/rules)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", flags=re.MULTILINE)


def _extract_json_object(text: str) -> dict[str, Any]:
    """
    Best-effort: extract a single top-level JSON object from model output.
    Some providers prepend/append extra text.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty model output")
    try:
        val = json.loads(text)
        if isinstance(val, dict):
            return val
    except Exception:
        pass
    m = _JSON_OBJECT_RE.search(text)
    if not m:
        raise ValueError("No JSON object found in model output")
    val = json.loads(m.group(0))
    if not isinstance(val, dict):
        raise ValueError("Extracted JSON is not an object")
    return val


def _is_effectively_empty(p: "SRSGlobalProfile") -> bool:
    """True if profile has no useful signals at all."""
    if p.locales or p.countries or p.regions:
        return False
    if p.timezone or p.currency:
        return False
    for k in [
        "formats",
        "privacy_rules",
        "business_rules",
        "datetime_policy",
        "id_conventions",
        "volume_hints",
        "distributions",
        "tenancy",
    ]:
        if getattr(p, k, None):
            return False
    return True


def _has_obvious_global_signals(srs_text: str) -> bool:
    """
    Lightweight detection of 'obvious' global signals.
    Used only to decide whether to retry the AI call if we got an empty/invalid profile.
    """
    t = (srs_text or "").strip()
    if not t:
        return False
    tl = t.lower()
    # Currency symbols/codes (common)
    if any(sym in t for sym in ["£", "€", "$", "₹", "¥"]):
        return True
    if re.search(r"\b(USD|GBP|EUR|INR|AUD|CAD|SGD|JPY|CNY)\b", t, flags=re.IGNORECASE):
        return True
    # Explicit timezone-like strings
    if re.search(r"\b[A-Za-z_]+/[A-Za-z_]+\b", t):
        return True
    # Country/region words
    if any(w in tl for w in ["country", "timezone", "currency", "region", "based in", "operating in"]):
        return True
    return False


def _extract_operating_country(srs_text: str) -> str | None:
    """
    If the SRS explicitly states "operating in <Country>", treat that as the primary country.
    This helps resolve conflicts when other lines mention different regions (e.g. currency vs address examples).
    """
    t = (srs_text or "").strip()
    if not t:
        return None
    # Example: "operating in Russia."
    m = re.search(r"\boperating\s+in\s+([A-Za-z][A-Za-z\s\-]+?)(?:[.\n,]|$)", t, flags=re.IGNORECASE)
    if not m:
        return None
    country = (m.group(1) or "").strip()
    # Avoid capturing trailing generic words
    country = re.sub(r"\b(the|a|an)\b", "", country, flags=re.IGNORECASE).strip()
    return country or None


class SRSGlobalProfile(BaseModel):
    """High-level constraints that apply across the whole dataset."""

    locales: list[str] = Field(default_factory=list, description="BCP-47-ish locales like en_IN, en_GB, hi_IN")
    countries: list[str] = Field(default_factory=list, description="Countries mentioned in SRS, e.g. India")
    regions: list[str] = Field(default_factory=list, description="Regions/states/cities mentioned, optional")
    timezone: str | None = Field(default=None, description="IANA timezone like Asia/Kolkata")
    currency: str | None = Field(default=None, description="ISO-4217 currency code like INR, USD")
    formats: dict[str, str] = Field(default_factory=dict, description="Format rules, e.g. phone/postal_code")
    privacy_rules: dict[str, Any] = Field(default_factory=dict, description="PII and masking constraints")
    business_rules: dict[str, Any] = Field(default_factory=dict, description="Global business rules/distributions")
    datetime_policy: dict[str, Any] = Field(
        default_factory=dict,
        description="Global date/time realism (ranges, business hours, precision)",
    )
    id_conventions: dict[str, Any] = Field(
        default_factory=dict,
        description="ID/identifier patterns (uuid vs int, prefixes, slug rules)",
    )
    volume_hints: dict[str, Any] = Field(
        default_factory=dict,
        description="Scale hints (approx row counts, ratios like orders_per_customer)",
    )
    distributions: dict[str, Any] = Field(
        default_factory=dict,
        description="Global value distributions (state percentages, rarity, skew)",
    )
    tenancy: dict[str, Any] = Field(
        default_factory=dict,
        description="Multi-tenant boundaries and default scoping (tenant/org isolation)",
    )


def _sanitize_profile(p: SRSGlobalProfile) -> SRSGlobalProfile:
    """Lightweight cleanup so downstream prompts don’t get nonsense."""
    # currency: 3-letter uppercase
    if p.currency is not None:
        cur = p.currency.strip().upper()
        p.currency = cur if re.fullmatch(r"[A-Z]{3}", cur or "") else None
    # timezone: basic IANA-ish check
    if p.timezone:
        tz = p.timezone.strip()
        p.timezone = tz if re.fullmatch(r"[A-Za-z_]+/[A-Za-z_]+", tz or "") else None
    # locales: keep simple pattern
    cleaned_locales = []
    for loc in p.locales:
        s = (loc or "").strip()
        if re.fullmatch(r"[a-z]{2}(?:_[A-Z]{2})?", s):
            cleaned_locales.append(s)
    p.locales = cleaned_locales
    # countries/regions: strip empties
    p.countries = [c.strip() for c in p.countries if (c or "").strip()]
    p.regions = [r.strip() for r in p.regions if (r or "").strip()]
    # Ensure dict-ish fields are dicts
    for k in ["formats", "privacy_rules", "business_rules", "datetime_policy", "id_conventions", "volume_hints", "distributions", "tenancy"]:
        v = getattr(p, k, None)
        if not isinstance(v, dict):
            setattr(p, k, {})
    return p


def _heuristic_profile_from_text(srs_text: str) -> SRSGlobalProfile:
    """
    Deterministic heuristic layer to catch common global constraints when AI misses them.
    Currently focuses on strong signals (country/currency/timezone).
    """
    t = (srs_text or "").lower()
    p = SRSGlobalProfile()
    if "england" in t or "united kingdom" in t or re.search(r"\buk\b", t) or "gbp" in t or "£" in srs_text:
        p.countries = ["United Kingdom"]
        p.locales = ["en_GB"]
        p.timezone = "Europe/London"
        p.currency = "GBP"
        p.formats = {"currency_display": "GBP"}
    if "india" in t or "inr" in t or "gst" in t or "aadhaar" in t or "pan " in t:
        p.countries = ["India"]
        p.locales = ["en_IN"]
        p.timezone = "Asia/Kolkata"
        p.currency = "INR"
        p.formats = {"currency_display": "INR", "tax": "GST"}
    return p


def extract_srs_global_profile(
    srs_text: str,
    *,
    llm_provider: str = "openai",
    model_id: str = "gpt-4.1-mini",
) -> SRSGlobalProfile:
    """
    Use AI to extract global constraints from SRS text as strict JSON.
    Returns a sanitized SRSGlobalProfile. On failure, returns an empty profile.
    """
    srs_text = (srs_text or "").strip()
    if not srs_text:
        return SRSGlobalProfile()

    try:
        from agno.agent import Agent
    except ImportError:
        logger.warning("Agno not installed; skipping SRS global profile extraction.")
        return SRSGlobalProfile()

    provider = (llm_provider or "ollama").strip().lower()
    if provider == "ollama":
        try:
            from agno.models.ollama import Ollama
        except ImportError:
            logger.warning("Agno Ollama support not available; skipping SRS global profile extraction.")
            return SRSGlobalProfile()
        model = Ollama(id=model_id or "qwen2:7b")
    else:
        try:
            from agno.models.openai import OpenAIResponses
        except ImportError:
            logger.warning("Agno OpenAI support not available; skipping SRS global profile extraction.")
            return SRSGlobalProfile()
        model = OpenAIResponses(id=model_id, temperature=0)

    system = (
        "You are a senior data engineer.\n"
        "Extract only GLOBAL constraints from the SRS that should influence synthetic data realism.\n"
        "Return ONLY valid JSON (no markdown, no extra text).\n"
        "JSON keys allowed: locales, countries, regions, timezone, currency, formats, privacy_rules, business_rules, "
        "datetime_policy, id_conventions, volume_hints, distributions, tenancy.\n"
        "All keys are optional; omit if unknown.\n"
        "Be conservative: include only what is clearly stated.\n"
        "Do not invent facts that are not implied by explicit text.\n"
        "If the SRS explicitly mentions a currency symbol/code (e.g. 'GBP' or '£'), include currency='GBP'.\n"
        "If the SRS explicitly mentions a country/region (e.g. 'England', 'India'), include it in countries.\n"
        "If the SRS explicitly mentions a timezone (e.g. 'Europe/London'), include it.\n"
        "If the SRS explicitly states a country/region/currency/timezone, include it.\n"
    )
    # IMPORTANT: Do NOT use output_schema with OpenAI here.
    # Some OpenAI Responses endpoints reject the generated JSON schema for complex Pydantic models.
    # We'll request plain JSON and validate locally.
    def run_once(instructions: str) -> tuple[SRSGlobalProfile, str]:
        agent = Agent(model=model, markdown=False, instructions=instructions)
        resp = agent.run(srs_text)
        content = resp.content
        raw_preview: str
        try:
            raw_preview = (content if isinstance(content, str) else json.dumps(content, default=str))  # type: ignore[arg-type]
        except Exception:
            raw_preview = "<unavailable>"
        try:
            if isinstance(content, SRSGlobalProfile):
                return _sanitize_profile(content), raw_preview
            if isinstance(content, dict):
                return _sanitize_profile(SRSGlobalProfile.model_validate(content)), raw_preview
            if isinstance(content, str):
                return _sanitize_profile(SRSGlobalProfile.model_validate(_extract_json_object(content))), raw_preview
        except Exception:
            pass
        return SRSGlobalProfile(), raw_preview

    ai_p, raw1 = run_once(system)

    # Retry once if we got an empty/invalid profile despite obvious signals in SRS.
    if _is_effectively_empty(ai_p) and _has_obvious_global_signals(srs_text):
        system_retry = system + (
            "\nRETRY:\n"
            "- Your previous output was empty or invalid.\n"
            "- If SRS contains explicit signals like 'GBP', '£', 'England', 'UK', you MUST include them.\n"
            "- Output MUST be a single JSON object. No code fences.\n"
        )
        ai_p2, raw2 = run_once(system_retry)
        if not _is_effectively_empty(ai_p2):
            ai_p = ai_p2
        else:
            # Preserve debuggability without breaking pipeline
            p1 = (raw1 or "").strip().replace("\n", " ")[:500]
            p2 = (raw2 or "").strip().replace("\n", " ")[:500]
            logger.warning("SRS global profile remained empty after retry. preview1=%s preview2=%s", p1, p2)

    # Resolve conflicting region signals:
    # If SRS explicitly says "operating in <country>", treat that as the primary country.
    primary_country = _extract_operating_country(srs_text)
    if primary_country:
        # Keep only the primary country to avoid confusing downstream generation.
        ai_p.countries = [primary_country]
        # If formats include country-specific adjectives that contradict primary country, soften them.
        # (We keep this lightweight; per-table prompts should rely on primary_country.)
        for k, v in list((ai_p.formats or {}).items()):
            if isinstance(v, str):
                # Replace explicit UK references if primary is not UK
                if primary_country.lower() != "united kingdom":
                    v2 = re.sub(r"\buk\b", primary_country, v, flags=re.IGNORECASE)
                    v2 = re.sub(r"\bunited\s+kingdom\b", primary_country, v2, flags=re.IGNORECASE)
                    v2 = re.sub(r"\bengland\b", primary_country, v2, flags=re.IGNORECASE)
                    ai_p.formats[k] = v2

    # Merge heuristic hints if AI missed strong signals
    heur = _heuristic_profile_from_text(srs_text)
    if heur.currency and not ai_p.currency:
        ai_p.currency = heur.currency
    if heur.timezone and not ai_p.timezone:
        ai_p.timezone = heur.timezone
    if heur.locales and not ai_p.locales:
        ai_p.locales = heur.locales
    if heur.countries and not ai_p.countries:
        ai_p.countries = heur.countries
    if heur.regions and not ai_p.regions:
        ai_p.regions = heur.regions

    return ai_p

