"""AI agent to align SRS entities/fields with schema tables/columns."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from synthetic_seeder.schema import NormalizedSchema
from synthetic_seeder.ai_layer.srs_schemas import SRSStructuredOutput


class FieldAlignment(BaseModel):
    srs_field: str
    column: str


class EntityAlignment(BaseModel):
    srs_entity: str
    table: str
    fields: list[FieldAlignment] = Field(default_factory=list)


class AlignmentResult(BaseModel):
    entities: list[EntityAlignment] = Field(default_factory=list)

    def table_for_entity(self, entity_name: str) -> str | None:
        key = entity_name.strip().lower()
        for e in self.entities:
            if e.srs_entity.strip().lower() == key:
                return e.table
        return None


def align_srs_to_schema(
    srs: SRSStructuredOutput,
    schema: NormalizedSchema,
    *,
    llm_provider: str = "openai",
    model_id: str = "gpt-4o-mini",
) -> AlignmentResult:
    """
    Use Agno/OpenAI to align SRS entities and fields to schema tables and columns.
    Returns a structured AlignmentResult. If the AI call fails, returns a best-effort
    heuristic alignment (simple name-based matches).
    """
    # First build a simple heuristic alignment as a fallback / hint
    heuristic = _heuristic_alignment(srs, schema)

    try:
        from agno.agent import Agent
        from agno.models.openai import OpenAIResponses
    except ImportError:
        return heuristic

    system = (
        "You are a database alignment assistant.\n"
        "Given a parsed SRS (entities and fields) and a parsed database schema "
        "(tables and columns), you must map each SRS entity to a table, and "
        "each SRS field to a column, where possible.\n"
        "Return ONLY JSON matching the AlignmentResult schema: "
        "{ 'entities': [ { 'srs_entity': str, 'table': str, 'fields': ["
        "{ 'srs_field': str, 'column': str } ] } ] }."
    )

    model = OpenAIResponses(id=model_id, temperature=0)
    agent = Agent(
        model=model,
        instructions=system,
        output_schema=AlignmentResult,
        markdown=False,
    )

    prompt = {
        "srs_entities": [e.model_dump() for e in srs.entities],
        "schema_tables": [
            {
                "name": t.name,
                "columns": [f.name for f in t.fields],
            }
            for t in schema.tables
        ],
    }

    try:
        resp = agent.run(prompt)
        if isinstance(resp.content, AlignmentResult):
            return resp.content
        if isinstance(getattr(resp, "content", None), dict):
            return AlignmentResult.model_validate(resp.content)
        return heuristic
    except Exception:
        return heuristic


def _heuristic_alignment(srs: SRSStructuredOutput, schema: NormalizedSchema) -> AlignmentResult:
    """Fallback alignment using simple name-based matching (case-insensitive)."""
    entities: list[EntityAlignment] = []
    tables_by_name = {t.name.strip().lower(): t for t in schema.tables}

    for e in srs.entities:
        key = e.name.strip().lower()
        table = tables_by_name.get(key)
        if not table:
            continue
        field_alignments: list[FieldAlignment] = []
        cols_lower = {f.name.strip().lower(): f.name for f in table.fields}
        for ef in e.fields:
            col = cols_lower.get(ef.name.strip().lower())
            if col:
                field_alignments.append(FieldAlignment(srs_field=ef.name, column=col))
        entities.append(
            EntityAlignment(
                srs_entity=e.name,
                table=table.name,
                fields=field_alignments,
            )
        )
    return AlignmentResult(entities=entities)

