import json
from pathlib import Path

from services.indexing.app.pipeline import _lookup_title_url_from_text_metadata 


def test_lookup_title_url(tmp_path, monkeypatch):
    # Create a fake text_metadata.jsonl
    meta_file = Path("/data/text_metadata.jsonl")
    meta_file.write_text(
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

    meta_file.unlink()
