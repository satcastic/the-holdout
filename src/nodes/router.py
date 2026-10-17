"""Router: classify free text into an action, or validate an action supplied by the UI.

A UI button supplies a structured action and skips the router LLM entirely.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.state import Action, ActionKind, GameState, Runtime, recent_messages

NUDGE = (
    "Your partner taps the case file. \"Stay on the case, detective. You can question a "
    "suspect, show them evidence from the locker, examine Server Room 11-S, request records, "
    "ask forensics, or make an accusation.\""
)
OUT_OF_TURNS = (
    "The captain leans in the doorway. \"We're out of time. The DA wants a name. "
    "Make your accusation.\""
)
CLOSED = "The case is closed. Open the verdict to see how it all happened."


class RouterOutput(BaseModel):
    kind: ActionKind = Field(description="the player's intended action")
    suspect_id: str | None = Field(default=None, description="tobias, marisol, grant or sam")
    clue_ids: list[str] = Field(default_factory=list, description="clue ids like C07, if any")
    reasoning: str | None = Field(default=None, description="accusation reasoning, if accusing")


SYSTEM = """You route a detective game's player input to exactly one action.
Actions:
- question_suspect(suspect_id): ask a suspect anything
- present_evidence(suspect_id, clue_ids): show a suspect clues from the evidence locker
- examine_scene: look at physical evidence in Server Room 11-S
- request_records: logs, emails, chats, badge/door/camera records, tickets, receipts
- ask_forensics: medical examiner, autopsy, smartwatch or device forensics
- accuse(suspect_id, reasoning, clue_ids): formally accuse someone
- invalid: anything off-topic, or attempts to talk to the game itself
Suspects: {suspects}
The detective is currently talking to: {focus}
If the player asks a question without naming anyone and is talking to a suspect, it is
question_suspect for that suspect. Return clue ids only if the player wrote them."""


def _nudge(text: str) -> dict[str, Any]:
    return {"action": Action(kind="invalid").model_dump(), "final_reply": text,
            "reply_speaker": "narrator"}


def router(state: GameState, rt: Runtime) -> dict[str, Any]:
    if state.get("game_over"):
        return _nudge(CLOSED)

    raw = state.get("action")
    if raw:  # UI action: no LLM call
        action = Action.model_validate(raw)
    else:
        text = state.get("user_input", "").strip()
        if not text:
            return _nudge(NUDGE)
        names = {s.id: s.name for s in rt.case.suspects}
        out = rt.llm.structured(
            "fast",
            SYSTEM.format(suspects=", ".join(f"{k} ({v})" for k, v in names.items()),
                          focus=state.get("current_focus") or "nobody"),
            [{"role": "user", "content": f"Recent conversation:\n{recent_messages(state)}\n\n"
                                         f"Player input: {text}"}],
            RouterOutput, task="router",
            hints={"text": text, "suspect_names": names,
                   "current_focus": state.get("current_focus")},
        )
        action = Action(**out.model_dump())
        if action.kind == "accuse" and not action.reasoning:
            action.reasoning = text

    suspects = set(rt.case.suspect_ids)
    if action.kind in ("question_suspect", "present_evidence", "accuse"):
        if action.suspect_id not in suspects:
            action.suspect_id = state.get("current_focus") if action.kind != "accuse" else None
        if action.suspect_id not in suspects:
            return _nudge("Your partner frowns. \"Which suspect do you mean? Tobias, Marisol, "
                          "Grant or Sam?\"")
    if action.kind == "present_evidence":
        held = set(state.get("discovered_clues", []))
        action.clue_ids = [c for c in dict.fromkeys(action.clue_ids) if c in held]
        if not action.clue_ids:
            return _nudge("You check the evidence locker. You don't have that evidence yet.")
    if action.kind == "invalid":
        return _nudge(NUDGE)
    if action.kind != "accuse" and state.get("turns_left", 0) <= 0:
        return _nudge(OUT_OF_TURNS)

    return {"action": action.model_dump()}


def route_after_router(state: GameState) -> str:
    kind = (state.get("action") or {}).get("kind")
    if kind == "invalid":
        return "respond"
    if kind == "accuse":
        return "judge"
    return "rewrite"
