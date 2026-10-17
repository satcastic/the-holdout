"""Vector stores and gated retrieval.

Access control has two layers:
1. A Pinecone metadata filter `{"known_by": {"$in": [actor]}}` (who may know a fact).
2. A Python post-filter: every id in `reveal_condition` must be in `discovered_clues`.
   Pinecone filters cannot express "array field is a subset of this list", so we
   over-fetch (top_k=20) and filter in code, then keep the top 5 survivors.
"""

from __future__ import annotations

import contextlib
import logging
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from src.config import get_settings
from src.embedder import Embedder, HashingEmbedder, PineconeIntegratedEmbedder
from src.models import CHANNELS, RetrievedChunk, load_case

log = logging.getLogger(__name__)

RETURN_FIELDS = ["chunk_id", "type", "title", "day", "time", "location", "entities",
                 "known_by", "reveal_condition", "clue_id", "text"]


@dataclass
class Hit:
    id: str
    score: float
    fields: dict[str, Any] = field(default_factory=dict)


class VectorStore(Protocol):
    def upsert(self, records: list[dict[str, Any]]) -> int: ...
    def query(self, text: str, flt: dict[str, Any], top_k: int) -> list[Hit]: ...
    def reset(self) -> None: ...
    def count(self) -> int: ...


# --------------------------------------------------------------------------- filters

def build_filter(actor: str) -> dict[str, Any]:
    """Metadata filter that restricts results to chunks the actor may know."""
    return {"known_by": {"$in": [actor]}}


def is_unlocked(reveal_condition: Iterable[str] | None, discovered: Iterable[str]) -> bool:
    """True if every prerequisite clue has been discovered (empty = always unlocked)."""
    return set(reveal_condition or ()) <= set(discovered)


def matches_filter(fields: dict[str, Any], flt: dict[str, Any]) -> bool:
    """Evaluate the subset of Pinecone's filter language that we use."""
    for key, cond in flt.items():
        if key == "$and":
            if not all(matches_filter(fields, c) for c in cond):
                return False
            continue
        if key == "$or":
            if not any(matches_filter(fields, c) for c in cond):
                return False
            continue
        value = fields.get(key)
        values = value if isinstance(value, list) else ([] if value is None else [value])
        if not isinstance(cond, dict):
            cond = {"$eq": cond}
        for op, arg in cond.items():
            if op == "$in" and not any(v in arg for v in values):
                return False
            if op == "$nin" and any(v in arg for v in values):
                return False
            if op == "$eq" and arg not in values:
                return False
            if op == "$ne" and arg in values:
                return False
    return True


# --------------------------------------------------------------------------- stores

class MemoryStore:
    """In-process store with the same interface as Pinecone (offline tests and dev)."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or HashingEmbedder()
        self._records: dict[str, tuple[list[float], dict[str, Any]]] = {}

    def upsert(self, records: list[dict[str, Any]]) -> int:
        vecs = self.embedder.embed([r["chunk_text"] for r in records], "passage")
        for r, v in zip(records, vecs, strict=True):
            self._records[r["_id"]] = (v, dict(r))
        return len(records)

    def query(self, text: str, flt: dict[str, Any], top_k: int) -> list[Hit]:
        q = self.embedder.embed([text], "query")[0]
        scored = [
            Hit(id=rid, score=sum(a * b for a, b in zip(q, v, strict=True)), fields=f)
            for rid, (v, f) in self._records.items()
            if matches_filter(f, flt)
        ]
        scored.sort(key=lambda h: (-h.score, h.id))
        return scored[:top_k]

    def reset(self) -> None:
        self._records.clear()

    def count(self) -> int:
        return len(self._records)


class PineconeStore:
    """Pinecone serverless index with integrated embeddings, one namespace per case."""

    def __init__(self, embedder: PineconeIntegratedEmbedder | None = None) -> None:
        from pinecone import Pinecone

        s = get_settings()
        if not s.pinecone_api_key:
            raise RuntimeError("VECTOR_BACKEND=pinecone requires PINECONE_API_KEY")
        self.settings = s
        self.embedder = embedder or PineconeIntegratedEmbedder(s.pinecone_embed_model)
        self.pc = Pinecone(api_key=s.pinecone_api_key)
        self.namespace = s.pinecone_namespace
        self._index = None

    def ensure_index(self) -> None:
        s = self.settings
        if not self.pc.has_index(s.pinecone_index):
            log.info("Creating Pinecone index %s (%s)", s.pinecone_index, self.embedder.name)
            self.pc.create_index_for_model(
                name=s.pinecone_index,
                cloud=s.pinecone_cloud,
                region=s.pinecone_region,
                embed={"model": self.embedder.name, "field_map": {"text": "chunk_text"}},
            )

    @property
    def index(self):
        if self._index is None:
            self._index = self.pc.Index(name=self.settings.pinecone_index)
        return self._index

    def upsert(self, records: list[dict[str, Any]]) -> int:
        n = 0
        for i in range(0, len(records), 90):  # integrated upserts allow up to 96 per call
            batch = records[i : i + 90]
            self.index.upsert_records(namespace=self.namespace, records=batch)
            n += len(batch)
        return n

    def query(self, text: str, flt: dict[str, Any], top_k: int) -> list[Hit]:
        res = self.index.search(
            namespace=self.namespace, top_k=top_k, inputs={"text": text},
            filter=flt, fields=RETURN_FIELDS,
        )
        return [Hit(id=h.id, score=float(h.score), fields=dict(h.fields or {}))
                for h in res.result.hits]

    def reset(self) -> None:
        from pinecone import NotFoundError

        with contextlib.suppress(NotFoundError):
            self.index.delete(delete_all=True, namespace=self.namespace)

    def count(self) -> int:
        stats = self.index.describe_index_stats()
        ns = (stats.namespaces or {}).get(self.namespace)
        return int(ns.vector_count) if ns else 0


@lru_cache
def get_store() -> VectorStore:
    s = get_settings()
    if s.vector_backend == "pinecone":
        return PineconeStore()
    from src.ingest import build_records

    store = MemoryStore()
    store.upsert(build_records(load_case()))
    return store


# --------------------------------------------------------------------------- retriever

def valid_actors() -> set[str]:
    return set(CHANNELS) | set(load_case().suspect_ids)


class Retriever:
    """Query -> access filter -> over-fetch -> gating post-filter -> top-k survivors."""

    def __init__(self, store: VectorStore, cache_size: int = 512) -> None:
        self.store = store
        self._cache: OrderedDict[tuple, list[RetrievedChunk]] = OrderedDict()
        self._cache_size = cache_size

    def search(
        self, actor: str, query: str, discovered: Iterable[str], *,
        top_k: int | None = None, overfetch: int | None = None, gating: bool = True,
    ) -> list[RetrievedChunk]:
        s = get_settings()
        top_k = top_k or s.retrieval_top_k
        overfetch = max(overfetch or s.retrieval_overfetch, top_k)
        if actor not in valid_actors():
            raise ValueError(f"unknown actor {actor!r}")
        found = frozenset(discovered)
        key = (actor, query, found, top_k, overfetch, gating)
        if key in self._cache:
            self._cache.move_to_end(key)
            return list(self._cache[key])

        hits = self.store.query(query, build_filter(actor), overfetch)
        survivors: list[RetrievedChunk] = []
        for h in hits:
            f = h.fields
            # Defence in depth: re-check the access filter even though the store applied it.
            if actor not in (f.get("known_by") or []):
                continue
            if gating and not is_unlocked(f.get("reveal_condition"), found):
                continue
            survivors.append(RetrievedChunk(
                id=f.get("chunk_id", h.id), score=round(h.score, 4), type=f["type"],
                title=f["title"], day=f.get("day"), time=f.get("time"),
                location=f.get("location"), clue_id=f.get("clue_id"), text=f["text"],
            ))
            if len(survivors) == top_k:
                break

        self._cache[key] = survivors
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return list(survivors)


@lru_cache
def get_retriever() -> Retriever:
    return Retriever(get_store())


def visible_chunk_ids(actor: str, discovered: Iterable[str]) -> set[str]:
    """All chunk ids the actor could retrieve right now (used by the gate guard)."""
    found = set(discovered)
    return {c.id for c in load_case().fact_chunks
            if actor in c.known_by and is_unlocked(c.reveal_condition, found)}
