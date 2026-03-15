"""Internal schema models: schema-agnostic representation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DatabaseType(str, Enum):
    """Detected database type for output generation."""

    SQL = "sql"
    MONGODB = "mongodb"
    UNKNOWN = "unknown"


class FieldDef(BaseModel):
    """Single column/field definition. All constraints must be respected by the generator."""

    name: str
    data_type: str = "string"
    nullable: bool = True
    default: Any = None
    max_length: int | None = None
    min_length: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    enum_values: list[str] | None = None
    is_primary_key: bool = False
    is_auto_increment: bool = False
    is_unique: bool = False
    description: str | None = None


class UniqueKeyDef(BaseModel):
    """Unique constraint (single or composite)."""

    name: str | None = None
    columns: list[str]


class ForeignKeyDef(BaseModel):
    """Foreign key relationship."""

    name: str | None = None
    source_columns: list[str]
    target_table: str
    target_columns: list[str]
    on_delete: str | None = None
    on_update: str | None = None


class IndexDef(BaseModel):
    """Index definition."""

    name: str | None = None
    columns: list[str]
    unique: bool = False


class TableDef(BaseModel):
    """Table or collection definition."""

    name: str
    fields: list[FieldDef] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)
    unique_keys: list[UniqueKeyDef] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyDef] = Field(default_factory=list)
    indexes: list[IndexDef] = Field(default_factory=list)
    description: str | None = None
    state_fields: dict[str, list[str]] = Field(default_factory=dict)
    role_hints: list[str] = Field(default_factory=list)


class NormalizedSchema(BaseModel):
    """Unified internal schema."""

    database_type: DatabaseType = DatabaseType.UNKNOWN
    tables: list[TableDef] = Field(default_factory=list)
    insert_order: list[str] | None = None
