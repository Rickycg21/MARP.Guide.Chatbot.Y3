import os
from pathlib import Path
import pytest
import services.extraction.app.extractor as extractor


def test_paths_for(tmp_path, monkeypatch):
    """
    Ensure that _paths_for:
    - Builds correct PDF and TXT paths
    - Creates the text directory
    """
    class FakeSettings:
        data_root = str(tmp_path)

    monkeypatch.setattr(extractor, "settings", FakeSettings())

    pdf_path, text_dir, text_path = extractor._paths_for("abc123")

    assert pdf_path == os.path.join(str(tmp_path), "pdfs", "abc123.pdf")
    assert text_dir == os.path.join(str(tmp_path), "text")
    assert text_path == os.path.join(text_dir, "abc123.txt")
    assert os.path.isdir(text_dir)


def test_extract_to_text_fault_tolerance(tmp_path, monkeypatch):
    """
    extract_to_text should raise FileNotFoundError when PDF does not exist.
    """
    class FakeSettings:
        data_root = str(tmp_path)

    monkeypatch.setattr(extractor, "settings", FakeSettings())

    with pytest.raises(FileNotFoundError):
        extractor.extract_to_text("missing")

def test_extract_to_text(tmp_path, monkeypatch):
    """
    Validate the full happy path for extract_to_text.
    """
    class FakeSettings:
        data_root = str(tmp_path)

    monkeypatch.setattr(extractor, "settings", FakeSettings())

    # Fake PDF file
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir(parents=True)
    pdf_file = pdf_dir / "doc123.pdf"
    pdf_file.write_bytes(b"dummy")

    # Fake pages
    class FakePage:
        def __init__(self, text):
            self.text = text
        def extract_text(self):
            return self.text

    class FakePdf:
        def __init__(self, pages):
            self.pages = pages
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def fake_pdf_open(path):
        assert str(path) == str(pdf_file)
        return FakePdf([
            FakePage("hello world"),
            FakePage("second page")
        ])

    monkeypatch.setattr(extractor.pdfplumber, "open", fake_pdf_open)

    # Fake encoder
    class FakeEncoder:
        def encode(self, text):
            return text.split()

    monkeypatch.setattr(extractor, "_ENCODER", FakeEncoder())

    # Run function
    outpath, page_count, token_count = extractor.extract_to_text("doc123")

    assert page_count == 2
    assert token_count == 4

    assert os.path.exists(outpath)
    content = Path(outpath).read_text()
    assert "--- page 0 ---" in content
    assert "hello world" in content
    assert "--- page 1 ---" in content
    assert "second page" in content
