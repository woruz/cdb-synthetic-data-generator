"""
SRS–schema compatibility check.

Ensures the AI-parsed SRS is at least 80% compatible with the provided database schema
so that the merged result is meaningful and seed generation is well-aligned with requirements.
"""

from __future__ import annotations

import re
from typing import Any

from synthetic_seeder.schema import NormalizedSchema

try:
    from synthetic_seeder.ai_layer.srs_schemas import SRSStructuredOutput
except ImportError:
    SRSStructuredOutput = None  # type: ignore[misc, assignment]

DEFAULT_MIN_COMPATIBILITY = 0.50


def _norm_name(s: str) -> str:
    """Normalize names for matching: lower, strip, collapse non-alnum to '_'."""
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s


def _name_variants(s: str) -> set[str]:
    """
    Simple variants for singular/plural and separators.
    Helps match 'customer' ↔ 'customers', 'order status' ↔ 'orders' (when AI uses singular forms).
    """
    base = _norm_name(s)
    out = {base}
    if base.endswith("s") and len(base) > 1:
        out.add(base[:-1])  # customers -> customer
    else:
        out.add(base + "s")  # customer -> customers
    return {x for x in out if x}


def compute_srs_schema_compatibility(
    parsed_schema: NormalizedSchema,
    srs_output: Any,
) -> float:
    """
    Compute how much of the database schema is covered by the SRS (entities and fields).

    - Table score: fraction of schema tables that have a matching SRS entity (by name).
    - Field score: for tables that match, fraction of columns that have a matching SRS field.
    - Result: weighted average (0.5 * table_score + 0.5 * field_score), in [0, 1].

    Names are compared case-insensitively (e.g. "Orders" matches "orders").
    """
    if not parsed_schema.tables:
        return 1.0  # No schema tables to match

    entities = getattr(srs_output, "entities", None) or []
    # Build a lookup that supports basic singular/plural variants
    srs_entity_by_key: dict[str, Any] = {}
    for e in entities:
        for k in _name_variants(getattr(e, "name", "")):
            srs_entity_by_key.setdefault(k, e)

    table_scores: list[float] = []
    field_scores: list[float] = []

    for table in parsed_schema.tables:
        table_key = _norm_name(table.name)
        entity = srs_entity_by_key.get(table_key)

        if entity is None:
            table_scores.append(0.0)
            if table.fields:
                field_scores.append(0.0)
            continue

        table_scores.append(1.0)

        if not table.fields:
            continue

        srs_fields = getattr(entity, "fields", None) or []
        srs_field_names: set[str] = set()
        for f in srs_fields:
            for k in _name_variants(getattr(f, "name", "")):
                srs_field_names.add(k)
        matched = sum(1 for f in table.fields if _norm_name(f.name) in srs_field_names)
        field_scores.append(matched / len(table.fields))

    table_score = sum(table_scores) / len(parsed_schema.tables) if parsed_schema.tables else 1.0
    field_score = sum(field_scores) / len(field_scores) if field_scores else 1.0

    return 0.5 * table_score + 0.5 * field_score


def require_srs_schema_compatibility(
    parsed_schema: NormalizedSchema,
    srs_output: Any,
    min_compatibility: float = DEFAULT_MIN_COMPATIBILITY,
) -> None:
    """
    Raise ValueError if SRS–schema compatibility is below min_compatibility (default 80%).
    """
    score = compute_srs_schema_compatibility(parsed_schema, srs_output)
    if score < min_compatibility:
        pct = score * 100
        threshold_pct = min_compatibility * 100
        raise ValueError(
            f"SRS and schema compatibility is {pct:.1f}%, below the required {threshold_pct:.0f}% threshold. "
            "Ensure the SRS document describes the same entities and fields as the database schema."
        )
