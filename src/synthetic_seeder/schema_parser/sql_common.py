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


def split_create_table_blocks(
    content: str,
    strip_prefix: str = r"^\s*(?:IF\s+NOT\s+EXISTS|OR\s+REPLACE)\s+",
) -> list[str]:
    """
    Split content into per-table blocks for CREATE TABLE statements.

    Returns blocks that start at the table identifier line (i.e. text immediately after
    'CREATE TABLE') and include the full column/constraint body up to the matching ')'
    (and trailing ';' if present).

    This avoids accidentally including interleaved statements like 'CREATE TYPE ...'
    between tables, which would otherwise be mis-parsed as columns (e.g. a bogus column
    named 'CREATE').
    """
    if not content or not content.strip():
        return []

    create_iter = list(re.finditer(r"\bCREATE\s+TABLE\s+", content, flags=re.IGNORECASE))
    if not create_iter:
        return []

    blocks: list[str] = []
    for m in create_iter:
        start = m.end()
        rest = content[start:]
        # Optionally strip dialect prefix like IF NOT EXISTS / OR REPLACE immediately after CREATE TABLE
        if strip_prefix:
            rest = re.sub(strip_prefix, "", rest, flags=re.IGNORECASE)
        # Find first '(' which starts the table body
        open_idx = rest.find("(")
        if open_idx < 0:
            continue
        # Scan to matching ')'
        depth = 0
        end_idx = None
        for i, ch in enumerate(rest[open_idx:], start=open_idx):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx is None:
            continue
        # Include trailing ';' if present
        semi_idx = rest.find(";", end_idx)
        slice_end = (semi_idx + 1) if semi_idx != -1 else (end_idx + 1)
        block = rest[:slice_end].strip()
        if block:
            blocks.append(block)

    return blocks
