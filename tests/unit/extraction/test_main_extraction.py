import os
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

import services.extraction.app.main as extraction_main

def test_now_iso():
    """Validate now_iso function."""

    from services.extraction.app.main import now_iso
    assert "T" in now_iso()

@pytest.fixture(autouse=True)
def patch_paths(tmp_path, monkeypatch):
    """
    Redirects STATUS_PATH and META_PATH to temporary test paths.
    Also patches settings to use tmp_path as data_root.
    """
    class FakeSettings:
        data_root = str(tmp_path)
        service_name = "extraction"

    monkeypatch.setattr(extraction_main, "settings", FakeSettings())

    monkeypatch.setattr(
        extraction_main,
        "STATUS_PATH",
        os.path.join(str(tmp_path), "text_status.jsonl"),
    )
    monkeypatch.setattr(
        extraction_main,
        "META_PATH",
        os.path.join(str(tmp_path), "text_metadata.jsonl"),
    )

    return tmp_path

def test_status_unknown_when_no_file(tmp_path):
    """When no status file exists, status should be 'unknown'"""

    res = extraction_main.status("doc-1")
    assert res.document_id == "doc-1"
    assert res.status == "unknown"

@pytest.mark.asyncio
async def test_startup_starts_consumer(monkeypatch):
    """
    startup() should launch a task with consume("DocumentDiscovered", handler).
    """
    started = {}

    async def fake_consume(event_name, handler):
        started["event"] = event_name
        started["handler"] = handler

    monkeypatch.setattr(extraction_main, "consume", fake_consume)

    created_tasks = []

    def fake_create_task(coro):
        created_tasks.append(coro)
        class DummyTask:
            pass
        return DummyTask()

    monkeypatch.setattr(extraction_main.asyncio, "create_task", fake_create_task)

    await extraction_main.startup()

    # At least one task has been created
    assert created_tasks
    # Run the coroutine to verify consume parameters
    await created_tasks[0]
    assert started["event"] == "DocumentDiscovered"
    assert started["handler"] is extraction_main.handle_document_discovered

@pytest.mark.asyncio
async def test_handle_document_discovered_happy_path(monkeypatch):
    """
    handle_document_discovered:
      - marks 'pending'
      - calls _do_extract with the correct documentId
      - acks the message on success
    """
    do_extract_calls = []

    async def fake_do_extract(doc_id, correlation_id):
        do_extract_calls.append((doc_id, correlation_id))

    monkeypatch.setattr(extraction_main, "_do_extract", fake_do_extract)

    status_calls = []

    def fake_status_upsert(document_id, status, message=""):
        status_calls.append((document_id, status, message))

    monkeypatch.setattr(extraction_main, "_status_upsert", fake_status_upsert)

    class FakeMsg:
        def __init__(self):
            self.acked = False
            self.nacked = False
            self.requeue = None

        async def ack(self):
            self.acked = True

        async def nack(self, requeue=False):
            self.nacked = True
            self.requeue = requeue

    msg = FakeMsg()
    env = MagicMock()
    env.payload = {"documentId": "doc-777"}
    env.correlationId = "corr-777"

    await extraction_main.handle_document_discovered(env, msg)

    assert status_calls[0][0] == "doc-777"
    assert status_calls[0][1] == "pending"

    # _do_extract was called
    assert do_extract_calls == [("doc-777", "corr-777")]

    # Message ACK
    assert msg.acked is True
    assert msg.nacked is False

def test_status_and_status_all_read_last_line(monkeypatch):
    """
    status() should return the LAST line for that document_id.
    status_all() should return the entire history.
    """
    path = extraction_main.STATUS_PATH

    # Simulate multiple history lines
    lines = [
        {"document_id": "doc-1", "status": "pending"},
        {"document_id": "doc-2", "status": "error"},
        {"document_id": "doc-1", "status": "done"},
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in lines:
            f.write(json.dumps(rec) + "\n")

    one = extraction_main.status("doc-1")
    assert one.document_id == "doc-1"
    assert one.status == "done"  # TAKE LAST

    all_status = extraction_main.status_all()
    assert len(all_status.status_history) == 3
    assert {r.document_id for r in all_status.status_history} == {"doc-1", "doc-2"}

@pytest.mark.asyncio
async def test_do_extract_happy_path(tmp_path, monkeypatch):
    """
    _do_extract should:
    - call extract_to_text
    - read ingestion metadata
    - write text_metadata.jsonl
    - write status=done
    - publish DocumentExtracted event
    """

    # Fake extract_to_text
    text_dir = tmp_path / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    fake_text_path = text_dir / "doc123.txt"
    fake_text_path.write_text("dummy text")

    def fake_extract_to_text(doc_id):
        assert doc_id == "doc-123"
        return str(fake_text_path), 5, 42

    monkeypatch.setattr(extraction_main, "extract_to_text", fake_extract_to_text)

    # Fake ingestion metadata
    ingestion_meta = tmp_path / "pdf_metadata.jsonl"
    ingestion_meta.write_text(json.dumps({
        "document_id": "doc-123",
        "title": "My Title",
        "url": "https://example.com"
    }) + "\n")

    # Mock publish_event & new_event
    published = []

    async def fake_publish(evt):
        published.append(evt)

    def fake_new_event(event_type, payload, correlation_id):
        return {
            "event_type": event_type,
            "payload": payload,
            "correlation_id": correlation_id
        }

    monkeypatch.setattr(extraction_main, "publish_event", fake_publish)
    monkeypatch.setattr(extraction_main, "new_event", fake_new_event)
    monkeypatch.setattr(extraction_main, "now_iso", lambda: "2025-01-01T00:00:00")

    await extraction_main._do_extract("doc-123", correlation_id="corr-1")

    # Validate metadata written
    meta_path = Path(extraction_main.META_PATH)
    rec = json.loads(meta_path.read_text().strip().splitlines()[0])
    assert rec["document_id"] == "doc-123"
    assert rec["title"] == "My Title"
    assert rec["url"].rstrip("/") == "https://example.com"
    assert rec["text_path"] == str(fake_text_path)

    # Validate status written
    status_path = Path(extraction_main.STATUS_PATH)
    last_line = json.loads(status_path.read_text().splitlines()[-1])
    assert last_line["status"] == "done"

    #Event published
    assert len(published) == 1
    assert published[0]["event_type"] == "DocumentExtracted"
    assert published[0]["correlation_id"] == "corr-1"
