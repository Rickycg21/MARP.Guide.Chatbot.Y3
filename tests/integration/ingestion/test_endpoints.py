import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Correct imports now that we use namespace packages
from services.ingestion.app.main import app
from services.ingestion.common.config import settings

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert "service" in data


def test_get_documents_empty(tmp_path):
    data_root = Path(settings.data_root)
    catalog_path = data_root / "pdf_metadata.jsonl"

    if catalog_path.exists():
        catalog_path.unlink()

    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data["documents"], list)
    assert len(data["documents"]) == 0


def test_get_documents_with_catalog(tmp_path):
    data_root = Path(settings.data_root)
    data_root.mkdir(parents=True, exist_ok=True)

    catalog_path = data_root / "pdf_metadata.jsonl"

    sample_entries = [
        {
            "document_id": "test-doc-001",
            "title": "Test MARP Document 1",
            "url": "https://example.com/1.pdf",
            "download_path": "/tmp/file1.pdf",
            "pages": 5,
            "discovered_at": "2025-01-01T00:00:00Z"
        },
        {
            "document_id": "test-doc-002",
            "title": "Test MARP Document 2",
            "url": "https://example.com/2.pdf",
            "download_path": "/tmp/file2.pdf",
            "pages": 12,
            "discovered_at": "2025-01-01T00:01:00Z"
        }
    ]

    with open(catalog_path, "w", encoding="utf-8") as f:
        import json
        for entry in sample_entries:
            f.write(json.dumps(entry) + "\n")

    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()

    docs = data["documents"]
    assert len(docs) == 2
    assert docs[0]["document_id"] == "test-doc-001"
    assert docs[1]["document_id"] == "test-doc-002"