#!/usr/bin/env python3
"""CLI for Synthetic Data & Seeder Generator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from synthetic_seeder.config import GeneratorConfig, PipelineConfig
from synthetic_seeder.pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-Assisted Universal Synthetic Data & Seeder Generator. "
        "Converts SRS text + DB schema → executable seeder file."
    )
    parser.add_argument(
        "srs_file",
        help="Path to SRS file: .txt (plain text) or .pdf (Agno will read and extract structure)",
    )
    parser.add_argument("schema_file", help="Path to database schema file (SQL DDL or MongoDB JSON)")
    parser.add_argument("-o", "--output", default=None, help="Output seeder file path")
    parser.add_argument("--db-type", choices=["auto", "sql", "mongodb"], default="auto", help="Database type hint")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument(
        "--strategy",
        choices=["random", "edge-case"],
        default="edge-case",
        help="Generation strategy: random (fixed row count) or edge-case (coverage-based)",
    )
    parser.add_argument("--rows", type=int, default=1, dest="row_multiplier", help="Row multiplier per table (used when --strategy random)")
    parser.add_argument("--no-agno", action="store_true", help="Skip Agno SRS extraction (schema-only)")
    parser.add_argument(
        "--srs-chunk-size",
        type=int,
        default=None,
        metavar="CHARS",
        help="Max characters per chunk for long SRS/PDF (default ~80k). Tune for very long PDFs.",
    )
    parser.add_argument(
        "--log-srs",
        dest="srs_extract_log_path",
        default=None,
        metavar="PATH",
        help="Write Agno SRS extraction (entities, relationships, states, etc.) to this JSON file.",
    )
    parser.add_argument(
        "--srs-min-compatibility",
        type=float,
        default=0.50,
        metavar="0.0-1.0",
        help="Require SRS and schema to be at least this compatible (default 0.5 = 50%%).",
    )
    parser.add_argument("--use-ai", action="store_true", help="Use AI to generate semantic value pools (realistic names, bios, etc.)")
    parser.add_argument("--ai-pool-size", type=int, default=50, help="Number of semantic values to generate per AI-enabled field")
    parser.add_argument("--no-align-ai", action="store_true", help="Disable AI-based SRS/schema alignment and use heuristic only")
    parser.add_argument("--no-seed-plan-ai", action="store_true", help="Disable AI-based seed plan; use default per-table coverage")
    parser.add_argument("--project", default="default", help="Project name")
    args = parser.parse_args()

    srs_path = Path(args.srs_file)
    schema_path = Path(args.schema_file)
    if not srs_path.exists():
        print(f"Error: SRS file not found: {srs_path}", file=sys.stderr)
        return 1
    if not schema_path.exists():
        print(f"Error: Schema file not found: {schema_path}", file=sys.stderr)
        return 1

    schema_content = schema_path.read_text(encoding="utf-8", errors="replace")
    is_pdf = srs_path.suffix.lower() == ".pdf"
    if is_pdf:
        srs_text = None
        srs_pdf_path = srs_path
    else:
        srs_text = srs_path.read_text(encoding="utf-8", errors="replace")
        srs_pdf_path = None

    config = PipelineConfig(
        generator=GeneratorConfig(
            seed=args.seed,
            row_multiplier=args.row_multiplier,
            strategy=args.strategy,
            use_ai_values=args.use_ai,
            ai_rows_for_pool=args.ai_pool_size,
        ),
        database_type_hint=args.db_type,
        output_path=args.output,
        project_name=args.project,
        srs_max_chars_per_chunk=args.srs_chunk_size,
        srs_extract_log_path=args.srs_extract_log_path,
        srs_min_compatibility=args.srs_min_compatibility,
        use_alignment_ai=not args.no_align_ai,
        use_seed_plan_ai=not args.no_seed_plan_ai,
    )

    try:
        schema, rows_by_table, seeder_content = run_pipeline(
            schema_content,
            config,
            srs_text=srs_text,
            srs_pdf_path=srs_pdf_path,
            use_agno=not args.no_agno,
        )
    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(seeder_content, encoding="utf-8")
        print(f"Seeder written to {args.output}")
    else:
        print(seeder_content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
