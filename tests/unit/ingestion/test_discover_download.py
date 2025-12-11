import pytest
import services.ingestion.app.crawler as crawler
from pathlib import Path

@pytest.mark.asyncio
async def test_discover_and_download_yields_metadata(monkeypatch, tmp_path):
    """
    discover_and_download should yield correct metadata dicts
    when all dependencies are mocked.
    """

    class FakeSettings:
        data_root = str(tmp_path)

    monkeypatch.setattr(crawler, "settings", FakeSettings())

    # Mock async HTML fetch
    async def fake_fetch(client, url):
        return "<html></html>"
    monkeypatch.setattr(crawler, "fetch_html", fake_fetch)

    # Mock PDF links
    monkeypatch.setattr(
        crawler,
        "parse_pdf_links",
        lambda html, base: [("Doc1", "http://x/doc1.pdf")]
    )

    # Mock download
    async def fake_download(client, url, path):
        Path(path).write_bytes(b"PDF")
    monkeypatch.setattr(crawler, "download_pdf", fake_download)

    # Mock page count
    monkeypatch.setattr(crawler, "count_pages", lambda path: 7)

    # Run generator
    results = []
    async for meta in crawler.discover_and_download():
        results.append(meta)

    assert len(results) == 1
    m = results[0]

    assert m["title"] == "Doc1"
    assert m["url"] == "http://x/doc1.pdf"
    assert m["pages"] == 7
    assert m["downloadPath"].endswith(".pdf")
    assert m["documentId"].startswith("marp-")
    assert "discoveredAt" in m

