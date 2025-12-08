# MARP-Guide Chatbot — Sprint 2 Retrospective

This document summarizes the team’s reflection after completing **Sprint 2 (Weeks 6–10)** for the MARP-Guide project.  
The sprint focused on **system stability, testing, CI automation, monitoring features, hybrid search improvements, and delivering the final Chat UI interface**.

---

## Sprint recap
**Sprint Goal:**  
> Deliver a stable, fully tested system with automated CI pipelines, hybrid retrieval improvements, monitoring capabilities, and a functional Chat UI.

**Sprint Outcome:**  
Achieved.  
All remaining features from Sprint 1 were completed, including testing, CI, hybrid search, monitoring service, and the user interface.  
The entire system is now stable and ready for final assessment.

---

## What went well

| Category | Notes |
|-----------|--------|
| **Testing & Quality Assurance** | Over 20+ unit and integration tests implemented with >90% coverage |
| **CI Automation** | GitHub Actions fully operational: installs dependencies, runs tests, and validates all services on every push. |
| **Debugging & Stability** | Fixed issues across Retrieval, Monitoring, and Indexing. |
| **Retrieval Improvements** | Hybrid search (BM25) implemented and tuned for better ranking accuracy. |
| **Monitoring Service** | `/metrics` endpoint, event counters, and health checks completed. |
| **Chat UI Completion** | Fully functional UI delivered, enabling end-to-end user interaction with >2 citations. Handled graceful fallback and failure |
| **Team Collaboration** | Consistent communication via Discord, WhatsApp and weekly in person meetings. Fast debugging cycles and shared responsibility. |

---

## What didn’t go well

| Category | Notes |
|-----------|--------|
| **Initial Test Failures** | Several tests failed due to import collisions, filesystem paths, and event mocks. Required multiple iterations to stabilise. |
| **CI Environment Differences** | GitHub Actions runners behaved differently from local Docker runs (missing models, dependency caching, path issues). |
| **Time Spent Debugging** | Significant time was invested in fixing Retrieval hybrid logic, Monitoring JSON outputs, and PYTHONPATH errors. |

---

## Summary

- **Sprint Success:** All remaining work from Sprint 1 was completed. The system is now fully tested, monitored, CI-validated, and includes the final user interface.  
- **Team Work:** Collaboration strengthened during debugging and CI challenges.  
- **Outcome:** The MARP-Guide system is stable, complete, and aligns with all assessment requirements.

---

_Last updated: December 2025_  
_Team: MARP.Guide.Y3 — Diego Laforet Fernández, Ricardo Coll González, Dominik Turowski, Youssef Bahaa._




