from pathlib import Path

import pytest

from app.ingestion.docling_parser import parse_to_markdown

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


def test_fixture_exists() -> None:
    assert FIXTURE_PATH.exists(), (
        f"Missing fixture {FIXTURE_PATH}. Regenerate per backend/tests/fixtures/README.md."
    )


@pytest.mark.slow
def test_parse_to_markdown_returns_text_and_two_pages() -> None:
    markdown, metadata = parse_to_markdown(FIXTURE_PATH)

    assert isinstance(markdown, str)
    assert len(markdown) > 0
    # Some text from page 1 should appear in the rendered markdown.
    lowered = markdown.lower()
    assert "page one" in lowered or "quick brown fox" in lowered

    assert metadata["page_count"] == 2
    assert metadata["source_format"] == "pdf"


def test_parse_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        parse_to_markdown(Path("/nonexistent-docling-fixture.pdf"))
