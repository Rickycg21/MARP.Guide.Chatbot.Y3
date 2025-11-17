# Monitoring Service

## Responsibility
Provide a Basic Monitoring Dashboard (Tier 1 Feature) that aggregates service health, pipeline event statistics, indexing progress, and request counts.
It consumes all events produced by the RAG pipeline and exposes a small dashboard showing live system metrics.

## Data Owned
- `/data/metrics/events.jsonl` — append-only event log
- `/data/metrics/metrics.json` — aggregated service metrics snapshot  
  (updated_at, event_counts{}, by_service{}, avg_latency_ms{}, indexing{}, requests{}, last_seen{}).


## API Endpoints
| Method | Endpoint | Description | Returns |
|---------|-----------|--------------|----------|
| GET | `/metrics` | Return aggregated service metrics | 200 OK + JSON |
| GET | `/dashboard` | Simple web UI showing status per service | 200 OK + HTML |
| GET | `/health` | Health check | 200 OK |

## Events
- **Consumes:** `DocumentDiscovered`, `DocumentExtracted`, `ChunksIndexed`, `RetrievalCompleted`, `AnswerGenerated`
- **Publishes:** *(none)*

## Communicates With
- RabbitMQ (event broker)
- Local `data/` folder