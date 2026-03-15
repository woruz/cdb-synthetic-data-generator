"""Detect database schema type from raw schema content."""

from __future__ import annotations

from synthetic_seeder.schema import DatabaseType


def detect_schema_type(schema_content: str) -> DatabaseType:
    """
    Heuristic detection: SQL vs MongoDB vs unknown.
    SQL: CREATE TABLE, columns with types, REFERENCES, etc.
    MongoDB: collection, BSON, insertMany, db., schema with type "object", etc.
    """
    content = schema_content.strip().upper()
    if not content:
        return DatabaseType.UNKNOWN
    # MongoDB indicators
    mongo_indicators = [
        "COLLECTION",
        "DB.",
        "INSERTMANY",
        "BSON",
        '"TYPE":',
        "'TYPE':",
        "OBJECTID",
        "DOCUMENT(",
    ]
    for ind in mongo_indicators:
        if ind in content:
            return DatabaseType.MONGODB
    # SQL indicators
    sql_indicators = [
        "CREATE TABLE",
        "CREATE INDEX",
        "REFERENCES ",
        "PRIMARY KEY",
        "FOREIGN KEY",
        "INT ",
        "VARCHAR",
        "NOT NULL",
        "ALTER TABLE",
    ]
    for ind in sql_indicators:
        if ind in content:
            return DatabaseType.SQL
    # JSON schema style often used for MongoDB
    if content.startswith("{") and ("OBJECT" in content or "BSON" in content or "COLLECTION" in content):
        return DatabaseType.MONGODB
    return DatabaseType.UNKNOWN
