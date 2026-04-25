"""Synchronous Docling parser wrapper.

Designed to be invoked from async code via ``asyncio.to_thread`` (see M3.6).
Kept module-private to ingestion; do not import directly from agent or API
code — always go through the ingest worker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter


def parse_to_markdown(path: Path | str) -> tuple[str, dict[str, Any]]:
    """Parse a document into markdown plus minimal metadata.

    Args:
        path: filesystem path to a PDF (or other Docling-supported format).

    Returns:
        ``(markdown_text, metadata)`` where ``metadata`` contains at least:

        - ``page_count`` (``int``)
        - ``source_format`` (``str``, e.g. ``"pdf"``)

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        Exception: any error raised by Docling propagates to the caller
            (the ingest worker maps it to ``status=failed``).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Document not found: {p}")

    converter = DocumentConverter()
    result = converter.convert(str(p))

    # Docling 2.x: ``result.document`` is a ``DoclingDocument``.
    # - ``export_to_markdown()`` returns the rendered markdown.
    # - ``pages`` is a ``dict[int, PageItem]`` keyed by 1-based page number.
    # - ``num_pages`` is a method (not a property) on the same object; we
    #   prefer ``len(pages)`` because it works without calling a bound
    #   method and matches what we already inspect.
    document = result.document
    markdown: str = document.export_to_markdown()

    page_count = 0
    pages = getattr(document, "pages", None)
    if pages is not None:
        try:
            page_count = len(pages)
        except TypeError:
            page_count = len(list(pages))
    elif hasattr(document, "num_pages"):
        num_pages_attr = document.num_pages
        page_count = (
            int(num_pages_attr())  # type: ignore[no-untyped-call]
            if callable(num_pages_attr)
            else int(num_pages_attr)
        )

    metadata: dict[str, Any] = {
        "page_count": page_count,
        "source_format": p.suffix.lstrip(".").lower() or "unknown",
    }
    return markdown, metadata
