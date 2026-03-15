# Example SRS and schema files

Use these to test the synthetic data seeder (CLI or web UI).

## Generate all examples (PDF + schemas)

From the **project root** (`data generator`):

```bash
python scripts/generate_all_examples.py
```

With the project venv:

```bash
.venv/bin/python scripts/generate_all_examples.py
```

This creates/overwrites in `examples/`:

| File | Description |
|------|-------------|
| `shopflow_srs_200_pages.pdf` | ~200-page SRS (text-rich) for long-doc + Agno testing |
| `shopflow_srs_short.txt` | Short SRS summary (tenants, orders, enums) |
| `shopflow_schema_50_tables_postgres.sql` | PostgreSQL: 50 tables, CREATE TYPE enums, FKs, CHECK |
| `shopflow_schema_mysql.sql` | MySQL: ENUM columns, FKs |
| `shopflow_schema_sqlserver.sql` | SQL Server: bracketed identifiers, CHECK IN |
| `shopflow_schema_mongo.json` | MongoDB: JSON schema with enums |

## Generate only the PDF

```bash
python scripts/generate_example_pdf.py
```

## Suggested test pairs

- **Postgres (large):** `shopflow_srs_short.txt` + `shopflow_schema_50_tables_postgres.sql`
- **Postgres (enum):** use existing `enum_srs.txt` + `enum_schema.sql`
- **Long PDF:** `shopflow_srs_200_pages.pdf` + `shopflow_schema_50_tables_postgres.sql`
- **MySQL:** `shopflow_srs_short.txt` + `shopflow_schema_mysql.sql`
- **MongoDB:** `shopflow_srs_short.txt` + `shopflow_schema_mongo.json`
