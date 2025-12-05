import pytest
import services.ingestion.app.crawler as crawler


def test_doc_id_from_url_stable_and_lowercase():
    """
    _doc_id_from_url should:
    - normalize case
    - hash deterministically
    - prefix with 'marp-'
    """
    url1 = "HTTPS://Example.COM/Doc.PDF"
    url2 = "https://example.com/doc.pdf"

    id1 = crawler._doc_id_from_url(url1)
    id2 = crawler._doc_id_from_url(url2)

    assert id1 == id2
    assert id1.startswith("marp-")
    assert len(id1) == len("marp-" + "0123456789abcdef")

def test_parse_pdf_links_extracts_only_pdf_urls():
    """
    parse_pdf_links should return only PDF links and ignore non-PDF links.
    """
    html = """
        <html>
         <body>
            <a href="a.pdf">Alpha</a>
            <a href="b.PDF">Bravo</a>
            <a href="doc.txt">Ignore me</a>
            <a>No href</a>
         </body>
        </html>
    """

    base = "https://site.com/base/"

    links = crawler.parse_pdf_links(html, base)

    assert len(links) == 2
    assert links[0][0] == "Alpha"
    assert links[1][0] == "Bravo"
    assert links[0][1].endswith("a.pdf")
    assert links[1][1].endswith("b.PDF")

def test_count_pages_returns_page_count(monkeypatch, tmp_path):
    """
    count_pages should return the number of pages using a mocked pdfplumber object.
    """
    fake_pdf_path = tmp_path / "x.pdf"
    fake_pdf_path.write_bytes(b"dummy")

    class FakePdf:
        def __init__(self):
            self.pages = [1, 2, 3]
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(crawler.pdfplumber, "open", lambda p: FakePdf())

    pages = crawler.count_pages(str(fake_pdf_path))
    assert pages == 3