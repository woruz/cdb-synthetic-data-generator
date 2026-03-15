"""Generate MongoDB seeder script using insertMany()."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from synthetic_seeder.schema import NormalizedSchema


def _mongo_serialize(val: Any) -> Any:
    """Convert Python values to JSON-serializable for MongoDB."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return {"$date": val.isoformat()}
    if isinstance(val, (list, tuple)):
        return [_mongo_serialize(v) for v in val]
    if isinstance(val, dict):
        return {k: _mongo_serialize(v) for k, v in val.items()}
    return val


def write_mongo_seeder(
    schema: NormalizedSchema,
    rows_by_table: dict[str, list[dict[str, Any]]],
    out_path: str | None = None,
    db_name: str = "db",
) -> str:
    """
    Produce MongoDB seed script (insertMany) with logical collection order.
    Returns the script content; if out_path is set, writes to file.
    """
    order = schema.insert_order or [t.name for t in schema.tables]
    lines = [
        "// Generated MongoDB seeder (deterministic)",
        "// Run with: mongosh <connection> < this_file.js",
        "",
        f"const db = db.getSiblingDB('{db_name}');",
        "",
    ]
    for coll_name in order:
        if coll_name not in rows_by_table:
            continue
        rows = rows_by_table[coll_name]
        if not rows:
            continue
        docs = []
        for row in rows:
            doc = _mongo_serialize(row)
            docs.append(doc)
        docs_json = json.dumps(docs, indent=2, default=str)
        lines.append(f"db.getCollection('{coll_name}').insertMany(")
        for seg in docs_json.split("\n"):
            lines.append(seg)
        lines.append(");")
        lines.append("")
    content = "\n".join(lines)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    return content


def write_mongo_seeder_to_string(
    schema: NormalizedSchema,
    rows_by_table: dict[str, list[dict[str, Any]]],
    db_name: str = "db",
) -> str:
    """Convenience: return MongoDB script content without writing to file."""
    return write_mongo_seeder(schema, rows_by_table, out_path=None, db_name=db_name)
