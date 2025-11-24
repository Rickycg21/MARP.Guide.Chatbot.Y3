import sys
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient

# --- FIX IMPORT COLLISION ---
SERVICE_ROOT = Path(__file__).resolve().parents[3] / "services" / "ingestion"
sys.path.insert(0, str(SERVICE_ROOT))
# ----------------------------------------

from services.ingestion.app.main import app
from services.ingestion.common.config import settings
import services.ingestion.app.main as main_module


client = TestClient(app)


@pytest.mark.asyncio
async def test_discover_integration(monkeypatch, tmp_path):
    """
    Integration test for /discover:
      - Mock crawler INSIDE main.py
      - Mock publish_event INSIDE main.py
      - Validate catalog + response count
    """

    # Fake publish_event used by main
    async def fake_publish(evt):
        return None

    monkeypatch.setattr(main_module, "publish_event", fake_publish)

    #Fake crawler used by main 
    fake_records = [
        {
            "documentId": "doc-001",
            "title": "Fake PDF 1",
            "url": "https://example.com/1.pdf",
            "downloadPath": "/tmp/file1.pdf",
            "pages": 10,
            "discoveredAt": "2025-01-01T00:00:00Z",
        },
        {
            "documentId": "doc-002",
            "title": "Fake PDF 2",
            "url": "https://example.com/2.pdf",
            "downloadPath": "/tmp/file2.pdf",
            "pages": 4,
            "discoveredAt": "2025-01-01T00:01:00Z",
        },
    ]

    async def fake_discover():
        for rec in fake_records:
            yield rec

    monkeypatch.setattr(main_module, "discover_and_download", fake_discover)

    # Prepare catalog
    data_root = Path(settings.data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    catalog_path = data_root / "pdf_metadata.jsonl"

    if catalog_path.exists():
        catalog_path.unlink()

    # Call endpoint
    response = client.post("/discover")
    assert response.status_code in (200, 202)

    data = response.json()
    assert data["discovered_count"] == 2

    # Validate catalog
    lines = catalog_path.read_text().splitlines()
    ids = [json.loads(line)["document_id"] for line in lines]

    assert ids == ["doc-001", "doc-002"]
