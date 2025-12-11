import json
import pytest
from pathlib import Path
import sys
import types

# --- FIX PYTHONPATH ---
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
# ------------------------

# --- FIX IMPORT COLLISION FOR CI  ---
fake_app_models = types.ModuleType("app.models")

from services.monitoring.app.models import (
    MetricsSnapshot,
    IndexingMetrics,
    RequestMetrics,
)

fake_app_models.MetricsSnapshot = MetricsSnapshot
fake_app_models.IndexingMetrics = IndexingMetrics
fake_app_models.RequestMetrics = RequestMetrics

# Register fake module
sys.modules["app.models"] = fake_app_models
# ---------------------------------------------

import services.monitoring.app.metrics as metrics_mod
from services.monitoring.common.events import EventEnvelope


class FakeMessage:
    """
    Minimal async message stub used to simulate aio_pika.AbstractIncomingMessage.

    - handle_any_event() expects .ack() and .nack() methods.
    - This avoids requiring a live RabbitMQ connection during integration tests.
    """
    def __init__(self):
        self.acked = False
        self.nacked = False

    async def ack(self):
        """Mark message as acknowledged"""
        self.acked = True

    async def nack(self, requeue=True):
        """Mark message as rejected"""
        self.nacked = True


@pytest.fixture(autouse=True)
def clean_metrics_dir(tmp_path, monkeypatch):
    """
    Redirect metrics storage to a temp directory so tests do not touch /data.
    """
    fake_dir = tmp_path / "metrics"
    fake_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(metrics_mod, "METRICS_DIR", fake_dir)
    monkeypatch.setattr(metrics_mod, "EVENTS_LOG_PATH", fake_dir / "events.jsonl")
    monkeypatch.setattr(metrics_mod, "METRICS_JSON_PATH", fake_dir / "metrics.json")

    return fake_dir


@pytest.mark.asyncio
async def test_handle_chunksindexed_updates_state(clean_metrics_dir):
    """
    Integration test for core metrics aggregation:
    Simulate a ChunksIndexed event being processed by handle_any_event()
    """
    env = EventEnvelope(
        eventId="evt-1",
        eventType="ChunksIndexed",
        version=1,
        timestamp="2025-01-01T12:00:00Z",
        correlationId="abc-123",
        source="indexing-service",
        payload={"chunkCount": 7},
    )

    msg = FakeMessage()

    # IMPORTANTÍSIMO: llamar siempre al handler desde el módulo parcheado
    await metrics_mod.handle_any_event(env, msg)

    assert msg.acked is True
    assert msg.nacked is False

    # COMPROBAR rutas parcheadas: metrics_mod.EVENTS_LOG_PATH
    assert metrics_mod.EVENTS_LOG_PATH.exists()

    lines = metrics_mod.EVENTS_LOG_PATH.read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["eventType"] == "ChunksIndexed"
    assert record["payload"]["chunkCount"] == 7

    assert metrics_mod.METRICS_JSON_PATH.exists()

    snap = await metrics_mod.get_metrics_snapshot()
    assert snap.indexing.documentsIndexed == 1
    assert snap.indexing.chunksTotal == 7
    assert snap.eventCounts["ChunksIndexed"] == 1
    assert snap.byService["indexing-service"] == 1
    assert snap.lastSeen["indexing-service"] == "2025-01-01T12:00:00Z"
