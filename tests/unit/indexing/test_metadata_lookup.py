import json
from pathlib import Path
from services.indexing.app.pipeline import _lookup_title_url_from_text_metadata
import services.indexing.app.pipeline as pipeline


def test_lookup_title_url(tmp_path, monkeypatch):
    # Fake settings object, replacing the frozen dataclass entirely
    class FakeSettings:
        data_root = str(tmp_path)

    monkeypatch.setattr(pipeline, "settings", FakeSettings())

    # Create fake text_metadata.jsonl inside tmp_path
    meta_file = tmp_path / "text_metadata.jsonl"
    meta_file.write_text(
        json.dumps({
            "document_id": "docX",
            "title": "My Title",
            "url": "http://example.com"
        }) + "\n",
        encoding="utf-8"
    )

    # Run the function
    title, url = _lookup_title_url_from_text_metadata("docX")

    assert title == "My Title"
    assert url == "http://example.com"

    meta_file.unlink()