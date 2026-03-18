"""AI semantic value generation: generates pools of realistic values for specific fields."""

import logging
from typing import Any
from pydantic import BaseModel, Field

from synthetic_seeder.schema import NormalizedSchema

logger = logging.getLogger(__name__)

def generate_semantic_pools(
    schema: NormalizedSchema,
    pool_size: int = 50,
    llm_provider: str = "openai",
    model_id: str = "gpt-4.1-mini",
) -> dict[str, dict[str, list[Any]]]:
    """
    Generate semantic value pools for fields that appear to be textual/descriptive.
    Returns: { table_name: { field_name: [list_of_values] } }
    """
    try:
        from agno.agent import Agent
    except ImportError:
        logger.warning("Agno not installed, skipping semantic AI generation.")
        return {}

    semantic_fields = []
    for table_name, table in schema.tables.items():
        for field_name, field in table.fields.items():
            # Identify fields that benefit from AI: Strings with "name", "desc", "bio", "title", etc.
            if field.data_type.lower() == "string" and not field.enum_values:
                name_lower = field_name.lower()
                if any(hint in name_lower for hint in ["name", "desc", "bio", "title", "comment", "address", "company", "subject"]):
                   semantic_fields.append((table_name, field_name, field.description))

    if not semantic_fields:
        return {}

    logger.info("Generating semantic pools for %s fields using AI...", len(semantic_fields))
    
    # We'll use a single prompt to generate multiple pools to save on tokens/latency
    fields_desc = "\n".join([f"- {t}.{f}: {d or 'No description'}" for t, f, d in semantic_fields])
    
    prompt = f"""Generate a list of exactly {pool_size} realistic, diverse, and unique synthetic values for each of the following database fields.
Each value must be a string and should respect the context of the field name and description.

FIELDS:
{fields_desc}

Return the results as a JSON object where keys are "table.field" and values are lists of strings.
Example: {{ "users.bio": ["Tech enthusiast...", "Artist and traveler..."], "products.name": ["Wireless Mouse", "Mechanical Keyboard"] }}
"""

    try:
        from agno.models.openai import OpenAIResponses
        model = OpenAIResponses(id=model_id, temperature=0.7)
    except ImportError:
        logger.error("Agno OpenAI support not found.")
        return {}

    class _PoolsEnvelope(BaseModel):
        __root__: dict[str, list[str]] = Field(default_factory=dict)
    agent = Agent(model=model, markdown=False, output_schema=_PoolsEnvelope)
    
    try:
        response = agent.run(prompt)
        if isinstance(response.content, _PoolsEnvelope):
            data = response.content.__root__
        elif isinstance(getattr(response, "content", None), dict):
            data = _PoolsEnvelope.model_validate(response.content).__root__
        elif isinstance(getattr(response, "content", None), str):
            data = _PoolsEnvelope.model_validate_json(response.content).__root__
        else:
            data = {}
        
        pools = {}
        for key, values in data.items():
            if "." in key:
                t, f = key.split(".", 1)
                if t not in pools:
                    pools[t] = {}
                pools[t][f] = values
        
        return pools
    except Exception as e:
        logger.error("Failed to generate semantic pools: %s", e)
        return {}
