import json
from unittest.mock import MagicMock
import pytest
import importlib, sys, types
import builtins

# --- FIX IMPORT COLLISION ---
retrieval_models = importlib.import_module("services.retrieval.app.models")
fake_module = types.ModuleType("app.models")
for attr in dir(retrieval_models):
    setattr(fake_module, attr, getattr(retrieval_models, attr))
sys.modules["app.models"] = fake_module
# ----------------------------

import services.retrieval.app.main as rmain
from services.retrieval.app.retriever import Retriever
from services.retrieval.app.main import _log_query_jsonl, publish_retrieval_completed


def test_log_query_jsonl_writes_line(monkeypatch, tmp_path):
    """
    Ensure _log_query_jsonl writes a JSONL line to /data/query_metadata.jsonl.
    """

    # Temporary file path
    fake_path = tmp_path / "query_metadata.jsonl"

    # Patch built-in open() globally so _log_query_jsonl writes to fake_path
    # Save real open BEFORE patching
    real_open = builtins.open

    # Patch open only for the specific path
    def fake_open(path, *a, **k):
        # If retrieval tries to write to /data/query_metadata.jsonl -> redirect to tmp
        if path == "/data/query_metadata.jsonl":
            return real_open(fake_path, *a, **k)
        # Otherwise use real open
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", fake_open)

    # Fake result object (SearchResult-like)
    class FakeScores:
        semantic = 0.9
        bm25 = 0.5
        combined = 0.7

    class FakeResult:
        document_id = "D1"
        chunk_id = "C1"
        page = 3
        title = "Title"
        url = "https://x.com"
        scores = FakeScores()

    _log_query_jsonl(
        query_id="Q1",
        query_text="hello",
        mode="semantic",
        top_k=5,
        retrieval_time_ms=12,
        results=[FakeResult()],
    )

    assert fake_path.exists()
    data = json.loads(fake_path.read_text().strip())
    assert data["query_id"] == "Q1"
    assert data["results"][0]["document_id"] == "D1"


@pytest.mark.asyncio
async def test_search_semantic_path(monkeypatch):
    """Test Retriever.search semantic path."""

    r = Retriever(chroma_dir="/tmp/dummy")

    fake_raw = {
        "documents": [["doc1", "doc2"]],
        "metadatas": [[
            {"document_id": "D1"},
            {"document_id": "D2"}
        ]],
        "distances": [[0.2, 0.8]],  # semantic sims: [0.9, 0.6]
    }

    r._coll = MagicMock()
    r._coll.query.return_value = fake_raw

    rows, meta = await r.search("hello", top_k=2, mode="semantic")

    assert len(rows) == 2
    assert rows[0]["scores"]["combined"] == 0.9
    assert rows[1]["scores"]["semantic"] == 0.6


@pytest.mark.asyncio
async def test_publish_retrieval_completed(monkeypatch):
    """
    Ensure publish_retrieval_completed builds the event properly
    and calls the underlying publish function.
    """

    # Enable event publishing
    monkeypatch.setenv("RETRIEVAL_PUBLISH_EVENTS", "true")

    # Re-import rmain so it picks up the updated environment variable
    importlib.reload(rmain)

    calls = []

    async def fake_publish(evt):
        calls.append(evt)

    # Patch global _publish to capture the event
    monkeypatch.setattr(rmain, "_publish", fake_publish)

    # Fake input results
    rows = [
        {
            "document_id": "D1",
            "chunk_id": "C1",
            "page": 1,
            "title": "Hello",
            "url": "x",
            "scores": {"semantic": 0.9, "bm25": 0.3, "combined": 0.8},
        }
    ]

    # Call function under test
    await publish_retrieval_completed(
        correlation_id="CORR1",
        query_id="Q1",
        query_text="test",
        mode="semantic",
        top_k=5,
        duration_ms=10,
        results=rows,
    )

    # Assertions
    assert len(calls) == 1
    evt = calls[0]

    assert evt.payload.queryId == "Q1"
    assert evt.payload.resultsCount == 1
    assert evt.payload.topScore == 0.8
