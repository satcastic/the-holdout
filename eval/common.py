"""Shared helpers for the evaluation scripts."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from src.config import ROOT, get_settings
from src.graph import build_graph, play_turn, start_session
from src.llm import LLM, get_llm
from src.state import Runtime

RESULTS = ROOT / "eval" / "results"


def run_meta(**extra: Any) -> dict[str, Any]:
    s = get_settings()
    return {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "llm_mode": s.llm_mode,
        "llm_model_main": s.llm_model_main if s.llm_mode == "real" else "FakeLLM",
        "llm_model_fast": s.llm_model_fast if s.llm_mode == "real" else "FakeLLM",
        "vector_backend": s.vector_backend,
        "embedder": s.pinecone_embed_model if s.vector_backend == "pinecone" else "hashing-2048",
        **extra,
    }


def save(name: str, payload: dict[str, Any]) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2))
    print(f"saved {path.relative_to(ROOT)}")
    return path


class EvalGame:
    """One isolated session on a fresh graph."""

    def __init__(self, checker_enabled: bool = True, llm: LLM | None = None) -> None:
        self.rt = Runtime(llm=llm or get_llm(), checker_enabled=checker_enabled)
        self.graph = build_graph(self.rt, checkpointer=InMemorySaver())
        self.sid = uuid.uuid4().hex
        self.state = start_session(self.graph, self.sid)

    def play(self, text: str = "", **action: Any) -> dict[str, Any]:
        self.state = play_turn(self.graph, self.sid, text, action or None)
        return self.state
