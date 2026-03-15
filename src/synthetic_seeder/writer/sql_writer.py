"""Generate SQL seeder file: INSERT statements in FK-safe order."""

from __future__ import annotations

from typing import Any

from synthetic_seeder.schema import DatabaseType, NormalizedSchema


def escape_sql_string(s: str) -> str:
    """Escape single quotes for SQL."""
    return s.replace("'", "''")


def format_sql_value(val: Any) -> str:
    """Format a Python value for SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    if hasattr(val, "isoformat"):  # date, datetime
        return "'" + val.isoformat() + "'"
    return "'" + escape_sql_string(str(val)) + "'"


def write_sql_seeder(
    schema: NormalizedSchema,
    rows_by_table: dict[str, list[dict[str, Any]]],
    out_path: str | None = None,
) -> str:
    """
    Produce SQL seeder content (INSERTs) with parent tables before children.
    Returns the file content; if out_path is set, also writes to file.
    """
    order = schema.insert_order or [t.name for t in schema.tables]
    table_by_name = {t.name: t for t in schema.tables}
    lines = [
        "-- Generated seeder (deterministic, FK-safe order)",
        "",
    ]
    for table_name in order:
        if table_name not in rows_by_table or table_name not in table_by_name:
            continue
        table = table_by_name[table_name]
        rows = rows_by_table[table_name]
        if not rows:
            continue
        # Use schema-defined column order to avoid dropping columns that are missing in the first row.
        columns = [f.name for f in table.fields]
        cols_str = ", ".join(f'"{c}"' for c in columns)
        for row in rows:
            vals = [format_sql_value(row.get(c)) for c in columns]
            vals_str = ", ".join(vals)
            lines.append(f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({vals_str});')
        lines.append("")
    content = "\n".join(lines)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    return content


def write_sql_seeder_to_string(schema: NormalizedSchema, rows_by_table: dict[str, list[dict[str, Any]]]) -> str:
    """Convenience: return SQL content without writing to file."""
    return write_sql_seeder(schema, rows_by_table, out_path=None)
