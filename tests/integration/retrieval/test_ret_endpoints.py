import pytest
from httpx import AsyncClient, ASGITransport
import sys
from pathlib import Path
import importlib
import types
import os
import tempfile

# --- FIX PYTHONPATH ---
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
# -----------------------

# --- FORCE ISOLATED CHROMA DIR FOR TESTING ---
temp_dir = tempfile.mkdtemp()
os.environ["CHROMA_DIR"] = temp_dir
# ----------------------------------------------

# --- FORCE OVERRIDE OF app.models ---
retrieval_models = importlib.import_module("services.retrieval.app.models")
fake_app_models = types.ModuleType("app.models")
for attr in dir(retrieval_models):
    setattr(fake_app_models, attr, getattr(retrieval_models, attr))
sys.modules["app.models"] = fake_app_models
# ------------------------------------


from services.retrieval.app.main import app, startup


@pytest.mark.asyncio
async def test_health_endpoint():
    """Integration test for /health."""

    #Manually run FastAPI startup
    await startup()

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200

        data = resp.json()
        assert "status" in data
        assert data["status"] in ["ok", "degraded", "down"]
        assert "chromaDir" in data
        assert "embedding" in data
        assert "bm25_pipeline" in data


@pytest.mark.asyncio
async def test_search_empty_query_rejected():
    """Empty q must return 422."""

    await startup()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/search?q=&topK=3")
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_hybrid_success():
    """Valid hybrid search should not fail."""

    await startup()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/search?q=test&topK=3&mode=hybrid")
        assert resp.status_code == 200

        data = resp.json()
        assert "queryId" in data
        assert "results" in data
        assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_search_bm25_not_implemented():
    """BM25 alone mode must return 400."""

    await startup()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/search?q=test&mode=bm25")
        assert resp.status_code == 400
        assert "BM25" in resp.text
