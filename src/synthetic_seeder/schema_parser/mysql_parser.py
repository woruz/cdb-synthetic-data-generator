"""MySQL DDL parser. Handles backticks, AUTO_INCREMENT, IF NOT EXISTS, MySQL types."""

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

DIALECT = "mysql"

_MYSQL_TYPE_MAP = {
    "INT": "int", "INTEGER": "int", "BIGINT": "int", "SMALLINT": "int",
    "TINYINT": "int", "MEDIUMINT": "int",
    "FLOAT": "float", "DOUBLE": "float", "REAL": "float",
    "DECIMAL": "float", "NUMERIC": "float",
    "BOOLEAN": "bool", "BOOL": "bool",
    "DATE": "date", "DATETIME": "datetime", "TIMESTAMP": "datetime", "TIME": "string",
    "TEXT": "string", "VARCHAR": "string", "CHAR": "string", "CHARACTER": "string",
    "LONGTEXT": "string", "MEDIUMTEXT": "string", "TINYTEXT": "string",
    "JSON": "string", "BLOB": "string", "ENUM": "string", "SET": "string",
}


def _normalize_type(sql_type: str) -> str:
    upper = sql_type.upper().strip()
    base = re.sub(r"\([^)]*\)", "", upper).strip()
    return _MYSQL_TYPE_MAP.get(base, "string")


def _norm(name: str) -> str:
    return normalize_identifier(name, DIALECT)


def _parse_enum_values(col_type: str) -> list[str] | None:
    """Extract ENUM('a','b','c') or SET('a','b') values from MySQL type."""
    m = re.search(r"ENUM\s*\(([^)]+)\)", col_type, re.IGNORECASE)
    if not m:
        m = re.search(r"SET\s*\(([^)]+)\)", col_type, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1)
    values = []
    for part in re.findall(r"'([^']*)'|\"([^\"]*)\"", raw):
        values.append((part[0] or part[1]).strip())
    return values if values else None


def _parse_table_block(block: str) -> TableDef | None:
    lines = [s.strip() for s in block.split("\n")]
    if not lines:
        return None
    first = lines[0]
    name_match = re.match(r"((?:[\w.]+\.)?[`\w]+)\s*\(?", first, re.IGNORECASE)
    if not name_match:
        return None
    raw = name_match.group(1)
    table_name = _norm(raw.split(".")[-1] if "." in raw else raw)
    fields: list[FieldDef] = []
    primary_key: list[str] = []
    unique_keys: list[UniqueKeyDef] = []
    foreign_keys: list[ForeignKeyDef] = []

    for line in lines[1:]:
        line = line.rstrip(",").strip()
        if not line or line.startswith(")"):
            continue
        upper = line.upper()
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
        if "REFERENCES" in upper or upper.startswith("FOREIGN KEY"):
            fk = _parse_fk(line)
            if fk:
                foreign_keys.append(fk)
            continue
        col_match = re.match(r"^([`\w]+)\s+(\S+(?:\s*\([^)]*\))?)\s*(.*)$", line, re.IGNORECASE)
        if col_match:
            col_name = _norm(col_match.group(1))
            col_type = col_match.group(2)
            rest = col_match.group(3).upper()
            nullable = "NOT NULL" not in rest
            is_pk = "PRIMARY KEY" in rest
            is_auto = "AUTO_INCREMENT" in rest
            is_unique = "UNIQUE" in rest
            if is_pk:
                primary_key.append(col_name)
            enum_vals = _parse_enum_values(col_type)
            fields.append(
                FieldDef(
                    name=col_name,
                    data_type=_normalize_type(col_type),
                    nullable=nullable,
                    max_length=parse_length(col_type),
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
        col_match = re.match(r"^([`\w]+)\s+", line, re.IGNORECASE)
        source_cols = [_norm(col_match.group(1))] if col_match else []
    if not source_cols:
        return None
    return ForeignKeyDef(source_columns=source_cols, target_table=target_table, target_columns=target_cols)


def parse_mysql_schema(schema_content: str) -> NormalizedSchema:
    """Parse MySQL DDL into NormalizedSchema."""
    blocks = split_create_table_blocks(
        schema_content,
        strip_prefix=r"^\s*(?:IF\s+NOT\s+EXISTS|OR\s+REPLACE)\s+",
    )
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
