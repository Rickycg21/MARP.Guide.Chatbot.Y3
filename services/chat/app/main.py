"""
---Chat Service--- 

FastAPI entrypoint wires retrieval, generation, citation, 
and event publication into a single /chat endpoint.

Includes:
 - Configuration / fallbacks for running inside or outside Docker (for testing).
 - Using shared event helpers, models and utilities (Pydantic schemas, retrieval + LLM helpers).
 - Appending answer metadata to /data/answer_metadata.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
import textwrap
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

try:
    # shared config
    from common.config import settings
except Exception:
    @dataclass(frozen=True)
    class _Settings:
        service_name: str = os.getenv("SERVICE_NAME", "chat")
        service_port: int = int(os.getenv("SERVICE_PORT", "5005"))
        rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://admin:admin@localhost:5672/")
        data_root: str = os.getenv("DATA_ROOT", "./data")
        log_level: str = os.getenv("LOG_LEVEL", "INFO")

    settings = _Settings()

try:
    # shared event helpers for consistent envelope
    from common.events import new_event, publish_event, now_iso
except Exception:
    import datetime as _dt
    from dataclasses import dataclass as _dataclass

    @_dataclass(frozen=True)
    class _FallbackEvent:
        eventType: str
        eventId: str
        timestamp: str
        correlationId: Optional[str]
        source: str
        version: str
        payload: Dict[str, Any]

    def now_iso() -> str:
        return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()

    def new_event(
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: str,
        *,
        version: str = "1.0",
        source: Optional[str] = None,
    ):
        return _FallbackEvent(
            eventType=event_type,
            eventId=str(uuid.uuid4()),
            timestamp=now_iso(),
            correlationId=correlation_id,
            source=source or getattr(settings, "service_name", "chat"),
            version=version,
            payload=payload,
        )

    async def publish_event(event: Any) -> None:
        logging.getLogger("chat-service").warning(
            "Event bus unavailable; dropped event %s", getattr(event, "eventType", "unknown")
        )


logging.basicConfig(
    level=getattr(logging, str(getattr(settings, "log_level", "INFO")).upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("chat-service")

# --- Config via env ----------------------------------------------------------
RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://retrieval:8000")
RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "hybrid")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE = os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
try:
    _cit_limit_env = int(os.getenv("CHAT_CITATION_LIMIT", "3"))
except ValueError:
    _cit_limit_env = 3
# Control how many retrieval snippets are forwarded to the LLM as citations.
# Clamp to 2-3 so answers carry at least two sources when available.
CITATION_LIMIT = min(3, max(2, _cit_limit_env))
SCORE_THRESHOLD = 0.5

# --- Data locations ----------------------------------------------------------
DATA_DIR = settings.data_root
ANSWER_META_PATH = os.path.join(DATA_DIR, "answer_metadata.jsonl")
os.makedirs(DATA_DIR, exist_ok=True)


# --- Pydantic schemas --------------------------------------------------------
class Citation(BaseModel):
    title: str
    page: Optional[int] = None
    url: Optional[str] = None


class RetrievedChunk(BaseModel):
    text: str
    title: Optional[str] = None
    page: Optional[int] = None
    url: Optional[str] = None
    score: Optional[float] = None


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: int = Field(5, ge=1, le=10)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    model: str
    tokens_used: Optional[int] = None
    latency_ms: int
    correlation_id: str


def _select_context(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    # Picks subset of retrieved chunks that will be turned into citations.
    # Aim for up to CITATION_LIMIT snippets; if fewer exist, use all.
    return chunks[:CITATION_LIMIT] if chunks else []

# --- OpenRouter call ---------------------------------------------------------
# Calling LLM and retrieval call logic almost entirely AI generated, with minor tweaks
async def _llm_answer(question: str, context_blocks: List[RetrievedChunk]) -> Dict[str, Any]:
    """
    Call OpenRouter's chat completions endpoint, returning the generated answer,
    token usage, model, and supporting citations.
    """
    selected = _select_context(context_blocks)
    if not selected:
        raise HTTPException(status_code=500, detail="No context available for generation")

    # Attach contextual metadata that will eventually be echoed back to the
    # client. Missing titles are replaced with a friendly fallback so the
    # response structure stays deterministic.
    citations = [
        Citation(
            title=block.title or "MARP Source",
            page=block.page,
            url=block.url,
        )
        for block in selected
    ]
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    # Collect lines that will be embedded in the user prompt. We mirror the
    # numeric index used in the instructions so the LLM can reference the
    # correct snippet with [1].
    context_lines: List[str] = []
    for idx, block in enumerate(selected, start=1):
        details = []
        if block.title:
            details.append(block.title)
        if block.page is not None:
            details.append(f"p.{block.page}")
        suffix = f" ({', '.join(details)})" if details else ""
        context_lines.append(f"[{idx}] {block.text.strip()}{suffix}")
    context_text = "\n".join(context_lines)

    system_prompt = (
        "You are a MARP assistant answering questions for students and staff. "
        "Use only the supplied context snippets. "
        "Provide 2-3 sources when available and cite them as [1], [2], [3] in-line. "
        "If fewer than two sources are relevant, cite all available. "
        "If at least two snippets are relevant, you must produce a grounded answer using those snippets. "
        "Do not respond with uncertainty if any snippet is relevant; give the best concise answer supported by the snippets."
    )

    user_prompt = (
        f"Question: {question.strip()}\n\n"
        f"Context:\n{context_text}\n\n"
        "Respond concisely (1-3 sentences), grounded entirely in the context. "
        "If any snippet mentions a rule, timeframe, or deadline relevant to the question, state it plainly. "
        "Include inline markers [1], [2], [3] for each cited snippet you use (at least two when available). "
        "If information is partial, still provide the best grounded answer and cite the relevant snippets."
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "http://localhost"),
        "X-Title": os.getenv("OPENROUTER_TITLE", "MARP-Guide Chat"),
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=payload
        )
        if response.status_code >= 400:
            logger.error("OpenRouter error %s: %s", response.status_code, response.text)
            raise HTTPException(status_code=502, detail="LLM generation failed")
        data = response.json()

    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content", "")
    if not content:
        raise HTTPException(status_code=502, detail="LLM returned empty response")

    text = content.strip()
    # Ensure the response carries citation markers for the snippets we sent.
    # Use up to CITATION_LIMIT, but try to include at least two markers when available.
    required_refs = len(citations) if len(citations) < 2 else min(CITATION_LIMIT, len(citations))
    for idx in range(1, required_refs + 1):
        if f"[{idx}]" not in text:
            text = f"{text} [{idx}]".strip()

    usage = data.get("usage") or {}

    return {
        "text": text,
        "tokens_used": usage.get("total_tokens"),
        "model": data.get("model", OPENROUTER_MODEL),
        "citations": citations,
    }


# --- Retrieval call ----------------------------------------------------------
async def _retrieve(
    question: str,
    top_k: int,
    correlation_id: Optional[str],
) -> Tuple[List[RetrievedChunk], Dict[str, Any]]:
    """
    Call the Retrieval service to obtain MARP snippets.
    Returns both the normalised chunks and a metadata dict from the retrieval call.
    """
    limit = max(1, min(top_k, 3))
    url = f"{RETRIEVAL_URL.rstrip('/')}/search"
    params: Dict[str, Any] = {"q": question, "topK": limit, "mode": RETRIEVAL_MODE}
    if correlation_id:
        params["correlationId"] = correlation_id

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(url, params=params)
        if response.status_code >= 400:
            logger.error("Retrieval error %s: %s", response.status_code, response.text)
            raise HTTPException(status_code=502, detail="Retrieval failed")
        data = response.json()

    results = data.get("results") or []
    if not isinstance(results, list):
        raise HTTPException(status_code=502, detail="Retrieval payload malformed")

    chunks: List[RetrievedChunk] = []
    result_summaries: List[Dict[str, Any]] = []
    # Normalise the retrieval payload into RetrievedChunk models and collect a
    # lightweight summary for downstream metadata/event payloads.
    # Be tolerant to upstream field naming.

    def _pick_str(d: Dict[str, Any], keys: List[str]) -> str:
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _pick_int(d: Dict[str, Any], keys: List[str]) -> Optional[int]:
        for k in keys:
            v = d.get(k)
            if v is None:
                continue
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
        return None

    for raw in results:
        # Prefer 'snippet' but support common alternatives from prototype services
        snippet = _pick_str(raw, ["snippet", "text", "content", "chunk", "passage"])
        if not snippet:
            logger.debug("Skipping retrieval hit without snippet: %s", raw)
            continue

        scores = raw.get("scores") or {}
        score_val: Optional[float] = None
        if isinstance(scores, dict):
            for key in ("combined", "semantic", "bm25"):
                val = scores.get(key)
                if isinstance(val, (int, float)):
                    score_val = float(val)
                    break

        try:
            chunk = RetrievedChunk(
                text=snippet,
                title=_pick_str(raw, ["title", "documentTitle", "docTitle", "sourceTitle"]) or None,
                page=_pick_int(raw, ["page", "pageNumber", "page_index"]),
                url=_pick_str(raw, ["url", "link", "sourceUrl", "source_url"]) or None,
                score=score_val,
            )
        except Exception as exc:
            logger.warning("Skipping malformed chunk: %s (%s)", raw, exc)
            continue

        # Only keep chunks meeting the score threshold.
        if chunk.score is None or chunk.score < SCORE_THRESHOLD:
            logger.debug("Dropping chunk below score threshold: %s (score=%s)", chunk.title, chunk.score)
            continue

        chunks.append(chunk)
        result_summaries.append(
            {
                "document_id": raw.get("documentId") or raw.get("document_id"),
                "chunk_id": raw.get("chunkId") or raw.get("chunk_id"),
                "score": score_val,
            }
        )

    # Sort descending by score to prioritize higher-signal snippets.
    chunks.sort(key=lambda c: (c.score is None, -(c.score or 0)))

    if not chunks:
        raise HTTPException(status_code=404, detail="No supporting sources found")

    meta = {
        "query_id": data.get("queryId"),
        "mode": data.get("mode"),
        "duration_ms": data.get("durationMs"),
        "result_count": len(chunks),
        # Only keep IDs + scores here; the full snippet text lives in the
        # context_used section of the stored metadata to avoid duplication.
        "results": result_summaries,
    }

    return chunks, meta


# --- Metadata persistence ----------------------------------------------------
def _append_answer_metadata(record: Dict[str, Any]) -> None:
    # Append-only log used for audits and debugging. Keeping it on disk inside
    # DATA_DIR means the JSONL survives container restarts and can be shipped
    # elsewhere if required for assessment evidence.
    os.makedirs(os.path.dirname(ANSWER_META_PATH), exist_ok=True)
    with open(ANSWER_META_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


# --- FastAPI app -------------------------------------------------------------
app = FastAPI(title="MARP-Guide Chat Service")

UI_HTML = textwrap.dedent(
    """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>MARP Chat</title>
      <style>
        :root { color-scheme: dark; }
        body {
          margin: 0;
          font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
          background: #0b1224;
          color: #e2e8f0;
          min-height: 100vh;
        }
        .page {
          max-width: 1000px;
          margin: 0 auto;
          padding: 32px 20px 48px;
        }
        header { margin-bottom: 18px; }
        h1 { margin: 0 0 6px; font-size: 26px; letter-spacing: 0.5px; }
        p { margin: 4px 0; color: #cbd5e1; }
        .panel {
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 14px;
          padding: 18px;
          box-shadow: 0 12px 30px rgba(0,0,0,0.25);
          margin-bottom: 16px;
        }
        label { display: block; margin: 0 0 8px; font-weight: 700; }
        textarea {
          width: 100%;
          background: #0b162d;
          color: #e2e8f0;
          border: 1px solid #1f2937;
          border-radius: 10px;
          padding: 12px;
          font-size: 16px;
          box-sizing: border-box;
          min-height: 110px;
          resize: vertical;
        }
        .actions {
          margin-top: 12px;
          display: flex;
          gap: 10px;
          align-items: center;
        }
        button {
          background: linear-gradient(90deg, #2563eb, #22d3ee);
          color: #0b1224;
          border: none;
          padding: 12px 18px;
          border-radius: 10px;
          font-weight: 800;
          cursor: pointer;
          box-shadow: 0 8px 24px rgba(34, 211, 238, 0.35);
        }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        .status { color: #93c5fd; font-size: 14px; }
        .board {
          background: #0d1427;
          border: 1px solid #1e293b;
          border-radius: 16px;
          padding: 10px;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
          max-height: 70vh;
          overflow-y: auto;
        }
        .empty { text-align: center; padding: 24px; color: #94a3b8; }
        .msg {
          display: grid;
          grid-template-columns: 70px 1fr;
          gap: 10px;
          padding: 12px;
          border-bottom: 1px solid #1f2937;
        }
        .msg:last-child { border-bottom: none; }
        .role {
          font-weight: 800;
          color: #a5b4fc;
          text-transform: uppercase;
          font-size: 12px;
          letter-spacing: 0.5px;
        }
        .role.user { color: #60a5fa; }
        .bubble {
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 12px;
          padding: 12px 14px;
          line-height: 1.5;
          white-space: pre-wrap;
        }
        .msg.user .bubble { background: #0b162d; border-color: #1d4ed8; }
        .msg.bot .bubble { background: #0f172a; border-color: #1f2937; }
        .badges { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
        .badge {
          padding: 4px 10px;
          border-radius: 999px;
          border: 1px solid #1f2937;
          background: #0b162d;
          color: #cbd5e1;
          font-size: 12px;
        }
        .citations { margin-top: 10px; }
        .citation {
          display: block;
          margin: 4px 0;
          color: #a5b4fc;
          font-size: 14px;
        }
        a { color: #60a5fa; }
      </style>
    </head>
    <body>
      <div class="page">
        <header>
          <h1>MARP Chat</h1>
          <p>Ask questions about Lancaster University&#39;s MARP. Messages stack like a board so you can see prior Q&A.</p>
        </header>

        <div class="panel">
          <form id="chat-form" method="post" action="#">
            <label for="question">Ask MARP</label>
            <textarea id="question" name="question" required minlength="3" placeholder="e.g., How many days do I have to submit an appeal?"></textarea>
            <div class="actions">
              <button id="submit-btn" type="submit">Send</button>
              <div id="status" class="status"></div>
            </div>
          </form>
        </div>

        <div class="board" id="board">
          <div class="empty">No messages yet. Ask your first question.</div>
        </div>
      </div>

      <script>
        const form = document.getElementById("chat-form");
        const questionEl = document.getElementById("question");
        const submitBtn = document.getElementById("submit-btn");
        const statusEl = document.getElementById("status");
        const board = document.getElementById("board");

        const clearEmpty = () => {
          const empty = board.querySelector(".empty");
          if (empty) empty.remove();
        };

        const addMessage = (role, text, meta = {}) => {
          clearEmpty();
          const wrap = document.createElement("div");
          wrap.className = `msg ${role}`;

          const roleEl = document.createElement("div");
          roleEl.className = `role ${role}`;
          roleEl.textContent = role === "user" ? "You" : "Assistant";

          const bubble = document.createElement("div");
          bubble.className = "bubble";
          bubble.innerHTML = (text || "").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\\n/g, "<br>");

          if (meta.citations && meta.citations.length) {
            const list = document.createElement("div");
            list.className = "citations";
            list.innerHTML = meta.citations
              .map((c, idx) => {
                const page = c.page !== null && c.page !== undefined ? ` (p.${c.page})` : "";
                const link = c.url ? ` <a href=\\"${c.url}\\" target=\\"_blank\\" rel=\\"noreferrer\\">open</a>` : "";
                return `<span class="citation">[${idx + 1}] ${c.title || "Source"}${page}${link}</span>`;
              })
              .join("");
            bubble.appendChild(list);
          }

          if (meta.latency || meta.model || meta.correlation || meta.tokens) {
            const badges = document.createElement("div");
            badges.className = "badges";
            if (meta.latency) badges.innerHTML += `<span class="badge">Latency: ${meta.latency} ms</span>`;
            if (meta.model) badges.innerHTML += `<span class="badge">Model: ${meta.model}</span>`;
            if (meta.tokens) badges.innerHTML += `<span class="badge">Tokens: ${meta.tokens}</span>`;
            if (meta.correlation) badges.innerHTML += `<span class="badge">Corr ID: ${meta.correlation}</span>`;
            bubble.appendChild(badges);
          }

          wrap.appendChild(roleEl);
          wrap.appendChild(bubble);
          board.appendChild(wrap);
          board.scrollTop = board.scrollHeight;
        };

        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          const question = questionEl.value.trim();
          if (question.length < 3) {
            statusEl.textContent = "Please enter a longer question.";
            return;
          }

          addMessage("user", question);
          submitBtn.disabled = true;
          statusEl.textContent = "Thinking...";

          try {
            const response = await fetch("/chat", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ question })
            });

            if (!response.ok) {
              const detail = await response.text();
              throw new Error(`Request failed (${response.status}): ${detail}`);
            }

            const data = await response.json();
            addMessage("bot", data.answer || "No answer returned.", {
              citations: data.citations || [],
              latency: data.latency_ms ?? null,
              model: data.model || null,
              tokens: data.tokens_used !== null && data.tokens_used !== undefined ? data.tokens_used : null,
              correlation: data.correlation_id || null,
            });
            statusEl.textContent = "Done";
            questionEl.value = "";
          } catch (err) {
            statusEl.textContent = err.message || "Something went wrong.";
            addMessage("bot", `Error: ${err.message || "Unknown error."}`);
          } finally {
            submitBtn.disabled = false;
          }
        });
      </script>
    </body>
    </html>
    """
).strip()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/", response_class=HTMLResponse)
async def ui() -> HTMLResponse:
    return HTMLResponse(content=UI_HTML, status_code=200)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    start = time.perf_counter()
    # Corr. ID puts retrieval, generation, andAnswerGenerated event
    # together so monitoring can follow a single request across
    # services. session_id enables conversation on the client side.
    correlation_id = str(uuid.uuid4())
    session_id = req.session_id or str(uuid.uuid4())

    # 1) Retrieve supporting chunks
    try:
        chunks, retrieval_meta = await _retrieve(req.question, req.top_k, correlation_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            # Graceful fallback for irrelevant/unsupported questions: still consult the LLM to craft a polite reply
            # with no citations.
            try:
                fallback = await _llm_fallback(req.question)
                latency_ms = int((time.perf_counter() - start) * 1000)
                return ChatResponse(
                    answer=fallback["text"],
                    citations=[],
                    model=fallback["model"],
                    tokens_used=fallback.get("tokens_used"),
                    latency_ms=latency_ms,
                    correlation_id=correlation_id,
                )
            except Exception:
                latency_ms = int((time.perf_counter() - start) * 1000)
                return ChatResponse(
                    answer="I don't have information on that topic yet. Source: not available. (error code: 404)",
                    citations=[],
                    model="n/a",
                    tokens_used=None,
                    latency_ms=latency_ms,
                    correlation_id=correlation_id,
                )
        raise

    context_blocks = _select_context(chunks)

    # 2) Generate grounded answer
    try:
        llm_result = await _llm_answer(req.question, context_blocks)
    except HTTPException as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        if exc.status_code == 500 and "OPENROUTER_API_KEY" in str(exc.detail):
            msg = f"OpenRouter API key is not configured; unable to generate an answer right now. (error code: {exc.status_code})"
        else:
            msg = f"The LLM service is unavailable (network/API issue); unable to generate an answer right now. (error code: {exc.status_code})"
        logger.warning("LLM unavailable (%s): %s", exc.status_code, exc.detail)
        return ChatResponse(
            answer=msg,
            citations=[],
            model="n/a",
            tokens_used=None,
            latency_ms=latency_ms,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        # Graceful fallback when LLM is unavailable (unexpected error).
        logger.warning("LLM unavailable, returning static fallback: %s", exc)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ChatResponse(
            answer="LLM error occurred; unable to generate an answer right now. (error code: 500)",
            citations=[],
            model="n/a",
            tokens_used=None,
            latency_ms=latency_ms,
            correlation_id=correlation_id,
        )

    latency_ms = int((time.perf_counter() - start) * 1000)

    response = ChatResponse(
        answer=llm_result["text"],
        citations=llm_result["citations"],
        model=llm_result["model"],
        tokens_used=llm_result.get("tokens_used"),
        latency_ms=latency_ms,
        correlation_id=correlation_id,
    )

    # 3) Persist metadata for auditability
    meta_record = {
        "timestamp": now_iso(),
        "session_id": session_id,
        "correlation_id": correlation_id,
        "question": req.question,
        "top_k": req.top_k,
        "model": response.model,
        "tokens_used": response.tokens_used,
        "latency_ms": response.latency_ms,
        "citations": [c.model_dump() for c in response.citations],
        "context_used": [block.model_dump() for block in context_blocks],
        "retrieval": retrieval_meta,
    }
    _append_answer_metadata(meta_record)

    # 4) Publish AnswerGenerated event for downstream consumers
    try:
        # payload looks like the stored metadata for monitoring services
        event = new_event(
            "AnswerGenerated",
            payload={
                "session_id": session_id,
                "question": req.question,
                "answer": response.answer,
                "citations": [c.model_dump() for c in response.citations],
                "model": response.model,
                "tokens_used": response.tokens_used,
                "latency_ms": response.latency_ms,
                "citation_limit": CITATION_LIMIT,
                "retrieval": {
                    "query_id": retrieval_meta.get("query_id"),
                    "duration_ms": retrieval_meta.get("duration_ms"),
                    "result_count": retrieval_meta.get("result_count"),
                },
            },
            correlation_id=correlation_id,
        )
        await publish_event(event)
    except Exception as exc:
        logger.warning("Failed to publish AnswerGenerated event: %s", exc)

    return response


async def _llm_fallback(question: str) -> Dict[str, Any]:
    """
    Call the LLM with a guardrailed prompt to politely decline when no MARP
    context is available. Returns text, tokens_used, and model. No citations.
    """
    if not OPENROUTER_API_KEY:
        return {
            "text": "OpenRouter API key is not configured; unable to answer without MARP sources. (error code: 500)",
            "tokens_used": None,
            "model": "n/a",
        }

    system_prompt = (
        "You are a MARP assistant. No supporting MARP sources are available for this question. "
        "Reply briefly that you cannot answer from MARP, without inventing details or citations. "
        "Encourage the user to ask about MARP policies, regulations, appeals, assessments, or timelines."
    )
    user_prompt = (
        f"Question: {question.strip()}\n\n"
        "You have zero supporting context. Do not fabricate an answer. "
        "Politely say you lack information from MARP on this topic, and suggest they ask a MARP-related question."
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "http://localhost"),
        "X-Title": os.getenv("OPENROUTER_TITLE", "MARP-Guide Chat"),
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=payload)
        if response.status_code >= 400:
            logger.error("OpenRouter fallback error %s: %s", response.status_code, response.text)
            raise HTTPException(status_code=502, detail="LLM generation failed")
        data = response.json()

    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content", "")
    if not content:
        raise HTTPException(status_code=502, detail="LLM returned empty response")

    usage = data.get("usage") or {}
    return {
        "text": content.strip(),
        "tokens_used": usage.get("total_tokens"),
        "model": data.get("model", OPENROUTER_MODEL),
    }

# Uvicorn entrypoint for Docker
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
