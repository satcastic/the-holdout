"""Retrieve: Pinecone query with the actor filter, over-fetch, gating post-filter."""

from __future__ import annotations

from typing import Any

from src.state import GameState, Runtime


def retrieve(state: GameState, rt: Runtime) -> dict[str, Any]:
    chunks = rt.retriever.search(
        state["retrieval_actor"], state["rewritten_query"], state.get("discovered_clues", []),
    )
    return {"retrieved": [c.model_dump() for c in chunks]}


def route_after_retrieve(state: GameState) -> str:
    return "suspect" if state["action"]["kind"] in ("question_suspect", "present_evidence") \
        else "records"
