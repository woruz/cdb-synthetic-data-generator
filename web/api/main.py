"""FastAPI backend: file upload, list, delete, generate seeder."""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

# Ensure project root and src are on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

# So Agno/SRS extraction logs appear when running under uvicorn (stdout is often buffered)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("synthetic_seeder").setLevel(logging.INFO)

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SRS_EXTENSIONS = {".pdf", ".txt"}
SCHEMA_EXTENSIONS = {".sql", ".json"}

app = FastAPI(title="Synthetic Data Seeder API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in SRS_EXTENSIONS:
        return "srs"
    if ext in SCHEMA_EXTENSIONS:
        return "schema"
    return "other"


def _list_files() -> list[dict]:
    out = []
    for f in UPLOAD_DIR.iterdir():
        if f.is_file():
            out.append({
                "id": f.name,
                "filename": f.name,
                "original_name": f.name.split("_", 1)[-1] if "_" in f.name else f.name,
                "type": _file_type(f.name),
            })
    return sorted(out, key=lambda x: x["filename"])


@app.get("/api/files")
def list_files():
    """List all uploaded files with type (srs vs schema)."""
    return _list_files()


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file (SRS: PDF/TXT or Schema: SQL/JSON). Stored with a unique prefix."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SRS_EXTENSIONS and ext not in SCHEMA_EXTENSIONS:
        raise HTTPException(
            400,
            f"Allowed: SRS {list(SRS_EXTENSIONS)} or Schema {list(SCHEMA_EXTENSIONS)}",
        )
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    path = UPLOAD_DIR / unique_name
    content = await file.read()
    path.write_bytes(content)
    return {
        "id": unique_name,
        "filename": unique_name,
        "original_name": file.filename,
        "type": _file_type(file.filename or ""),
    }


@app.delete("/api/files/{file_id:path}")
async def delete_file(file_id: str):
    """Delete an uploaded file by id (filename)."""
    path = UPLOAD_DIR / file_id
    if not path.is_file():
        raise HTTPException(404, "File not found")
    path.unlink()
    return {"ok": True}


class GenerateRequest(BaseModel):
    srs_filename: str
    schema_filename: str
    use_ai: bool = False
    ai_pool_size: int = 10
    strategy: str = "edge-case"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"


@app.post("/api/generate")
async def generate_seeder(req: GenerateRequest):
    """Run pipeline with selected SRS and schema files; return seeder file for download."""
    srs_path = UPLOAD_DIR / req.srs_filename
    schema_path = UPLOAD_DIR / req.schema_filename
    if not srs_path.is_file():
        raise HTTPException(404, f"SRS file not found: {req.srs_filename}")
    if not schema_path.is_file():
        raise HTTPException(404, f"Schema file not found: {req.schema_filename}")

    from synthetic_seeder.config import GeneratorConfig, PipelineConfig
    from synthetic_seeder.pipeline import run_pipeline
    from synthetic_seeder.schema import DatabaseType

    config = PipelineConfig(
        generator=GeneratorConfig(
            seed=42, 
            strategy=req.strategy,
            use_ai_values=req.use_ai,
            ai_rows_for_pool=req.ai_pool_size,
        ),
        srs_extract_log_path="logs/srs_extract.json",
    )
    schema_content = schema_path.read_text(encoding="utf-8", errors="replace")
    is_pdf = srs_path.suffix.lower() == ".pdf"
    srs_text = None if is_pdf else srs_path.read_text(encoding="utf-8", errors="replace")
    srs_pdf_path = srs_path if is_pdf else None

    try:
        schema, rows_by_table, seeder_content = run_pipeline(
            schema_content,
            config,
            srs_text=srs_text,
            srs_pdf_path=srs_pdf_path,
            use_agno=True,
        )
    except Exception as e:
        raise HTTPException(500, str(e))

    ext = ".js" if schema.database_type == DatabaseType.MONGODB else ".sql"
    out_name = "seed" + ext
    return Response(
        content=seeder_content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={out_name}"},
    )


@app.get("/")
def index():
    """Serve the frontend."""
    web_dir = Path(__file__).resolve().parent.parent
    index_file = web_dir / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return PlainTextResponse("Frontend not found. Put index.html in web/static/.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
