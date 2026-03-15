# Pipeline flow: file upload → seed file generation

End-to-end flow from uploading files (web or CLI) to downloading a generated seeder file.

---

## 1. High-level flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  USER: Upload SRS (PDF/TXT) + Schema (SQL/JSON)  →  Select pair  →  Generate │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. SRS input     PDF → extract text  OR  use raw text                      │
│  2. Clean         Normalize whitespace, line endings                         │
│  3. AI (Agno)     Extract structured JSON (entities, enums, states, etc.)   │
│  4. Schema        Parse SQL/Mongo → detect dialect → NormalizedSchema        │
│  5. Merge         Normalizer: merge SRS JSON + parsed schema                 │
│  6. Generate      Rule-based engine: rows per table (random or edge-case)   │
│  7. Validate      Check rows vs schema (null, enum, length, numeric)        │
│  8. Write         SQL INSERTs or Mongo insertMany() → seeder file           │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                         Seeder file returned (download or stdout)
```

---

## 2. Where it starts: Web vs CLI

### Web (`web/api/main.py`)

| Step | Handler | What it does |
|------|---------|----------------|
| Upload | `POST /api/upload` → `upload_file()` | Saves file to `web/uploads/` with a unique prefix (`uuid_originalname`). Returns `id`, `filename`, `type` (srs/schema). |
| List | `GET /api/files` → `list_files()` | Uses `_list_files()`: scans `UPLOAD_DIR`, tags each file as `srs` or `schema` via `_file_type()` (`.pdf`/`.txt` → srs, `.sql`/`.json` → schema). |
| Delete | `DELETE /api/files/{file_id}` → `delete_file()` | Deletes file by id (filename) from `UPLOAD_DIR`. |
| Generate | `POST /api/generate` → `generate_seeder()` | Reads `srs_filename` and `schema_filename` from body; loads both from `UPLOAD_DIR`. If SRS is `.pdf`, sets `srs_text=None`, `srs_pdf_path=path`; else reads SRS as text. Builds `PipelineConfig` (seed=42, strategy=`edge-case`), then calls **`run_pipeline()`**. Returns seeder content as attachment (`seed.sql` or `seed.js`). |

### CLI (`src/synthetic_seeder/cli.py`)

| Step | Entry | What it does |
|------|--------|----------------|
| Parse | `main()` | Parses `srs_file`, `schema_file`, `-o`, `--db-type`, `--seed`, `--strategy`, `--rows`, `--no-agno`, `--srs-chunk-size`, `--log-srs`, `--project`. |
| Load | In `main()` | Reads `schema_content` from schema file. If SRS is `.pdf`: `srs_text=None`, `srs_pdf_path=srs_path`. Else: `srs_text=srs_path.read_text()`, `srs_pdf_path=None`. |
| Run | `run_pipeline(schema_content, config, srs_text=..., srs_pdf_path=..., use_agno=not args.no_agno)` | Same pipeline as web. |
| Output | After `run_pipeline` | If `-o` set: writes `seeder_content` to file. Else: prints to stdout. |

So both web and CLI converge on **`run_pipeline()`** in `src/synthetic_seeder/pipeline/orchestrator.py`.

---

## 3. Core pipeline: `run_pipeline()` (orchestrator.py)

**Signature:**  
`run_pipeline(schema_content, config=None, *, srs_text=None, srs_pdf_path=None, use_agno=True) → (NormalizedSchema, rows_by_table, seeder_content)`

**Called from:**  
- Web: `web/api/main.py` → `generate_seeder()`  
- CLI: `src/synthetic_seeder/cli.py` → `main()`

**Step-by-step:**

| # | Code in `run_pipeline` | Function / module | What it does |
|---|------------------------|-------------------|--------------|
| 1 | `extract_text_from_pdf(path)` if `srs_pdf_path` | **text_layer.pdf_loader** | Reads PDF with `pypdf.PdfReader`, concatenates per-page text with `\n\n`. Produces raw SRS string. |
| 2 | `clean_srs_text(srs_text)` | **text_layer.cleaner** | Normalizes line endings, collapses multiple newlines/spaces, trims. Returns cleaned string. |
| 3 | `extract_srs_structure(cleaned_srs, max_chars_per_chunk=...)` if `use_agno` and non-empty | **ai_layer.srs_agent** | Agno agent (OpenAI, temp=0) returns strict JSON → `SRSStructuredOutput`. Long text is chunked with `_chunk_text()`; each chunk sent to `_extract_single_chunk()`; results merged with **ai_layer.srs_merge** `merge_srs_outputs()`. Optional: `_log_srs_extract()` writes JSON to file. |
| 4 | `normalize_schema(schema_content, db_type_hint, srs_output)` | **normalizer.normalizer** | Detects DB type, parses schema, merges SRS; returns single **NormalizedSchema**. |
| 5 | `generate_seed_data(schema, config.generator)` | **generator.engine** | Builds `rows_by_table`: dict of table name → list of row dicts. Uses **generator.value_gen** and **generator.coverage**; strategy is `random` or `edge-case`. |
| 6 | `validate_rows(schema, rows_by_table)` | **validator.validator** | Checks every row: NOT NULL, no empty string, enum membership, length, numeric min/max, bool type. Returns list of error strings. |
| 7 | If errors: `raise ValueError(...)` | — | Pipeline stops; no seeder file is written. |
| 8 | `write_sql_seeder(...)` or `write_mongo_seeder(...)` | **writer** | Produces seeder file content (INSERTs or insertMany). Optionally writes to `config.output_path`. |
| 9 | Return | — | `(schema, rows_by_table, seeder_content)`. |

---

## 4. Where each function lives and what it does

### 4.1 Text layer

| Function | File | What it does |
|----------|------|--------------|
| `extract_text_from_pdf(path)` | `src/synthetic_seeder/text_layer/pdf_loader.py` | Uses `pypdf.PdfReader`, iterates pages, `page.extract_text()`, joins with `\n\n`. |
| `get_pdf_page_texts(path)` | Same | Same but returns list of strings (one per page). |
| `clean_srs_text(raw)` | `src/synthetic_seeder/text_layer/cleaner.py` | Replaces `\r\n`/`\r` with `\n`, collapses 3+ newlines to 2, spaces/tabs to single space, strips lines. |

### 4.2 AI layer (Agno)

| Function | File | What it does |
|----------|------|--------------|
| `extract_srs_structure(srs_text, model_id, max_chars_per_chunk)` | `src/synthetic_seeder/ai_layer/srs_agent.py` | Creates Agno `Agent` with `OpenAIResponses(id=model_id, temperature=0)`, `output_schema=SRSStructuredOutput`. If text length > chunk size: `_chunk_text()` → list of chunks; each chunk → `_extract_single_chunk()` (agent.run(prompt)); then `merge_srs_outputs(outputs)`. Otherwise single `_extract_single_chunk(srs_text, agent)`. |
| `_chunk_text(text, max_chars)` | Same | Splits at paragraph boundaries (`\n\n`) so each chunk ≤ max_chars. |
| `_extract_single_chunk(srs_text, agent)` | Same | Builds prompt with SRS text, `agent.run(prompt)`, maps response to `SRSStructuredOutput`. |
| `get_srs_system_instructions()` | Same | Returns system prompt: JSON-only, extract entities, relationships, state machines, constraints, etc. |
| `merge_srs_outputs(outputs)` | `src/synthetic_seeder/ai_layer/srs_merge.py` | Merges multiple `SRSStructuredOutput` (from chunks): entities, relationships, state_machines, workflows, constraints, roles, enums; deduplicates by key. |

SRS Pydantic models (e.g. `SRSStructuredOutput`, `SRSEntity`, `StateMachineDef`) live in **`src/synthetic_seeder/ai_layer/srs_schemas.py`**.

### 4.3 Schema parsing and normalization

| Function | File | What it does |
|----------|------|--------------|
| `detect_schema_type(schema_content)` | `src/synthetic_seeder/schema_parser/detector.py` | Heuristics: MongoDB (e.g. COLLECTION, "type":, OBJECTID) vs SQL (CREATE TABLE, REFERENCES, etc.) → `DatabaseType.MONGODB` or `DatabaseType.SQL`. |
| `parse_sql_schema(schema_content, dialect)` | `src/synthetic_seeder/schema_parser/sql_parser.py` | If dialect is None, `detect_sql_dialect(schema_content)` (mysql/postgres/sqlserver). Dispatches to `parse_mysql_schema`, `parse_postgres_schema`, or `parse_sqlserver_schema`. Returns `NormalizedSchema` (tables, FKs, enums from DDL). |
| `parse_mongo_schema(schema_content)` | `src/synthetic_seeder/schema_parser/mongo_parser.py` | Parses JSON schema; builds `NormalizedSchema` with collections as “tables”, properties as fields, incl. `enum` in properties. |
| `normalize_schema(schema_content, db_type_hint, srs_output)` | `src/synthetic_seeder/normalizer/normalizer.py` | Calls `detect_schema_type` (if hint is UNKNOWN), then `parse_sql_schema` or `parse_mongo_schema`. Then `_merge_srs(normalized, srs_output)`: matches SRS entities to tables by name, merges state_fields, state_machines, enums into tables/fields; sets `normalized.database_type`; if missing, computes `insert_order` via `_topological_order(tables)` (parents before children). Returns one `NormalizedSchema`. |

Schema models (`NormalizedSchema`, `TableDef`, `FieldDef`, `ForeignKeyDef`, etc.) live in **`src/synthetic_seeder/schema/models.py`**.

### 4.4 Generator

| Function | File | What it does |
|----------|------|--------------|
| `generate_seed_data(schema, config)` | `src/synthetic_seeder/generator/engine.py` | Creates `rng = make_rng(config.seed)`. Uses `schema.insert_order` and `table_by_name`. If `config.strategy == "edge-case"`: `_generate_edge_case(...)`; else `_generate_random(...)`. Returns `rows_by_table`. |
| `_generate_random(...)` | Same | For each table in order: `num_rows` from row_multiplier (and state/boundary/null tweaks). For each row: `_generate_row(..., field_overrides=None, boundary_kind=None)`. Appends row and PK to `rows_by_table` and `pk_values`. |
| `_generate_edge_case(...)` | Same | For each table: `build_coverage_plan(table, min_children_per_parent)` → plan with row_specs (enum/state overrides, boundary_kind min/max/null). For child tables, `child_table_coverage_count(...)` and `_distribute_children_over_parents(...)` so each parent gets at least N children. For each row: `_generate_row(..., field_overrides=spec.field_overrides, boundary_kind=spec.boundary_kind, force_parent_index=...)`. |
| `_generate_row(table, rng, config, pk_values, row_index, field_overrides, boundary_kind, force_parent_index)` | Same | Builds one row dict. Applies overrides (with enum validation); for FK columns picks parent PK (using force_parent_index or rng); auto_increment = row_index+1; boundary_kind null/min/max uses `gen_boundary_value`; enum/state fields use `_gen_field_value` or state list; else `_gen_field_value`. Fills any missing columns. Returns (row, pk_vals). |
| `_gen_field_value(field, rng, config, null_chance)` | Same | Delegates to **value_gen** `gen_value_for_field(...)` (enum, nullability, length, min/max value). |
| `build_coverage_plan(table, min_children_per_parent)` | `src/synthetic_seeder/generator/coverage.py` | Builds list of `RowSpec`: one row per enum/state combination, then one “min”, one “max”, one “null”. Sets `TableCoveragePlan.num_rows` and `row_specs`. |
| `child_table_coverage_count(parent_pk_count, min_children_per_parent, base_plan_rows)` | Same | `max(base_plan_rows, parent_pk_count * min_children_per_parent)`. |
| `gen_value_for_field`, `gen_boundary_value`, `make_rng` | `src/synthetic_seeder/generator/value_gen.py` | Seeded RNG; generate string/int/float/bool/date/enum; boundary values (min/max/empty) respecting enum and numeric bounds. |

### 4.5 Validator

| Function | File | What it does |
|----------|------|--------------|
| `validate_rows(schema, rows_by_table)` | `src/synthetic_seeder/validator/validator.py` | For each table and each row: null only if field nullable; NOT NULL → no empty string; enum fields: value in enum_values; int/float: within min_value/max_value; bool: type is bool; string: length ≤ max_length. Appends message per violation. Returns list of error strings. |

### 4.6 Writer

| Function | File | What it does |
|----------|------|--------------|
| `write_sql_seeder(schema, rows_by_table, out_path)` | `src/synthetic_seeder/writer/sql_writer.py` | Iterates tables in `schema.insert_order`. For each table, columns = `[f.name for f in table.fields]`. For each row, formats values with `format_sql_value()` (NULL, int, float, bool, date, escaped string). Emits `INSERT INTO "table" (cols) VALUES (...);`. Optionally writes to `out_path`. Returns content string. |
| `write_mongo_seeder(schema, rows_by_table, out_path)` | `src/synthetic_seeder/writer/mongo_writer.py` | For each collection in order, builds array of docs, outputs `db.collection.insertMany([...]);` (or similar). Returns content string; optionally writes to file. |

---

## 5. Data flow summary

- **SRS**: PDF or text → (optional) PDF text extraction → clean → (optional) Agno → `SRSStructuredOutput` (entities, enums, state machines, relationships, etc.).
- **Schema**: Raw string → `detect_schema_type` → `parse_sql_schema` or `parse_mongo_schema` → `NormalizedSchema` (tables, fields, FKs, enums from DDL).
- **Merge**: `normalize_schema` merges SRS into that `NormalizedSchema` (state_fields, enums, etc.) and sets `insert_order`.
- **Generate**: `generate_seed_data` uses only the merged schema and config (no AI); produces `rows_by_table`.
- **Validate**: `validate_rows` ensures every value obeys the schema; pipeline raises if any errors.
- **Write**: `write_sql_seeder` or `write_mongo_seeder` turns `rows_by_table` into the final seeder file string (and optionally writes it).

So: **upload → load SRS + schema → run_pipeline (text/PDF → clean → Agno → parse → merge → generate → validate → write) → return or save seeder file.**
