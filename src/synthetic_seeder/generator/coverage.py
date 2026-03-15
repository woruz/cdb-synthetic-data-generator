"""Coverage plan for edge-case strategy: enum, state, boundary, null, relationship."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from synthetic_seeder.schema import TableDef


@dataclass
class RowSpec:
    """Spec for one row in coverage plan: optional overrides per field."""

    field_overrides: dict[str, Any] = field(default_factory=dict)
    boundary_kind: str | None = None  # "min" | "max" | "null"
    row_index: int = 0


@dataclass
class TableCoveragePlan:
    """How many rows to generate for a table and what each row must cover."""

    table_name: str
    num_rows: int
    row_specs: list[RowSpec]
    min_children_per_parent: int = 0


def build_coverage_plan(table: TableDef, min_children_per_parent: int = 2) -> TableCoveragePlan:
    """
    Build a coverage plan for one table: enum/state coverage, boundary rows, null row.
    Does not consider FK parent count; caller (engine) ensures child count from parent rows.
    """
    row_specs: list[RowSpec] = []
    enum_state_fields: list[tuple[str, list[str]]] = []

    for f in table.fields:
        if f.enum_values:
            enum_state_fields.append((f.name, list(f.enum_values)))
        elif f.name in table.state_fields and table.state_fields[f.name]:
            enum_state_fields.append((f.name, list(table.state_fields[f.name])))

    n_enum_rows = 0
    if enum_state_fields:
        n_enum_rows = max(len(values) for _, values in enum_state_fields)
        for i in range(n_enum_rows):
            overrides = {}
            for field_name, values in enum_state_fields:
                overrides[field_name] = values[i % len(values)]
            row_specs.append(RowSpec(field_overrides=overrides, row_index=i))

    boundary_start = len(row_specs)
    row_specs.append(RowSpec(boundary_kind="min", row_index=boundary_start))
    row_specs.append(RowSpec(boundary_kind="max", row_index=boundary_start + 1))
    row_specs.append(RowSpec(boundary_kind="null", row_index=boundary_start + 2))

    num_rows = len(row_specs)
    return TableCoveragePlan(
        table_name=table.name,
        num_rows=num_rows,
        row_specs=row_specs,
        min_children_per_parent=min_children_per_parent,
    )


def child_table_coverage_count(
    parent_pk_count: int,
    min_children_per_parent: int,
    base_plan_rows: int,
) -> int:
    """Required child rows so that each parent has at least min_children_per_parent children."""
    return max(base_plan_rows, parent_pk_count * min_children_per_parent)
