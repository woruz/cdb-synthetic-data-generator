# Synthetic Data Seeder – Web UI

Upload SRS (PDF/TXT) and schema (SQL/JSON) files, then generate and download a seeder file.

## Run the app

From the **project root** (the `data generator` folder):

```bash
# Install web dependencies (first time)
pip install -e ".[web]"

# Start the server
uvicorn web.api.main:app --reload --app-dir .
```

Or from the `web` directory:

```bash
cd web
uvicorn api.main:app --reload
```

Then open **http://localhost:8000** in your browser.

## Flow

1. **Upload** – Drag & drop or click to upload SRS (`.pdf`, `.txt`) and schema (`.sql`, `.json`) files.
2. **List** – Uploaded files appear in the list with a type badge (SRS / Schema). Use **Delete** to remove a file.
3. **Select** – Choose one SRS file and one schema file from the dropdowns.
4. **Generate** – Click **Generate seeder file**. The pipeline runs (with Agno if SRS is provided) and the seeder file is downloaded (e.g. `seed.sql` or `seed.js`).

## API

- `GET /api/files` – List uploaded files
- `POST /api/upload` – Upload a file (multipart)
- `DELETE /api/files/{filename}` – Delete a file
- `POST /api/generate` – Body: `{ "srs_filename": "...", "schema_filename": "..." }` → returns seeder file as attachment
