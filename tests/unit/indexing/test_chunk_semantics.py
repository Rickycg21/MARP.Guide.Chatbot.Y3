import pytest

from services.indexing.app.pipeline import chunk_text_semantic
import services.indexing.app.pipeline as pipeline


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

@pytest.mark.asyncio
async def test_publish_chunks_indexed(monkeypatch):
    """publish_chunks_indexed should build correct event and call publish_event."""

    calls = {}

    async def fake_publish(evt):
        calls["evt"] = evt

    def fake_new_event(event_type, payload, correlation_id, source):
        return {"type": event_type, "payload": payload, "cid": correlation_id}

    monkeypatch.setattr(pipeline, "publish_event", fake_publish)
    monkeypatch.setattr(pipeline, "new_event", fake_new_event)

    await pipeline.publish_chunks_indexed("D1", 10, "C123")

    evt = calls["evt"]

    assert evt["type"] == "ChunksIndexed"
    assert evt["cid"] == "C123"
    assert evt["payload"]["documentId"] == "D1"
    assert evt["payload"]["chunkCount"] == 10