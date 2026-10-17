"""Judge: interpret an accusation and score it deterministically from the rubric.

The LLM only extracts which clue ids and motive elements the player's reasoning relies on.
It never sees the rubric or the solution. Only clues the player has discovered count.

Score /100: correct suspect 40, alibi flaw 20 (10 for the partial pair), eliminations
10 each up to 20, motive 10, turns remaining up to 10 (suspect-dependent parts score only
when the suspect is right).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.models import Case
from src.nodes.checker import extract_tokens
from src.state import GameState, Runtime
from src.truth_store import Rubric, get_rubric

MOTIVE_ELEMENTS = ["vp_override", "attestation", "report_contamination", "retention_offer",
                   "share_sale", "mining_rig"]


class JudgeExtraction(BaseModel):
    clue_ids: list[str] = Field(default_factory=list,
                                description="ids of the listed clues the reasoning relies on")
    motive_elements: list[str] = Field(default_factory=list,
                                       description=f"subset of {MOTIVE_ELEMENTS}")


SYSTEM = """You read a detective's written accusation and list what it relies on.
Return the ids of clues from the EVIDENCE LOCKER that the reasoning cites, either by id or
by clearly describing their content. Do not add clues the reasoning does not use, and do not
judge whether the reasoning is right.
Also return which motive elements it argues, from this list only:
- vp_override: the VP-level override that merged PR #2291 without reviews
- attestation: the signed Clinical Performance Attestation of 97.4% recall
- report_contamination: the integrity report showing evaluation data leaked into training
- retention_offer: a retention package / NDA offered to Elena
- share_sale: selling Larkspur's shares to Northgate before disclosure
- mining_rig: an unauthorised mining rig / unmetered load in Cage C3

EVIDENCE LOCKER:
{locker}"""


class Breakdown(BaseModel):
    suspect: int = 0
    alibi: int = 0
    eliminations: int = 0
    motive: int = 0
    turns: int = 0


class Verdict(BaseModel):
    accused: str
    correct: bool
    grade: Literal["full_credit", "partial_credit", "wrong", "case_lost"]
    score: int
    breakdown: Breakdown
    cleared_suspects: list[str]
    counted_clues: list[str]
    ignored_clues: list[str]
    feedback: str
    accusations_left: int
    game_over: bool


def score_accusation(rubric: Rubric, accused: str, cited: Iterable[str],
                     motive_elements: Iterable[str], discovered: Iterable[str],
                     turns_left: int, start_turns: int, wrong_so_far: int,
                     max_wrong: int) -> Verdict:
    found = set(discovered)
    claimed = set(cited) | {rubric.motive_elements[m] for m in motive_elements
                            if m in rubric.motive_elements}
    counted = claimed & found
    correct = accused == rubric.correct_suspect
    b = Breakdown()
    cleared: list[str] = []
    if correct:
        b.suspect = 40
        if any(set(rule) <= counted for rule in rubric.alibi_rules):
            b.alibi = 20
        elif any(set(rule) <= counted for rule in rubric.partial_alibi_rules):
            b.alibi = 10
        cleared = [s for s, alts in rubric.clearing_rules.items()
                   if any(set(a) <= counted for a in alts)]
        b.eliminations = min(20, 10 * len(cleared))
        b.motive = 10 if counted & set(rubric.motive_clues) else 0
        b.turns = round(10 * max(0, turns_left) / max(1, start_turns))

    wrong_total = wrong_so_far + (0 if correct else 1)
    lost = not correct and wrong_total >= max_wrong
    if correct:
        full = b.alibi == 20 and len(cleared) >= 2 and b.motive == 10
        grade = "full_credit" if full else "partial_credit"
        feedback = _correct_feedback(b, cleared)
    else:
        grade = "case_lost" if lost else "wrong"
        feedback = rubric.wrong_suspect_feedback.get(accused, "The evidence doesn't hold up.")

    return Verdict(
        accused=accused, correct=correct, grade=grade, score=sum(b.model_dump().values()),
        breakdown=b, cleared_suspects=cleared, counted_clues=sorted(counted),
        ignored_clues=sorted(claimed - found), feedback=feedback,
        accusations_left=max(0, max_wrong - wrong_total), game_over=correct or lost,
    )


def _correct_feedback(b: Breakdown, cleared: list[str]) -> str:
    gaps = []
    if b.alibi < 20:
        gaps.append("you never fully broke the alibi")
    if len(cleared) < 2:
        gaps.append("you didn't rule out the other suspects")
    if not b.motive:
        gaps.append("you didn't establish a motive")
    if not gaps:
        return "Alibi broken, the others ruled out, motive established. It will stand up in court."
    return "Right person, but the case is thin: " + "; ".join(gaps) + "."


def sanitize_feedback(text: str, case: Case, chunks_seen: Iterable[str]) -> str:
    """Rubric feedback may quote details the player has not uncovered; mask them."""
    seen = set(chunks_seen)
    seen_text = "\n".join(case.chunk_by_id[i].embed_text for i in seen)
    unseen_text = "\n".join(c.embed_text for c in case.fact_chunks if c.id not in seen)
    hidden = extract_tokens(unseen_text) - extract_tokens(seen_text)
    for tok in sorted(hidden, key=len, reverse=True):
        if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", tok):
            text = text.replace(tok, "the time of death")
    return text


def judge(state: GameState, rt: Runtime) -> dict[str, Any]:
    action = state["action"]
    accused = action["suspect_id"]
    discovered = state.get("discovered_clues", [])
    reasoning = (action.get("reasoning") or state.get("user_input") or "").strip()

    extraction = JudgeExtraction()
    if reasoning:
        locker = "\n".join(f"- {c}: {rt.case.clue_by_id[c].notebook}" for c in discovered) \
            or "(empty)"
        extraction = rt.llm.structured(
            "main", SYSTEM.format(locker=locker),
            [{"role": "user", "content": f"Accused: {accused}\nReasoning: {reasoning}"}],
            JudgeExtraction, task="judge", hints={"reasoning": reasoning},
        )

    prior = state.get("accusations_made", [])
    verdict = score_accusation(
        get_rubric(), accused, set(action.get("clue_ids") or []) | set(extraction.clue_ids),
        extraction.motive_elements, discovered, state.get("turns_left", 0),
        state.get("start_turns", rt.settings.start_turns),
        sum(1 for a in prior if not a["correct"]), rt.settings.max_wrong_accusations,
    )
    verdict.feedback = sanitize_feedback(verdict.feedback, rt.case, state.get("chunks_seen", []))
    name = rt.case.suspect_by_id[accused].name

    if verdict.correct:
        reply = (f"The DA reads your report twice, then signs the warrant for {name}. "
                 f"\"{verdict.feedback}\" Final score: {verdict.score}/100.")
    elif verdict.game_over:
        reply = (f"The DA drops your report on the desk. \"{verdict.feedback}\" "
                 f"{rt.settings.max_wrong_accusations} wrong accusations. You're off the case. Final score: {verdict.score}/100.")
    else:
        reply = (f"The DA slides the file back. \"Not {name}. {verdict.feedback}\" "
                 f"You have {verdict.accusations_left} accusation left.")

    record = {"suspect_id": accused, "correct": verdict.correct, "score": verdict.score,
              "grade": verdict.grade}
    return {
        "verdict": verdict.model_dump(),
        "accusations_made": [*prior, record],
        "game_over": verdict.game_over,
        "final_reply": reply,
        "reply_speaker": "narrator",
    }
