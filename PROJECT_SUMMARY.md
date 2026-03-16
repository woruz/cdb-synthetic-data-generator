# CDB Synthetic Data Generator – Project Summary

**GitHub:** https://github.com/woruz/cdb-synthetic-data-generator  
**Demo:** https://drive.google.com/file/d/1OCf2wDRPeLiRkJtMnyKApWLGnTeXtDdm/view?usp=sharing  
**Time taken:** 6 hours 30 minutes  

---

## Project statement

In my synthetic data generator I have used **Agno with the OpenAI API only for parsing and structuring the SRS document into machine-readable information.** The actual seed data generation is done **deterministically** using the parsed rules and the provided database schema, ensuring consistent and reproducible outputs without relying on AI for the final data generation.

**Gaps and limitations:** Automated tests are not yet in place. Composite UNIQUE constraints are parsed but not enforced during generation. The web UI has no progress indicator for long runs and no auth or rate limiting. There is no Docker/CI setup, no `.env.example`, and no health endpoint. Data is synthetic (e.g. `name_123`) with no Faker or locale options; SQL Server enum extraction is weaker than Postgres/MySQL. MongoDB refs support only single-collection references.

---

## Tech stack (complete)

In my synthetic data generator I have used:

### Core / runtime
- **Python 3.10+** – Main language and runtime.
- **Pydantic v2** – Config (e.g. `GeneratorConfig`, `PipelineConfig`), internal schema models (`NormalizedSchema`, `TableDef`, `FieldDef`), and SRS extraction output schemas. Used for validation and serialization.
- **dataclasses** – Used in generator coverage planning (`RowSpec`, `TableCoveragePlan`).

### Web
- **FastAPI** – REST API backend in `web/api/main.py`: file upload, list, delete, generate; serves static frontend.
- **Uvicorn** – ASGI server to run the FastAPI app (with optional `--reload`).
- **Vanilla HTML/CSS/JavaScript** – Single-page frontend in `web/static/index.html` (no React/Vue); uses Fetch API for upload, list, delete, generate, and file download.

### AI / SRS + planning
- **Agno** – Agent framework used in three places:
  1. To turn SRS text (or PDF-extracted text) into strict JSON (entities, relationships, state machines, enums, constraints).
  2. To align SRS entities/fields with DB tables/columns (alignment agent).
  3. To propose a high-level seed plan (scenarios + per-table targets and coverage hints).  
  **No AI is used for generating the final seed row values.**
- **OpenAI API** (via Agno) – Model (e.g. `gpt-4o` / `gpt-4o-mini`), temperature 0, for deterministic SRS, alignment, and plan extraction. Requires `OPENAI_API_KEY`.

### PDF and text
- **PyPDF** – PDF text extraction in `text_layer/pdf_loader.py` for long SRS documents (e.g. 200-page PDFs). Text is then cleaned and optionally chunked before sending to Agno.

### Schema and data
- **sqlparse** – Used indirectly or for SQL parsing utilities.
- **Custom SQL parsers** – Dialect-specific parsers for **PostgreSQL**, **MySQL**, and **SQL Server** (CREATE TABLE, ENUM/CREATE TYPE, CHECK, REFERENCES, NUMERIC bounds). Output is a unified internal schema.
- **MongoDB JSON schema parsing** – Parses collection schemas with `properties`, `required`, `maxLength`, `enum`, `ref` (for FK-style references), `minimum`/`maximum`.
- **Deterministic RNG** – Python `random.Random(seed)` for reproducible value generation (no AI for data).

### Validation and output
- **Custom validator** – Checks NOT NULL, empty strings, enum membership, string length, numeric min/max, types before writing the seeder.
- **SQL writer** – Emits `INSERT INTO ...` in FK-safe order; respects schema column order and quoting.
- **MongoDB writer** – Emits `db.getCollection(...).insertMany([...])` scripts.

### Other
- **httpx** – HTTP client (dependency of Agno/OpenAI).
- **python-dotenv** – For loading `.env` (e.g. API keys).
- **Ruff** – Linter/formatter (dev).
- **pytest / pytest-cov** – Testing (dev, optional).

---

## What the system does (short)

1. **Input:** SRS (PDF or TXT) + database schema (SQL DDL or MongoDB JSON).
2. **SRS:** Text is cleaned; if PDF, extracted with PyPDF. Optionally, Agno (OpenAI) extracts structured JSON; long docs are chunked and results merged.
3. **Schema:** Parsed into a single internal model (tables, fields, types, FKs, enums, UNIQUE, NOT NULL, lengths, numeric bounds). SRS output is merged to enrich enums/state fields.
4. **Planning & alignment:** Optional AI agents align SRS entities to schema tables and propose a `SeedPlan` (scenarios + per-table coverage goals). There are deterministic fallbacks when AI is disabled.
5. **Generation:** Deterministic, rule-based engine (two strategies: random row count vs edge-case coverage) that consumes the `SeedPlan`. Generates FK-consistent rows, unique values for UNIQUE columns, and respects NOT NULL/enum/length/bounds.
6. **Validation:** All rows checked against the schema; pipeline fails if any row violates constraints.
7. **Output:** Ready-to-run SQL or MongoDB seeder file (download from web UI or CLI/stdout).

---

## What’s missing / possible improvements

### Functionality
- **Tests** – No automated tests in the repo yet. Adding unit tests for parsers, generator, validator, and pipeline would improve reliability.
- **Composite UNIQUE** – Only single-column UNIQUE is fully handled (via `field.is_unique`). Composite UNIQUE keys are parsed but not enforced during generation.
- **MongoDB refs** – Only single-collection refs (e.g. `ref: "tenants.tenant_id"`) are supported. Nested or multi-hop references are not.
- **SQL Server enums** – SQL Server has no native ENUM; CHECK constraints are parsed where supported, but enum extraction is weaker than for Postgres/MySQL.
- **Incremental / append seeds** – No option to generate “append-only” seeds (e.g. for existing DBs). Seeds assume empty tables or truncate.
- **Environment/config** – No `.env.example` or documented env vars (e.g. `OPENAI_API_KEY`, optional chunk size). Web upload path is hardcoded under `web/uploads/`.

### UX / operations
- **Progress for long runs** – For long PDFs or many tables, the web UI has no progress indicator; the request blocks until the seeder is ready.
- **Error messages in UI** – API errors (e.g. validation failure, Agno timeout) are shown as a single message; no structured error codes or field-level details in the UI.
- **Logging** – Basic logging exists; no log levels or rotation. No request ID or correlation for debugging.
- **Rate limiting / auth** – No rate limiting or authentication on upload/generate; fine for demo, not for shared production.

### Data quality
- **Realistic data** – Values are synthetic (e.g. `name_123`, `domain_0_456`). No Faker or templates for realistic names, emails, addresses.
- **Locale / format** – Dates/timestamps use fixed format; no locale or timezone options.
- **Custom generators** – No way to plug in project-specific value generators (e.g. “always use these statuses for this table”).

### Docs and examples
- **API docs** – FastAPI exposes `/docs`, but no high-level “how to integrate” or Postman collection.
- **Example env** – No `.env.example` or README section listing required/optional variables.
- **Video/README** – Demo link is Drive; a short “Quick start” in the main README (with screenshots or a 1‑minute flow) would help.

### DevOps / deployment
- **Docker** – No Dockerfile or docker-compose; install is `pip install -e .[web]` and run uvicorn manually.
- **CI/CD** – No GitHub Actions (or other CI) for lint, test, or build.
- **Health check** – No `/health` or `/ready` endpoint for load balancers or orchestrators.

---

## Summary table

| Area              | Status / note                                                                 |
|-------------------|-------------------------------------------------------------------------------|
| **Tech used**     | Python 3.10+, FastAPI, Uvicorn, Pydantic, Agno, OpenAI, PyPDF, custom parsers, deterministic generator, SQL + Mongo writers. |
| **Completeness**  | End-to-end pipeline (SRS + schema → seeder), CLI + Web UI, multi-DB, edge-case strategy, UNIQUE and NOT NULL handling. |
| **Missing**       | Tests, composite UNIQUE, progress UI, auth/rate limit, Docker, CI, realistic data options, `.env.example`, health endpoint. |

You can copy the “Tech stack (complete)” and “What’s missing” sections into a README, portfolio, or submission document as needed.
