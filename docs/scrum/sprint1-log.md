# MARP-Guide Chatbot — Sprint Log (Sprint 1)

This document records the sprint planning, progress, and outcomes for the MARP-Guide project.  
It focuses on **Sprint 1 (Weeks 1–5)** — the first increment required by the assessment:  
> “Core RAG Pipeline” — functional microservices architecture, event-driven communication, and basic RAG capability (≥1 citation).

---

## Sprint Overview

| Sprint | Duration | Sprint Goal | Status |
|--------|------------|--------------|---------|
| **Sprint 1** | Week 1 → Week 5 | Deliver a fully functional **RAG pipeline** connecting ingestion → extraction → indexing → retrieval → chat, with working events and Docker deployment. | Completed |

---

## Sprint Goal

> Implement the end-to-end data flow from MARP document ingestion to generating an answer with one citation using the RAG architecture.  
> All core services must run in Docker Compose and communicate asynchronously through RabbitMQ.

---

## Sprint Backlog

### Completed Items (Sprint 1)

| Epic | ID | Task | Responsible | Status | Notes |
|------|----|-------|-------------|---------|--------|
| **Ingestion** | ING-1 | Discover MARP PDF URLs | Youssef, Dominik | ✅ | Automatic discovery implemented |
| | ING-2 | Download PDFs and store metadata | Youssef, Dominik | ✅ | PDFs stored with metadata |
| | ING-3 | Publish `DocumentDiscovered` event | Youssef | ✅ | Event schema created and emitted |
| | ING-4 | Implement `/discover` endpoint | Youssef | ✅ | Manual trigger for discovery |
| **Extraction** | EXT-1 | Parse PDFs into clean text | Youssef, Ricardo | ✅ | Implemented with pdfplumber |
| | EXT-2 | Store extracted text as JSON | Youssef, Ricardo | ✅ | JSON output prepared for Indexing |
| | EXT-3 | Publish `DocumentExtracted` event | Youssef, Ricardo | ✅ | Successfully triggers Indexing |
| | EXT-4 | Implement `/health` endpoint | Ricardo | ✅ | Docker health checks enabled |
| **Indexing** | IDX-1 | Implement chunking strategy | Diego | ✅ | Custom chunking (~450 tokens + overlap) |
| | IDX-2 | Generate embeddings | Diego | ✅ | Uses Sentence-Transformers |
| | IDX-3 | Store embeddings in ChromaDB | Diego | ✅ | Chunks stored with metadata |
| | IDX-4 | Publish `ChunksIndexed` event | Diego | ✅ | Triggers Retrieval service |
| **Retrieval** | RET-1 | Implement `/search` endpoint | Ricardo | ✅ | Returns top-k chunks with metadata |
| | RET-2 | Include page number + title + URL | Ricardo | ✅ | Citation metadata added |
| | RET-3 | Publish `RetrievalCompleted` event | Ricardo | ✅ | Event forwarded to Monitoring |
| **RAG Chat Service** | RAG-1 | Implement `/chat` endpoint | Dominik | ✅ | Integrated LLM call |
| | RAG-2 | Prompt engineering | Dominik | ✅ | Ensures citation formatting |
| | RAG-3 | ≥1 citation generation | Dominik | ✅ | Core RAG pipeline functional |
| | RAG-5 | Publish `AnswerGenerated` event | Dominik | ✅ | Final pipeline step implemented |
| **Infrastructure** | INF-1 | Docker Compose setup | Diego, Youssef | ✅ | All services run together |
| | INF-2 | RabbitMQ integration | Youssef | ✅ | Reliable AMQP connectivity |
| | INF-5a | Service documentation | All | ✅ | Architecture, API schemas completed |
| | INF-5b | Project documentation | Diego, Youssef | ✅ | Scrum artefacts and deliverables written |
| | TEST-INF | Basic service health & container tests | All | ✅ | Confirmed services reachable |

---

## In Progress / Planned for Sprint 2

| Epic | ID | Task | Responsible | Status |
|------|----|-------|-------------|---------|
| **Ingestion** | TEST-ING | Unit tests | All | 🔜 Planned |
| **Extraction** | TEST-EXT | Unit tests | All | 🔜 Planned |
| **Indexing** | TEST-IDX | Unit tests | Diego | 🔄 In progress |
| **Retrieval** | TEST-RET | Unit tests | All | 🔜 Planned |
| **RAG Chat** | TEST-RAG | Unit tests | All | 🔜 Planned |
| **Monitoring** | MON-1 | Health dashboard | Youssef | 🔜 Planned |
| | MON-2 | Event counter metrics | Youssef | 🔜 Planned |
| | MON-3 | `/metrics` endpoint | Youssef | 🔜 Planned |
| **Infrastructure** | INF-3 | Automated testing | All | 🔜 Planned |
| | INF-4 | CI/CD pipeline | Diego | 🔄 In progress |

---

## Sprint Progress Summary

- **Total planned items:** 33  
- **Completed:** 26 ✅  
- **In progress:** 2 🔄  
- **Planned (next sprint):** 5 🔜  

Overall sprint completion: **≈75% functional coverage achieved.**  
Core RAG pipeline successfully implemented across all services.  
Unit tests initiated for each component; full automation and CI integration scheduled for Sprint 2.

---

## Review Summary

- All core services communicate via network interfaces (HTTP + RabbitMQ).  
- Events (`DocumentDiscovered`, `DocumentExtracted`, `ChunksIndexed`, `RetrievalCompleted`, `AnswerGenerated`) validated end-to-end.  
- Docker Compose confirmed operational with `docker compose up`.  
- Monitoring and testing to be expanded in Sprint 2.

---

_Last updated: November 2025_  
_Team: MARP.Guide.Y3 — Diego Laforet Fernández, Ricardo Coll González, Dominik Turowski, Youssef Bahaa._








