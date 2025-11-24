import pytest
from pathlib import Path
import asyncio

from services.indexing.app.pipeline import read_text_file


@pytest.mark.asyncio
async def test_read_text_file_ok(tmp_path):
    """File exists and contains text."""
    file_path = tmp_path / "doc.txt"
    file_path.write_text("Hello MARP!", encoding="utf-8")

    text = await read_text_file(str(file_path))
    assert text == "Hello MARP!"


@pytest.mark.asyncio
async def test_read_text_file_missing(tmp_path):
    """Should raise FileNotFoundError."""
    missing_file = tmp_path / "does_not_exist.txt"
    with pytest.raises(FileNotFoundError):
        await read_text_file(str(missing_file))


@pytest.mark.asyncio
async def test_read_text_file_empty(tmp_path):
    """Should raise ValueError when file is empty."""
    file_path = tmp_path / "empty.txt"
    file_path.write_text("   \n  ", encoding="utf-8")

    with pytest.raises(ValueError):
        await read_text_file(str(file_path))
