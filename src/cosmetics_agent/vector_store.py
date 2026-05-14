from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from typing import Any

from .config import VectorStoreConfig
from .models import KnowledgeChunk


def chroma_available() -> bool:
    try:
        import chromadb  # noqa: F401
    except Exception:
        return False
    return True


class LocalVectorStore:
    def __init__(self, config: VectorStoreConfig | None = None) -> None:
        self.config = config or VectorStoreConfig.from_env()

    def enabled(self) -> bool:
        return self.config.enabled and self.config.provider == "chroma" and chroma_available()

    def upsert_knowledge_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if not self.enabled():
            return
        client = self._client()
        collection = client.get_or_create_collection(name=self.config.collection_name)
        existing = collection.get(include=[])
        existing_ids = set(existing.get("ids", [])) if isinstance(existing, dict) else set()

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        embeddings: list[list[float]] = []

        for chunk in chunks:
            metadata = _chunk_metadata(chunk)
            text = _chunk_document(chunk)
            embedding = _pseudo_embedding(text)
            ids.append(chunk.id)
            documents.append(text)
            metadatas.append(metadata)
            embeddings.append(embedding)

        if existing_ids == set(ids):
            return

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    def query(self, query_text: str, top_k: int = 8) -> list[dict[str, Any]]:
        if not self.enabled():
            return []
        client = self._client()
        collection = client.get_or_create_collection(name=self.config.collection_name)
        result = collection.query(
            query_embeddings=[_pseudo_embedding(query_text)],
            n_results=max(1, top_k),
            include=["metadatas", "documents", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]
        rows: list[dict[str, Any]] = []
        for item_id, metadata, document, distance in zip(ids, metadatas, documents, distances):
            rows.append(
                {
                    "id": item_id,
                    "metadata": metadata or {},
                    "document": document,
                    "distance": float(distance or 0.0),
                }
            )
        return rows

    def reset_collection(self) -> None:
        if not self.enabled():
            return
        client = self._client()
        try:
            client.delete_collection(name=self.config.collection_name)
        except Exception:
            pass

    @lru_cache(maxsize=1)
    def _client(self):
        import chromadb

        self.config.persist_path.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(self.config.persist_path))


def _chunk_document(chunk: KnowledgeChunk) -> str:
    payload = {
        "title": chunk.title,
        "category": chunk.category,
        "content": chunk.content,
        "tags": chunk.tags,
        "concerns": chunk.concerns,
        "skin_types": chunk.skin_types,
        "ingredients": chunk.ingredients,
        "scenarios": chunk.scenarios,
        "finish_preferences": chunk.finish_preferences,
        "evidence_type": chunk.evidence_type,
    }
    return json.dumps(payload, ensure_ascii=False)


def _chunk_metadata(chunk: KnowledgeChunk) -> dict[str, Any]:
    return {
        "title": chunk.title,
        "category": chunk.category,
        "product_ids": ",".join(chunk.product_ids),
        "concerns": ",".join(chunk.concerns),
        "skin_types": ",".join(chunk.skin_types),
        "ingredients": ",".join(chunk.ingredients),
        "scenarios": ",".join(chunk.scenarios),
        "finish_preferences": ",".join(chunk.finish_preferences),
        "evidence_type": chunk.evidence_type,
    }


def _pseudo_embedding(text: str, dims: int = 64) -> list[float]:
    buckets = [0.0] * dims
    for token in _simple_terms(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = digest[0] % dims
        sign = 1.0 if digest[1] % 2 == 0 else -1.0
        buckets[index] += sign
    norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
    return [value / norm for value in buckets]


def _simple_terms(text: str) -> list[str]:
    buffer = []
    current = []
    for char in text.lower():
        if char.isalnum() or char in {"_", "-", "."}:
            current.append(char)
        else:
            if current:
                buffer.append("".join(current))
                current = []
            if "\u4e00" <= char <= "\u9fff":
                buffer.append(char)
    if current:
        buffer.append("".join(current))
    return buffer
