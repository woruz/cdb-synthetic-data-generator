"""AI agent to generate a high-level seed plan from SRS + alignment + schema graph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from synthetic_seeder.ai_layer.srs_schemas import SRSStructuredOutput
from synthetic_seeder.ai_layer.alignment_agent import AlignmentResult
from synthetic_seeder.graph.model import SchemaGraph
from synthetic_seeder.generator.plan_models import SeedPlan, SeedScenario, TableSeedPlan


def generate_seed_plan(
    srs: SRSStructuredOutput,
    alignment: AlignmentResult,
    graph: SchemaGraph,
    *,
    llm_provider: str = "openai",
    model_id: str = "gpt-4o-mini",
) -> SeedPlan:
    """
    Use Agno/OpenAI to produce a high-level SeedPlan.
    The plan describes scenarios and per-table coverage targets.
    Final row values are still produced deterministically by the generator.
    """
    # Basic default plan: one scenario, at least 3 rows per table
    default_plan = _default_seed_plan(graph)

    try:
        from agno.agent import Agent
        from agno.models.openai import OpenAIResponses
    except ImportError:
        return default_plan

    system = (
        "You are a synthetic data planning assistant.\n"
        "You receive:\n"
        "- Parsed SRS (entities, fields, states).\n"
        "- An alignment mapping SRS entities/fields to DB tables/columns.\n"
        "- A relationship graph of the schema.\n"
        "Your job is to propose a high-level seed plan that:\n"
        "- Covers realistic user stories (scenarios).\n"
        "- Ensures all enum/state values are represented.\n"
        "- Includes boundary values and null cases where allowed.\n"
        "- Provides target row counts per table and relationship coverage hints.\n"
        "Return ONLY JSON compatible with the SeedPlan schema: "
        "{ 'scenarios': [...], 'tables': [...] }.\n"
        "Do NOT include actual IDs, emails, names, etc. Only counts and flags."
    )

    model = OpenAIResponses(id=model_id, temperature=0)
    agent = Agent(
        model=model,
        instructions=system,
        output_schema=SeedPlan,
        markdown=False,
    )

    payload: dict[str, Any] = {
        "srs_entities": [e.model_dump() for e in srs.entities],
        "srs_state_machines": [sm.model_dump() for sm in srs.state_machines],
        "alignment": alignment.model_dump(),
        "graph": {
            "nodes": {name: {"parents": n.parents, "children": n.children} for name, n in graph.nodes.items()},
            "roots": graph.roots(),
            "leaves": graph.leaves(),
        },
    }

    try:
        resp = agent.run(payload)
        plan: SeedPlan | None = None
        if isinstance(resp.content, SeedPlan):
            plan = resp.content
        elif isinstance(getattr(resp, "content", None), dict):
            plan = SeedPlan.model_validate(resp.content)
        # If AI did not return a useful plan or tables, fall back to schema-driven default.
        if plan is None:
            return default_plan
        # Strict filter: only keep tables that exist in the schema graph
        allowed = {name.strip().lower() for name in graph.nodes.keys()}
        filtered_tables = [
            t for t in plan.tables if t.table_name.strip().lower() in allowed
        ]
        plan.tables = filtered_tables
        if not plan.tables:
            return default_plan
        return plan
    except Exception:
        return default_plan


def _default_seed_plan(graph: SchemaGraph) -> SeedPlan:
    """Fallback seed plan if AI is unavailable: 3 rows per table, with coverage flags enabled."""
    scenarios = [
        SeedScenario(
            name="default_coverage",
            description="Default coverage scenario generated without AI: basic rows for all tables.",
            involved_entities=list(graph.nodes.keys()),
        )
    ]
    tables = [
        TableSeedPlan(
            table_name=name,
            target_rows=3,
            cover_all_enum_values=True,
            include_boundary_values=True,
            include_null_cases=True,
            min_children_per_parent=1,
        )
        for name in graph.nodes.keys()
    ]
    return SeedPlan(scenarios=scenarios, tables=tables)

