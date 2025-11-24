import os
import sys
import shutil
import tempfile
from pathlib import Path
import pytest

# --- FIX PYTHONPATH ---
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
# -----------------------

import services.extraction.app.extractor as extractor


@pytest.fixture(autouse=True)
def patch_paths(monkeypatch):
    """
    Redirect extractor._paths_for so all I/O happens inside a temporary directory,
    without modifying settings.data_root (frozen dataclass).
    """
    tmp = tempfile.mkdtemp()

    def fake_paths(doc_id):
        pdf_dir = os.path.join(tmp, "pdfs")
        os.makedirs(pdf_dir, exist_ok=True)

        text_dir = os.path.join(tmp, "text")
        os.makedirs(text_dir, exist_ok=True)

        pdf_path = os.path.join(pdf_dir, f"{doc_id}.pdf")
        text_path = os.path.join(text_dir, f"{doc_id}.txt")
        return pdf_path, text_dir, text_path

    monkeypatch.setattr(extractor, "_paths_for", fake_paths)

    yield tmp
    shutil.rmtree(tmp)


def test_extract_to_text_missing_pdf():
    """extract_to_text should raise FileNotFoundError when PDF does not exist."""
    with pytest.raises(FileNotFoundError):
        extractor.extract_to_text("DOES_NOT_EXIST")


def test_extract_to_text_success(monkeypatch):
    """
    Full extractor test:
    - Mock pdfplumber to simulate two pages
    - Mock tokenizer to control token count
    - Validate that the output file contains pages starting at index 1 (current real behaviour)
    """

    pdf_path, text_dir, text_path = extractor._paths_for("DOC123")
    Path(pdf_path).touch()

    class FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class FakePDF:
        def __init__(self):
            self.pages = [
                FakePage("Content 1"),
                FakePage("Content 2"),
            ]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    def fake_open(path):
        assert path == pdf_path
        return FakePDF()

    monkeypatch.setattr(extractor.pdfplumber, "open", fake_open)

    class FakeEncoder:
        def encode(self, text):
            return text.split()

    monkeypatch.setattr(extractor, "_ENCODER", FakeEncoder())

    result_path, page_count, token_count = extractor.extract_to_text("DOC123")

    assert page_count == 2
    assert token_count == 4 

    assert os.path.exists(result_path)

    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "--- page 1 ---" in content
    assert "Content 1" in content
    assert "--- page 2 ---" in content
    assert "Content 2" in content