"""Build per-table markdown context from schema + SRS + relationships."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synthetic_seeder.graph.model import SchemaGraph
from synthetic_seeder.schema import FieldDef, ForeignKeyDef, NormalizedSchema, TableDef

try:
    from synthetic_seeder.ai_layer.srs_schemas import SRSStructuredOutput
except Exception:  # pragma: no cover
    SRSStructuredOutput = Any  # type: ignore[assignment,misc]


@dataclass(frozen=True)
class IncomingFK:
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    fk_name: str | None = None


def _table_by_name(schema: NormalizedSchema) -> dict[str, TableDef]:
    return {t.name: t for t in schema.tables}


def _field_by_name(table: TableDef) -> dict[str, FieldDef]:
    return {f.name: f for f in table.fields}


def _incoming_fks(schema: NormalizedSchema, target_table: str) -> list[IncomingFK]:
    incoming: list[IncomingFK] = []
    for t in schema.tables:
        for fk in t.foreign_keys:
            if fk.target_table == target_table:
                incoming.append(
                    IncomingFK(
                        from_table=t.name,
                        from_columns=list(fk.source_columns),
                        to_table=fk.target_table,
                        to_columns=list(fk.target_columns),
                        fk_name=fk.name,
                    )
                )
    return incoming


def _srs_entity_hint(srs: SRSStructuredOutput | None, table_name: str) -> tuple[str | None, dict[str, list[str]]]:
    """
    Best-effort SRS lookup by name (case-insensitive).
    Returns (description, state_fields).
    """
    if srs is None:
        return None, {}
    key = (table_name or "").strip().lower()
    for e in getattr(srs, "entities", []) or []:
        if (getattr(e, "name", "") or "").strip().lower() == key:
            return getattr(e, "description", None), dict(getattr(e, "state_fields", {}) or {})
    return None, {}


def _format_constraints(field: FieldDef) -> str:
    parts: list[str] = []
    parts.append("NOT NULL" if not field.nullable else "NULLABLE")
    if field.is_unique:
        parts.append("UNIQUE")
    if field.is_primary_key:
        parts.append("PK")
    if field.is_auto_increment:
        parts.append("AUTO_INCREMENT")
    if field.max_length is not None:
        parts.append(f"max_length={field.max_length}")
    if field.min_length is not None:
        parts.append(f"min_length={field.min_length}")
    if field.min_value is not None:
        parts.append(f"min={field.min_value}")
    if field.max_value is not None:
        parts.append(f"max={field.max_value}")
    if field.enum_values:
        parts.append(f"enum={field.enum_values}")
    return ", ".join(parts)


def build_table_context_markdown(
    *,
    srs: SRSStructuredOutput | None,
    profile: Any | None = None,
    schema: NormalizedSchema,
    graph: SchemaGraph | None,
    table: TableDef,
) -> str:
    """
    Build markdown guidance for AI-driven row generation for a single table.

    The markdown is meant to be consumed by an LLM (and also helpful for humans).
    It is grounded in the parsed schema (constraints + relationships). SRS is used
    only as domain flavor (descriptions/state fields) when available.
    """
    table_desc, state_fields = _srs_entity_hint(srs, table.name)
    incoming = _incoming_fks(schema, table.name)
    outgoing = list(table.foreign_keys or [])

    lines: list[str] = []
    lines.append(f"## Table: `{table.name}`")
    if table_desc:
        lines.append("")
        lines.append(f"**SRS hint:** {table_desc}")

    if profile is not None:
        # Keep this section short and high-signal; full JSON is stored separately.
        locales = getattr(profile, "locales", None) or []
        countries = getattr(profile, "countries", None) or []
        timezone = getattr(profile, "timezone", None)
        currency = getattr(profile, "currency", None)
        if locales or countries or timezone or currency:
            lines.append("")
            lines.append("### Global SRS constraints (apply to all tables)")
            if locales:
                lines.append(f"- locales: {locales}")
            if countries:
                lines.append(f"- countries: {countries}")
            if timezone:
                lines.append(f"- timezone: {timezone}")
            if currency:
                lines.append(f"- currency: {currency}")

    lines.append("")
    lines.append("### Columns (schema-grounded)")
    field_map = _field_by_name(table)
    for f in table.fields:
        desc = f.description or ""
        desc_part = f" — {desc}" if desc else ""
        lines.append(f"- `{f.name}` ({f.data_type}) — {_format_constraints(f)}{desc_part}")

    if state_fields:
        lines.append("")
        lines.append("### State fields (from SRS)")
        for k, vals in state_fields.items():
            if k in field_map:
                lines.append(f"- `{k}` allowed states: {vals}")

    lines.append("")
    lines.append("### Relationships (foreign keys)")
    if outgoing:
        lines.append("")
        lines.append("**Outgoing FKs (this table references parents):**")
        for fk in outgoing:
            lines.append(
                f"- `{fk.source_columns}` → `{fk.target_table}`.`{fk.target_columns}`"
                + (f" (name={fk.name})" if fk.name else "")
            )
    else:
        lines.append("")
        lines.append("**Outgoing FKs:** none")

    if incoming:
        lines.append("")
        lines.append("**Incoming FKs (children reference this table):**")
        for infk in incoming:
            lines.append(
                f"- `{infk.from_table}`.`{infk.from_columns}` → `{infk.to_table}`.`{infk.to_columns}`"
                + (f" (name={infk.fk_name})" if infk.fk_name else "")
            )
    else:
        lines.append("")
        lines.append("**Incoming FKs:** none")

    if graph is not None and table.name in getattr(graph, "nodes", {}):
        node = graph.nodes[table.name]
        lines.append("")
        lines.append("### Graph position")
        lines.append(f"- parents: {getattr(node, 'parents', [])}")
        lines.append(f"- children: {getattr(node, 'children', [])}")

    lines.append("")
    lines.append("### Validation rules (must satisfy)")
    lines.append("- Use ONLY the listed column names. Do not add or rename keys.")
    lines.append("- For NOT NULL columns: value must not be null/empty string.")
    lines.append("- For enum columns: value must be one of the enum values exactly.")
    lines.append("- For strings: must not exceed max_length (if present).")
    lines.append("- For numeric columns: must be within min/max (if present).")
    lines.append("- For foreign keys: reference an existing parent row id/value.")

    return "\n".join(lines).strip() + "\n"

