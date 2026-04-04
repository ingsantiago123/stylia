"""
Utilidades para manejo de PDFs con PyMuPDF (fitz).
"""

import logging
import tempfile
import subprocess
from pathlib import Path

import fitz  # PyMuPDF

from app.config import settings

logger = logging.getLogger(__name__)


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Cuenta las páginas de un PDF desde bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    count = len(doc)
    doc.close()
    return count


def extract_page_text_blocks(pdf_bytes: bytes, page_no: int) -> list[dict]:
    """
    Extrae bloques de texto de una página con posición y fuente.
    page_no es 0-indexed.
    
    Retorna lista de bloques con estructura:
    {
        "block_no": int,
        "type": "text" | "image",
        "bbox": [x0, y0, x1, y1],
        "text": str,
        "lines": [{
            "bbox": [x0, y0, x1, y1],
            "spans": [{
                "text": str,
                "font": str,
                "size": float,
                "color": int,
                "flags": int,
                "bbox": [x0, y0, x1, y1]
            }]
        }]
    }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_no]

    text_dict = page.get_text("dict", sort=True)
    blocks = []

    for i, block in enumerate(text_dict.get("blocks", [])):
        block_type = "image" if block.get("type") == 1 else "text"

        block_data = {
            "block_no": i,
            "type": block_type,
            "bbox": list(block["bbox"]),
        }

        if block_type == "text":
            lines = []
            full_text_parts = []
            for line in block.get("lines", []):
                spans = []
                for span in line.get("spans", []):
                    spans.append({
                        "text": span["text"],
                        "font": span["font"],
                        "size": span["size"],
                        "color": span["color"],
                        "flags": span["flags"],
                        "bbox": list(span["bbox"]),
                    })
                    full_text_parts.append(span["text"])
                lines.append({
                    "bbox": list(line["bbox"]),
                    "spans": spans,
                })
            block_data["lines"] = lines
            block_data["text"] = " ".join(full_text_parts).strip()
        else:
            block_data["text"] = ""
            block_data["lines"] = []

        blocks.append(block_data)

    doc.close()
    return blocks


def render_page_preview(pdf_bytes: bytes, page_no: int, dpi: int = 150) -> bytes:
    """Renderiza una página como PNG para preview."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_no]
    pix = page.get_pixmap(dpi=dpi)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def extract_and_render_all_pages(
    pdf_bytes: bytes,
    dpi: int = 150,
) -> list[tuple[list[dict], bytes]]:
    """
    Batch extraction: opens the PDF once and extracts text blocks + renders
    a preview PNG for every page.

    Returns a list of (blocks, preview_png) tuples, one per page (0-indexed).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    results: list[tuple[list[dict], bytes]] = []

    for page_no in range(len(doc)):
        page = doc[page_no]

        # --- Extract text blocks (same logic as extract_page_text_blocks) ---
        text_dict = page.get_text("dict", sort=True)
        blocks: list[dict] = []
        for i, block in enumerate(text_dict.get("blocks", [])):
            block_type = "image" if block.get("type") == 1 else "text"
            block_data: dict = {
                "block_no": i,
                "type": block_type,
                "bbox": list(block["bbox"]),
            }
            if block_type == "text":
                lines = []
                full_text_parts = []
                for line in block.get("lines", []):
                    spans = []
                    for span in line.get("spans", []):
                        spans.append({
                            "text": span["text"],
                            "font": span["font"],
                            "size": span["size"],
                            "color": span["color"],
                            "flags": span["flags"],
                            "bbox": list(span["bbox"]),
                        })
                        full_text_parts.append(span["text"])
                    lines.append({"bbox": list(line["bbox"]), "spans": spans})
                block_data["lines"] = lines
                block_data["text"] = " ".join(full_text_parts).strip()
            else:
                block_data["text"] = ""
                block_data["lines"] = []
            blocks.append(block_data)

        # --- Render preview PNG ---
        pix = page.get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes("png")

        results.append((blocks, png_bytes))

    doc.close()
    logger.info(f"Batch extract+render: {len(results)} páginas procesadas (1 fitz.open)")
    return results


def convert_docx_to_pdf(docx_path: str, output_dir: str | None = None) -> str:
    """
    Convierte un DOCX a PDF usando LibreOffice headless.
    Retorna la ruta del PDF generado.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()

    cmd = [
        settings.libreoffice_path,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        docx_path,
    ]

    logger.info(f"Convirtiendo DOCX a PDF: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 min max
    )

    if result.returncode != 0:
        logger.error(f"LibreOffice error: {result.stderr}")
        raise RuntimeError(f"Error convirtiendo DOCX a PDF: {result.stderr}")

    # Buscar el PDF generado
    docx_stem = Path(docx_path).stem
    pdf_path = Path(output_dir) / f"{docx_stem}.pdf"

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF no generado: {pdf_path}")

    logger.info(f"PDF generado: {pdf_path}")
    return str(pdf_path)


def extract_full_text(pdf_bytes: bytes) -> str:
    """Extrae todo el texto de un PDF como string."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text("text"))
    doc.close()
    return "\n\n".join(text_parts)
