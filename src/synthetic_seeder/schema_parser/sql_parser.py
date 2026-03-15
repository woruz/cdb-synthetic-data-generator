"""SQL schema parser: dispatches to dialect-specific parsers (MySQL, PostgreSQL, SQL Server)."""

from __future__ import annotations

from typing import Literal

from synthetic_seeder.schema import NormalizedSchema

from .mysql_parser import parse_mysql_schema
from .postgres_parser import parse_postgres_schema
from .sql_dialect import detect_sql_dialect
from .sqlserver_parser import parse_sqlserver_schema

SqlDialect = Literal["mysql", "postgres", "sqlserver"]

_PARSERS = {
    "mysql": parse_mysql_schema,
    "postgres": parse_postgres_schema,
    "sqlserver": parse_sqlserver_schema,
}


def parse_sql_schema(
    schema_content: str,
    dialect: SqlDialect | None = None,
) -> NormalizedSchema:
    """
    Parse SQL DDL into NormalizedSchema.
    If dialect is None, it is auto-detected from the schema content.
    """
    if dialect is None:
        dialect = detect_sql_dialect(schema_content)
    parser = _PARSERS.get(dialect, parse_postgres_schema)
    return parser(schema_content)


# Re-export for callers that want to pass a dialect hint
__all__ = ["parse_sql_schema", "detect_sql_dialect", "SqlDialect"]
