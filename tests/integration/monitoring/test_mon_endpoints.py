import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# --- FIX PYTHONPATH ---
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
# ------------------------

# Import the FastAPI app
from services.monitoring.app.main import app  

@pytest.fixture(autouse=True)
def mock_startup(monkeypatch):
    """
    Integration test patch:
    Avoid the real startup behaviour (RabbitMQ consumers + file writes).
    Replace startup_metrics() with a dummy async function and block consume().
    """
    async def fake_startup_metrics():
        return None

    async def fake_consume(*args, **kwargs):
        return None

    # Patch imports used in main.py
    import services.monitoring.app.metrics as metrics_mod
    import services.monitoring.common.events as events_mod

    monkeypatch.setattr(metrics_mod, "startup_metrics", fake_startup_metrics)
    monkeypatch.setattr(events_mod, "consume", fake_consume)

@pytest.fixture
def client():
    """
    Test client wrapping FastAPI.
    """
    return TestClient(app)

def test_health_endpoint(client):
    """
    Integration test for GET /health.
    Ensures the monitoring service responds with status=ok and service name.
    """
    res = client.get("/health")
    assert res.status_code == 200

    body = res.json()
    assert body["status"] == "ok"
    assert "service" in body

def test_metrics_endpoint(client):
    """
    Integration test for GET /metrics.
    Should return a valid MetricsSnapshot (all fields present, empty state).
    """
    res = client.get("/metrics")
    assert res.status_code == 200

    data = res.json()

    # Mandatory fields from MetricsSnapshot model
    assert "updatedAt" in data
    assert "eventCounts" in data
    assert "byService" in data
    assert "avgLatencyMs" in data
    assert "indexing" in data
    assert "requests" in data
    assert "lastSeen" in data

    # metrics.json baseline when no events happened
    assert data["indexing"]["documentsIndexed"] == 0
    assert data["indexing"]["chunksTotal"] == 0
    assert data["requests"]["retrievalRequests"] == 0
    assert data["requests"]["chatRequests"] == 0


def test_dashboard_html(client):
    """
    Integration test for GET /dashboard.
    Should return HTML with expected title.
    """
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]

    html = res.text
    assert "<title>MARP-Guide Monitoring Dashboard</title>" in html


def test_root_alias(client):
    """
    Integration test for GET /.
    Should be identical to /dashboard.
    """
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]

    html = res.text
    assert "Monitoring Dashboard" in html
