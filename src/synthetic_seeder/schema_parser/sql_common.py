"""Shared utilities for SQL dialect parsers. Used by MySQL, PostgreSQL, SQL Server parsers."""

from __future__ import annotations

import re
from typing import Literal

from synthetic_seeder.schema import TableDef

SqlDialect = Literal["mysql", "postgres", "sqlserver"]


def topological_order(tables: list[TableDef]) -> list[str]:
    """Order table names so parents come before children (FK order)."""
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


def normalize_identifier(name: str, dialect: SqlDialect) -> str:
    """Strip dialect-specific quoting to get bare identifier."""
    s = name.strip()
    if len(s) < 2:
        return s
    if dialect == "sqlserver":
        if s.startswith("[") and s.endswith("]"):
            return s[1:-1]
    elif dialect == "mysql":
        if s.startswith("`") and s.endswith("`"):
            return s[1:-1]
    elif dialect == "postgres":
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
    # Fallback: strip any of the three styles
    for left, right in [('"', '"'), ("'", "'"), ("[", "]"), ("`", "`")]:
        if s.startswith(left) and s.endswith(right):
            return s[1:-1]
    return s


def parse_length(sql_type: str) -> int | None:
    """Extract max length from e.g. VARCHAR(255)."""
    m = re.search(r"\((\d+)\)", sql_type)
    return int(m.group(1)) if m else None


def split_create_table_blocks(content: str, strip_prefix: str = r"^\s*(?:IF\s+NOT\s+EXISTS|OR\s+REPLACE)\s+") -> list[str]:
    """Split content into per-table blocks (CREATE TABLE ...)."""
    parts = re.split(r"\bCREATE\s+TABLE\s+", content, flags=re.IGNORECASE)
    result = []
    for p in parts[1:]:
        rest = re.sub(strip_prefix, "", p, flags=re.IGNORECASE) if strip_prefix else p
        end = re.search(r"\bCREATE\s+TABLE\s+", rest, re.IGNORECASE)
        block = rest[: end.start()].strip() if end else rest.strip()
        if block:
            result.append(block)
    return result
