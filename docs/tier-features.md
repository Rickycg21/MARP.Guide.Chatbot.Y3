# MARP-Guide Chatbot — Tier 1 and 2 Features

This document provides a deeper explanation of the tier 1 and 2 features available in the MARP.Guide project pipeline.  

---

## Tier 1 Choice: Basic Monitoring Dashboard

The **Monitoring Service** is an independent microservice responsible for passive system observability.  
It consumes all events emitted across the pipeline—`DocumentDiscovered`, `DocumentFetched`, `DocumentExtracted`,  
`DocumentIndexed`, `QueryRequested`, `AnswerGenerated`, and others—without ever interfering with core workflows.

### Key Capabilities

- **Operational Metrics Tracking**
  - Counts how many documents were discovered, fetched, extracted, and indexed.  
  - Records how many retrieval or chat queries were processed.  
  - Tracks system errors and anomalies inferred from event patterns.

- **Latency Measurement**
  - Measures round-trip latency for retrieval requests and chat responses.  
  - Supports simple SLA or performance-trend observation.

- **Health Observation via Event Heartbeats**
  - Infers service health based on incoming events’ `source` fields.  
  - Detects when a pipeline stage becomes silent or falls behind.

- **Lightweight Dashboard**
  - Exposes a minimal HTML dashboard showing counters, charts, and status indicators.  
  - Intended for demonstration and teaching, not enterprise-grade monitoring.

### Architecture Notes

- Communicates **only via AMQP (RabbitMQ)** — no REST calls are made to any service.  
- Stores simple counters and timestamps locally.  
- Fully decoupled: the pipeline continues even if Monitoring is offline.

This tier enhances visibility into pipeline behavior while remaining safe, read-only, and minimalistic.

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