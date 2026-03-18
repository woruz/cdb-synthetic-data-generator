"""AI-based schema parser (testing). Produces NormalizedSchema from raw schema text."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from synthetic_seeder.schema import DatabaseType, NormalizedSchema
from synthetic_seeder.schema_parser.sql_common import split_create_table_blocks

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", flags=re.MULTILINE)


def _extract_json_object(text: str) -> dict[str, Any]:
    """
    Best-effort: extract a single top-level JSON object from model output.
    Many local LLMs sometimes prepend/append explanation text.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("AI schema parser returned empty text")
    try:
        val = json.loads(text)
        if isinstance(val, dict):
            return val
    except Exception:
        pass
    m = _JSON_OBJECT_RE.search(text)
    if not m:
        raise ValueError("AI schema parser did not return a JSON object")
    val = json.loads(m.group(0))
    if not isinstance(val, dict):
        raise ValueError("AI schema parser JSON is not an object")
    return val


def _split_ref(ref: Any) -> tuple[str | None, str | None]:
    if isinstance(ref, str):
        s = ref.strip().strip('"').strip("'")
        if "." in s:
            t, c = s.split(".", 1)
            return t.strip(), c.strip()
    return None, None


def _normalize_ai_schema_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize common LLM schema shapes into our NormalizedSchema shape.

    Handles:
    - unique_keys: ["email"] -> [{columns:["email"]}]
    - foreign_keys: {table, column, ref_table/ref_column or ref_column:"users.id"} -> {source_columns, target_table, target_columns}
    - state_fields: [] -> {}
    """
    out: dict[str, Any] = dict(data)
    tables = out.get("tables")
    if not isinstance(tables, list):
        return out

    norm_tables: list[dict[str, Any]] = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        tt: dict[str, Any] = dict(t)

        # state_fields must be a dict[str, list[str]]
        sf = tt.get("state_fields")
        if isinstance(sf, list):
            tt["state_fields"] = {}
        elif sf is None:
            tt["state_fields"] = {}

        # role_hints should be a list
        if not isinstance(tt.get("role_hints"), list):
            tt["role_hints"] = []

        # unique_keys normalization
        uks = tt.get("unique_keys")
        if isinstance(uks, list):
            fixed_uks: list[dict[str, Any]] = []
            for uk in uks:
                if isinstance(uk, str):
                    fixed_uks.append({"columns": [uk]})
                elif isinstance(uk, dict):
                    if "columns" in uk and isinstance(uk["columns"], list):
                        fixed_uks.append(uk)
                    elif "column" in uk and isinstance(uk["column"], str):
                        fixed_uks.append({"name": uk.get("name"), "columns": [uk["column"]]})
            tt["unique_keys"] = fixed_uks
        elif uks is None:
            tt["unique_keys"] = []

        # foreign_keys normalization
        fks = tt.get("foreign_keys")
        if isinstance(fks, list):
            fixed_fks: list[dict[str, Any]] = []
            for fk in fks:
                if not isinstance(fk, dict):
                    continue
                if {"source_columns", "target_table", "target_columns"}.issubset(set(fk.keys())):
                    fixed_fks.append(fk)
                    continue

                # Common LLM shape: {table, column, ref_table, ref_column} or {column, references:"users.id"}
                src_col = fk.get("column") or fk.get("source_column") or fk.get("from_column")
                if isinstance(src_col, list) and len(src_col) == 1:
                    src_col = src_col[0]

                tgt_table = fk.get("ref_table") or fk.get("references_table") or fk.get("to_table")
                tgt_col = fk.get("ref_column") or fk.get("references_column") or fk.get("to_column")

                # Sometimes only "ref_column": "users.id" is provided
                if not tgt_table and isinstance(tgt_col, str) and "." in tgt_col:
                    rt, rc = _split_ref(tgt_col)
                    tgt_table = rt
                    tgt_col = rc

                # Sometimes "references": "users(id)" or "users.id"
                refs = fk.get("references") or fk.get("ref") or fk.get("target")
                if (not tgt_table or not tgt_col) and isinstance(refs, str):
                    s = refs.strip()
                    m = re.match(r"^\s*([\"\w]+)\s*\(\s*([\"\w]+)\s*\)\s*$", s)
                    if m:
                        tgt_table = m.group(1).strip('"')
                        tgt_col = m.group(2).strip('"')
                    else:
                        rt, rc = _split_ref(s)
                        if rt and rc:
                            tgt_table, tgt_col = rt, rc

                if isinstance(src_col, str) and isinstance(tgt_table, str) and isinstance(tgt_col, str):
                    fixed_fks.append(
                        {
                            "name": fk.get("name"),
                            "source_columns": [src_col],
                            "target_table": tgt_table,
                            "target_columns": [tgt_col],
                            "on_delete": fk.get("on_delete"),
                            "on_update": fk.get("on_update"),
                        }
                    )
            tt["foreign_keys"] = fixed_fks
        elif fks is None:
            tt["foreign_keys"] = []

        # fields must be list[dict] (Pydantic will validate each)
        if not isinstance(tt.get("fields"), list):
            tt["fields"] = []
        if not isinstance(tt.get("primary_key"), list):
            tt["primary_key"] = []
        if not isinstance(tt.get("indexes"), list):
            tt["indexes"] = []

        norm_tables.append(tt)

    out["tables"] = norm_tables
    return out


def parse_schema_ai(
    schema_content: str,
    *,
    db_type_hint: DatabaseType = DatabaseType.UNKNOWN,
    llm_provider: str = "openai",
    model_id: str = "gpt-4.1-mini",
) -> NormalizedSchema:
    """
    Use an LLM to parse schema text into NormalizedSchema (Pydantic).
    This is a testing path; deterministic parsers remain the source of truth.
    """
    schema_content = (schema_content or "").strip()
    if not schema_content:
        return NormalizedSchema(database_type=db_type_hint)

    try:
        from agno.agent import Agent
    except ImportError as err:
        raise ImportError("Agno is required for AI schema parsing. Install with: pip install agno") from err

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

    # IMPORTANT: Do NOT use output_schema=NormalizedSchema with Ollama.
    # Ollama's `format` JSON schema support is stricter and can reject complex schemas,
    # causing: "invalid JSON schema in format (status code: 500)".
    # Instead, we prompt for plain JSON and validate ourselves.
    system = (
        "You are a database schema parser.\n"
        "Return ONLY valid JSON.\n"
        "Convert the given schema text into a NormalizedSchema JSON object with EXACT keys:\n"
        "- database_type: 'sql'|'mongodb'|'unknown'\n"
        "- tables: [TableDef]\n"
        "- insert_order: [table_name,...]\n"
        "TableDef keys (EXACT):\n"
        "- name: string\n"
        "- fields: [FieldDef]\n"
        "- primary_key: [string]\n"
        "- unique_keys: [{ name?: string|null, columns: [string] }]\n"
        "- foreign_keys: [{ name?: string|null, source_columns: [string], target_table: string, target_columns: [string], on_delete?: string|null, on_update?: string|null }]\n"
        "- indexes: [{ name?: string|null, columns: [string], unique: boolean }]\n"
        "- state_fields: { [field_name: string]: [allowed_value: string] }\n"
        "- role_hints: [string]\n"
        "Rules:\n"
        "- Do not invent tables/columns/foreign keys.\n"
        "- Prefer exact names from the schema.\n"
        "- For UUID types, use data_type='string'.\n"
        "- PRIMARY KEY columns must be nullable=false.\n"
    )

    agent = Agent(model=model, markdown=False, instructions=system)
    resp = agent.run(schema_content)
    content = resp.content
    data: Any
    if isinstance(content, dict):
        data = content
    elif isinstance(content, str):
        data = _extract_json_object(content)
    else:
        # Some Agno model wrappers return objects; try best-effort extraction
        data = getattr(content, "model_dump", lambda: None)() if content is not None else None
        if data is None:
            raise ValueError("AI schema parser returned no JSON content")

    if isinstance(data, dict):
        data = _normalize_ai_schema_dict(data)
    out = NormalizedSchema.model_validate(data)

    # Ensure database_type is set from hint if missing/unknown
    if out.database_type == DatabaseType.UNKNOWN and db_type_hint != DatabaseType.UNKNOWN:
        out.database_type = db_type_hint
    # Ensure insert_order exists if missing
    if not out.insert_order and out.tables:
        out.insert_order = _topo_order(out)
    _require_schema_grounding(out, schema_content, db_type_hint=db_type_hint)
    return out


def _topo_order(schema: NormalizedSchema) -> list[str]:
    name_to_table = {t.name: t for t in schema.tables}
    order: list[str] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        if name in seen or name not in name_to_table:
            return
        seen.add(name)
        t = name_to_table[name]
        for fk in t.foreign_keys:
            visit(fk.target_table)
        order.append(name)

    for t in schema.tables:
        visit(t.name)
    return order


def _require_schema_grounding(schema: NormalizedSchema, schema_content: str, *, db_type_hint: DatabaseType) -> None:
    """
    Hard guardrail to reduce hallucination: require that every table/column the AI produced
    is actually present in the raw schema text, and that FK targets exist.

    Raises ValueError with details if grounding fails.
    """
    content_l = (schema_content or "").lower()
    errors: list[str] = []

    # Only implement SQL grounding for now (this project uses SQL heavily).
    # For Mongo JSON schema we can add analogous checks later.
    blocks = split_create_table_blocks(schema_content, strip_prefix="")
    table_block: dict[str, str] = {}
    for b in blocks:
        # Extract table identifier from CREATE TABLE ... (<cols>)
        # split_create_table_blocks() returns statements that start with CREATE TABLE ...
        first_line = b.splitlines()[0].strip()
        m = re.search(
            r"create\s+table\s+(?:if\s+not\s+exists\s+)?((?:[\"\w]+\.)?[\"\w]+)\s*\(",
            first_line,
            flags=re.IGNORECASE,
        )
        if not m:
            # As a fallback, scan the whole block header (some DDLs break lines oddly)
            header = " ".join(b.splitlines()[:3])
            m = re.search(
                r"create\s+table\s+(?:if\s+not\s+exists\s+)?((?:[\"\w]+\.)?[\"\w]+)\s*\(",
                header,
                flags=re.IGNORECASE,
            )
        if not m:
            continue
        raw = m.group(1)
        name = raw.split(".")[-1].strip().strip('"').strip("'")
        table_block[name.lower()] = b.lower()

    ai_tables = [t.name for t in schema.tables]
    for t in schema.tables:
        tname_l = (t.name or "").strip().lower()
        if not tname_l:
            errors.append("AI schema has an empty table name")
            continue
        if tname_l not in table_block:
            # Allow a looser check: CREATE TABLE <name> appears somewhere
            if f"create table {tname_l}" not in content_l:
                errors.append(f"AI table not found in schema text: {t.name}")
        blk = table_block.get(tname_l, "")
        # Require each column name to appear in its CREATE TABLE block
        for f in t.fields:
            cname_l = (f.name or "").strip().lower()
            if not cname_l:
                errors.append(f"{t.name}: empty column name")
                continue
            if blk and re.search(rf"\\b{re.escape(cname_l)}\\b", blk) is None:
                errors.append(f"{t.name}.{f.name}: column not found in schema text")

    # FK target sanity: referenced table/column must exist in AI schema too
    table_by_name = {t.name: t for t in schema.tables}
    for t in schema.tables:
        for fk in t.foreign_keys or []:
            if fk.target_table not in table_by_name:
                errors.append(f"{t.name}: FK targets missing table {fk.target_table}")
                continue
            tgt = table_by_name[fk.target_table]
            tgt_cols = {c.name for c in tgt.fields}
            for c in fk.target_columns:
                if c not in tgt_cols:
                    errors.append(f"{t.name}: FK targets missing column {fk.target_table}.{c}")

    # insert_order must only contain known tables
    if schema.insert_order:
        known = {t.name for t in schema.tables}
        for name in schema.insert_order:
            if name not in known:
                errors.append(f"insert_order includes unknown table: {name}")

    if errors:
        msg = "AI-parsed schema failed grounding checks:\n" + "\n".join(f"- {e}" for e in errors[:50])
        raise ValueError(msg)

