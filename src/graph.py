"""Builds and compiles the game graph.

Usage: python -m src.graph --mermaid docs/graph.md
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.config import get_settings
from src.nodes.checker import checker, deflect, route_after_checker
from src.nodes.clues import clues, finalize, respond
from src.nodes.judge import judge
from src.nodes.records import records
from src.nodes.retrieve import retrieve, route_after_retrieve
from src.nodes.rewrite import rewrite
from src.nodes.router import route_after_router, router
from src.nodes.suspect import suspect
from src.state import GameState, Runtime, initial_state, turn_input

# Shown to the player while a node runs (SSE `status` events).
STATUS = {
    "router": "Reading your notes",
    "rewrite": "Sharpening the question",
    "retrieve": "Pulling the case files",
    "suspect": "The suspect considers the question",
    "records": "Checking the logs",
    "checker": "Cross-checking the statement",
    "deflect": "Cross-checking the statement",
    "finalize": "Wrapping up",
    "clues": "Updating the evidence locker",
    "judge": "The DA reviews your case",
    "respond": "Writing it up",
}


NODE_DOCS = {
    "router": "Classifies free text into an action (fast model); UI actions skip the LLM. "
              "Invalid input, out-of-turns and closed cases go straight to `respond`.",
    "rewrite": "Builds a standalone query (fast model) and the access filter (in code).",
    "retrieve": "Pinecone query with `known_by` filter, top_k=20, gating post-filter, top 5.",
    "suspect": "In-character reply (main model) from own chunks + private brief.",
    "records": "Scene / records / forensics answer quoting retrieved chunks (main model).",
    "checker": "Gate guard + statement guard + LLM review (fast model). Fail loops back with "
               "feedback, at most 2 retries.",
    "deflect": "Safe in-character deflection after the retries are used up.",
    "finalize": "Promotes the checked draft to `final_reply`.",
    "clues": "Unlocks clues from surfaced channel chunks; decrements turns.",
    "judge": "Extracts cited clues (main model) and scores deterministically from the rubric.",
    "respond": "Appends the turn to the conversation history (checked text only).",
}


def _bind(fn: Callable[[GameState, Runtime], dict[str, Any]], rt: Runtime):
    def node(state: GameState) -> dict[str, Any]:
        return fn(state, rt)

    node.__name__ = fn.__name__
    return node


def build_graph(rt: Runtime | None = None, checkpointer: Any = None):
    rt = rt or Runtime()
    g = StateGraph(GameState)
    nodes = [("router", router), ("rewrite", rewrite), ("retrieve", retrieve),
             ("suspect", suspect), ("records", records), ("finalize", finalize),
             ("clues", clues), ("judge", judge), ("respond", respond)]
    if rt.checker_enabled:
        nodes += [("checker", checker), ("deflect", deflect)]
    for name, fn in nodes:
        g.add_node(name, _bind(fn, rt))

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_after_router,
                            {"respond": "respond", "judge": "judge", "rewrite": "rewrite"})
    g.add_edge("rewrite", "retrieve")
    g.add_conditional_edges("retrieve", route_after_retrieve,
                            {"suspect": "suspect", "records": "records"})
    if rt.checker_enabled:
        g.add_edge("suspect", "checker")
        g.add_edge("records", "checker")
        max_retries = rt.settings.max_retries
        g.add_conditional_edges(
            "checker", lambda st: route_after_checker(st, max_retries),
            {"pass": "finalize", "retry_suspect": "suspect", "retry_records": "records",
             "deflect": "deflect"},
        )
        g.add_edge("deflect", "clues")
    else:  # evaluation baseline only: drafts go straight to the player
        g.add_edge("suspect", "finalize")
        g.add_edge("records", "finalize")
    g.add_edge("finalize", "clues")
    g.add_edge("clues", "respond")
    g.add_edge("judge", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer if checkpointer is not None else make_checkpointer())


def config_for(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def start_session(graph, session_id: str, start_turns: int | None = None) -> GameState:
    """Seed a new thread with the initial state (thread_id = session_id)."""
    graph.update_state(config_for(session_id), initial_state(session_id, start_turns),
                       as_node="respond")
    return graph.get_state(config_for(session_id)).values


def play_turn(graph, session_id: str, text: str = "", action: Any = None) -> GameState:
    return graph.invoke(turn_input(text, action), config_for(session_id))


def make_checkpointer():
    s = get_settings()
    if s.checkpointer == "sqlite":
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        return SqliteSaver(sqlite3.connect(s.sqlite_path, check_same_thread=False))
    return InMemorySaver()


def write_mermaid(path: str) -> None:
    graph = build_graph(checkpointer=InMemorySaver())
    mermaid = graph.get_graph().draw_mermaid()
    legend = "\n".join(f"| `{name}` | {desc} |" for name, desc in NODE_DOCS.items())
    Path(path).write_text(
        "# Game graph\n\nGenerated by `make graph` from `src/graph.py`. Dotted edges are "
        "conditional.\n\n"
        f"```mermaid\n{mermaid}```\n\n| Node | Role |\n|---|---|\n{legend}\n"
    )
    print(f"wrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mermaid", default="docs/graph.md")
    write_mermaid(ap.parse_args().mermaid)
