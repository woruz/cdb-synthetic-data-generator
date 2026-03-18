"""PostgreSQL DDL parser. Handles double-quoted identifiers, SERIAL, PostgreSQL types."""

from __future__ import annotations

import re

from synthetic_seeder.schema import (
    DatabaseType,
    FieldDef,
    ForeignKeyDef,
    NormalizedSchema,
    TableDef,
    UniqueKeyDef,
)
from synthetic_seeder.schema_parser.sql_common import (
    normalize_identifier,
    parse_length,
    split_create_table_blocks,
    topological_order,
)

DIALECT = "postgres"

_POSTGRES_TYPE_MAP = {
    "INT": "int", "INTEGER": "int", "BIGINT": "int", "SMALLINT": "int",
    "SERIAL": "int", "BIGSERIAL": "int", "SMALLSERIAL": "int",
    "FLOAT": "float", "DOUBLE PRECISION": "float", "REAL": "float",
    "DECIMAL": "float", "NUMERIC": "float", "MONEY": "float",
    "BOOLEAN": "bool", "BOOL": "bool",
    "DATE": "date", "TIMESTAMP": "datetime", "TIMESTAMPTZ": "datetime",
    "TIME": "string", "TIMETZ": "string",
    "TEXT": "string", "VARCHAR": "string", "CHAR": "string", "CHARACTER": "string",
    "CHARACTER VARYING": "string", "JSON": "string", "JSONB": "string",
    "UUID": "string", "BYTEA": "string",
}


def _normalize_type(sql_type: str) -> str:
    upper = sql_type.upper().strip()
    base = re.sub(r"\([^)]*\)", "", upper).strip()
    if "DOUBLE PRECISION" in base:
        return "float"
    if "CHARACTER VARYING" in base:
        return "string"
    return _POSTGRES_TYPE_MAP.get(base, "string")


def _norm(name: str) -> str:
    return normalize_identifier(name, DIALECT)


def _parse_check_in_from_block(block: str) -> dict[str, list[str]]:
    """Extract CHECK (col IN ('a','b')) constraints from block. Returns dict column_name -> allowed values."""
    out = {}
    for m in re.finditer(
        r"CHECK\s*\(\s*([\"\w]+)\s+IN\s*\(([^)]+)\)\s*\)",
        block,
        re.IGNORECASE | re.DOTALL,
    ):
        col = _norm(m.group(1))
        raw = m.group(2)
        values = []
        for part in re.findall(r"'([^']*)'|\"([^\"]*)\"", raw):
            values.append((part[0] or part[1]).strip())
        if values:
            out[col] = values
    return out


def _parse_pg_enum_types(schema_content: str) -> dict[str, list[str]]:
    """
    Parse PostgreSQL enum types:
      CREATE TYPE customer_type_t AS ENUM ('regular', 'premium');
    Returns mapping: type_name(lower) -> allowed values.
    """
    out: dict[str, list[str]] = {}
    for m in re.finditer(
        r"CREATE\s+TYPE\s+([\"\w]+)\s+AS\s+ENUM\s*\(([^;]+)\)\s*;",
        schema_content,
        re.IGNORECASE | re.DOTALL,
    ):
        type_name = _norm(m.group(1)).lower()
        raw = m.group(2)
        values = []
        for part in re.findall(r"'([^']*)'|\"([^\"]*)\"", raw):
            values.append((part[0] or part[1]).strip())
        if values:
            out[type_name] = values
    return out


def _parse_numeric_precision_scale(sql_type: str) -> tuple[int, int] | None:
    """Parse NUMERIC(p,s) / DECIMAL(p,s) -> (p,s)."""
    m = re.search(r"\b(?:NUMERIC|DECIMAL)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", sql_type, re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _numeric_bounds_from_precision_scale(p: int, s: int) -> tuple[float, float]:
    """
    Approximate inclusive bounds for NUMERIC(p,s):
      max = 10^(p-s) - 10^-s
      min = -max
    """
    max_val = (10 ** (p - s)) - (10 ** (-s))
    return -max_val, max_val


def _parse_table_block(block: str) -> TableDef | None:
    lines = [s.strip() for s in block.split("\n")]
    if not lines:
        return None
    first = lines[0]
    # "schema"."table" or "table" or table
    name_match = re.match(r"((?:[\"\w]+\.)?[\"\w]+)\s*\(?", first, re.IGNORECASE)
    if not name_match:
        return None
    raw = name_match.group(1)
    table_name = _norm(raw.split(".")[-1] if "." in raw else raw)
    check_enum = _parse_check_in_from_block(block)
    # enum types are detected outside and injected via a closure variable (set in parse_postgres_schema)
    pg_enum_types: dict[str, list[str]] = getattr(_parse_table_block, "_pg_enum_types", {})  # type: ignore[attr-defined]
    fields: list[FieldDef] = []
    primary_key: list[str] = []
    unique_keys: list[UniqueKeyDef] = []
    foreign_keys: list[ForeignKeyDef] = []

    for line in lines[1:]:
        line = line.rstrip(",").strip()
        if not line or line.startswith(")"):
            continue
        upper = line.upper()
        # Table-level CHECK (col IN (...)) - already handled by _parse_check_in_from_block; do not treat as column
        if upper.startswith("CHECK ") and " IN " in upper:
            continue
        if upper.startswith("PRIMARY KEY"):
            m = re.search(r"PRIMARY\s+KEY\s*\(([^)]+)\)", line, re.IGNORECASE)
            if m:
                primary_key = [_norm(c.strip()) for c in m.group(1).split(",")]
            continue
        if upper.startswith("UNIQUE"):
            m = re.search(r"UNIQUE\s*\(([^)]+)\)", line, re.IGNORECASE)
            if m:
                unique_keys.append(UniqueKeyDef(columns=[_norm(c.strip()) for c in m.group(1).split(",")]))
            continue
        # Standalone FOREIGN KEY constraint line - no column, only FK
        if upper.startswith("FOREIGN KEY"):
            fk = _parse_fk(line)
            if fk:
                foreign_keys.append(fk)
            continue
        # Column definition (may include inline REFERENCES)
        col_match = re.match(r"^([\"\w]+)\s+(\S+(?:\s*\([^)]*\))?)\s*(.*)$", line, re.IGNORECASE)
        if col_match:
            # Parse FK if present (inline REFERENCES on same line); add FK and still add the column below
            if "REFERENCES" in upper:
                fk = _parse_fk(line)
                if fk:
                    foreign_keys.append(fk)
            col_name = _norm(col_match.group(1))
            col_type = col_match.group(2)
            rest = col_match.group(3).upper()
            is_pk = "PRIMARY KEY" in rest
            # PRIMARY KEY implies NOT NULL even if not spelled out
            nullable = ("NOT NULL" not in rest) and (not is_pk)
            is_auto = "SERIAL" in col_type.upper() or "BIGSERIAL" in col_type.upper()
            is_unique = "UNIQUE" in rest
            if is_pk:
                primary_key.append(col_name)
            enum_vals = check_enum.get(col_name)
            # If column type is a named enum type, attach its allowed values.
            if enum_vals is None:
                enum_vals = pg_enum_types.get(_norm(col_type).lower())

            min_value = None
            max_value = None
            ps = _parse_numeric_precision_scale(col_type)
            if ps:
                min_value, max_value = _numeric_bounds_from_precision_scale(ps[0], ps[1])
            fields.append(
                FieldDef(
                    name=col_name,
                    data_type=_normalize_type(col_type),
                    nullable=nullable,
                    max_length=parse_length(col_type),
                    min_value=min_value,
                    max_value=max_value,
                    enum_values=enum_vals,
                    is_primary_key=is_pk,
                    is_auto_increment=is_auto,
                    is_unique=is_unique,
                )
            )

    return TableDef(
        name=table_name,
        fields=fields,
        primary_key=primary_key or [f.name for f in fields if f.is_primary_key],
        unique_keys=unique_keys,
        foreign_keys=foreign_keys,
        indexes=[],
    )


def _parse_fk(line: str) -> ForeignKeyDef | None:
    ref_match = re.search(r"REFERENCES\s+([^(\s]+)\s*\(([^)]+)\)", line, re.IGNORECASE)
    if not ref_match:
        return None
    target_table = _norm(ref_match.group(1).split(".")[-1])
    target_cols = [_norm(c.strip()) for c in ref_match.group(2).split(",")]
    fk_match = re.search(r"FOREIGN\s+KEY\s*\(([^)]+)\)", line, re.IGNORECASE)
    if fk_match:
        source_cols = [_norm(c.strip()) for c in fk_match.group(1).split(",")]
    else:
        col_match = re.match(r"^([\"\w]+)\s+", line, re.IGNORECASE)
        source_cols = [_norm(col_match.group(1))] if col_match else []
    if not source_cols:
        return None
    return ForeignKeyDef(source_columns=source_cols, target_table=target_table, target_columns=target_cols)


def parse_postgres_schema(schema_content: str) -> NormalizedSchema:
    """Parse PostgreSQL DDL into NormalizedSchema."""
    # Pre-scan for CREATE TYPE ... AS ENUM so enum columns can be constrained.
    enum_types = _parse_pg_enum_types(schema_content)
    # Inject into table parser (simple, keeps module small)
    setattr(_parse_table_block, "_pg_enum_types", enum_types)  # type: ignore[attr-defined]
    blocks = split_create_table_blocks(schema_content, strip_prefix="")
    tables: list[TableDef] = []
    for block in blocks:
        t = _parse_table_block(block)
        if t:
            tables.append(t)
    return NormalizedSchema(
        database_type=DatabaseType.SQL,
        tables=tables,
        insert_order=topological_order(tables),
    )
