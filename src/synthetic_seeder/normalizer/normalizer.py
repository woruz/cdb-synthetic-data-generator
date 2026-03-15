"""Merge Agno SRS output with DB schema; validate and produce unified NormalizedSchema."""

from __future__ import annotations

from typing import Any

from synthetic_seeder.schema import (
    DatabaseType,
    NormalizedSchema,
    TableDef,
)
from synthetic_seeder.schema_parser import detect_schema_type, parse_mongo_schema, parse_sql_schema

try:
    from synthetic_seeder.ai_layer.srs_schemas import SRSStructuredOutput
except ImportError:
    SRSStructuredOutput = None  # type: ignore[misc, assignment]


def normalize_schema(
    schema_content: str,
    db_type_hint: DatabaseType | str = DatabaseType.UNKNOWN,
    srs_output: Any = None,
) -> NormalizedSchema:
    """
    Merge parsed DB schema with SRS structured output.
    - Detect or use DB type; parse schema accordingly.
    - Enrich tables with SRS entities (states, enums, constraints).
    - Resolve insert order for FKs.
    """
    hint = db_type_hint if isinstance(db_type_hint, DatabaseType) else DatabaseType(db_type_hint)
    detected = detect_schema_type(schema_content)
    db_type = hint if hint != DatabaseType.UNKNOWN else detected
    if db_type == DatabaseType.UNKNOWN:
        db_type = DatabaseType.SQL  # default to SQL if unclear

    if db_type == DatabaseType.SQL:
        normalized = parse_sql_schema(schema_content)
    else:
        normalized = parse_mongo_schema(schema_content)

    if srs_output is not None and SRSStructuredOutput is not None:
        normalized = _merge_srs(normalized, srs_output)

    normalized.database_type = db_type
    if not normalized.insert_order and normalized.tables:
        normalized.insert_order = _topological_order(normalized.tables)
    return normalized


def _merge_srs(schema: NormalizedSchema, srs: SRSStructuredOutput) -> NormalizedSchema:
    """Enrich schema with SRS entities, state machines, enums, constraints."""
    table_by_name = {t.name: t for t in schema.tables}
    srs_entity_by_name = {e.name.lower(): e for e in srs.entities}

    for table in schema.tables:
        key = table.name.lower()
        if key not in srs_entity_by_name:
            continue
        entity = srs_entity_by_name[key]
        # Merge state_fields from entity and state_machines
        for field_name, states in entity.state_fields.items():
            table.state_fields[field_name] = states
        for sm in srs.state_machines:
            if sm.entity_or_field.lower() == table.name.lower() or sm.entity_or_field in [f.name for f in table.fields]:
                field_name = sm.entity_or_field if sm.entity_or_field in [f.name for f in table.fields] else None
                if field_name:
                    table.state_fields[field_name] = sm.states
                else:
                    for f in table.fields:
                        if "status" in f.name.lower() or "state" in f.name.lower():
                            table.state_fields[f.name] = sm.states
                            break
        # Enrich fields with SRS enum_values and types
        for field in table.fields:
            for ef in entity.fields:
                if ef.name.lower() == field.name.lower():
                    if ef.enum_values and not field.enum_values:
                        field.enum_values = ef.enum_values
                    if ef.max_length is not None and field.max_length is None:
                        field.max_length = ef.max_length
                    if ef.min_length is not None and field.min_length is None:
                        field.min_length = ef.min_length
                    break
        for enum_name, values in srs.enums.items():
            for field in table.fields:
                if field.name.lower() == enum_name.lower() or enum_name.lower() in field.name.lower():
                    if not field.enum_values:
                        field.enum_values = values

    # Add relationships as FK hints where table exists (SQL already has FKs; MongoDB we don't add FK defs, just order)
    return schema


def _topological_order(tables: list[TableDef]) -> list[str]:
    """Order table names: parents before children."""
    name_to_table = {t.name: t for t in tables}
    order: list[str] = []
    seen = set()

    def visit(name: str) -> None:
        if name in seen or name not in name_to_table:
            return
        seen.add(name)
        t = name_to_table[name]
        for fk in t.foreign_keys:
            visit(fk.target_table)
        order.append(name)

    for t in tables:
        visit(t.name)
    return order
