# AI-Assisted Universal Synthetic Data & Seeder Generator

Converts **SRS (Software Requirements) text or PDF + Database schema** into a **valid, executable seeder file** for SQL or MongoDB.

## Architecture (hybrid, multi-stage)

- **AI (Agno + OpenAI)** is used in **three places**:
  - To parse and structure the **SRS** into entities, fields, enums, state machines and constraints (strict JSON).
  - To **align** SRS entities/fields with actual DB tables/columns (via an alignment agent).
  - To generate a **high-level seed plan** (scenarios, coverage goals, per-table targets) – but **not concrete row values**.
- **All concrete data generation, validation, and seeder writing** are **deterministic and rule-based**. No AI is used for the final seed rows.

## Pipeline

1. **SRS input** – SRS can be **plain text** (`.txt`) or **PDF** (`.pdf`). For PDFs, text is extracted with `pypdf`; Agno then reads the text (no pre-extraction needed).
2. **Long documents** – For long SRS (e.g. **200-page PDFs**), the text is split into chunks (~80k chars by default). Agno runs on each chunk; results are merged (entities, relationships, state machines, etc.) into one structured output.
3. **Agno SRS structuring** – An Agno agent (OpenAI, temperature=0) extracts: entities, fields, relationships, enums, state machines, workflows, constraints, roles. Output is a single structured JSON object.
4. **Schema normalization** – The actual DB schema (SQL DDL or MongoDB JSON) is parsed and merged with the SRS output. Conflicts are resolved; insert order for foreign keys is computed and SRS–schema compatibility is checked.
5. **Alignment AI (optional)** – A separate Agno-based agent aligns SRS entities/fields with schema tables/columns, producing an alignment map. There is a heuristic fallback if AI is disabled.
6. **Schema relationship graph** – The normalized schema is turned into a graph (tables as nodes, FKs as edges) to understand parent/child relationships.
7. **Seed plan AI (optional)** – Another agent consumes SRS + alignment + graph and outputs a **SeedPlan**: scenarios plus per-table targets (row counts, enum coverage, boundary/null hints). If disabled or unavailable, a deterministic default SeedPlan is used.
8. **Deterministic generator** – Seed data is generated with a fixed seed and the SeedPlan: valid rows, boundary values, null/optional cases, unique and FK-safe values, business-state variations.
9. **Validation** – Generated rows are checked against the normalized schema.
10. **Seeder writer** – A ready-to-run file is emitted:
   - **SQL**: `INSERT` statements in parent-before-child order.
   - **MongoDB**: script using `insertMany()`.

## Requirements

- Python 3.10+
- `OPENAI_API_KEY` set (for Agno SRS extraction)

## Install

```bash
cd "data generator"
pip install -e .
```

## Web UI

Upload PDF/TXT and schema files, then generate and download a seeder from the browser:

```bash
pip install -e ".[web]"
uvicorn web.api.main:app --reload --app-dir .
```

Open **http://localhost:8000**. See [web/README.md](web/README.md) for details.

## Usage

**CLI (SRS file + schema file → seeder):**

```bash
# Plain text SRS
synthetic-seeder path/to/srs.txt path/to/schema.sql -o seed.sql

# PDF SRS (Agno reads the PDF text; supports long docs e.g. 200 pages)
synthetic-seeder path/to/srs.pdf path/to/schema.sql -o seed.sql

# MongoDB (auto-detected from schema content)
synthetic-seeder srs.txt schema.json -o seed.js

# Long PDF: tune chunk size (default ~80k chars per chunk)
synthetic-seeder long_srs.pdf schema.sql -o seed.sql --srs-chunk-size 60000

# Edge-case / coverage strategy (enum, state, boundary, null, relationship coverage)
synthetic-seeder srs.txt schema.sql -o seed.sql --strategy edge-case

# Other options
synthetic-seeder srs.txt schema.sql -o seed.sql --db-type sql --seed 42 --rows 5
synthetic-seeder srs.txt schema.sql --no-agno   # schema-only, no AI
```

**From Python:**

```python
from pathlib import Path
from synthetic_seeder.config import PipelineConfig, GeneratorConfig
from synthetic_seeder.pipeline import run_pipeline

schema_content = Path("schema.sql").read_text()
config = PipelineConfig(
    generator=GeneratorConfig(seed=42, row_multiplier=2),
    output_path="seed.sql",
)

# From text
schema, rows_by_table, seeder_content = run_pipeline(
    schema_content, config, srs_text=Path("srs.txt").read_text()
)

# From PDF (Agno extracts structure; long PDFs are chunked and merged)
schema, rows_by_table, seeder_content = run_pipeline(
    schema_content, config, srs_pdf_path=Path("srs.pdf")
)
```

## Project layout

- `text_layer` – Clean/normalize SRS text; extract text from PDF (`pdf_loader`).
- `ai_layer` – Agno agent + Pydantic schemas for SRS extraction (strict JSON).
- `schema` – Internal normalized schema (tables, fields, FKs, enums, state fields).
- `schema_parser` – SQL and MongoDB schema parsing; DB type detection.
- `normalizer` – Merge SRS + DB schema; compute insert order.
- `generator` – Rule-based, seeded value generation and row building.
- `validator` – Check generated data against schema.
- `writer` – SQL and MongoDB seeder file emission.
- `pipeline` – Orchestrator that runs the full flow.

## Design principles

- **Generic** – No hardcoded project or domain (e.g. no ecommerce-specific logic). Business states and workflows are inferred from the SRS.
- **Deterministic** – Same SRS + schema + seed → same seeder output.
- **Modular** – Each layer can be tested or replaced independently.
- **Multi-project** – One codebase for any project and DB type (SQL/MongoDB).

## Generation strategies

- **`--strategy random`** (default): Fixed row count per table (`--rows` multiplier). Good for quick seeds.
- **`--strategy edge-case`**: Coverage-based generation. Ignores fixed row count and ensures:
  - **Enum coverage**: At least one row per enum value for every enum field.
  - **State coverage**: At least one row per business state (e.g. pending, paid, cancelled) when detected from SRS.
  - **Boundary rows**: Min/zero/empty, max/max_length, and a dedicated null row (all nullables set to null).
  - **Relationship coverage**: Multiple child rows per parent (configurable `min_children_per_parent`).
  - Deterministic: same schema + same `--seed` → same output.

## Edge cases generated

- Boundary values (min/max length, numeric limits).
- Null/optional fields where allowed.
- Unique and FK-safe values.
- Business-state coverage (e.g. pending, paid, cancelled) when detected from SRS.
- With `--strategy random`: configurable row count via `--rows`. With `--strategy edge-case`: row count is derived from coverage.
