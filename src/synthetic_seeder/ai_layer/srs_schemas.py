"""Pydantic schemas for Agno agent output: strict JSON only, no markdown."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityField(BaseModel):
    """A field belonging to an entity (from SRS)."""

    name: str = Field(description="Field name as in requirements")
    data_type_hint: str = Field(default="string", description="Suggested type: string, int, float, bool, date, datetime, enum")
    optional: bool = Field(default=False, description="Whether the field can be null/absent")
    description: str | None = Field(default=None, description="Brief description from SRS")
    enum_values: list[str] | None = Field(default=None, description="If enum, list of allowed values")
    max_length: int | None = Field(default=None, description="Max length if specified")
    min_length: int | None = Field(default=None, description="Min length if specified")


class RelationshipDef(BaseModel):
    """Relationship between two entities (from SRS)."""

    from_entity: str = Field(description="Source entity/table name")
    to_entity: str = Field(description="Target entity/table name")
    relationship_type: str = Field(default="one_to_many", description="one_to_one, one_to_many, many_to_many")
    from_field: str | None = Field(default=None, description="Source field if specified")
    to_field: str | None = Field(default=None, description="Target field if specified")
    description: str | None = Field(default=None)


class StateMachineDef(BaseModel):
    """State machine or workflow states (from SRS)."""

    entity_or_field: str = Field(description="Entity or field this applies to")
    states: list[str] = Field(description="List of possible states e.g. pending, paid, cancelled")
    description: str | None = Field(default=None)


class WorkflowDef(BaseModel):
    """Workflow or process (from SRS)."""

    name: str = Field(description="Workflow name")
    steps_or_states: list[str] = Field(default_factory=list, description="Steps or states in order")
    involved_entities: list[str] = Field(default_factory=list, description="Entities involved")
    description: str | None = Field(default=None)


class ConstraintDef(BaseModel):
    """Constraint or validation rule (from SRS)."""

    entity: str = Field(description="Entity/table this applies to")
    field: str | None = Field(default=None, description="Field if constraint is field-level")
    constraint_type: str = Field(description="e.g. unique, required, range, format")
    description: str | None = Field(default=None)


class RoleDef(BaseModel):
    """Role or permission (from SRS)."""

    name: str = Field(description="Role name")
    permissions_or_scope: list[str] = Field(default_factory=list, description="Permissions or scope")
    description: str | None = Field(default=None)


class SRSEntity(BaseModel):
    """Single entity (table/collection) extracted from SRS."""

    name: str = Field(description="Entity/table name")
    fields: list[EntityField] = Field(default_factory=list)
    description: str | None = Field(default=None)
    state_fields: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map field name to list of allowed states if state machine",
    )


class SRSStructuredOutput(BaseModel):
    """
    Root schema for Agno agent output.
    Agent must return this structure only; no explanations, no markdown.
    """

    entities: list[SRSEntity] = Field(default_factory=list, description="Entities/tables identified from SRS")
    relationships: list[RelationshipDef] = Field(default_factory=list, description="Relationships between entities")
    state_machines: list[StateMachineDef] = Field(default_factory=list, description="State machines and workflows")
    workflows: list[WorkflowDef] = Field(default_factory=list, description="Workflows or processes")
    constraints: list[ConstraintDef] = Field(default_factory=list, description="Constraints and validation rules")
    roles: list[RoleDef] = Field(default_factory=list, description="Roles and permissions if present")
    enums: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Named enums: enum_name -> list of values",
    )
