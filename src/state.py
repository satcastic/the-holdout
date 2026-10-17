"""LangGraph state and the shared runtime handed to every node."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.llm import LLM, get_llm
from src.models import Case, load_case
from src.retrieval import Retriever, get_retriever

ActionKind = Literal[
    "question_suspect", "present_evidence", "examine_scene", "request_records",
    "ask_forensics", "accuse", "invalid",
]
CHANNEL_ACTIONS = {"examine_scene": "scene", "request_records": "records", "ask_forensics": "forensics"}
SUSPECT_ACTIONS = {"question_suspect", "present_evidence"}
INVESTIGATIVE = set(CHANNEL_ACTIONS) | SUSPECT_ACTIONS


class Action(BaseModel):
    kind: ActionKind
    suspect_id: str | None = None
    clue_ids: list[str] = Field(default_factory=list)
    reasoning: str | None = None


class GameState(TypedDict, total=False):
    # persistent across turns
    session_id: str
    messages: list[dict[str, str]]
    suspect_history: dict[str, list[dict[str, str]]]
    discovered_clues: list[str]
    chunks_seen: list[str]
    suspects_questioned: list[str]
    current_focus: str | None
    turns_left: int
    start_turns: int
    accusations_made: list[dict[str, Any]]
    verdict: dict[str, Any] | None
    game_over: bool
    # per turn (reset by turn_input)
    user_input: str
    action: dict[str, Any] | None
    rewritten_query: str
    retrieval_actor: str
    retrieval_filter: dict[str, Any]
    retrieved: list[dict[str, Any]]
    presented_clues: list[str]
    draft_reply: str
    final_reply: str
    reply_speaker: str
    check: dict[str, Any] | None
    retries: int
    new_clues: list[str]


def initial_state(session_id: str, start_turns: int | None = None) -> GameState:
    turns = start_turns or get_settings().start_turns
    return GameState(
        session_id=session_id, messages=[], suspect_history={}, discovered_clues=[],
        chunks_seen=[], suspects_questioned=[], current_focus=None, turns_left=turns,
        start_turns=turns, accusations_made=[], verdict=None, game_over=False,
        **turn_input("", None),
    )


def turn_input(user_input: str, action: Action | dict[str, Any] | None) -> dict[str, Any]:
    """Graph input for one turn: the player's move plus resets of every per-turn field."""
    if isinstance(action, Action):
        action = action.model_dump()
    return {
        "user_input": user_input, "action": action, "rewritten_query": "",
        "retrieval_actor": "", "retrieval_filter": {}, "retrieved": [], "presented_clues": [], "draft_reply": "",
        "final_reply": "", "reply_speaker": "", "check": None, "retries": 0, "new_clues": [],
    }


@dataclass
class Runtime:
    llm: LLM = field(default_factory=get_llm)
    retriever: Retriever = field(default_factory=get_retriever)
    case: Case = field(default_factory=load_case)
    settings: Settings = field(default_factory=get_settings)
    checker_enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.checker_enabled is None:
            self.checker_enabled = self.settings.checker_enabled


def recent_messages(state: GameState, n: int = 6) -> str:
    lines = [f"{m['role']}: {m['content']}" for m in state.get("messages", [])[-n:]]
    return "\n".join(lines) or "(no prior conversation)"
