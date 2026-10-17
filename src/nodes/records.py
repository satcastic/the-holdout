"""Records, scene and forensics node: answers strictly from retrieved chunks."""

from __future__ import annotations

from typing import Any

from src.state import GameState, Runtime

DESKS = {
    "records": ("records", "the records desk", "Nothing in the records answers that."),
    "scene": ("scene", "the scene", "There is nothing at the scene that answers that."),
    "forensics": ("forensics", "the forensics lab", "Forensics has nothing available on that."),
}

SYSTEM = """You are {desk} in a police investigation, reporting to the detective.
Answer ONLY from the ITEMS below. Quote the relevant log lines, times and figures exactly as
written, and name the item each quote comes from. Use 24-hour times as written.
Do not summarise beyond the items, do not speculate about guilt or who did it, and do not
mention, hint at or guess about any item not listed (no "there may be more", no "locked
files"). If no item answers the question, reply exactly: "{empty}"
Write plainly, at most 180 words.

ITEMS:
{items}"""


def records(state: GameState, rt: Runtime) -> dict[str, Any]:
    actor = state["retrieval_actor"]
    speaker, desk, empty = DESKS[actor]
    retrieved = state.get("retrieved", [])
    if not retrieved:  # nothing survived gating: fixed reply, no LLM call
        return {"draft_reply": empty, "reply_speaker": speaker}

    items = "\n\n".join(
        f"[{c['title']}] ({c['type']}{', ' + c['time'] if c.get('time') else ''})\n{c['text']}"
        for c in retrieved
    )
    system = SYSTEM.format(desk=desk, empty=empty, items=items)
    check = state.get("check") or {}
    if state.get("retries", 0) and check.get("issues"):
        system += "\n\nYour previous answer was rejected; fix: " + "; ".join(check["issues"])
    question = state.get("user_input", "").strip() or state["rewritten_query"]
    draft = rt.llm.generate(
        "main", system, [{"role": "user", "content": question}], task="records",
        max_tokens=rt.settings.max_tokens_main, hints={"chunks": retrieved, "actor": actor},
    )
    return {"draft_reply": draft, "reply_speaker": speaker}
