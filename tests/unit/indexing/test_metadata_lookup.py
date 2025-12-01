import json
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
