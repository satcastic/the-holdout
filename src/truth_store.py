"""The ONLY module allowed to read solution.json.

Exposes narrow providers so each caller sees the minimum it needs:
- get_private_brief(suspect_id): that one suspect's brief (suspect node only)
- get_rubric(): deterministic scoring data (judge node only)
- get_reveal(): true timeline and crime narrative (post-game reveal endpoint only)

tests/test_isolation.py enforces who may import what.
"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from typing import Any

from pydantic import BaseModel

from src.config import CASE_DIR

_SOLUTION_PATH = CASE_DIR / "solution.json"
_CLUE_RE = re.compile(r"\bC\d{2}\b")


@lru_cache
def _load() -> dict[str, Any]:
    return json.loads(_SOLUTION_PATH.read_text())


def get_private_brief(suspect_id: str) -> dict[str, Any]:
    """Return a copy of ONE suspect's private brief. Raises KeyError for unknown ids."""
    return copy.deepcopy(_load()["suspect_private_briefs"][suspect_id])


class Rubric(BaseModel):
    correct_suspect: str
    alibi_rules: list[list[str]]          # any satisfied set -> full alibi credit
    partial_alibi_rules: list[list[str]]  # any satisfied set -> half alibi credit
    clearing_rules: dict[str, list[list[str]]]
    motive_clues: list[str]
    motive_elements: dict[str, str]       # extracted motive keyword -> clue id
    wrong_suspect_feedback: dict[str, str]
    full_credit: str
    partial_credit: list[str]


def get_rubric() -> Rubric:
    """Scoring data derived from accusation_rubric + deduction_model (see DECISIONS D14)."""
    sol = _load()
    rub = sol["accusation_rubric"]
    dm = sol["deduction_model"]
    alibi = [list(a) for a in dm["killer_rules"]["alibi_broken_by"]]
    alibi_ids = {c for a in alibi for c in a}
    clearing = {k: [list(a) for a in v] for k, v in dm["clearing_rules"].items()}
    clearing_ids = {c for alts in clearing.values() for a in alts for c in a}

    full_ids = _CLUE_RE.findall(rub["full_credit"])
    motive = [c for c in full_ids if c not in alibi_ids and c not in clearing_ids]
    for alt in dm["killer_rules"]["motive_by"]:
        motive += [c for c in alt if c not in motive]

    partial: list[list[str]] = []
    for line in rub["partial_credit"]:
        ids = _CLUE_RE.findall(line)
        if alibi_ids & set(ids):
            rest = [c for c in ids if c not in alibi_ids]
            if rest:
                partial.append(rest)

    return Rubric(
        correct_suspect=rub["correct_suspect"],
        alibi_rules=alibi,
        partial_alibi_rules=partial,
        clearing_rules=clearing,
        motive_clues=motive,
        motive_elements={"vp_override": "C04", "attestation": "C06",
                         "report_contamination": "C03"},
        wrong_suspect_feedback=dict(rub["wrong_suspect_feedback"]),
        full_credit=rub["full_credit"],
        partial_credit=list(rub["partial_credit"]),
    )


class TimelineEvent(BaseModel):
    day: str
    start: str
    end: str
    actors: list[str]
    location: str
    event: str


class Reveal(BaseModel):
    killer: str
    crime: dict[str, str]
    true_timeline: list[TimelineEvent]
    clue_chain: list[str]
    alibi_flaw: str


def get_reveal() -> Reveal:
    """Post-game only: the truth, minus the private briefs and the rubric."""
    sol = _load()
    timeline = sorted(sol["true_timeline"], key=lambda e: (e["day"], e["start"]))
    return Reveal(
        killer=sol["killer"],
        crime={k: str(v) for k, v in sol["crime"].items()},
        true_timeline=[TimelineEvent(**{k: e[k] for k in TimelineEvent.model_fields})
                       for e in timeline],
        clue_chain=list(sol["clue_chain"]["steps"]),
        alibi_flaw=sol["alibi_flaw"]["flaw"],
    )
