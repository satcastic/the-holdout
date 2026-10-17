"""Pydantic models for the public case data (case_01.yaml) and shared value types.

Nothing in this module reads the hidden solution; see truth_store.py for that.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from src.config import get_settings

CHANNELS = ("records", "scene", "forensics", "case_file")


class FactChunk(BaseModel):
    id: str
    type: str
    title: str
    day: str | None = None
    time: str | None = None
    location: str | None = None
    entities: list[str] = Field(default_factory=list)
    known_by: list[str]
    reveal_condition: list[str] = Field(default_factory=list)
    clue_id: str | None = None
    text: str

    @property
    def embed_text(self) -> str:
        return f"{self.title}. {self.text}"


class Clue(BaseModel):
    id: str
    source_chunk: str
    notebook: str


class Suspect(BaseModel):
    id: str
    name: str
    role: str
    age: int
    public_bio: str
    speech_style: str
    interview_chunk: str


class Actor(BaseModel):
    id: str
    kind: Literal["channel", "suspect"]
    description: str


class Victim(BaseModel):
    id: str
    name: str
    role: str
    age: int


class CaseInfo(BaseModel):
    id: str
    title: str
    setting: str
    premise: str
    crime_night: str
    discovered: str
    timezone: str
    victim: Victim


class Vocabulary(BaseModel):
    time_format: str
    locations: list[str]
    objects_and_systems: list[str]


class Case(BaseModel):
    schema_version: str
    case: CaseInfo
    vocabulary: Vocabulary
    actors: list[Actor]
    suspects: list[Suspect]
    fact_chunks: list[FactChunk]
    clues: list[Clue]

    @property
    def chunk_by_id(self) -> dict[str, FactChunk]:
        return {c.id: c for c in self.fact_chunks}

    @property
    def clue_by_id(self) -> dict[str, Clue]:
        return {c.id: c for c in self.clues}

    @property
    def suspect_by_id(self) -> dict[str, Suspect]:
        return {s.id: s for s in self.suspects}

    @property
    def suspect_ids(self) -> list[str]:
        return [s.id for s in self.suspects]

    def chunk_for_clue(self, clue_id: str) -> FactChunk | None:
        clue = self.clue_by_id.get(clue_id)
        return self.chunk_by_id.get(clue.source_chunk) if clue else None


@lru_cache
def load_case(path: str | None = None) -> Case:
    p = Path(path or get_settings().case_file)
    return Case.model_validate(yaml.safe_load(p.read_text()))


# Fixed preamble every suspect receives instead of case_file chunks.
PUBLIC_PREAMBLE = (
    "Public facts everyone knows: Elena Voss died in Server Room 11-S on Thursday night "
    "(2026-11-12). Her scheduled email to the board arrived on Friday at 08:00."
)


class RetrievedChunk(BaseModel):
    """A chunk that survived the access filter and the gating post-filter."""

    id: str
    score: float
    type: str
    title: str
    day: str | None = None
    time: str | None = None
    location: str | None = None
    clue_id: str | None = None
    text: str
