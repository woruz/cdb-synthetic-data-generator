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
from synthetic_seeder.context import build_table_context_markdown
from synthetic_seeder.ai_layer.table_data_agent import generate_table_rows_ai
from synthetic_seeder.context import extract_srs_global_profile, SRSGlobalProfile
from synthetic_seeder.ai_layer.table_context_agent import generate_table_context_markdown_ai
from synthetic_seeder.ai_layer.schema_agent import parse_schema_ai


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

    # In the new 2-step flow we use SRS only for context, not for merging/enrichment.
    # So we skip SRS–schema compatibility gating and SRS merge by not passing srs_output.
    schema = normalize_schema(
        schema_content,
        db_type_hint=db_hint,
        srs_output=None,
        min_srs_compatibility=0.0,
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


def run_pipeline_two_step_ai(
    schema_content: str,
    config: PipelineConfig | None = None,
    *,
    srs_text: str | None = None,
    srs_pdf_path: str | Path | None = None,
    use_agno: bool = True,
    max_rows_per_table: int = 200,
    context_dir: str = "logs/context",
    ai_rows_dir: str = "logs/ai_rows",
) -> tuple[NormalizedSchema, dict[str, list[dict]], str]:
    """
    New 2-step flow:
    1) For each table (FK-safe order), build markdown context (schema-grounded + SRS hints).
       Write `logs/context/{table}.md` and `logs/context/combined.md`.
    2) For each table, call an AI row generator using the markdown + strict schema columns.
       Write raw AI rows to `logs/ai_rows/{table}.json`.
    3) Validate; then write the seeder (SQL/Mongo).
    """
    config = config or PipelineConfig()

    # ---- SRS load + clean ----
    if srs_pdf_path is not None:
        path = Path(srs_pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"SRS PDF not found: {path}")
        srs_text = extract_text_from_pdf(path)
    if srs_text is None:
        srs_text = ""
    cleaned_srs = clean_srs_text(srs_text)

    srs_structured = None
    srs_profile: SRSGlobalProfile | None = None
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

        # Global profile is best-effort; don't fail pipeline if it can't be extracted.
        try:
            srs_profile = extract_srs_global_profile(
                cleaned_srs,
                llm_provider=config.llm_provider,
                model_id=config.llm_model,
            )
        except Exception as e:
            logger.warning("SRS global profile extraction failed; continuing without it: %s", e, exc_info=True)
            srs_profile = None

    # ---- Schema normalize ----
    db_hint = config.database_type_hint
    if db_hint == "auto":
        db_hint = DatabaseType.UNKNOWN
    else:
        db_hint = DatabaseType(db_hint)

    # Old (deterministic) schema parsing (kept for rollback):
    # schema = normalize_schema(
    #     schema_content,
    #     db_type_hint=db_hint,
    #     srs_output=None,
    #     min_srs_compatibility=0.0,
    # )

    # TEMP (testing): AI-based schema parsing.
    schema = parse_schema_ai(
        schema_content,
        db_type_hint=db_hint,
        llm_provider=config.llm_provider,
        model_id=config.llm_model,
    )

    # Persist AI-parsed schema for inspection (debug)
    try:
        Path(context_dir).mkdir(parents=True, exist_ok=True)
        (Path(context_dir) / "normalized_schema_ai.json").write_text(
            schema.model_dump_json(indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("Failed to write normalized_schema_ai.json: %s", e, exc_info=True)

    # ---- Graph + context ----
    graph = build_schema_graph(schema)
    order = schema.insert_order or [t.name for t in schema.tables]
    table_by_name = {t.name: t for t in schema.tables}

    context_path = Path(context_dir)
    context_path.mkdir(parents=True, exist_ok=True)
    combined_lines: list[str] = []

    # Persist profile for inspection (optional)
    if srs_profile is not None:
        (context_path / "srs_profile.json").write_text(srs_profile.model_dump_json(indent=2), encoding="utf-8")

    # ---- AI rows per table (FK-safe order) ----
    rows_by_table: dict[str, list[dict]] = {}
    ai_rows_path = Path(ai_rows_dir)
    ai_rows_path.mkdir(parents=True, exist_ok=True)

    for table_name in order:
        table = table_by_name.get(table_name)
        if table is None:
            continue

        # Old (deterministic) context builder (kept for easy rollback):
        # md = build_table_context_markdown(
        #     srs=srs_structured,
        #     profile=srs_profile,
        #     schema=schema,
        #     graph=graph,
        #     table=table,
        # )

        # TEMP (testing): generate table context markdown via AI instead of deterministic builder.
        md = generate_table_context_markdown_ai(
            table=table,
            schema=schema,
            srs_text=cleaned_srs,
            srs_profile=(srs_profile.model_dump() if srs_profile is not None else None),
            llm_provider=config.llm_provider,
            model_id=config.llm_model,
        )
        (context_path / f"{table_name}.md").write_text(md, encoding="utf-8")
        combined_lines.append(md)

        # AI generation uses previously generated parent rows for FK pools
        table_rows = generate_table_rows_ai(
            schema=schema,
            table=table,
            context_markdown=md,
            parent_rows_by_table=rows_by_table,
            srs_profile=(srs_profile.model_dump() if srs_profile is not None else None),
            llm_provider=config.llm_provider,
            model_id=config.llm_model,
            max_rows=max_rows_per_table,
        )
        _fill_primary_keys(table, table_rows)
        (ai_rows_path / f"{table_name}.json").write_text(
            json_dumps(table_rows),
            encoding="utf-8",
        )
        rows_by_table[table_name] = table_rows

    (context_path / "combined.md").write_text("\n\n".join(combined_lines).strip() + "\n", encoding="utf-8")

    # ---- Validate and write ----
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
        Path(out_path).write_text(seeder_content, encoding="utf-8")

    return schema, rows_by_table, seeder_content


def json_dumps(obj: object) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _fill_primary_keys(table, rows: list[dict]) -> None:
    """
    Fill missing PK values deterministically so FK pools can work for child tables.

    Supports single-column PKs:
    - int PKs (SERIAL/AUTO_INCREMENT or plain int): fill 1..N (continuing from max existing)
    - string-like PKs (UUID/text): fill with a stable prefix + counter, respecting max_length

    Composite PKs are left untouched (AI must provide them).
    """
    fields = list(getattr(table, "fields", []) or [])
    # Determine PK columns
    pk_cols = list(getattr(table, "primary_key", []) or [])
    if not pk_cols:
        pk_cols = [f.name for f in fields if getattr(f, "is_primary_key", False)]
    if not pk_cols:
        # Common convention fallback
        for f in fields:
            if f.name.lower() == "id":
                pk_cols = [f.name]
                break
    if not pk_cols:
        return
    if len(pk_cols) != 1:
        # Composite PKs: do not invent; let AI populate and validator catch issues
        return

    pk = pk_cols[0]
    field_map = {f.name: f for f in fields}
    f = field_map.get(pk)
    if f is None:
        return

    type_lower = (getattr(f, "data_type", None) or "string").lower()
    # If every row already has a non-null PK, nothing to do
    if rows and all(r.get(pk) is not None for r in rows):
        return

    if type_lower in ("int", "integer"):
        existing: list[int] = []
        for r in rows:
            v = r.get(pk)
            if isinstance(v, int):
                existing.append(v)
            elif isinstance(v, str) and v.isdigit():
                existing.append(int(v))
        next_id = (max(existing) + 1) if existing else 1
        for r in rows:
            if r.get(pk) is None:
                r[pk] = next_id
                next_id += 1
        return

    # String-like PKs: generate a deterministic prefix+counter
    prefix = f"{table.name[:12]}_{pk[:12]}_".lower()
    max_len = getattr(f, "max_length", None)
    used: set[str] = set()
    for r in rows:
        v = r.get(pk)
        if isinstance(v, str) and v:
            used.add(v)
    counter = 1
    for r in rows:
        if r.get(pk) is not None:
            continue
        while True:
            candidate = f"{prefix}{counter}"
            counter += 1
            if max_len is not None and len(candidate) > max_len:
                # Truncate deterministically from the end (keep uniqueness via counter suffix)
                suffix = str(counter - 1)
                base_max = max(1, max_len - (len(suffix) + 1))
                candidate = (prefix[:base_max] + "_" + suffix)[:max_len]
            if candidate not in used:
                used.add(candidate)
                r[pk] = candidate
                break
