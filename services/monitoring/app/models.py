"""
Pydantic models (schemas) used by the Monitoring service.
These models define the shape of the JSON returned by GET /metrics.
"""

from typing import Dict
from pydantic import BaseModel, Field


class IndexingMetrics(BaseModel):
    """
    Aggregated indexing-related metrics.

    documentsIndexed:
        How many documents have produced at least one ChunksIndexed event.
    chunksTotal:
        Total number of chunks reported across all ChunksIndexed events.
    """
    documentsIndexed: int = 0
    chunksTotal: int = 0


class RequestMetrics(BaseModel):
    """
    Aggregated request counts for the user-facing services.

    retrievalRequests:
        Number of retrieval queries observed (RetrievalCompleted events).
    chatRequests:
        Number of chat answers observed (AnswerGenerated events).
    """
    retrievalRequests: int = 0
    chatRequests: int = 0


class MetricsSnapshot(BaseModel):
    """
    Top-level metrics snapshot returned by GET /metrics and written to
    /data/metrics/metrics.json.

    updatedAt:
        ISO timestamp (UTC) when this snapshot was computed.
    eventCounts:
        How many events we've seen per eventType.
    byService:
        How many events we've seen per source service_name.
    avgLatencyMs:
        Average latency per event type that carries a latency field in its payload
        (RetrievalCompleted and AnswerGenerated).
    indexing:
        Indexing-related metrics (documents indexed, total chunks).
    requests:
        Request counts for retrieval and chat.
    lastSeen:
        Last event timestamp observed per service_name.
    """
    updatedAt: str
    eventCounts: Dict[str, int] = Field(default_factory=dict)
    byService: Dict[str, int] = Field(default_factory=dict)
    avgLatencyMs: Dict[str, float] = Field(default_factory=dict)
    indexing: IndexingMetrics = Field(default_factory=IndexingMetrics)
    requests: RequestMetrics = Field(default_factory=RequestMetrics)
    lastSeen: Dict[str, str] = Field(default_factory=dict)