"""Validate generated seed data against normalized schema. Strict: no invalid enum, null, empty, or out-of-range."""

from __future__ import annotations

from typing import Any

from synthetic_seeder.schema import NormalizedSchema, TableDef


def validate_rows(
    schema: NormalizedSchema,
    rows_by_table: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """
    Validate that generated rows conform to schema.
    Returns list of error messages; empty if valid.
    - NOT NULL: never null, never empty string.
    - Enum: value must be exactly in enum_values.
    - String: length <= max_length.
    - Numeric: within min_value/max_value if defined.
    - Boolean: must be bool type.
    """
    errors: list[str] = []
    table_by_name = {t.name: t for t in schema.tables}
    for table_name, rows in rows_by_table.items():
        if table_name not in table_by_name:
            errors.append(f"Unknown table: {table_name}")
            continue
        table = table_by_name[table_name]
        field_by_name = {f.name: f for f in table.fields}
        for i, row in enumerate(rows):
            for col, val in row.items():
                if col not in field_by_name:
                    continue
                f = field_by_name[col]
                if val is None:
                    if not f.nullable:
                        errors.append(f"{table_name}[{i}].{col}: null but field is NOT NULL")
                    continue
                if not f.nullable and isinstance(val, str) and val == "":
                    errors.append(f"{table_name}[{i}].{col}: empty string not allowed for NOT NULL")
                if f.enum_values and str(val) not in f.enum_values:
                    errors.append(f"{table_name}[{i}].{col}: value '{val}' not in enum {f.enum_values}")
                if f.data_type == "int":
                    try:
                        nval = int(val) if val is not None else None
                    except (TypeError, ValueError):
                        nval = None
                    if val is not None and nval is None:
                        errors.append(f"{table_name}[{i}].{col}: expected int, got {type(val).__name__}")
                    elif nval is not None:
                        if f.min_value is not None and nval < f.min_value:
                            errors.append(f"{table_name}[{i}].{col}: {nval} < min_value {f.min_value}")
                        if f.max_value is not None and nval > f.max_value:
                            errors.append(f"{table_name}[{i}].{col}: {nval} > max_value {f.max_value}")
                if f.data_type == "float":
                    try:
                        nval = float(val) if val is not None else None
                    except (TypeError, ValueError):
                        nval = None
                    if val is not None and nval is None:
                        errors.append(f"{table_name}[{i}].{col}: expected number, got {type(val).__name__}")
                    elif nval is not None:
                        if f.min_value is not None and nval < f.min_value:
                            errors.append(f"{table_name}[{i}].{col}: {nval} < min_value {f.min_value}")
                        if f.max_value is not None and nval > f.max_value:
                            errors.append(f"{table_name}[{i}].{col}: {nval} > max_value {f.max_value}")
                if f.data_type in ("bool", "boolean") and not isinstance(val, bool):
                    errors.append(f"{table_name}[{i}].{col}: expected bool, got {type(val).__name__}")
                if f.max_length is not None and isinstance(val, str) and len(val) > f.max_length:
                    errors.append(f"{table_name}[{i}].{col}: length {len(val)} > max_length {f.max_length}")
    return errors
