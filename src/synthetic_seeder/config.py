"""Configuration for the seeder pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


GenerationStrategy = Literal["random", "edge-case"]


@dataclass
class GeneratorConfig:
    """Deterministic data generation options."""

    seed: int = 42
    row_multiplier: int = 1
    strategy: GenerationStrategy = "random"
    include_null_cases: bool = True
    include_boundary_cases: bool = True
    include_state_variations: bool = True
    include_invalid_format_examples: bool = False
    max_enum_permutations: int = 100
    # Edge-case strategy: min children per parent for relationship coverage
    min_children_per_parent: int = 2
    # AI-enhanced data generation: use LLM for semantic values (names, bios, etc.)
    use_ai_values: bool = False
    ai_rows_for_pool: int = 50
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"


@dataclass
class PipelineConfig:
    """Full pipeline configuration."""

    generator: GeneratorConfig | None = None
    database_type_hint: Literal["sql", "mongodb", "auto"] = "auto"
    output_path: str | None = None
    project_name: str = "default"
    # Long SRS (e.g. 200-page PDF): max characters per chunk for Agno. None = use default (~80k).
    srs_max_chars_per_chunk: int | None = None
    # If set, write Agno SRS extraction (structured JSON) to this path for inspection.
    srs_extract_log_path: str | None = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"

    def __post_init__(self) -> None:
        if self.generator is None:
            self.generator = GeneratorConfig()
