import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

# Importa la app real
import services.chat.app.main as chat_mod


@pytest.mark.asyncio
async def test_chat_integration(monkeypatch):
    """
    Integration test:
    - /chat endpoint is called through FastAPI
    - Retrieval returns 2 chunks
    - LLM returns grounded answer
    """

    async def fake_retrieve(question: str, top_k: int, correlation_id: str):
        chunks = [
            chat_mod.RetrievedChunk(text="A", title="DocA", score=0.9),
            chat_mod.RetrievedChunk(text="B", title="DocB", score=0.8),
        ]
        meta = {
            "query_id": "Q123",
            "mode": "hybrid",
            "duration_ms": 10,
            "result_count": 2,
            "results": [],
        }
        return chunks, meta

    async def fake_llm_answer(question, context):
        return {
            "text": "Integration grounded answer [1] [2]",
            "tokens_used": 12,
            "model": "test-model",
            "citations": [
                chat_mod.Citation(title="DocA"),
                chat_mod.Citation(title="DocB"),
            ],
        }

    ev_published = []

    async def fake_publish(event):
        ev_published.append(event)

    # Patch services
    monkeypatch.setattr(chat_mod, "_retrieve", fake_retrieve)
    monkeypatch.setattr(chat_mod, "_llm_answer", fake_llm_answer)
    monkeypatch.setattr(chat_mod, "publish_event", fake_publish)
    monkeypatch.setattr(chat_mod, "_append_answer_metadata", lambda rec: None)

    transport = ASGITransport(app=chat_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/chat", json={"question": "Hello?", "top_k": 3})

    assert response.status_code == 200
    data = response.json()

    assert data["answer"].startswith("Integration grounded answer")
    assert data["model"] == "test-model"
    assert len(data["citations"]) == 2
    assert data["latency_ms"] >= 0

    # Must produce one AnswerGenerated event
    assert len(ev_published) == 1


@pytest.mark.asyncio
async def test_chat_integration_llm_failure(monkeypatch):
    """
    Integration test:
    - retrieval ok → LLM throws exception → chat returns static error msg
    """

    async def fake_retrieve(*args, **kwargs):
        chunks = [
            chat_mod.RetrievedChunk(text="A", score=0.9),
            chat_mod.RetrievedChunk(text="B", score=0.8),
        ]
        meta = {
            "query_id": "Q999",
            "mode": "hybrid",
            "duration_ms": 10,
            "result_count": 2,
            "results": [],
        }
        return chunks, meta

    async def fake_llm_answer(*args, **kwargs):
        raise HTTPException(status_code=502, detail="LLM down")

    monkeypatch.setattr(chat_mod, "_retrieve", fake_retrieve)
    monkeypatch.setattr(chat_mod, "_llm_answer", fake_llm_answer)
    monkeypatch.setattr(chat_mod, "publish_event", lambda e: None)
    monkeypatch.setattr(chat_mod, "_append_answer_metadata", lambda r: None)

    transport = ASGITransport(app=chat_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/chat", json={"question": "Test error", "top_k": 2})

    assert response.status_code == 200
    data = response.json()

    assert "LLM service is unavailable" in data["answer"]
    assert data["model"] == "n/a"
    assert data["citations"] == []
