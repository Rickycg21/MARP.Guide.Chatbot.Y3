import pytest
import numpy as np
import services.indexing.app.pipeline as pipeline

def test_generate_embeddings(monkeypatch):
    """generate_embeddings should attach embedding vectors to each chunk."""
    
    # Fake chunks
    chunks = [
        {"text": "Hello"},
        {"text": "World"}
    ]

    # Fake model.encode
    def fake_encode(texts, convert_to_numpy):
        return np.array([[1, 2, 3], [4, 5, 6]])

    monkeypatch.setattr(pipeline.model, "encode", fake_encode)

    out = pipeline.generate_embeddings(chunks)

    assert "embedding" in out[0]
    assert out[0]["embedding"] == [1, 2, 3]
    assert out[1]["embedding"] == [4, 5, 6]

def test_store_embeddings(monkeypatch):
    """store_embeddings should call collection.add with correct structured data."""
    
    recorded = {}

    class FakeCollection:
        def add(self, ids, embeddings, documents, metadatas):
            recorded["ids"] = ids
            recorded["embeddings"] = embeddings
            recorded["documents"] = documents
            recorded["metadatas"] = metadatas

    fake = FakeCollection()

    monkeypatch.setattr(pipeline, "collection", fake)

    chunks = [
        {
            "chunkId": "doc1-0001",
            "text": "hello",
            "embedding": [1, 2, 3],
            "document_id": "doc1",
            "page": 1,
            "title": "T",
            "url": "U"
        }
    ]

    pipeline.store_embeddings("doc1", chunks)

    assert recorded["ids"] == ["doc1-0001"]
    assert recorded["documents"] == ["hello"]
    assert recorded["embeddings"] == [[1, 2, 3]]
    assert recorded["metadatas"][0]["document_id"] == "doc1"
    assert recorded["metadatas"][0]["page"] == 1