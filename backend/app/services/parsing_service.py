import os
import tempfile
from pathlib import Path

_TEXT_MIME = {"text/plain", "text/markdown"}
_TEXT_EXT = {".txt", ".md"}

_PDF_MIME = {"application/pdf"}
_PDF_EXT = {".pdf"}

_DOCX_MIME = {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
_DOCX_EXT = {".docx"}

_HTML_MIME = {"text/html"}
_HTML_EXT = {".html", ".htm"}


def parse_document(content: bytes, filename: str, mime_type: str) -> str:
    ext = Path(filename).suffix.lower()

    if mime_type in _TEXT_MIME or ext in _TEXT_EXT:
        return content.decode("utf-8")

    if mime_type in _PDF_MIME or ext in _PDF_EXT:
        text = _parse_pdf(content)
    elif mime_type in _DOCX_MIME or ext in _DOCX_EXT:
        text = _parse_docx(content)
    elif mime_type in _HTML_MIME or ext in _HTML_EXT:
        text = _parse_html(content)
    else:
        raise ValueError(f"Unsupported file type: mime={mime_type!r}, filename={filename!r}")

    text = _sanitize(text)
    if not text.strip():
        raise RuntimeError(
            "Document parsed but produced no text. "
            "If this is a scanned PDF, it may be image-only and not supported."
        )
    return text


def _sanitize(text: str) -> str:
    return text.replace("\x00", "")


def _parse_pdf(content: bytes) -> str:
    import fitz  # pymupdf
    doc = fitz.open(stream=content, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def _parse_docx(content: bytes) -> str:
    import io
    from docx import Document
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


def _parse_html(content: bytes) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    return soup.get_text(separator="\n")
