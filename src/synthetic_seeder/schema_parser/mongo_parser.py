"""Parse MongoDB schema (JSON schema or collection docs) into NormalizedSchema."""

from __future__ import annotations

import json
import re

from synthetic_seeder.schema import (
    DatabaseType,
    FieldDef,
    ForeignKeyDef,
    NormalizedSchema,
    TableDef,
)
from synthetic_seeder.schema_parser.sql_common import topological_order


def _json_type_to_internal(js: str) -> str:
    """Map JSON schema type to internal data_type."""
    m = {
        "string": "string",
        "number": "float",
        "integer": "int",
        "boolean": "bool",
        "object": "string",
        "array": "string",
        "date": "date",
        "datetime": "datetime",
    }
    return m.get(js.lower(), "string")


def parse_mongo_schema(schema_content: str) -> NormalizedSchema:
    """
    Parse MongoDB-style schema (JSON schema or list of collection names with optional BSON).
    Accepts:
    - JSON object with collection names as keys and schema as value
    - JSON array of { "name": "collectionName", "schema": {...} }
    - Simple list of collection names in text
    """
    content = schema_content.strip()
    tables: list[TableDef] = []

    # Try JSON
    if content.startswith("{") or content.startswith("["):
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                collections = data.get("collections")
                if isinstance(collections, list):
                    for coll in collections:
                        if isinstance(coll, dict):
                            name = coll.get("name") or coll.get("collection")
                            if not name:
                                continue
                            schema = coll.get("fields") or {}
                            # Convert fields map to properties-like format
                            props = {k: {"type": v} for k, v in schema.items()}
                            tables.append(_table_from_mongo_schema(str(name), {"properties": props}))
                    # done
                else:
                    for coll_name, schema in data.items():
                        if isinstance(schema, dict):
                            tables.append(_table_from_mongo_schema(coll_name, schema))
                        else:
                            tables.append(TableDef(name=coll_name, fields=[]))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("collection") or "unknown"
                        schema = item.get("schema") or item.get("properties") or {}
                        tables.append(_table_from_mongo_schema(str(name), schema))
                    elif isinstance(item, str):
                        tables.append(TableDef(name=item, fields=[]))
        except json.JSONDecodeError:
            pass

    if not tables and content:
        # Fallback: line-based collection names or "collection: name"
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"(?:collection|db\.)\s*[.:]?\s*[\"]?(\w+)[\"]?", line, re.IGNORECASE)
            if m:
                tables.append(TableDef(name=m.group(1), fields=[]))
            elif re.match(r"^\w+$", line):
                tables.append(TableDef(name=line, fields=[]))

    # Parent collections before children when refs/FKs are present
    insert_order = topological_order(tables) if tables else []
    return NormalizedSchema(
        database_type=DatabaseType.MONGODB,
        tables=tables if tables else [TableDef(name="collection1", fields=[])],
        insert_order=insert_order,
    )


def _parse_ref(ref: str) -> tuple[str, str] | None:
    """Parse 'collection.field' or 'collection' (default field = same as first PK convention). Returns (target_table, target_field) or None."""
    if not ref or not isinstance(ref, str):
        return None
    ref = ref.strip()
    if "." in ref:
        parts = ref.split(".", 1)
        return (parts[0].strip(), parts[1].strip())
    return (ref.strip(), "")  # target_table only; caller can use source field name


def _table_from_mongo_schema(collection_name: str, schema: dict) -> TableDef:
    """Build TableDef from a JSON-schema-like or BSON-like schema. Supports optional 'ref' for FK-style references."""
    fields: list[FieldDef] = []
    foreign_keys: list[ForeignKeyDef] = []
    props = schema.get("properties") or schema.get("bsonType") or schema
    if isinstance(props, str):
        return TableDef(name=collection_name, fields=[])
    if not isinstance(props, dict):
        return TableDef(name=collection_name, fields=[])

    required = schema.get("required") or []
    for field_name, spec in props.items():
        if not isinstance(spec, dict):
            spec = {}
        bson = spec.get("bsonType") or spec.get("type")
        if isinstance(bson, list):
            bson = bson[0] if bson else "string"
        type_str = _json_type_to_internal(str(bson)) if bson else "string"
        enum_vals = spec.get("enum")
        if isinstance(enum_vals, list):
            enum_vals = [str(v) for v in enum_vals]
        else:
            enum_vals = None
        nullable = field_name not in required
        # JSON Schema uses maxLength (camelCase); accept both for robustness
        max_length = spec.get("maxLength") or spec.get("max_length")
        if max_length is not None and not isinstance(max_length, int):
            max_length = None
        min_length = spec.get("minLength") or spec.get("min_length")
        if min_length is not None and not isinstance(min_length, int):
            min_length = None
        # String fields without maxLength: default cap so generator/validator stay in bounds.
        if type_str == "string" and max_length is None:
            max_length = 128
        # Number bounds from JSON Schema minimum/maximum
        min_value = spec.get("minimum") if isinstance(spec.get("minimum"), (int, float)) else None
        max_value = spec.get("maximum") if isinstance(spec.get("maximum"), (int, float)) else None
        fields.append(
            FieldDef(
                name=field_name,
                data_type=type_str,
                nullable=nullable,
                max_length=max_length,
                min_length=min_length,
                min_value=min_value,
                max_value=max_value,
                enum_values=enum_vals,
                description=spec.get("description"),
            )
        )
        # Optional ref: "ref": "collection.field" or "ref": "collection" → FK so generator uses parent IDs
        ref_val = spec.get("ref") or spec.get("$ref")
        if ref_val and isinstance(ref_val, str):
            parsed = _parse_ref(ref_val)
            if parsed:
                target_table, target_field = parsed
                target_col = target_field if target_field else field_name  # same name if only collection given
                foreign_keys.append(
                    ForeignKeyDef(
                        source_columns=[field_name],
                        target_table=target_table,
                        target_columns=[target_col],
                    )
                )

    # Logical primary key for Mongo: first required field (so generator can store and resolve refs)
    primary_key: list[str] = []
    for f in required:
        if any(x.name == f for x in fields):
            primary_key.append(f)
            break

    return TableDef(
        name=collection_name,
        fields=fields,
        primary_key=primary_key,
        foreign_keys=foreign_keys,
    )
