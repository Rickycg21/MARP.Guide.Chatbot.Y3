import pytest
from pathlib import Path
from fastapi.testclient import TestClient

#Imports work because conftest.py injects the correct service root
from app.main import app # type: ignore[import]
from common.config import settings # type: ignore[import]

"""
Two DeprecationWarnings appear during tests because FastAPI's 'on_event'
is deprecated. They do not affect functionality and can be safely ignored.
"""

@pytest.fixture(scope="module", autouse=True)
def setup_test_text_file():
    """
    Creates a test text file in /data/text before tests,
    and deletes it after all tests.
    """
    data_root = Path(settings.data_root) / "text"
    data_root.mkdir(parents=True, exist_ok=True)

    test_file = data_root / "test_doc_endpoint.txt"
    test_file.write_text(
        "This is a document used for endpoint testing.",
        encoding="utf-8"
    )

    print(f"[TEST] Creating test file at: {test_file}")
    yield

    if test_file.exists():
        test_file.unlink()
        print(f"[TEST] Deleted test file: {test_file}")

#Instantiate the TestClient with the FastAPI app
client = TestClient(app)

def test_health_endpoint():
    """
    Verify that GET /health returns the expected service health status.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    print("[TEST] /health passed ✓ - service is healthy")

def test_index_document_endpoint():
    """
    Test POST /index/{document_id} with a real file created by the fixture.
    """
    response = client.post("/index/test_doc_endpoint")
    assert response.status_code == 202

    data = response.json()
    assert "correlationId" in data
    assert "message" in data

    print(f"[TEST] /index/test_doc_endpoint passed ✓ - correlationId: {data['correlationId']}")


def test_index_stats_endpoint():
    """
    Verify that GET /index/stats returns correct indexing statistics.
    """
    response = client.get("/index/stats")
    assert response.status_code == 200

    data = response.json()

    # Campos esperados del endpoint
    assert data.get("status") == "ok"
    assert "documentsIndexed" in data
    assert "chunksStored" in data
    assert "vectorDb" in data

    print(
        f"[TEST] /index/stats passed ✓ - docs: {data['documentsIndexed']}, "
        f"chunks: {data['chunksStored']}"
    )
