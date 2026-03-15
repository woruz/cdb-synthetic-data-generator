"""
Generate example SRS PDFs for testing.

Creates a text-rich PDF (no images) with many pages so that:
- PDF extraction yields real text (for Agno chunking)
- File can be used to test upload + long-document pipeline
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PdfObject:
    obj_id: int
    content: bytes


def _pdf_escape_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_simple_text_pdf(pages: list[str]) -> bytes:
    """
    Build a minimal, valid PDF containing selectable text for each page.
    Uses a built-in Type1 font (Helvetica).
    """
    objects: list[PdfObject] = []
    next_id = 1

    def add_obj(content: str) -> int:
        nonlocal next_id
        obj_id = next_id
        next_id += 1
        objects.append(PdfObject(obj_id=obj_id, content=content.encode("utf-8")))
        return obj_id

    # Font object
    font_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # Create content streams per page
    page_ids: list[int] = []
    content_ids: list[int] = []
    for page_text in pages:
        # Basic text placement; multiple lines split by newline.
        lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
        if not lines:
            lines = ["(blank)"]
        y = 760
        parts = ["BT", "/F1 11 Tf"]
        for ln in lines[:45]:
            txt = _pdf_escape_text(ln)
            parts.append(f"72 {y} Td ({txt}) Tj")
            y -= 14
        parts.append("ET")
        stream = "\n".join(parts).encode("utf-8")
        stream_obj = (
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\n"
            b"stream\n" + stream + b"\nendstream"
        )
        content_id = next_id
        next_id += 1
        objects.append(PdfObject(obj_id=content_id, content=stream_obj))
        content_ids.append(content_id)

        # Page object referencing font + stream; parent will be filled later.
        page_placeholder = f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        page_id = add_obj(page_placeholder)
        page_ids.append(page_id)

    # Pages tree object
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_id = add_obj(f"<< /Type /Pages /Count {len(page_ids)} /Kids [ {kids} ] >>")

    # Fix each page's parent reference (replace "Parent 0 0 R" with real one)
    for i, pid in enumerate(page_ids):
        obj = next(o for o in objects if o.obj_id == pid)
        obj.content = obj.content.replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode("ascii"))

    # Catalog
    catalog_id = add_obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    # Write PDF with xref
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = bytearray()
    offsets: dict[int, int] = {}
    for obj in objects:
        offsets[obj.obj_id] = len(header) + len(body)
        body.extend(f"{obj.obj_id} 0 obj\n".encode("ascii"))
        body.extend(obj.content)
        body.extend(b"\nendobj\n")

    xref_start = len(header) + len(body)
    max_id = max(o.obj_id for o in objects)
    xref = bytearray()
    xref.extend(b"xref\n")
    xref.extend(f"0 {max_id + 1}\n".encode("ascii"))
    xref.extend(b"0000000000 65535 f \n")
    for i in range(1, max_id + 1):
        off = offsets.get(i, 0)
        xref.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    trailer = (
        b"trailer\n"
        + f"<< /Size {max_id + 1} /Root {catalog_id} 0 R >>\n".encode("ascii")
        + b"startxref\n"
        + f"{xref_start}\n".encode("ascii")
        + b"%%EOF\n"
    )
    return header + body + xref + trailer


def main() -> int:
    out_dir = Path(__file__).resolve().parent.parent / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 200-page-ish long SRS
    pages = []
    for i in range(1, 201):
        pages.append(
            "\n".join(
                [
                    f"ShopFlow Enterprise Platform – SRS (Synthetic) – Page {i}/200",
                    "",
                    "Section: Tenants & Stores",
                    "- tenant posture states: active, suspended, closed",
                    "- store_status states: active, maintenance, disabled",
                    "",
                    "Section: Orders",
                    "- order_status: draft, pending, confirmed, packed, shipped, delivered, returned, cancelled",
                    "- payment_status: unpaid, authorized, captured, refunded, chargeback",
                    "- fulfillment_status: unfulfilled, partial, fulfilled, failed",
                    "",
                    "Constraints:",
                    "- emails must be unique per tenant",
                    "- quantity must be >= 1",
                    "- totals must be >= 0 and <= 99999999.99",
                    "- status fields must use allowed enums only",
                ]
            )
        )

    pdf_bytes = build_simple_text_pdf(pages)
    out_path = out_dir / "shopflow_srs_200_pages.pdf"
    out_path.write_bytes(pdf_bytes)
    print(f"Wrote {out_path} ({len(pdf_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

