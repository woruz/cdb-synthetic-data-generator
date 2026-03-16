"""Orchestrate full pipeline: text or PDF → Agno SRS → schema merge → generate → validate → write."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from synthetic_seeder.config import PipelineConfig

# Load environment variables from .env file if it exists
dotenv_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger(__name__)


def _log_srs_extract(srs_structured: object, log_path: str) -> None:
    """Write Agno SRS extraction to a JSON file for later inspection."""
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    json_str = srs_structured.model_dump_json(indent=2)
    path.write_text(json_str, encoding="utf-8")
from synthetic_seeder.schema import DatabaseType, NormalizedSchema
from synthetic_seeder.text_layer import clean_srs_text, extract_text_from_pdf
from synthetic_seeder.normalizer import normalize_schema
from synthetic_seeder.graph.builder import build_schema_graph
from synthetic_seeder.ai_layer.alignment_agent import align_srs_to_schema, AlignmentResult
from synthetic_seeder.ai_layer.seed_plan_agent import generate_seed_plan
from synthetic_seeder.generator.plan_models import SeedPlan
from synthetic_seeder.generator import generate_seed_data
from synthetic_seeder.validator import validate_rows
from synthetic_seeder.writer import write_sql_seeder, write_mongo_seeder


def run_pipeline(
    schema_content: str,
    config: PipelineConfig | None = None,
    *,
    srs_text: str | None = None,
    srs_pdf_path: str | Path | None = None,
    use_agno: bool = True,
) -> tuple[NormalizedSchema, dict[str, list[dict]], str]:
    """
    Run the full pipeline.

    SRS input: provide either srs_text (plain text) or srs_pdf_path (path to PDF).
    For long PDFs (e.g. 200 pages), Agno is called on chunks and results are merged.

    1. Load SRS from text or PDF (extract text if PDF)
    2. Clean SRS text
    3. (Optional) Agno agent → structured SRS JSON (chunked for long docs)
    4. Parse schema, merge with SRS, normalize
    5. Deterministic data generation
    6. Validate
    7. Write seeder file

    Returns (normalized_schema, rows_by_table, seeder_content).
    """
    config = config or PipelineConfig()
    if srs_pdf_path is not None:
        path = Path(srs_pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"SRS PDF not found: {path}")
        srs_text = extract_text_from_pdf(path)
    if srs_text is None:
        srs_text = ""
    cleaned_srs = clean_srs_text(srs_text)
    srs_structured = None
    if use_agno and cleaned_srs.strip():
        logger.info("Extracting structured SRS with Agno agent...")
        try:
            from synthetic_seeder.ai_layer import extract_srs_structure
            srs_structured = extract_srs_structure(
                cleaned_srs,
                llm_provider=config.llm_provider,
                model_id=config.llm_model,
                max_chars_per_chunk=config.srs_max_chars_per_chunk,
            )
            if srs_structured is not None and config.srs_extract_log_path:
                _log_srs_extract(srs_structured, config.srs_extract_log_path)
        except Exception as e:
            logger.warning("Agno SRS extraction failed (continuing with schema only): %s", e, exc_info=True)
            srs_structured = None

    db_hint = config.database_type_hint
    if db_hint == "auto":
        db_hint = DatabaseType.UNKNOWN
    else:
        db_hint = DatabaseType(db_hint)

    schema = normalize_schema(
        schema_content,
        db_type_hint=db_hint,
        srs_output=srs_structured,
        min_srs_compatibility=config.srs_min_compatibility,
    )

    seed_plan: SeedPlan | None = None
    alignment_result: AlignmentResult | None = None
    if use_agno and srs_structured is not None and config.use_alignment_ai:
        try:
            graph = build_schema_graph(schema)
            alignment = align_srs_to_schema(
                srs_structured,
                schema,
                llm_provider=config.llm_provider,
                model_id=config.llm_model,
            )
            alignment_result = alignment
            # Optional: write alignment JSON log next to SRS extract log if configured
            if config.srs_extract_log_path:
                log_path = Path(config.srs_extract_log_path)
                align_path = log_path.with_name("alignment.json")
                align_path.parent.mkdir(parents=True, exist_ok=True)
                align_path.write_text(alignment.model_dump_json(indent=2), encoding="utf-8")
            if config.use_seed_plan_ai:
                seed_plan = generate_seed_plan(
                    srs_structured,
                    alignment,
                    graph,
                    llm_provider=config.llm_provider,
                    model_id=config.llm_model,
                )
                # Optional: write seed plan JSON log next to SRS extract log if configured
                if config.srs_extract_log_path:
                    log_path = Path(config.srs_extract_log_path)
                    plan_path = log_path.with_name("seed_plan.json")
                    plan_path.parent.mkdir(parents=True, exist_ok=True)
                    plan_path.write_text(seed_plan.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Alignment/seed-plan AI failed; continuing without seed plan: %s", e, exc_info=True)

    semantic_pools = None
    if config.generator and config.generator.use_ai_values:
        logger.info("Semantic AI generation enabled. Building value pools...")
        try:
            from synthetic_seeder.ai_layer.semantic_gen import generate_semantic_pools
            semantic_pools = generate_semantic_pools(
                schema, 
                pool_size=config.generator.ai_rows_for_pool,
                llm_provider=config.generator.llm_provider,
                model_id=config.generator.llm_model
            )
        except Exception as e:
            logger.warning("Failed to generate semantic AI pools: %s", e)

    rows_by_table = generate_seed_data(schema, config.generator, semantic_pools=semantic_pools, seed_plan=seed_plan)
    errors = validate_rows(schema, rows_by_table)
    if errors:
        raise ValueError(
            "Generated data violates schema constraints. Fix generator or schema.\n" + "\n".join(errors[:20])
            + ("\n..." if len(errors) > 20 else "")
        )

    if schema.database_type == DatabaseType.SQL:
        seeder_content = write_sql_seeder(schema, rows_by_table, out_path=None)
    elif schema.database_type == DatabaseType.MONGODB:
        seeder_content = write_mongo_seeder(schema, rows_by_table, out_path=None)
    else:
        seeder_content = write_sql_seeder(schema, rows_by_table, out_path=None)

    out_path = config.output_path
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(seeder_content)

    return schema, rows_by_table, seeder_content
