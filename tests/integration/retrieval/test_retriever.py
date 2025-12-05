import pytest
import tempfile
import os
from pathlib import Path
import sys

# --- FIX PYTHONPATH ---
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
# -----------------------

from services.retrieval.app.retriever import Retriever


@pytest.mark.asyncio
async def test_retriever_health():
    """
    Integration test for Retriever.health().
    Validates:
      - Returns a dict
      - Contains required health fields
    """
    #Use an isolated Chroma directory for testing
    temp_dir = tempfile.mkdtemp()
    os.environ["CHROMA_DIR"] = temp_dir

    retriever = Retriever()

    health = await retriever.health()

    assert isinstance(health, dict)
    assert "status" in health
    assert health["status"] in ["ok", "degraded", "down"]
    assert "embedding" in health
    assert "bm25_pipeline" in health


@pytest.mark.asyncio
async def test_retriever_search_semantic():
    """
    Integration test for semantic-only search.
    Since the test Chroma index is empty, it should return an empty list,
    but must never fail.
    """
    temp_dir = tempfile.mkdtemp()
    os.environ["CHROMA_DIR"] = temp_dir

    retriever = Retriever()

    rows, meta = await retriever.search(q="test", top_k=5, mode="semantic")

    assert isinstance(rows, list)
    assert isinstance(meta, dict)


@pytest.mark.asyncio
async def test_retriever_search_hybrid():
    """
    Integration test for hybrid search.
    With an empty index, should still return empty list and not crash.
    """
    temp_dir = tempfile.mkdtemp()
    os.environ["CHROMA_DIR"] = temp_dir

    retriever = Retriever()

    rows, meta = await retriever.search(q="test", top_k=5, mode="hybrid")

    assert isinstance(rows, list)
    assert isinstance(meta, dict)


@pytest.mark.asyncio
async def test_retriever_search_rejects_empty_query():
    """
    search(q="") must raise ValueError according to implementation.
    """
    temp_dir = tempfile.mkdtemp()
    os.environ["CHROMA_DIR"] = temp_dir

    retriever = Retriever()

    with pytest.raises(ValueError):
        await retriever.search(q="   ", top_k=5)
