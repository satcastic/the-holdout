"""Clue unlocks, turn accounting, and the final `respond` step that records history.

Only chunks surfaced by records, scene or forensics unlock clues, and only after the
checker passed (a deflected draft surfaced nothing). Suspect speech never unlocks clues.
"""

from __future__ import annotations

from typing import Any

from src.state import CHANNEL_ACTIONS, INVESTIGATIVE, GameState, Runtime


def clues(state: GameState, rt: Runtime) -> dict[str, Any]:
    action = state["action"]
    kind = action["kind"]
    check = state.get("check") or {"ok": True}
    discovered = list(state.get("discovered_clues", []))
    seen = list(state.get("chunks_seen", []))
    new: list[str] = []

    if kind in CHANNEL_ACTIONS and check.get("ok", True):
        for c in state.get("retrieved", []):
            if c["id"] not in seen:
                seen.append(c["id"])
            cid = c.get("clue_id")
            if cid and cid not in discovered:
                discovered.append(cid)
                new.append(cid)

    update: dict[str, Any] = {"discovered_clues": discovered, "chunks_seen": seen,
                              "new_clues": new}
    if kind in INVESTIGATIVE:
        update["turns_left"] = max(0, state.get("turns_left", 0) - 1)
    if kind in ("question_suspect", "present_evidence"):
        sid = action["suspect_id"]
        questioned = list(state.get("suspects_questioned", []))
        if sid not in questioned:
            questioned.append(sid)
        update["suspects_questioned"] = questioned
        update["current_focus"] = sid
    elif kind in CHANNEL_ACTIONS:
        update["current_focus"] = None
    return update


def finalize(state: GameState, rt: Runtime) -> dict[str, Any]:
    """Promote the checked draft to final_reply (used when the checker is disabled)."""
    return {"final_reply": state.get("draft_reply", "")}


def respond(state: GameState, rt: Runtime) -> dict[str, Any]:
    """Append the turn to the conversation history. Only checked text is stored."""
    action = state.get("action") or {}
    reply = state.get("final_reply", "")
    speaker = state.get("reply_speaker") or "narrator"
    player = state.get("user_input", "").strip() or _describe(action)
    messages = list(state.get("messages", [])) + [
        {"role": "player", "content": player},
        {"role": speaker, "content": reply},
    ]
    update: dict[str, Any] = {"messages": messages}
    if action.get("kind") in ("question_suspect", "present_evidence"):
        from src.nodes.suspect import player_line

        sid = action["suspect_id"]
        history = {k: list(v) for k, v in state.get("suspect_history", {}).items()}
        history.setdefault(sid, []).extend([
            {"role": "user", "content": player_line(state, rt)},
            {"role": "assistant", "content": reply},
        ])
        update["suspect_history"] = history
    return update


def _describe(action: dict[str, Any]) -> str:
    kind = action.get("kind", "")
    labels = {
        "examine_scene": "Examine Server Room 11-S.",
        "request_records": "Request records.",
        "ask_forensics": "Ask forensics.",
        "question_suspect": f"Question {action.get('suspect_id', '')}.",
        "present_evidence": f"Present {', '.join(action.get('clue_ids', []))} to "
                            f"{action.get('suspect_id', '')}.",
        "accuse": f"Accuse {action.get('suspect_id', '')}.",
    }
    return labels.get(kind, "...")
