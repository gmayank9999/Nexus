"""Extract raw text from PDF, TXT, Markdown, and DOCX files."""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

_SUPPORTED_MIMES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def supported_mime(mime: str) -> bool:
    return mime in _SUPPORTED_MIMES


def extract_text(content: bytes, mime_type: str) -> str:
    """Return plain text from the given file bytes.

    Raises ValueError for unsupported MIME types or extraction failures.
    """
    if not supported_mime(mime_type):
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    if mime_type == "application/pdf":
        return _extract_pdf(content)
    if mime_type in {"text/plain", "text/markdown"}:
        return content.decode("utf-8", errors="replace")
    if mime_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        return _extract_docx(content)
    raise ValueError(f"No extractor for: {mime_type}")


def _extract_pdf(content: bytes) -> str:
    try:
        import pypdf  # type: ignore[import-untyped]

        reader = pypdf.PdfReader(io.BytesIO(content))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return "\n\n".join(p for p in pages if p.strip())
    except ImportError:
        # Fallback: try pypdf2 (legacy package name)
        try:
            import PyPDF2  # type: ignore[import-untyped]

            reader2 = PyPDF2.PdfReader(io.BytesIO(content))
            pages2: list[str] = []
            for page in reader2.pages:
                text = page.extract_text() or ""
                pages2.append(text)
            return "\n\n".join(p for p in pages2 if p.strip())
        except Exception as exc2:
            logger.warning("PDF extraction failed: %s", exc2)
            raise ValueError(f"PDF extraction failed: {exc2}") from exc2
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        raise ValueError(f"PDF extraction failed: {exc}") from exc


def _extract_docx(content: bytes) -> str:
    try:
        import docx  # type: ignore[import-untyped]

        doc = docx.Document(io.BytesIO(content))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        raise ValueError(f"DOCX extraction failed: {exc}") from exc
