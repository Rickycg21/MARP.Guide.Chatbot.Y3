import json
import pytest
from pathlib import Path

import services.monitoring.app.metrics as metrics
from services.monitoring.common.events import EventEnvelope


@pytest.mark.asyncio
async def test_record_event_basic_counts(monkeypatch):
    """
    _record_event should increment eventCounts, byService and lastSeen.
    """

    # Reset internal state
    metrics._event_counts.clear()
    metrics._by_service.clear()
    metrics._last_seen.clear()

    env = EventEnvelope(
        eventId="evt-1",
        version=1,
        eventType="DocumentDiscovered",
        source="ingestion",
        payload={"x": 1},
        timestamp="2025-01-01T00:00:00+00:00",
        correlationId="c1",
    )


    # Call
    await metrics._record_event(env)

    assert metrics._event_counts["DocumentDiscovered"] == 1
    assert metrics._by_service["ingestion"] == 1
    assert metrics._last_seen["ingestion"] == "2025-01-01T00:00:00+00:00"

@pytest.mark.asyncio
async def test_record_event_chunksindexed(monkeypatch):
    """
    ChunksIndexed should increase chunk totals and documentsIndexed.
    """

    metrics._indexing_chunks_total = 0
    metrics._indexing_documents_indexed = 0

    env = EventEnvelope(
    eventId="evt-2",
    version=1,
    eventType="ChunksIndexed",
    source="indexing",
    payload={"chunkCount": 12},
    timestamp="t",
    correlationId="c",
    )


    await metrics._record_event(env)

    assert metrics._indexing_chunks_total == 12
    assert metrics._indexing_documents_indexed == 1

@pytest.mark.asyncio
async def test_get_metrics_snapshot(monkeypatch):
    """
    Snapshot should return a valid MetricsSnapshot that mirrors in-memory state.
    """

    # Seed some fake state
    metrics._event_counts.clear()
    metrics._event_counts["X"] = 3

    metrics._by_service.clear()
    metrics._by_service["svc"] = 2

    metrics._indexing_chunks_total = 5
    metrics._indexing_documents_indexed = 2

    metrics._retrieval_requests = 7
    metrics._chat_requests = 1

    metrics._last_seen.clear()
    metrics._last_seen["svc"] = "ts"

    snap = await metrics.get_metrics_snapshot()

    assert snap.eventCounts["X"] == 3
    assert snap.byService["svc"] == 2
    assert snap.indexing.chunksTotal == 5
    assert snap.indexing.documentsIndexed == 2
    assert snap.requests.retrievalRequests == 7
    assert snap.requests.chatRequests == 1
    assert snap.lastSeen["svc"] == "ts"

@pytest.mark.asyncio
async def test_append_event_log(tmp_path, monkeypatch):
    """
    _append_event_log should write one JSON line to events.jsonl.
    """

    class FakeSettings:
        data_root = str(tmp_path)

    monkeypatch.setattr(metrics, "settings", FakeSettings())

    log_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(metrics, "EVENTS_LOG_PATH", log_path)

    env = EventEnvelope(
        eventId="evt-log",
        version=1,
        eventType="X",
        source="svc",
        payload={"a": 1},
        timestamp="t",
        correlationId="c",
    )


    await metrics._append_event_log(env)

    assert log_path.exists()
    content = log_path.read_text().strip()
    assert '"eventType": "X"' in content
