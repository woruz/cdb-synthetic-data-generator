"""Seed plan models: scenarios and per-table plans produced by AI, consumed by deterministic generator."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SeedScenario(BaseModel):
    """High-level scenario/user story the seed data should cover."""

    name: str = Field(description="Scenario name, e.g. 'customer_places_order'")
    description: str | None = Field(default=None, description="Human-readable description of the flow")
    involved_entities: list[str] = Field(
        default_factory=list,
        description="Entity/table names involved in this scenario (schema names, case-insensitive)",
    )


class TableSeedPlan(BaseModel):
    """Seed coverage plan for a single table."""

    table_name: str = Field(description="Exact table/collection name from the normalized schema")
    # Target number of rows to generate for this table (minimum; generator may add a few more
    # for relationship coverage or additional edge cases).
    target_rows: int = Field(default=0, ge=0)

    # Coverage hints
    cover_all_enum_values: bool = Field(
        default=True,
        description="Ensure at least one row per enum value for enum/state fields.",
    )
    include_boundary_values: bool = Field(
        default=True,
        description="Generate min/max/zero boundary values for numeric and length-constrained fields.",
    )
    include_null_cases: bool = Field(
        default=True,
        description="Include rows where nullable fields are explicitly set to NULL.",
    )

    # Relationship hints
    min_children_per_parent: int = Field(
        default=1,
        ge=0,
        description="Desired minimum children per parent for fk-child tables (may be approximated).",
    )


class SeedPlan(BaseModel):
    """Global seed plan produced by AI and consumed by deterministic generator."""

    scenarios: list[SeedScenario] = Field(default_factory=list)
    tables: list[TableSeedPlan] = Field(default_factory=list)

    def table_plan_for(self, table_name: str) -> TableSeedPlan | None:
        key = table_name.strip().lower()
        for plan in self.tables:
            if plan.table_name.strip().lower() == key:
                return plan
        return None

