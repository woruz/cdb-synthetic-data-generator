"""Agno agent for SRS structuring: strict JSON output only. Supports long docs via chunking."""

from __future__ import annotations

import logging

from .srs_schemas import SRSStructuredOutput
from .srs_merge import merge_srs_outputs

logger = logging.getLogger(__name__)

# ~80k chars per chunk leaves room for system prompt + response in 128k context
DEFAULT_MAX_CHARS_PER_CHUNK = 80_000


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at paragraph boundaries, each <= max_chars."""
    if len(text) <= max_chars:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # Break at last paragraph boundary (\n\n) in this segment
            segment = text[start:end]
            last_pp = segment.rfind("\n\n")
            if last_pp > max_chars // 2:
                end = start + last_pp + 2
            else:
                last_nl = segment.rfind("\n")
                if last_nl > 0:
                    end = start + last_nl + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def get_srs_system_instructions() -> str:
    """Strict system instructions for SRS extraction: JSON only."""
    return """You are an SRS (Software Requirements Specification) analyzer.
Your ONLY job is to extract structured information from the given SRS text and return it as strict JSON matching the required schema.

RULES:
- Return ONLY valid JSON that conforms to the output schema. No markdown, no code fences, no explanations.
- Extract: entities (tables/collections), their fields, data types, optional/required, enums.
- Extract: relationships between entities (one-to-one, one-to-many, many-to-many) and which fields link them.
- Extract: state machines and workflows (e.g. order status: pending, paid, shipped, cancelled, refunded).
- Extract: constraints (unique, required, range, format) and validation rules.
- Extract: roles and permissions if mentioned.
- Use entity/table names as they appear or are implied in the SRS. Prefer singular or plural consistently.
- If a field has a fixed set of values, set enum_values. If an entity has a status/state field, add it to state_fields or state_machines.
- Be conservative: only include what you can clearly infer from the text. Empty lists are allowed."""


def _extract_single_chunk(srs_text: str, agent: "Agent") -> SRSStructuredOutput:
    """Run Agno on one chunk and return SRSStructuredOutput."""
    prompt = f"""Analyze the following SRS text and extract structured information.
Return ONLY valid JSON matching the required schema. No other text.

SRS TEXT:
---
{srs_text}
---
"""

    logger.info("Running Agno on one chunk (strict JSON)...")
    response = agent.run(prompt)
    logger.debug("Agno response: %s", response)
    if response.content is None:
        return SRSStructuredOutput()
    if isinstance(response.content, SRSStructuredOutput):
        return response.content
    if hasattr(response, "content") and isinstance(getattr(response, "content", None), dict):
        return SRSStructuredOutput.model_validate(response.content)
    return SRSStructuredOutput()


def extract_srs_structure(
    srs_text: str,
    llm_provider: str = "openai",
    model_id: str = "gpt-4.1-mini",
    max_chars_per_chunk: int | None = DEFAULT_MAX_CHARS_PER_CHUNK,
) -> SRSStructuredOutput:
    """
    Use Agno agent to extract structured SRS into strict JSON (Pydantic).
    For long documents (e.g. 200-page PDFs), text is chunked and results are merged.
    AI is used ONLY for this extraction; no AI for seed data generation.
    """

    logger.info("Extracting structured SRS with Agno (strict JSON)")
    srs_text = (srs_text or "").strip()
    logger.info("SRS text length: %s characters", len(srs_text))
    if not srs_text:
        return SRSStructuredOutput()

    logger.info("Using model: %s", model_id)
    try:
        from agno.agent import Agent
    except ImportError as err:
        raise ImportError(
            "Agno is required for SRS extraction. Install with: pip install agno"
        ) from err

    try:
        from agno.models.openai import OpenAIResponses
        model = OpenAIResponses(id=model_id, temperature=0)
    except ImportError:
        raise ImportError("Agno OpenAI support not found.")

    logger.info("Initialized Agno %s model for SRS extraction", llm_provider)
    agent = Agent(
        model=model,
        output_schema=SRSStructuredOutput,
        instructions=get_srs_system_instructions(),
        markdown=False,
    )

    logger.info("Extracting structured SRS (max %s chars per chunk)", max_chars_per_chunk)

    if max_chars_per_chunk and len(srs_text) > max_chars_per_chunk:
        logger.info("SRS text exceeds %s chars, chunking for Agno extraction...", max_chars_per_chunk)
        chunks = _chunk_text(srs_text, max_chars_per_chunk)
        logger.info("Processing %s chunks", len(chunks))
        outputs = [_extract_single_chunk(chunk, agent) for chunk in chunks]
        logger.info("Extracted from %s chunks, merging results", len(chunks))
        return merge_srs_outputs(outputs)

    return _extract_single_chunk(srs_text, agent)
