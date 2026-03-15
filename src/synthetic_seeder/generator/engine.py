"""Deterministic seed data generation engine: rule-based, no AI. Supports random and edge-case strategies."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from synthetic_seeder.config import GeneratorConfig
from synthetic_seeder.schema import FieldDef, NormalizedSchema, TableDef
from synthetic_seeder.generator.value_gen import (
    gen_boundary_value,
    gen_value_for_field,
    make_rng,
)


def _gen_field_value(
    field: FieldDef,
    table_name: str,
    rng: Any,
    config: GeneratorConfig,
    null_chance: float = 0.2,
    row_index: int | None = None,
) -> Any:
    """Generate a value for one field; strictly respects enum, nullability, length, and numeric bounds."""
    prefix_override = None
    if field.is_unique and (field.data_type or "string").lower() == "string" and row_index is not None:
        prefix_override = f"{field.name[:8]}_{row_index}_"
    return gen_value_for_field(
        field.name,
        field.data_type,
        rng,
        nullable=field.nullable,
        enum_values=field.enum_values,
        max_length=field.max_length,
        min_length=field.min_length,
        min_value=getattr(field, "min_value", None),
        max_value=getattr(field, "max_value", None),
        null_chance=null_chance,
        prefix_override=prefix_override,
        semantic_pool=getattr(config, "semantic_pools", {}).get(table_name, {}).get(field.name),
    )
from synthetic_seeder.generator.coverage import (
    build_coverage_plan,
    child_table_coverage_count,
    RowSpec,
)


def generate_seed_data(
    schema: NormalizedSchema,
    config: GeneratorConfig | None = None,
    semantic_pools: dict[str, dict[str, list[Any]]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Generate deterministic seed rows per table.
    - strategy=random: fixed row count with optional boundary/null/state tweaks.
    - strategy=edge-case: coverage-based (enum, state, boundary, null, relationship).
    - Respects FK order; uses config seed for reproducibility.
    """
    config = config or GeneratorConfig()
    # Temporary inject pools into config object for internal use
    setattr(config, "semantic_pools", semantic_pools or {})
    rng = make_rng(config.seed)
    tables = schema.tables
    order = schema.insert_order or [t.name for t in tables]
    table_by_name = {t.name: t for t in tables}
    rows_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pk_values: dict[str, list[tuple[list[str], list[Any]]]] = defaultdict(list)

    if config.strategy == "edge-case":
        _generate_edge_case(
            order, table_by_name, table_by_name, pk_values, rows_by_table, config, rng
        )
    else:
        _generate_random(
            order, table_by_name, pk_values, rows_by_table, config, rng
        )

    return dict(rows_by_table)


def _generate_random(
    order: list[str],
    table_by_name: dict[str, TableDef],
    pk_values: dict[str, list[tuple[list[str], list[Any]]]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    config: GeneratorConfig,
    rng: Any,
) -> None:
    """Row-based generation (original behavior)."""
    for table_name in order:
        if table_name not in table_by_name:
            continue
        table = table_by_name[table_name]
        pk_cols = table.primary_key or _infer_pk(table)
        num_rows = max(1, 2 * config.row_multiplier)
        if config.include_state_variations and table.state_fields:
            num_rows = max(num_rows, 4)
        if config.include_boundary_cases:
            num_rows = max(num_rows, 3)
        if config.include_null_cases:
            num_rows = max(num_rows, 2)
        for i in range(num_rows):
            row, pk_vals = _generate_row(
                table, rng, config, pk_values, i, field_overrides=None, boundary_kind=None
            )
            if row is not None:
                rows_by_table[table_name].append(row)
                if pk_cols and pk_vals is not None:
                    pk_values[table_name].append((pk_cols, pk_vals))


def _generate_edge_case(
    order: list[str],
    table_by_name: dict[str, TableDef],
    tables_by_name: dict[str, TableDef],
    pk_values: dict[str, list[tuple[list[str], list[Any]]]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    config: GeneratorConfig,
    rng: Any,
) -> None:
    """Coverage-based generation: enum, state, boundary, null, relationship."""
    for table_name in order:
        if table_name not in table_by_name:
            continue
        table = table_by_name[table_name]
        pk_cols = table.primary_key or _infer_pk(table)
        plan = build_coverage_plan(table, config.min_children_per_parent)

        parent_count = 0
        for fk in table.foreign_keys:
            parent_count = len(pk_values.get(fk.target_table, []))
            if parent_count > 0:
                break
        num_rows = child_table_coverage_count(
            parent_count, plan.min_children_per_parent, plan.num_rows
        )

        parent_indices = _distribute_children_over_parents(
            num_rows, parent_count, plan.min_children_per_parent, rng
        )

        for i in range(num_rows):
            spec = plan.row_specs[i % len(plan.row_specs)] if plan.row_specs else RowSpec()
            overrides = dict(spec.field_overrides) if spec.field_overrides else None
            boundary = spec.boundary_kind
            parent_idx = parent_indices[i] if parent_indices is not None else None
            row, pk_vals = _generate_row(
                table,
                rng,
                config,
                pk_values,
                i,
                field_overrides=overrides,
                boundary_kind=boundary,
                force_parent_index=parent_idx,
            )
            if row is not None:
                rows_by_table[table_name].append(row)
                if pk_cols and pk_vals is not None:
                    pk_values[table_name].append((pk_cols, pk_vals))


def _distribute_children_over_parents(
    num_rows: int,
    parent_count: int,
    min_children_per_parent: int,
    rng: Any,
) -> list[int] | None:
    """Return list of parent indices per row so each parent gets at least min_children_per_parent."""
    if parent_count <= 0:
        return None
    indices = []
    for p in range(parent_count):
        for _ in range(min_children_per_parent):
            indices.append(p)
    while len(indices) < num_rows:
        indices.append(rng.randint(0, parent_count - 1))
    rng.shuffle(indices)
    return indices[:num_rows]


def _infer_pk(table: TableDef) -> list[str]:
    """Infer primary key: explicit PK or first unique/auto field or 'id'."""
    if table.primary_key:
        return table.primary_key
    for f in table.fields:
        if f.is_primary_key:
            return [f.name]
        if f.name.lower() == "id" and (f.is_auto_increment or f.data_type == "int"):
            return [f.name]
    return []


def _generate_row(
    table: TableDef,
    rng: Any,
    config: GeneratorConfig,
    pk_values: dict[str, list[tuple[list[str], list[Any]]]],
    row_index: int,
    *,
    field_overrides: dict[str, Any] | None = None,
    boundary_kind: str | None = None,
    force_parent_index: int | None = None,
) -> tuple[dict[str, Any] | None, list[Any] | None]:
    """Generate one row. Optional overrides and boundary_kind for edge-case strategy."""
    row: dict[str, Any] = {}
    overrides = field_overrides or {}
    pk_cols = table.primary_key or _infer_pk(table)

    for field in table.fields:
        if field.name in overrides:
            val = overrides[field.name]
            if field.enum_values and val not in field.enum_values:
                val = _gen_field_value(field, table.name, rng, config, null_chance=0.0, row_index=row_index)
            row[field.name] = val
            continue

        fk = _find_fk_for_column(table, field.name)
        if fk:
            parent_rows = pk_values.get(fk.target_table, [])
            if parent_rows:
                if force_parent_index is not None and 0 <= force_parent_index < len(parent_rows):
                    _, ref_pk = parent_rows[force_parent_index]
                else:
                    _, ref_pk = rng.choice(parent_rows)
                if len(fk.source_columns) == 1 and len(ref_pk) == 1:
                    row[field.name] = ref_pk[0]
                else:
                    for sc, rv in zip(fk.source_columns, ref_pk):
                        row[sc] = rv
            else:
                val = _gen_field_value(field, table.name, rng, config, null_chance=0.0, row_index=row_index)
                row[field.name] = val
            continue

        if field.is_auto_increment:
            row[field.name] = row_index + 1
            continue

        if boundary_kind == "null" and field.nullable:
            row[field.name] = None
            continue
        if boundary_kind in ("min", "max"):
            kind = "max_length" if boundary_kind == "max" and field.data_type == "string" and field.max_length else boundary_kind
            if boundary_kind == "min" and field.data_type == "string" and not field.enum_values:
                kind = "empty" if field.nullable else "min"
            unique_suffix = row_index if field.is_unique else None
            row[field.name] = gen_boundary_value(
                field.name,
                field.data_type,
                kind,
                enum_values=field.enum_values,
                max_length=field.max_length,
                min_length=field.min_length,
                min_value=getattr(field, "min_value", None),
                max_value=getattr(field, "max_value", None),
                nullable=field.nullable,
                unique_suffix=unique_suffix,
            )
            continue

        if field.enum_values:
            row[field.name] = _gen_field_value(field, table.name, rng, config, null_chance=0.25 if config.include_null_cases else 0.0, row_index=row_index)
            continue
        if field.name in table.state_fields and table.state_fields[field.name]:
            states = table.state_fields[field.name]
            if field.enum_values:
                states = [s for s in states if s in field.enum_values]
            row[field.name] = rng.choice(states) if states else _gen_field_value(field, table.name, rng, config, null_chance=0.0, row_index=row_index)
            continue

        val = _gen_field_value(
            field, table.name, rng, config, null_chance=0.25 if config.include_null_cases else 0.0, row_index=row_index
        )
        row[field.name] = val

    for f in table.fields:
        if f.name not in row:
            row[f.name] = _gen_field_value(f, table.name, rng, config, null_chance=0.1, row_index=row_index)

    # Safeguard: NOT NULL columns must never be null (e.g. enum columns the parser missed, or boundary row)
    for f in table.fields:
        if not f.nullable and row.get(f.name) is None:
            row[f.name] = _gen_field_value(f, table.name, rng, config, null_chance=0.0, row_index=row_index)

    pk_vals_ordered = [row.get(c) for c in pk_cols] if pk_cols else None
    return row, pk_vals_ordered


def _find_fk_for_column(table: TableDef, column_name: str):
    """Return FK that has column_name as source."""
    for fk in table.foreign_keys:
        if column_name in fk.source_columns:
            return fk
    return None
