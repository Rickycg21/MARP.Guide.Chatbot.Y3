import pytest

#Imports work because conftest.py injects the correct service root
from app.pipeline import chunk_text_semantic


def test_chunk_text_semantic_basic():
    """Minimal text should produce at least one chunk."""
    text = "This is a test. Another sentence."
    chunks = chunk_text_semantic(text, doc_id="doc1")

    assert len(chunks) >= 1
    assert chunks[0]["document_id"] == "doc1"
    assert "text" in chunks[0]


def test_chunk_text_semantic_no_page_markers():
    """If no page markers exist, all chunks should have page = 1."""
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = chunk_text_semantic(text, doc_id="doc1")

    for c in chunks:
        assert c["page"] == 1


def test_chunk_text_semantic_with_page_markers():
    """Chunker should respect page boundaries."""
    text = """
    --- page 1 ---
    This is page one.

    --- page 2 ---
    This is page two.
    """

    chunks = chunk_text_semantic(text, doc_id="doc1")

    pages = {c["page"] for c in chunks}
    assert 1 in pages
    assert 2 in pages
