import pytest
from unittest.mock import MagicMock

from services.retrieval.app.retriever import Retriever

def test_tokenize_basic():
    """_tokenize should normalize text, split correctly, and handle empty/None input."""
    
    r = Retriever(chroma_dir="/tmp/doesntmatter")
    assert r._tokenize("Hello WORLD") == ["hello", "world"]
    assert r._tokenize("") == []
    assert r._tokenize(None) == []

@pytest.mark.asyncio
async def test_search_empty_query_raises():
    """search() should raise ValueError if the input query is empty."""

    r = Retriever(chroma_dir="/tmp/dummy")
    with pytest.raises(ValueError):
        await r.search("")

@pytest.mark.asyncio
async def test_search_no_results(monkeypatch):
    """search() should return empty rows when Chroma returns no documents."""


    r = Retriever(chroma_dir="/tmp/dummy")

    r._coll = MagicMock()
    r._coll.query.return_value = {"documents": [[]]}  # no results

    rows, meta = await r.search("hello", top_k=5)
    assert rows == []
    assert "duration_ms" in meta

@pytest.mark.asyncio
async def test_search_hybrid(monkeypatch):
    """Hybrid mode should properly fuse BM25 + semantic scores and sort by combined score."""

    r = Retriever(chroma_dir="/tmp/dummy")
    r.hybrid_alpha = 0.5  

    # Fake Chroma output: 3 candidates
    fake_query_result = {
        "documents": [["d1", "d2", "d3"]],
        "metadatas": [[
            {"document_id": "D1"}, {"document_id": "D2"}, {"document_id": "D3"}
        ]],
        "distances": [[0.2, 0.4, 0.8]],  # semantic: 0.9, 0.8, 0.6
    }
    r._coll = MagicMock()
    r._coll.query.return_value = fake_query_result

    # Mock BM25 scores
    # tokenized_docs and get_scores don't matter; return deterministic values
    fake_bm25 = MagicMock()
    fake_bm25.get_scores.return_value = [1.0, 3.0, 2.0]

    monkeypatch.setattr(
        "services.retrieval.app.retriever.BM25Okapi",
        lambda toks: fake_bm25,
    )

    rows, meta = await r.search("query", top_k=3, mode="hybrid")

    assert len(rows) == 3
    assert rows[0]["document_id"] in ["D1", "D2", "D3"]
    assert "combined" in rows[0]["scores"]

    # We verify that they are sorted by combined score
    combined_scores = [row["scores"]["combined"] for row in rows]
    assert combined_scores == sorted(combined_scores, reverse=True)

@pytest.mark.asyncio
async def test_health_chroma_down(monkeypatch):
    """health() should report 'down' when Chroma count() raises an exception."""

    r = Retriever(chroma_dir="/tmp/dummy")

    # Chroma fails on count()
    r._coll = MagicMock()
    r._coll.count.side_effect = Exception("no chroma")

    status = await r.health()

    assert status["status"] == "down"
    assert status["embedding"]["reachable"] is False
