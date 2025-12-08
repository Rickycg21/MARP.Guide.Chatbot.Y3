# MARP-Guide Chatbot — Sprint Log (Sprint 2)

This document records the sprint planning, progress, and outcomes for the MARP-Guide project.  
It focuses on **Sprint 2 (Weeks 6–10)** — the second increment required by the assessment:

> “Debugging, Testing & Features expansion” — complete CI integration, implement monitoring, finish testing coverage, improve retrieval quality, and deliver chat interface.

---

## Sprint Overview

| Sprint | Duration | Sprint Goal | Status |
|--------|------------|--------------|---------|
| **Sprint 2** | Week 6 → Week 10 | Deliver a stable, fully tested MARP RAG system with CI/CD automation, monitoring metrics, hybrid search improvements, and final Chat UI. | Completed |

---

## Sprint Goal

> Deliver a stable, fully tested system with automated CI/CD pipelines, hybrid retrieval logic, monitoring capabilities, and a functional Chat UI.  
> Ensure the entire RAG pipeline is reliable and ready for final assessment.

---

## Sprint Backlog

### Completed Items (Sprint 2)

| Epic | ID | Task | Responsible | Status | Notes |
|------|----|-------|-------------|---------|--------|
| **Ingestion** | TEST-ING | Unit tests for ingestion workflow | Diego | ✅ | Tests for URL discovery, download stubs, and event emission |
| **Extraction** | TEST-EXT | Unit tests for extraction logic | Diego | ✅ | Validates text extraction + event publication |
| **Indexing** | TEST-IDX | Unit tests for chunking & embedding pipeline | Diego | ✅ | Added deterministic chunk-ID tests and embedding mocks |
| **Retrieval** | RET-4 | Fix hybrid scoring formula | Ricardo | ✅ | Balanced dense + BM25 weighting for more accurate ranking |
| | TEST-RET | Unit tests for retrieval API | Diego | ✅ | Included tests for hybrid search and ranking behaviour |
| **RAG Chat** | RAG-4 | Answers with ≥2 citations | Dominik | ✅ | Final MVP requirement achieved |
| | RAG-6 | Build Chat UI | Dominik | ✅ | Interface for querying MARP with citations |
| | TEST-RAG | Unit tests for RAG builder | Diego | ✅ | Covers prompt assembly, context handling, and mock LLM output |
| **Monitoring** | MON-2 | Event counter metrics | Youssef | ✅ | Tracks event totals per service |
| | MON-3 | `/metrics` endpoint | Youssef | ✅ | Exposes counters in JSON for CI/Grafana |
| | TEST-MON | Monitoring endpoint tests | Diego | ✅ | Validates health + metrics JSON structure |
| **Infrastructure** | INF-3 | Automated testing | Diego | ✅ | Achieved 20+ tests across all services |
| | INF-4 | GitHub Actions CI pipeline | Diego | ✅ | CI now builds images, installs deps, runs tests successfully |

---

## Sprint Progress Summary

- **Total planned items:** 13  
- **Completed:** 13 (100%)  
- All carry-over tasks from Sprint 1 successfully finished.  
- CI pipeline fully implemented and running for all pushes.  
- Monitoring metrics and JSONL logging now provide system observability.  
- Retrieval hybrid search improved significantly with new scoring.  
- Final Chat UI completed inside the RAG epic.  
- Test coverage expanded across all services with consistent folder structure.

Overall sprint completion: **System fully stable, tested, monitored, and ready for final submission.**

---

## Review Summary

- CI pipeline operational (pytest + Docker + AMQP all verified).  
- Over 20 unit/integration tests added across services.  
- Monitoring service now exposes metrics required by Tier 1.  
- RAG service upgraded to produce ≥2 citations.  
- Retrieval's hybrid search improved and stabilised.  
- Chat UI functional and integrated with backend services.  
- System now meets all final assessment requirements.

---

_Last updated: December 2025_  
_Team: MARP.Guide.Y3 — Diego Laforet Fernández, Ricardo Coll González, Dominik Turowski, Youssef Bahaa._
