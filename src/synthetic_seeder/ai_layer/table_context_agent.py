"""AI agent to generate per-table markdown context (schema-grounded)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from synthetic_seeder.schema import NormalizedSchema, TableDef

logger = logging.getLogger(__name__)


class TableContextMD(BaseModel):
    markdown: str = Field(description="Markdown context for the target table.")

_MD_TEMPLATE = """## Table: `{table}`

### Global_SRS_Profile
- locales: {locales}
- countries: {countries}
- regions: {regions}
- timezone: {timezone}
- currency: {currency}

### Columns
{columns_bullets}

### Foreign_Keys
{fk_bullets}

### Validation_Rules
- Use ONLY the listed column names.
- Do not add/rename keys in generated rows.
- NOT NULL columns must not be null or empty string.
- Enum columns must match allowed values exactly.
- Strings must not exceed max_length.
- Numbers must be within min/max (if present).
- Foreign keys must reference existing parent values from fk_value_pools.
"""


def _looks_like_bad_markdown(md: str) -> bool:
    s = (md or "").strip()
    if not s:
        return True
    # Model sometimes echoes JSON payload or returns JSON-like string
    if s.startswith("{") or s.startswith("["):
        return True
    if "TABLE_PAYLOAD_JSON" in s or "srs_profile" in s and '"table"' in s:
        return True
    # Placeholder token patterns we saw in outputs
    if "$table$" in s or "$columns$" in s or "$generated_data$" in s:
        return True
    # If it's mostly braces/quotes, it's likely not markdown
    brace_like = len(re.findall(r"[{}\[\]\"]", s))
    if brace_like > max(50, len(s) // 3):
        return True
    # Must include required headings; otherwise model likely ignored template
    required = ["## Table:", "### Global_SRS_Profile", "### Columns", "### Foreign_Keys", "### Validation_Rules"]
    if any(r not in s for r in required):
        return True
    # Must include at least one column bullet
    if "### Columns" in s:
        after = s.split("### Columns", 1)[1]
        if "- `" not in after:
            return True
    return False


def _extract_markdown(resp_content: Any) -> str:
    if isinstance(resp_content, TableContextMD):
        return (resp_content.markdown or "").strip() + "\n"
    if isinstance(resp_content, dict):
        return (TableContextMD.model_validate(resp_content).markdown or "").strip() + "\n"
    if isinstance(resp_content, str):
        return (TableContextMD.model_validate_json(resp_content).markdown or "").strip() + "\n"
    return ""


def generate_table_context_markdown_ai(
    *,
    table: TableDef,
    schema: NormalizedSchema,
    srs_text: str = "",
    srs_profile: dict[str, Any] | None = None,
    llm_provider: str = "openai",
    model_id: str = "gpt-4.1-mini",
) -> str:
    """
    Generate markdown context for a table using an LLM.
    The prompt is schema-grounded: columns/constraints/FKs are provided explicitly.
    """
    try:
        from agno.agent import Agent
    except ImportError as err:
        raise ImportError("Agno is required for AI markdown generation. Install with: pip install agno") from err

    provider = (llm_provider or "ollama").strip().lower()
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
        model = OpenAIResponses(id=model_id, temperature=0)

    # Build a strict, schema-grounded payload (facts the model must not contradict)
    payload = {
        "table": table.name,
        "columns": [
            {
                "name": f.name,
                "type": f.data_type,
                "nullable": bool(f.nullable),
                "unique": bool(f.is_unique),
                "primary_key": bool(f.is_primary_key),
                "auto_increment": bool(f.is_auto_increment),
                "max_length": f.max_length,
                "min_value": f.min_value,
                "max_value": f.max_value,
                "enum_values": f.enum_values,
            }
            for f in table.fields
        ],
        "outgoing_foreign_keys": [
            {
                "source_columns": fk.source_columns,
                "target_table": fk.target_table,
                "target_columns": fk.target_columns,
            }
            for fk in (table.foreign_keys or [])
        ],
        "srs_profile": srs_profile or {},
    }

    columns_bullets = "\n".join(
        [
            f"- `{c['name']}` ({c['type']}): "
            f"nullable={c['nullable']}, unique={c['unique']}, pk={c['primary_key']}, "
            f"auto_increment={c['auto_increment']}, max_length={c['max_length']}, "
            f"min_value={c['min_value']}, max_value={c['max_value']}, enum_values={c['enum_values']}"
            for c in payload["columns"]
        ]
    )
    fk_bullets = "\n".join(
        [
            f"- `{fk['source_columns']}` -> `{fk['target_table']}`.`{fk['target_columns']}`"
            for fk in payload["outgoing_foreign_keys"]
        ]
    ) or "- none"

    profile = payload.get("srs_profile") or {}
    template_filled = _MD_TEMPLATE.format(
        table=payload["table"],
        locales=profile.get("locales", []),
        countries=profile.get("countries", []),
        regions=profile.get("regions", []),
        timezone=profile.get("timezone"),
        currency=profile.get("currency"),
        columns_bullets=columns_bullets,
        fk_bullets=fk_bullets,
    )

    system = (
        "You are a senior data engineer.\n"
        "Write markdown context for synthetic data generation for ONE table.\n"
        "Rules:\n"
        "- MUST follow the provided markdown template sections and headings exactly.\n"
        "- MUST NOT output JSON or echo any input payload.\n"
        "- MUST NOT invent columns/constraints/FKs beyond the provided payload.\n"
        "- Keep it concise and schema-grounded.\n"
        "Return ONLY JSON matching: {\"markdown\": \"...\"}.\n"
    )

    prompt = (
        "SRS_TEXT (may be empty):\n"
        + (srs_text or "")
        + "\n\nTABLE_FACTS_JSON (do not echo; use only as facts):\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nMARKDOWN_TEMPLATE (fill this, do not change headings):\n"
        + template_filled
    )

    agent = Agent(model=model, markdown=False, output_schema=TableContextMD, instructions=system)

    # First attempt
    resp = agent.run(prompt)
    md = _extract_markdown(resp.content)

    # Retry once if model echoed JSON / placeholders / junk
    if _looks_like_bad_markdown(md):
        system_retry = system + (
            "\nRETRY RULES:\n"
            "- Your previous output was invalid.\n"
            "- Do NOT start with '{' or '['.\n"
            "- Do NOT include TABLE_FACTS_JSON or any raw JSON.\n"
            "- Do NOT use placeholder tokens like $table$.\n"
            "- Output must be markdown following the template.\n"
        )
        agent_retry = Agent(model=model, markdown=False, output_schema=TableContextMD, instructions=system_retry)
        resp2 = agent_retry.run(prompt)
        md2 = _extract_markdown(resp2.content)
        if not _looks_like_bad_markdown(md2):
            return md2
        # Fall back to deterministic template (still valid markdown) if AI can't comply
        return template_filled.strip() + "\n"

    return md

