"""Ingest fact chunks from case_01.yaml into the vector store.

Idempotent (upsert by chunk_id). `--reset` wipes the namespace first. Reads only the
public case file; solution.json is never touched here.

Usage: python -m src.ingest [--reset]
"""

from __future__ import annotations

import argparse
import time
from typing import Any

from src.config import get_settings
from src.models import Case, FactChunk, load_case


def build_record(chunk: FactChunk) -> dict[str, Any]:
    """One record per chunk. Pinecone metadata rejects null, so null fields are omitted;
    empty lists are omitted too and read back as []."""
    record: dict[str, Any] = {
        "_id": chunk.id,
        "chunk_text": chunk.embed_text,  # embedded field (title + ". " + text)
        "chunk_id": chunk.id,
        "type": chunk.type,
        "title": chunk.title,
        "text": chunk.text,
        "entities": chunk.entities,
        "known_by": chunk.known_by,
        "reveal_condition": chunk.reveal_condition,
    }
    for key in ("day", "time", "location", "clue_id"):
        value = getattr(chunk, key)
        if value is not None:
            record[key] = value
    return {k: v for k, v in record.items() if v is not None and v != []}


def build_records(case: Case) -> list[dict[str, Any]]:
    return [build_record(c) for c in case.fact_chunks]


def print_summary(records: list[dict[str, Any]]) -> None:
    header = f"{'id':<4} {'type':<22} {'clue':<4} {'gated by':<10} known_by"
    print(header)
    print("-" * len(header) + "-" * 20)
    for r in records:
        print(f"{r['chunk_id']:<4} {r['type']:<22} {r.get('clue_id', '-'):<4} "
              f"{','.join(r.get('reveal_condition', [])) or '-':<10} {','.join(r['known_by'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="wipe the namespace first")
    args = parser.parse_args()

    from src.retrieval import get_store

    s = get_settings()
    store = get_store()
    if hasattr(store, "ensure_index"):
        store.ensure_index()
    if args.reset:
        print(f"Resetting namespace {s.pinecone_namespace!r}")
        store.reset()

    records = build_records(load_case())
    n = store.upsert(records)
    print_summary(records)
    print(f"\nUpserted {n} records into {s.vector_backend}:{s.pinecone_index}/{s.pinecone_namespace}")
    if s.vector_backend == "pinecone":
        for _ in range(10):  # serverless counts are eventually consistent
            count = store.count()
            if count >= n:
                break
            time.sleep(2)
        print(f"Namespace now holds {store.count()} records")


if __name__ == "__main__":
    main()
