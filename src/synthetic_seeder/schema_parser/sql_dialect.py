"""Detect which SQL dialect a schema uses (MySQL, PostgreSQL, SQL Server)."""

from __future__ import annotations

import re
from typing import Literal

SqlDialect = Literal["mysql", "postgres", "sqlserver"]


def detect_sql_dialect(schema_content: str) -> SqlDialect:
    """
    Heuristic detection of SQL dialect from DDL text.
    Returns mysql, postgres, or sqlserver; defaults to postgres if unclear.
    """
    content = schema_content.strip()
    if not content:
        return "postgres"
    upper = content.upper()
    # SQL Server: [dbo].[TableName], IDENTITY(1,1), [col], NVARCHAR, UNIQUEIDENTIFIER
    if re.search(r"\[[\w]+\]\.\[[\w]+\]", content):
        return "sqlserver"
    if "IDENTITY" in upper and "SERIAL" not in upper:
        return "sqlserver"
    if "UNIQUEIDENTIFIER" in upper or "NVARCHAR" in upper or "DATETIME2" in upper:
        return "sqlserver"
    # MySQL: backticks, AUTO_INCREMENT, IF NOT EXISTS, ENUM, LONGTEXT
    if "`" in content:
        return "mysql"
    if "AUTO_INCREMENT" in upper:
        return "mysql"
    if re.search(r"\bIF\s+NOT\s+EXISTS\b", content, re.IGNORECASE):
        return "mysql"
    if "LONGTEXT" in upper or "MEDIUMTEXT" in upper or "ENUM(" in upper:
        return "mysql"
    # PostgreSQL: SERIAL, BIGSERIAL, JSONB, "quoted", BYTEA
    if "SERIAL" in upper or "BIGSERIAL" in upper:
        return "postgres"
    if "JSONB" in upper or "BYTEA" in upper or "TIMESTAMPTZ" in upper:
        return "postgres"
    return "postgres"
