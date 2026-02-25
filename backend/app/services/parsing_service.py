import os
import tempfile
from pathlib import Path

_TEXT_MIME = {"text/plain", "text/markdown"}
_TEXT_EXT = {".txt", ".md"}

_DOCLING_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/html",
}
_DOCLING_EXT = {".pdf", ".docx", ".html", ".htm"}

_MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/html": ".html",
}


def parse_document(content: bytes, filename: str, mime_type: str) -> str:
    """Convert raw file bytes to plain text.

    Plain text and markdown are decoded directly.
    PDF, DOCX, and HTML are parsed via docling (blocking — call via asyncio.to_thread).

    Raises:
        ValueError: unsupported file type
        RuntimeError: docling conversion failed or produced empty output
    """
    ext = Path(filename).suffix.lower()

    if mime_type in _TEXT_MIME or ext in _TEXT_EXT:
        return content.decode("utf-8")

    if mime_type in _DOCLING_MIME or ext in _DOCLING_EXT:
        resolved_ext = ext if ext in _DOCLING_EXT else _MIME_TO_EXT.get(mime_type, ".bin")
        text = _parse_with_docling(content, resolved_ext)
        if not text.strip():
            raise RuntimeError(
                "Document parsed but produced no text. "
                "If this is a scanned PDF, it may be image-only and not supported."
            )
        return text

    raise ValueError(f"Unsupported file type: mime={mime_type!r}, filename={filename!r}")


def _parse_with_docling(content: bytes, ext: str) -> str:
    # Deferred import — keeps startup fast if docling is never called
    from docling.document_converter import DocumentConverter

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(content)
        tmp_path = f.name

    try:
        # One instance per call; cached model weights make re-instantiation cheap
        converter = DocumentConverter()
        result = converter.convert(tmp_path)
        return result.document.export_to_markdown()
    finally:
        os.unlink(tmp_path)
