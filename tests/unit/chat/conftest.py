import os
import tempfile
import pytest

# This runs BEFORE importing chat.main in the unit tests
# so environment variables override DATA_DIR correctly.
_temp = tempfile.mkdtemp()
os.environ["DATA_ROOT"] = _temp


@pytest.fixture(autouse=True)
def disable_metadata_write(monkeypatch):
    """
    Prevent unit tests from writing metadata files.
    This replaces _append_answer_metadata with a no-op.
    """
    monkeypatch.setattr(
        "services.chat.app.main._append_answer_metadata",
        lambda *a, **k: None,
        raising=False
    )
