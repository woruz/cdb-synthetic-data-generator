"""Merge Agno SRS output with DB schema and produce unified NormalizedSchema."""

from .normalizer import normalize_schema

__all__ = ["normalize_schema"]
