"""
Metrics aggregation + event handling for the Monitoring service.

Responsibilities:
- Maintain in-memory counters for events during the lifetime of the container.
- Persist a snapshot for the current run to /data/metrics/metrics.json.
- Append a JSONL event log for the current run to /data/metrics/events.jsonl.
- Provide helper functions used by the FastAPI layer (main.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, Optional
from aio_pika.abc import AbstractIncomingMessage

from common.config import settings
from common.events import EventEnvelope, now_iso

from app.models import MetricsSnapshot, IndexingMetrics, RequestMetrics

logger = logging.getLogger("monitoring")

# Directory + files under DATA_ROOT
METRICS_DIR = Path(settings.data_root) / "metrics"
EVENTS_LOG_PATH = METRICS_DIR / "events.jsonl"
METRICS_JSON_PATH = METRICS_DIR / "metrics.json"

# Event types Monitoring subscribes to in main.py
EVENT_TYPES = [
    "DocumentDiscovered",
    "DocumentExtracted",
    "ChunksIndexed",
    "RetrievalCompleted",
    "AnswerGenerated",
]

# -----------------------------------------------------------------------------
# In-memory state (protected by an asyncio.Lock)
# -----------------------------------------------------------------------------
_metrics_lock = asyncio.Lock()

_event_counts: Dict[str, int] = defaultdict(int)
_by_service: Dict[str, int] = defaultdict(int)

# latency aggregation per eventType: sum + count -> average
_latency_sum: Dict[str, float] = defaultdict(float)
_latency_count: Dict[str, int] = defaultdict(int)

_indexing_documents_indexed: int = 0
_indexing_chunks_total: int = 0

_retrieval_requests: int = 0
_chat_requests: int = 0

_last_seen: Dict[str, str] = {}  # service_name -> last event timestamp

# -----------------------------------------------------------------------------
# Startup helper
# -----------------------------------------------------------------------------
async def startup_metrics() -> None:
    """
    Initialise metrics storage for this run.

    - Ensure /data/metrics exists.
    - Ensure events.jsonl and metrics.json exist.
    - DO NOT load any previous content: each run starts from a clean state.
    """
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    # Ensure the events log file exists (JSON Lines, one event per line).
    if not EVENTS_LOG_PATH.exists():
        EVENTS_LOG_PATH.touch(exist_ok=True)

    # Ensure there is at least an initial empty metrics.json snapshot.
    snap = await get_metrics_snapshot()
    try:
        METRICS_JSON_PATH.write_text(
            json.dumps(snap.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to write initial metrics.json")

# -----------------------------------------------------------------------------
# Persistence helpers (for current run)
# -----------------------------------------------------------------------------
async def _persist_metrics_to_disk() -> None:
    """
    Serialise the current in-memory state into metrics.json.
    Called after each event update to keep the snapshot up-to-date.
    """
    snap = await get_metrics_snapshot()
    try:
        METRICS_JSON_PATH.write_text(
            json.dumps(snap.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to write metrics.json")


async def _append_event_log(envelope: EventEnvelope) -> None:
    """
    Append a single line to events.jsonl with a compact representation of the
    event.
    """
    try:
        data = {
            "timestamp": envelope.timestamp,
            "eventType": envelope.eventType,
            "source": envelope.source,
            "correlationId": envelope.correlationId,
            "payload": envelope.payload,
        }
        with EVENTS_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to append to events.log")

# -----------------------------------------------------------------------------
# Event handling / aggregation
# -----------------------------------------------------------------------------
def _update_latency(event_type: str, latency_ms: Optional[float]) -> None:
    """
    Update running sum + count for a latency metric keyed by event type.
    """
    if latency_ms is None:
        return
    try:
        value = float(latency_ms)
    except (TypeError, ValueError):
        return

    _latency_sum[event_type] += value
    _latency_count[event_type] += 1

async def _record_event(envelope: EventEnvelope) -> None:
    """
    Update in-memory metrics based on one incoming event.
    """
    global _indexing_documents_indexed, _indexing_chunks_total
    global _retrieval_requests, _chat_requests

    etype = envelope.eventType
    source = envelope.source or "unknown-service"
    payload = envelope.payload or {}

    async with _metrics_lock:
        # Basic counters
        _event_counts[etype] += 1
        _by_service[source] += 1
        _last_seen[source] = envelope.timestamp

        # Event-specific enrichment
        if etype == "ChunksIndexed":
            # payload: { documentId, chunkCount, embeddingModel, vectorDb, vectorDimension, indexPath }
            chunk_count = payload.get("chunkCount")
            if isinstance(chunk_count, (int, float)):
                _indexing_chunks_total += int(chunk_count)
            # count "documents indexed" by counting events
            _indexing_documents_indexed += 1

        elif etype == "RetrievalCompleted":
            # payload: { queryId, query, resultsCount, topScore, latencyMs, results[...] }
            _retrieval_requests += 1
            latency = payload.get("latencyMs") or payload.get("latency_ms")
            _update_latency(etype, latency)

        elif etype == "AnswerGenerated":
            # payload: includes latencyMs/latency_ms field from chat service
            _chat_requests += 1
            latency = payload.get("latencyMs") or payload.get("latency_ms")
            _update_latency(etype, latency)

async def handle_any_event(
    envelope: EventEnvelope,
    message: AbstractIncomingMessage,
) -> None:
    """
    Generic handler used for ALL subscribed event types.

    For each event:
    - update in-memory counters,
    - append to events.jsonl,
    - persist a fresh metrics.json snapshot,
    - and then ack() the message.

    On failure, it nack(requeue=True) so the event can be retried.
    """
    try:
        await _record_event(envelope)
        await _append_event_log(envelope)
        await _persist_metrics_to_disk()
        await message.ack()
    except Exception as exc:
        logger.exception("Failed to process event %s: %s", envelope.eventType, exc)
        await message.nack(requeue=True)

# -----------------------------------------------------------------------------
# Public helpers for FastAPI layer
# -----------------------------------------------------------------------------
async def get_metrics_snapshot() -> MetricsSnapshot:
    """
    Build a MetricsSnapshot from the current in-memory state.
    """
    async with _metrics_lock:
        # Compute average latencies from sum + count
        avg_latency: Dict[str, float] = {}
        for etype, total in _latency_sum.items():
            count = _latency_count.get(etype, 0) or 1
            avg_latency[etype] = float(total) / float(count)

        indexing = IndexingMetrics(
            documentsIndexed=_indexing_documents_indexed,
            chunksTotal=_indexing_chunks_total,
        )
        requests = RequestMetrics(
            retrievalRequests=_retrieval_requests,
            chatRequests=_chat_requests,
        )

        snap = MetricsSnapshot(
            updatedAt=now_iso(),
            eventCounts=dict(_event_counts),
            byService=dict(_by_service),
            avgLatencyMs=avg_latency,
            indexing=indexing,
            requests=requests,
            lastSeen=dict(_last_seen),
        )
        return snap

async def render_dashboard_html() -> str:
    """
    Render a small HTML dashboard using the current metrics snapshot.
    """
    snap = await get_metrics_snapshot()

    def _table(title: str, rows: Dict[str, Any]) -> str:
        if not rows:
            return f"<h3>{title}</h3><p><em>No data yet.</em></p>"
        cells = "\n".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in sorted(rows.items())
        )
        return f"""
        <h3>{title}</h3>
        <table>
          <thead><tr><th>Key</th><th>Value</th></tr></thead>
          <tbody>{cells}</tbody>
        </table>
        """

    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>MARP-Guide Monitoring Dashboard</title>
      <style>
        body {{
          font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          margin: 2rem;
          background-color: #0f172a;
          color: #e5e7eb;
        }}
        h1, h2, h3 {{ color: #facc15; }}
        .cards {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 1.5rem;
          margin-bottom: 2rem;
        }}
        .card {{
          background-color: #020617;
          border-radius: 1rem;
          padding: 1.25rem 1.5rem;
          box-shadow: 0 10px 40px rgba(15, 23, 42, 0.8);
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin-top: 0.5rem;
        }}
        th, td {{
          padding: 0.35rem 0.5rem;
          border-bottom: 1px solid #1f2937;
        }}
        th {{ text-align: left; color: #9ca3af; font-size: 0.8rem; }}
        td {{ font-size: 0.85rem; }}
        .pill {{
          display: inline-block;
          padding: 0.2rem 0.6rem;
          border-radius: 999px;
          background-color: #065f46;
          color: #bbf7d0;
          font-size: 0.75rem;
          font-weight: 600;
        }}
        small {{ color: #9ca3af; }}
      </style>
    </head>
    <body>
      <h1>MARP-Guide Monitoring Dashboard</h1>
      <p><small>Last updated: {snap.updatedAt}</small></p>

      <div class="cards">
        <div class="card">
          <h2>Pipeline Overview</h2>
          <p>Total events: <span class="pill">{sum(snap.eventCounts.values())}</span></p>
          <p>Documents indexed: <span class="pill">{snap.indexing.documentsIndexed}</span></p>
          <p>Total chunks: <span class="pill">{snap.indexing.chunksTotal}</span></p>
          <p>Retrieval requests: <span class="pill">{snap.requests.retrievalRequests}</span></p>
          <p>Chat answers: <span class="pill">{snap.requests.chatRequests}</span></p>
        </div>
        <div class="card">
          {_table("Events by Type", snap.eventCounts)}
        </div>
        <div class="card">
          {_table("Events by Service", snap.byService)}
        </div>
        <div class="card">
          {_table("Average Latency (ms)", snap.avgLatencyMs)}
        </div>
      </div>

      <div class="card">
        {_table("Last Seen per Service", snap.lastSeen)}
      </div>
    </body>
    </html>
    """
    return html