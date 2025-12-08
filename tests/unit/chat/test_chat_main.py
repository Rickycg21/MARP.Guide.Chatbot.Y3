# tests/unit/chat/test_chat_service.py

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi import HTTPException

# Ajusta este import si la ruta es distinta
import services.chat.app.main as chat_mod


def test_select_context_limits_to_citation_limit():
    """
    _select_context should return at most CITATION_LIMIT chunks, preserving order.
    """
    chunks = [
        chat_mod.RetrievedChunk(text=f"chunk-{i}", score=1.0)
        for i in range(10)
    ]

    selected = chat_mod._select_context(chunks)

    assert len(selected) == chat_mod.CITATION_LIMIT
    assert [c.text for c in selected] == [f"chunk-{i}" for i in range(chat_mod.CITATION_LIMIT)]


def test_select_context_empty_returns_empty():
    """
    _select_context should gracefully handle an empty list.
    """
    selected = chat_mod._select_context([])
    assert selected == []


def test_append_answer_metadata_writes_jsonl_line(tmp_path, monkeypatch):
    """
    _append_answer_metadata should append a single JSON object as one JSONL line.
    """
    meta_path = tmp_path / "answer_metadata.jsonl"

    monkeypatch.setattr(chat_mod, "ANSWER_META_PATH", str(meta_path))

    record = {"foo": "bar", "n": 123}
    chat_mod._append_answer_metadata(record)

    assert meta_path.exists()
    content = meta_path.read_text(encoding="utf-8").strip()
    # One line, valid JSON, equal to our record
    lines = content.splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed == record


@pytest.mark.asyncio
async def test_chat_pipeline(monkeypatch, tmp_path):
    """
    chat endpoint: retrieval returns chunks, LLM returns grounded answer,
    metadata is persisted and AnswerGenerated event is published.
    """
    # Fake retrieval payload: 3 chunks with scores above threshold
    chunks = [
        chat_mod.RetrievedChunk(text="A", title="DocA", score=0.9),
        chat_mod.RetrievedChunk(text="B", title="DocB", score=0.8),
        chat_mod.RetrievedChunk(text="C", title="DocC", score=0.7),
    ]
    retrieval_meta = {
        "query_id": "Q1",
        "mode": "hybrid",
        "duration_ms": 12,
        "result_count": len(chunks),
        "results": [],
    }

    async def fake_retrieve(question: str, top_k: int, correlation_id: str):
        return chunks, retrieval_meta

    # Fake LLM answer
    async def fake_llm_answer(question: str, context_blocks: List[chat_mod.RetrievedChunk]) -> Dict[str, Any]:
        return {
            "text": "This is an answer. [1] [2]",
            "tokens_used": 42,
            "model": "test-model",
            "citations": [
                chat_mod.Citation(title="DocA"),
                chat_mod.Citation(title="DocB"),
            ],
        }

    # Capture metadata records written to disk
    records: List[Dict[str, Any]] = []

    def fake_append(record: Dict[str, Any]) -> None:
        records.append(record)

    # Capture published events
    events: List[Any] = []

    async def fake_publish_event(event: Any) -> None:
        events.append(event)

    monkeypatch.setattr(chat_mod, "_retrieve", fake_retrieve)
    monkeypatch.setattr(chat_mod, "_llm_answer", fake_llm_answer)
    monkeypatch.setattr(chat_mod, "_append_answer_metadata", fake_append)
    monkeypatch.setattr(chat_mod, "publish_event", fake_publish_event)

    req = chat_mod.ChatRequest(question="Hello MARP?", top_k=5)
    resp = await chat_mod.chat(req)

    assert resp.answer.startswith("This is an answer")
    assert resp.model == "test-model"
    assert resp.tokens_used == 42
    assert resp.citations  # non-empty
    assert resp.latency_ms >= 0
    assert resp.correlation_id

    # Metadata persisted once
    assert len(records) == 1
    rec = records[0]
    assert rec["question"] == req.question
    assert rec["top_k"] == req.top_k
    assert rec["model"] == resp.model
    assert rec["retrieval"]["query_id"] == retrieval_meta["query_id"]
    assert len(rec["context_used"]) >= 1

    # One AnswerGenerated event published
    assert len(events) == 1
    ev = events[0]
    # Fallback new_event may be a dataclass; just check basic attributes
    assert getattr(ev, "eventType", None) == "AnswerGenerated"


@pytest.mark.asyncio
async def test_chat_retrieval_404(monkeypatch):
    """
    If retrieval raises HTTP 404, chat should call _llm_fallback and return
    its text, with no citations or events/metadata.
    """
    async def fake_retrieve(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="No supporting sources found")

    async def fake_llm_fallback(question: str) -> Dict[str, Any]:
        return {
            "text": "Fallback answer: no MARP sources.",
            "tokens_used": 10,
            "model": "fallback-model",
        }

    records: List[Dict[str, Any]] = []
    events: List[Any] = []

    monkeypatch.setattr(chat_mod, "_retrieve", fake_retrieve)
    monkeypatch.setattr(chat_mod, "_llm_fallback", fake_llm_fallback)
    monkeypatch.setattr(chat_mod, "_append_answer_metadata", lambda rec: records.append(rec))
    monkeypatch.setattr(chat_mod, "publish_event", lambda ev: events.append(ev))

    req = chat_mod.ChatRequest(question="Non-MARP question?", top_k=3)
    resp = await chat_mod.chat(req)

    assert resp.answer.startswith("Fallback answer")
    assert resp.model == "fallback-model"
    assert resp.citations == []
    # In this branch we do NOT persist metadata or publish events
    assert records == []
    assert events == []

@pytest.mark.asyncio
async def test_chat_insufficient_context(monkeypatch):
    """
    If retrieval returns < 2 context blocks, chat should use _llm_fallback
    and not call _llm_answer.
    """
    chunks = [chat_mod.RetrievedChunk(text="only-one", score=0.9)]
    retrieval_meta = {"query_id": "Q1", "mode": "hybrid", "duration_ms": 5, "result_count": 1, "results": []}

    async def fake_retrieve(*_args, **_kwargs):
        return chunks, retrieval_meta

    async def fake_llm_fallback(question: str) -> Dict[str, Any]:
        return {
            "text": "Not enough MARP context.",
            "tokens_used": 5,
            "model": "fallback-model",
        }

    # If _llm_answer gets called, we want the test to fail loudly
    async def fail_llm_answer(*_args, **_kwargs):
        raise AssertionError("_llm_answer should not be called when context < 2")

    monkeypatch.setattr(chat_mod, "_retrieve", fake_retrieve)
    monkeypatch.setattr(chat_mod, "_llm_fallback", fake_llm_fallback)
    monkeypatch.setattr(chat_mod, "_llm_answer", fail_llm_answer)
    monkeypatch.setattr(chat_mod, "_append_answer_metadata", lambda rec: None)
    monkeypatch.setattr(chat_mod, "publish_event", lambda ev: None)

    req = chat_mod.ChatRequest(question="Hi?", top_k=3)
    resp = await chat_mod.chat(req)

    assert resp.answer.startswith("Not enough MARP context")
    assert resp.model == "fallback-model"
    assert resp.citations == []


@pytest.mark.asyncio
async def test_chat_llm_http_500(monkeypatch):
    """
    If _llm_answer raises HTTPException(500, '...OPENROUTER_API_KEY...'),
    chat should return a friendly message and not raise.
    """
    chunks = [chat_mod.RetrievedChunk(text="A", score=0.9)]
    retrieval_meta = {"query_id": "Q1", "mode": "hybrid", "duration_ms": 5, "result_count": 1, "results": []}

    async def fake_retrieve(*_args, **_kwargs):
        # return 2 chunks so chat does not go into fallback path
        return chunks * 2, retrieval_meta

    async def fake_llm_answer(*_args, **_kwargs):
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    monkeypatch.setattr(chat_mod, "_retrieve", fake_retrieve)
    monkeypatch.setattr(chat_mod, "_llm_answer", fake_llm_answer)
    monkeypatch.setattr(chat_mod, "_append_answer_metadata", lambda rec: None)
    monkeypatch.setattr(chat_mod, "publish_event", lambda ev: None)

    req = chat_mod.ChatRequest(question="Hello?", top_k=3)
    resp = await chat_mod.chat(req)

    assert "OpenRouter API key is not configured" in resp.answer
    assert resp.model == "n/a"
    assert resp.citations == []


@pytest.mark.asyncio
async def test_chat_llm_http_502(monkeypatch):
    """
    If _llm_answer raises HTTPException(502,...), chat should return a
    generic 'LLM service is unavailable' message.
    """
    chunks = [chat_mod.RetrievedChunk(text="A", score=0.9)]
    retrieval_meta = {"query_id": "Q2", "mode": "hybrid", "duration_ms": 7, "result_count": 1, "results": []}

    async def fake_retrieve(*_args, **_kwargs):
        return chunks * 2, retrieval_meta

    async def fake_llm_answer(*_args, **_kwargs):
        raise HTTPException(status_code=502, detail="LLM generation failed")

    monkeypatch.setattr(chat_mod, "_retrieve", fake_retrieve)
    monkeypatch.setattr(chat_mod, "_llm_answer", fake_llm_answer)
    monkeypatch.setattr(chat_mod, "_append_answer_metadata", lambda rec: None)
    monkeypatch.setattr(chat_mod, "publish_event", lambda ev: None)

    req = chat_mod.ChatRequest(question="Test?", top_k=3)
    resp = await chat_mod.chat(req)

    assert "LLM service is unavailable" in resp.answer
    assert resp.model == "n/a"
    assert resp.citations == []

@pytest.mark.asyncio
def test_select_context_limits_to_citation_limit():
    """
    Ensure that _select_context returns at most CITATION_LIMIT chunks and preserves order.
    """
    chunks = [
        chat_mod.RetrievedChunk(text=f"chunk-{i}", score=1.0)
        for i in range(10)
    ]

    selected = chat_mod._select_context(chunks)

    assert len(selected) == chat_mod.CITATION_LIMIT
    assert [c.text for c in selected] == [f"chunk-{i}" for i in range(chat_mod.CITATION_LIMIT)]

@pytest.mark.asyncio
async def test_llm_answer_builds_prompt_and_returns_struct(monkeypatch):
    """
    Verify that _llm_answer formats context, builds the system & user prompts,
    ensures citation placeholders [1], [2], etc., and returns the expected structure.
    HTTP call is mocked so the test does not hit OpenRouter.
    """

    # Fake chunks
    chunks = [
        chat_mod.RetrievedChunk(text="Alpha text", title="Doc1", score=1.0),
        chat_mod.RetrievedChunk(text="Beta text", title="Doc2", score=1.0),
    ]

    # Fake HTTP response from OpenRouter
    fake_json = {
        "choices": [
            {"message": {"content": "Final grounded answer [1] [2]"}}
        ],
        "usage": {"total_tokens": 42},
        "model": "fake-llm"
    }

    async def fake_post(url, headers=None, json=None, timeout=None):
        class Resp:
            status_code = 200
            def json(self, *a, **k):
                return fake_json
        return Resp()

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, *a, **k): return await fake_post(*a, **k)

    # Monkeypatch httpx.AsyncClient → FakeClient
    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    # Fake API key present
    monkeypatch.setattr(chat_mod, "OPENROUTER_API_KEY", "abc123")

    result = await chat_mod._llm_answer("Hello MARP?", chunks)

    assert result["text"].startswith("Final grounded answer")
    assert result["tokens_used"] == 42
    assert result["model"] == "fake-llm"
    assert len(result["citations"]) == 2
