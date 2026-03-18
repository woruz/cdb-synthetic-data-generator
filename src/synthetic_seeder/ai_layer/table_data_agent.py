"""AI agent to generate table rows from a markdown context (strict schema-grounded)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from synthetic_seeder.schema import FieldDef, NormalizedSchema, TableDef

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", flags=re.MULTILINE)


def _extract_json_object(text: str) -> dict[str, Any]:
    """
    Best-effort: extract a single top-level JSON object from model output.
    Some providers prepend/append extra text even when asked for JSON only.
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


@dataclass(frozen=True)
class FKPool:
    """Allowed values for one FK column (single-column FK only)."""

    column: str
    allowed_values: list[Any]


def _table_by_name(schema: NormalizedSchema) -> dict[str, TableDef]:
    return {t.name: t for t in schema.tables}


def _field_by_name(table: TableDef) -> dict[str, FieldDef]:
    return {f.name: f for f in table.fields}


def _coerce_scalar(value: Any, field: FieldDef) -> Any:
    if value is None:
        return None
    t = (field.data_type or "string").lower()
    if t in ("int", "integer"):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if t in ("float", "number", "decimal"):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if t in ("bool", "boolean"):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1", "yes"):
                return True
            if v in ("false", "0", "no"):
                return False
        return value
    # string/date/datetime: leave as-is; writers/validator handle isoformat-ish strings as strings
    return value


def _sanitize_rows(
    *,
    table: TableDef,
    rows: list[dict[str, Any]],
    fk_pools: list[FKPool],
    max_rows: int,
) -> list[dict[str, Any]]:
    """Enforce strict column whitelist, fill missing columns, basic type coercion, FK value snapping."""
    allowed_cols = [f.name for f in table.fields]
    allowed_set = set(allowed_cols)
    field_map = _field_by_name(table)
    fk_pool_by_col = {p.column: p for p in fk_pools}

    cleaned: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[:max_rows]):
        if not isinstance(row, dict):
            continue
        # Drop unknown keys
        out = {k: v for k, v in row.items() if k in allowed_set}
        # Ensure all columns exist (fill missing with None)
        for col in allowed_cols:
            if col not in out:
                out[col] = None
        # Coerce scalars by schema types
        for col, val in list(out.items()):
            f = field_map.get(col)
            if f is not None:
                out[col] = _coerce_scalar(val, f)
                # Enforce enum membership
                if f.enum_values is not None and out[col] is not None:
                    if str(out[col]) not in f.enum_values:
                        out[col] = f.enum_values[0] if f.enum_values else out[col]
                # Enforce max_length on strings
                if f.max_length is not None and isinstance(out[col], str) and len(out[col]) > f.max_length:
                    out[col] = out[col][: f.max_length]
                # Enforce numeric bounds if present
                if f.data_type == "int" and isinstance(out[col], int):
                    if f.min_value is not None and out[col] < f.min_value:
                        out[col] = int(f.min_value)
                    if f.max_value is not None and out[col] > f.max_value:
                        out[col] = int(f.max_value)
                if f.data_type == "float" and isinstance(out[col], (int, float)):
                    valf = float(out[col])
                    if f.min_value is not None and valf < float(f.min_value):
                        valf = float(f.min_value)
                    if f.max_value is not None and valf > float(f.max_value):
                        valf = float(f.max_value)
                    out[col] = valf

                # Make nullable fields look more realistic (only if missing/empty).
                # This is deterministic and schema-safe; it avoids empty-string spam.
                name_l = col.lower()
                if f.data_type == "string":
                    if out[col] is None:
                        # Keep some nulls, but prefer filling descriptive fields
                        if any(k in name_l for k in ["description", "desc", "comment", "bio", "summary", "title"]):
                            out[col] = f"{col} {idx + 1}"
                    elif isinstance(out[col], str) and out[col].strip() == "":
                        if any(k in name_l for k in ["description", "desc", "comment", "bio", "summary"]):
                            out[col] = f"{col} {idx + 1}"
                if f.data_type == "date" and out[col] is None:
                    if "due" in name_l:
                        # Simple ISO date; safe for most DBs/parsers
                        out[col] = "2026-01-{:02d}".format(((idx % 28) + 1))
                if f.data_type == "datetime" and out[col] is None:
                    if "created" in name_l or "updated" in name_l:
                        out[col] = "2026-01-{:02d}T12:00:00".format(((idx % 28) + 1))
                if f.data_type == "int" and out[col] is None:
                    if "position" in name_l or name_l.endswith("_order"):
                        out[col] = idx + 1
        # Snap FK values to allowed pool if provided and value not in pool
        for col, pool in fk_pool_by_col.items():
            if not pool.allowed_values:
                continue
            if out.get(col) not in pool.allowed_values:
                out[col] = pool.allowed_values[0]
        cleaned.append(out)
    return cleaned


def _build_fk_pools(
    *,
    schema: NormalizedSchema,
    table: TableDef,
    parent_rows_by_table: dict[str, list[dict[str, Any]]],
) -> list[FKPool]:
    """
    Build FK allowed-values pools for single-column FKs.
    If parent PK values are known, constrain AI to use them.
    """
    pools: list[FKPool] = []
    for fk in table.foreign_keys or []:
        if len(fk.source_columns) != 1 or len(fk.target_columns) != 1:
            continue
        src = fk.source_columns[0]
        tgt_table = fk.target_table
        tgt_col = fk.target_columns[0]
        parents = parent_rows_by_table.get(tgt_table, [])
        allowed = [r.get(tgt_col) for r in parents if isinstance(r, dict) and r.get(tgt_col) is not None]
        pools.append(FKPool(column=src, allowed_values=allowed))
    return pools


def _prompt_for_table_rows(
    *,
    table: TableDef,
    context_markdown: str,
    fk_pools: list[FKPool],
    srs_profile: dict[str, Any] | None = None,
) -> str:
    cols = []
    for f in table.fields:
        cols.append(
            {
                "name": f.name,
                "type": f.data_type,
                "nullable": bool(f.nullable),
                "unique": bool(f.is_unique),
                "max_length": f.max_length,
                "min_value": f.min_value,
                "max_value": f.max_value,
                "enum_values": f.enum_values,
                "auto_increment": bool(f.is_auto_increment),
            }
        )
    fk_rules = [
        {"column": p.column, "allowed_values": p.allowed_values[:50]}  # cap in prompt
        for p in fk_pools
        if p.allowed_values
    ]
    payload = {
        "table": table.name,
        "columns": cols,
        "fk_value_pools": fk_rules,
        "srs_profile": srs_profile or {},
        "context_markdown": context_markdown,
    }

    return (
        "Return ONLY valid JSON.\n"
        "Generate a JSON object with the exact shape:\n"
        "{ \"rows\": [ {<column>: <value>, ...}, ... ] }\n"
        "Rules:\n"
        "- Use ONLY the column names provided in columns[].name.\n"
        "- Include ALL columns for every row.\n"
        "- Do not add extra keys.\n"
        "- Respect nullable, max_length, enum_values, min_value/max_value.\n"
        "- If fk_value_pools is provided for a column, the value MUST be one of those allowed_values.\n"
        "- If srs_profile provides locale/country/timezone/currency, generated values must match it.\n"
        "- Decide a reasonable number of rows (keep it small; 5-50).\n"
        "\n"
        "INPUT:\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def generate_table_rows_ai(
    *,
    schema: NormalizedSchema,
    table: TableDef,
    context_markdown: str,
    parent_rows_by_table: dict[str, list[dict[str, Any]]],
    srs_profile: dict[str, Any] | None = None,
    llm_provider: str = "openai",
    model_id: str = "gpt-4.1-mini",
    max_rows: int = 200,
) -> list[dict[str, Any]]:
    """
    Use an LLM to generate rows for a single table, grounded by:
    - schema columns + constraints
    - per-table markdown context
    - FK value pools from already-generated parent rows

    Output is sanitized to strict schema columns (drop extras, fill missing).
    """
    fk_pools = _build_fk_pools(schema=schema, table=table, parent_rows_by_table=parent_rows_by_table)
    prompt = _prompt_for_table_rows(
        table=table,
        context_markdown=context_markdown,
        fk_pools=fk_pools,
        srs_profile=srs_profile,
    )

    try:
        from agno.agent import Agent
    except ImportError as err:
        raise ImportError("Agno is required for AI row generation. Install with: pip install agno") from err

    provider = (llm_provider or "openai").strip().lower()
    if provider == "ollama":
        try:
            from agno.models.ollama import Ollama
        except ImportError as err:
            raise ImportError("Agno Ollama support is required. Install with: pip install agno") from err
        model = Ollama(id=model_id or "qwen2:7b")
    else:
        try:
            from agno.models.openai import OpenAIResponses
        except ImportError as err:
            raise ImportError("Agno OpenAI support requires `openai` package. Install with: pip install openai") from err
        model = OpenAIResponses(id=model_id, temperature=0.4)

    class _RowsEnvelope(BaseModel):
        rows: list[dict[str, Any]] = Field(default_factory=list)

    # IMPORTANT: Do NOT use output_schema with OpenAI here.
    # Some OpenAI Responses endpoint variants reject generated JSON schemas.
    # We'll request plain JSON and validate locally.
    agent = Agent(model=model, markdown=False)

    resp = agent.run(prompt)
    content = resp.content
    if isinstance(content, _RowsEnvelope):
        rows = content.rows
    elif isinstance(content, dict):
        rows = _RowsEnvelope.model_validate(content).rows
    elif isinstance(content, str):
        rows = _RowsEnvelope.model_validate(_extract_json_object(content)).rows
    else:
        rows = []

    return _sanitize_rows(table=table, rows=rows, fk_pools=fk_pools, max_rows=max_rows)

