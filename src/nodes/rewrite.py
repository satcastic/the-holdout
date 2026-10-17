"""Query rewriter: vague or pronoun-heavy input -> standalone retrieval query.

The metadata filter is built here deterministically from the action's actor. The LLM only
writes query text, so it can never widen what an actor may retrieve.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.llm import LLM
from src.models import Case
from src.retrieval import build_filter
from src.state import CHANNEL_ACTIONS, GameState, Runtime, recent_messages

DEFAULT_QUERIES = {
    "scene": "physical evidence and scene notes in Server Room 11-S",
    "forensics": "medical examiner findings, cause and time of death, device forensics",
    "records": "logs, emails and records from the night of 2026-11-12",
}


class RewriteOutput(BaseModel):
    query: str = Field(description="standalone search query using canonical names")
    focus_entities: list[str] = Field(default_factory=list,
                                      description="canonical rooms, objects, people or times")


SYSTEM = """Rewrite the detective's latest input into ONE standalone search query for a case
file search engine. Resolve pronouns and follow-ups ("and after that?", "what about him?")
using the recent conversation. Use canonical vocabulary exactly as written below and 24-hour
HH:MM times. Do not add facts, guesses or answers. Keep it under 30 words.
The search is over: {target}
Canonical locations: {locations}
Canonical objects and systems: {objects}
People: elena (Elena Voss, victim), {people}"""


def rewrite_query(llm: LLM, case: Case, text: str, history: str, target: str,
                  focus_terms: str = "") -> tuple[str, list[str]]:
    """Pure helper (also used by eval/retrieval_eval.py)."""
    people = ", ".join(f"{s.id} ({s.name})" for s in case.suspects)
    out = llm.structured(
        "fast",
        SYSTEM.format(target=target, locations="; ".join(case.vocabulary.locations),
                      objects="; ".join(case.vocabulary.objects_and_systems), people=people),
        [{"role": "user", "content": f"Recent conversation:\n{history}\n\nLatest input: {text}"}],
        RewriteOutput, task="rewrite",
        hints={"text": text, "focus_terms": focus_terms},
    )
    query = out.query.strip() or text
    extra = [e for e in out.focus_entities if e.lower() not in query.lower()]
    return (f"{query} {' '.join(extra)}".strip(), out.focus_entities)


def rewrite(state: GameState, rt: Runtime) -> dict[str, Any]:
    action = state["action"]
    kind = action["kind"]
    text = state.get("user_input", "").strip()

    if kind in CHANNEL_ACTIONS:
        actor = CHANNEL_ACTIONS[kind]
        target = f"the {actor} channel"
        default = DEFAULT_QUERIES[actor]
    else:
        actor = action["suspect_id"]
        suspect = rt.case.suspect_by_id[actor]
        target = f"what {suspect.name} knows"
        default = f"{suspect.name} movements and knowledge on 2026-11-12"

    if kind == "present_evidence":
        # Deterministic: the evidence itself is the best query.
        notes = [rt.case.clue_by_id[c].notebook for c in action["clue_ids"]]
        query = " ".join(([text] if text else []) + notes)
    elif not text:
        query = default  # button press with no text: no LLM call
    else:
        focus = rt.case.suspect_by_id[actor].name if actor in rt.case.suspect_by_id else ""
        query, _ = rewrite_query(rt.llm, rt.case, text, recent_messages(state), target, focus)

    return {"rewritten_query": query, "retrieval_actor": actor,
            "retrieval_filter": build_filter(actor)}
