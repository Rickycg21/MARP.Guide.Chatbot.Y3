import pytest
import sys
from pathlib import Path
import numpy as np

# --- FIX IMPORT COLLISION ---
SERVICE_ROOT = Path(__file__).resolve().parents[3] / "services" / "indexing"
sys.path.insert(0, str(SERVICE_ROOT))
# ----------------------------

from services.indexing.app.pipeline import manual_index_document, collection


@pytest.mark.asyncio
async def test_manual_index_document(tmp_path):
    """
    Integration test for the manual_index_document() pipeline.
    Ensures that:
      • A real .txt file can be indexed end-to-end.
      • Embeddings and metadata are stored in ChromaDB.
      • The created chunks are associated with the correct document_id.
    """

    #Create a temporary text file to simulate extracted content
    doc_id = "test_doc_001"
    test_text = "This is a simple test document.\nIt contains two sentences."
    text_file = tmp_path / f"{doc_id}.txt"
    text_file.write_text(test_text, encoding="utf-8")

    #Run the indexing pipeline
    correlation_id = "manual-test-123"
    await manual_index_document(doc_id, str(text_file), correlation_id)

    #Verify ChromaDB now contains the embeddings for this document
    results = collection.get(where={"document_id": doc_id})

    assert results is not None
    assert len(results["ids"]) > 0       # At least one chunk indexed
    assert all(doc_id in cid for cid in results["ids"])  # All chunk IDs belong to this doc

    print(f"\n[TEST] Indexed {len(results['ids'])} chunks successfully.")

    #Cleanup — remove stored embeddings so tests remain isolated
    collection.delete(where={"document_id": doc_id})

@pytest.mark.asyncio
async def test_reindex_overwrites_old_embeddings(tmp_path):
    """
    Ensures that re-indexing truly replaces old embeddings with updated content.
    """

    doc_id = "test_reindex_001"
    file_path = tmp_path / f"{doc_id}.txt"

    #First version of the document
    file_path.write_text("First version of the text.", encoding="utf-8")
    await manual_index_document(doc_id, str(file_path), "corr-1")

    first = collection.get(where={"document_id": doc_id}, include=["embeddings", "documents", "metadatas"])
    first_chunk_text = first["documents"][0]
    first_embedding = first["embeddings"][0]

    #Second version of the document
    file_path.write_text("Second version which should overwrite the old one.", encoding="utf-8")
    await manual_index_document(doc_id, str(file_path), "corr-2")

    second = collection.get(where={"document_id": doc_id}, include=["embeddings", "documents", "metadatas"])
    second_chunk_text = second["documents"][0]
    second_embedding = second["embeddings"][0]

    #Check that the content and embeddings have changed
    assert first_chunk_text != second_chunk_text      # content changed
    assert not np.allclose(first_embedding, second_embedding)

    print("[TEST] Reindex successful: old vs new chunk content and embeddings differ.")

    #Cleanup
    collection.delete(where={"document_id": doc_id})

