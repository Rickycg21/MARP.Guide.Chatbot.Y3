import os
import json
import shutil
import tempfile
import pytest
import sys
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# --- FIX PYTHONPATH ---
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
# ------------------------

from services.extraction.app.main import app
import services.extraction.app.main as ext_main
from services.extraction.app.models import ExtractResponse, ExtractStatus


@pytest.fixture(autouse=True)
def temp_data_root(monkeypatch):
    """
    Use a temp folder for STATUS_PATH and META_PATH without touching settings.data_root.
    """
    tmp = tempfile.mkdtemp()

    # Patch module-level paths
    monkeypatch.setattr(ext_main, "STATUS_PATH", os.path.join(tmp, "text_status.jsonl"))
    monkeypatch.setattr(ext_main, "META_PATH", os.path.join(tmp, "text_metadata.jsonl"))

    yield tmp
    shutil.rmtree(tmp)


def make_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health():
    async with make_client() as ac:
        res = await ac.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "service" in data


@pytest.mark.asyncio
async def test_manual_extract_endpoint_creates_pending_status(monkeypatch):
    async def fake_task(*args, **kwargs):
        return None

    monkeypatch.setattr("services.extraction.app.main._do_extract", fake_task)

    doc_id = "DOC123"

    async with make_client() as ac:
        res = await ac.post(f"/extract/{doc_id}")

    assert res.status_code == 202
    data = res.json()
    assert data == ExtractResponse().model_dump()

    # check patched STATUS_PATH (not imported constant!)
    assert os.path.exists(ext_main.STATUS_PATH)

    with open(ext_main.STATUS_PATH, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

    assert len(lines) == 1
    assert lines[0]["document_id"] == doc_id
    assert lines[0]["status"] == "pending"
    assert "manual trigger accepted" in lines[0]["message"]


@pytest.mark.asyncio
async def test_status_unknown_document():
    async with make_client() as ac:
        res = await ac.get("/status/XXX999")

    assert res.status_code == 200
    data = res.json()

    assert data["document_id"] == "XXX999"
    assert data["status"] == "unknown"


@pytest.mark.asyncio
async def test_status_all_empty():
    async with make_client() as ac:
        res = await ac.get("/status")

    assert res.status_code == 200
    data = res.json()

    assert data["status_history"] == []
