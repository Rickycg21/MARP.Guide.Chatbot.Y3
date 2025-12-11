import json
import builtins
import tempfile
import services.indexing.app.pipeline as pipeline
from services.indexing.app.pipeline import _lookup_title_url_from_text_metadata


def test_lookup_title_url(tmp_path, monkeypatch):
    """_lookup_title_url_from_text_metadata should return correct title and url"""
    
    fake_file = tmp_path / "text_metadata.jsonl"

    def fake_Path(_):
        return fake_file

    monkeypatch.setitem(pipeline.__dict__, "Path", fake_Path)

    # Write fake metadata
    fake_file.write_text(
        json.dumps({
            "document_id": "docX",
            "title": "My Title",
            "url": "http://example.com"
        }) + "\n",
        encoding="utf-8"
    )

    title, url = _lookup_title_url_from_text_metadata("docX")

    assert title == "My Title"
    assert url == "http://example.com"

def test_log_index_metadata(monkeypatch):
    """log_index_metadata should append a valid JSONL line to file."""

    tmp = tempfile.NamedTemporaryFile(delete=False)
    fake_path = tmp.name

    monkeypatch.setenv("METADATA_PATH", fake_path)

    # Save real open
    real_open = builtins.open

    def fake_open(path, mode="r", encoding=None):
        return real_open(fake_path, mode, encoding=encoding)

    monkeypatch.setattr(builtins, "open", fake_open)

    pipeline.log_index_metadata("docX", 5)

    data = real_open(fake_path, "r").read().strip()
    obj = json.loads(data)

    assert obj["document_id"] == "docX"
    assert obj["chunk_count"] == 5
    assert "indexed_at" in obj