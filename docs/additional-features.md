# MARP-Guide Chatbot — Tier 1 and 2 Features

This document provides a deeper explanation of the tier 1 and 2 features available in the MARP.Guide project pipeline.  

---

## Tier 1 Choice: Basic Monitoring Dashboard

### Overview

The Basic Monitoring Dashboard provides a real-time view of system activity across all services in the MARP-Guide RAG pipeline. It is implemented as an independent microservice that listens to all pipeline events via RabbitMQ and dynamically aggregates metrics in memory. It exposes both a machine-readable API (/metrics) and a human-friendly web UI (/dashboard) to visualise system performance during a run.

### Design

**Role of the Monitoring Service**  

The Monitoring service is a passive observer in the architecture. It does not modify system behaviour or call any other service’s APIs. Instead, it subscribes to all relevant events produced by the system:  
`DocumentDiscovered`  
`DocumentExtracted`  
`ChunksIndexed`  
`RetrievalCompleted`  
`AnswerGenerated`  

These event types provide complete visibility across the ingestion → extraction → indexing → retrieval → chat pipeline.

**Event-Driven Monitoring**

Monitoring uses the shared event infrastructure designed for all services:  
It binds a queue named monitoring-service.{eventType} for each event type and consumes events asynchronously using common.events.consume(...).  

Each received event updates an in-memory metrics state which ensures:  
decoupling from other services, zero modification to the pipeline, real-time metrics aggregation, proper microservice boundaries (no direct REST calls between services).  

**Run-Local Metrics Model**  

Metrics reset on each container start. The dashboard visualises the current run only. No cross-run persistence is performed (to avoid stale or confusing data during demonstrations).

**Dashboard Design**  

The dashboard (GET /dashboard) is a simple HTML page showing:  
- Total number of events processed  
- Documents indexed and total chunks stored  
- Retrieval request count  
- Chat request count  
- Events by type  
- Events by service  
- Average latency (retrieval + chat)  
- Last-seen timestamps for each service  

The UI uses a responsive CSS grid so it renders correctly on desktops, laptops, and tablets without any frontend frameworks.  

### Implementation  

**Startup Behaviour**  

On startup, Monitoring writes an initial empty snapshot into metrics.json and starts one background consumer task per event type.  
Metrics begin from zero for each run.  

**Event Handling**

Incoming events are processed by handle_any_event() and memory state is updated based on the incoming event which gives Monitoring a complete, real-time view of system activity.  

**No Cross-Service REST Calls**

Monitoring intentionally never makes REST calls to other services. All data flows through RabbitMQ, preserving microservice boundaries and following strict event-driven principles.  

### Rationale  

**Why Event-Driven Monitoring?**  

- Eliminates tight coupling  
- Avoids polling or REST dependency chains  
Works naturally with your existing event envelope structure  
- Scales well if new services or event types are added  

**Why Run-Local Instead of Persistent Metrics?**

- Simpler for demonstration  
- Prevents stale data after container restarts  
- Ensures every run starts from a clean and predictable state  

---

## Tier 2 Choice: Hybrid Search

The **Hybrid Search** tier improves retrieval relevance by combining two complementary retrieval strategies:  
**lexical matching** and **semantic similarity**.  
Instead of relying solely on embeddings or keyword search, it merges both. This ensures that the system returns passages that are both lexically relevant and contextually meaningful, even when user phrasing differs from the document wording.

### How Hybrid Search Works

1. **Semantic Vector Search**
   - Queries and document chunks are transformed into dense embeddings.  
   - Similarity is computed via cosine or dot-product distance.  
   - Captures meaning even when user phrasing differs from the text.

2. **Keyword (Lexical) Search via BM25**
   - Identifies documents containing key terms from the query.  
   - Strong when users reference specific terminology or names.

3. **Score Fusion**
   - Retrieves topk*5 candidate chunks semantically.  
   - Calculates the bm25 score for all candidate chunks.
   - Combines both scores of all candidate chunks and outputs topk chunks with the highest combined score.

### Benefits

- Handles vague or paraphrased questions more effectively than keyword-only systems.  
- Maintains precision for highly specific fact-based queries.  

### Architecture Notes

- Implemented entirely within the **Retrieval Service**.  
- For performance purposes, it does not calculate bm25 for all chunks, only the candidate ones chosen semantically.
- **Hybrid** mode is the default for all queries, however, it is possible to select **semantic** mode when using the retrieval endpoint.

Hybrid Search delivers the strongest retrieval performance while remaining modular and incrementally adoptable.

---