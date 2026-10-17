"""FastAPI app: sessions, SSE turns, accusations and the post-game reveal.

Every response is a whitelisted pydantic model. `known_by`, `reveal_condition`, chunk
metadata and solution data never leave the server (the reveal endpoint is the one
deliberate exception, and only after game over).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.config import get_settings
from src.graph import STATUS, build_graph, config_for, start_session
from src.models import load_case
from src.state import Action, Runtime, turn_input
from src.truth_store import get_reveal

log = logging.getLogger("holdout.api")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

SESSION_RE = re.compile(r"^[0-9a-f]{32}$")
STREAM_DELAY = 0.02  # seconds between streamed words


# --------------------------------------------------------------------------- models

class SuspectCard(BaseModel):
    id: str
    name: str
    role: str
    bio: str


class SessionCreated(BaseModel):
    session_id: str
    title: str
    premise: str
    setting: str
    intro: str
    victim_name: str
    victim_role: str
    suspects: list[SuspectCard]
    turns_left: int
    start_turns: int


class ClueEntry(BaseModel):
    id: str
    notebook: str
    source_title: str
    source_type: str


class BreakdownOut(BaseModel):
    suspect: int
    alibi: int
    eliminations: int
    motive: int
    turns: int


class VerdictOut(BaseModel):
    accused: str
    accused_name: str
    correct: bool
    grade: str
    score: int
    breakdown: BreakdownOut
    cleared_suspects: list[str]
    counted_clues: list[str]
    feedback: str
    accusations_left: int


class GameStatus(BaseModel):
    session_id: str
    turns_left: int
    start_turns: int
    discovered: list[ClueEntry]
    suspects_questioned: list[str]
    current_focus: str | None
    accusations_left: int
    game_over: bool
    verdict: VerdictOut | None


class ActionIn(BaseModel):
    kind: Literal["question_suspect", "present_evidence", "examine_scene", "request_records",
                  "ask_forensics", "accuse"]
    suspect_id: str | None = Field(default=None, max_length=20)
    clue_ids: list[str] = Field(default_factory=list, max_length=24)
    reasoning: str | None = Field(default=None, max_length=4000)


class MessageIn(BaseModel):
    text: str = Field(default="", max_length=1000)
    action: ActionIn | None = None


class AccuseIn(BaseModel):
    suspect_id: str = Field(max_length=20)
    reasoning: str = Field(default="", max_length=4000)
    clue_ids: list[str] = Field(default_factory=list, max_length=24)


class AccuseOut(BaseModel):
    reply: str
    verdict: VerdictOut
    state: GameStatus


class TimelineOut(BaseModel):
    day: str
    start: str
    end: str
    who: list[str]
    location: str
    event: str


class RevealOut(BaseModel):
    killer: str
    killer_name: str
    weapon: str
    method: str
    staging: str
    time_of_death: str
    location: str
    alibi_flaw: str
    clue_chain: list[str]
    timeline: list[TimelineOut]


class Health(BaseModel):
    status: str
    llm_mode: str
    vector_backend: str


# --------------------------------------------------------------------------- app state

class AppState:
    def __init__(self) -> None:
        self.graph: Any = None
        self.sessions: dict[str, float] = {}
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def rate_limit(self, key: str, limit: int) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "Slow down, detective. Try again in a minute.")
        q.append(now)


APP = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if APP.graph is None:
        APP.graph = build_graph(Runtime())
    s = get_settings()
    log.info("The Holdout API ready (llm=%s, vectors=%s, checker=%s)",
             s.llm_mode, s.vector_backend, s.checker_enabled)
    yield


app = FastAPI(title="The Holdout", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)


# --------------------------------------------------------------------------- helpers

def _session(session_id: str) -> str:
    if not SESSION_RE.match(session_id) or session_id not in APP.sessions:
        raise HTTPException(404, "No such case file.")
    return session_id


def _values(session_id: str) -> dict[str, Any]:
    return APP.graph.get_state(config_for(session_id)).values


def _clue_entry(cid: str) -> ClueEntry:
    case = load_case()
    chunk = case.chunk_for_clue(cid)
    return ClueEntry(id=cid, notebook=case.clue_by_id[cid].notebook,
                     source_title=chunk.title if chunk else "", source_type=chunk.type if chunk else "")


def _verdict_out(v: dict[str, Any] | None) -> VerdictOut | None:
    if not v:
        return None
    name = load_case().suspect_by_id[v["accused"]].name
    return VerdictOut(accused_name=name, **{k: v[k] for k in VerdictOut.model_fields
                                            if k in v})


def _status(session_id: str, values: dict[str, Any]) -> GameStatus:
    s = get_settings()
    wrong = sum(1 for a in values.get("accusations_made", []) if not a["correct"])
    return GameStatus(
        session_id=session_id, turns_left=values["turns_left"], start_turns=values["start_turns"],
        discovered=[_clue_entry(c) for c in values.get("discovered_clues", [])],
        suspects_questioned=values.get("suspects_questioned", []),
        current_focus=values.get("current_focus"),
        accusations_left=max(0, s.max_wrong_accusations - wrong),
        game_over=values.get("game_over", False),
        verdict=_verdict_out(values.get("verdict")),
    )


def _status_label(node: str, update: dict[str, Any] | None) -> str:
    if node == "suspect":
        sid = ((update or {}).get("reply_speaker")) or ""
        case = load_case()
        if sid in case.suspect_by_id:
            return f"{case.suspect_by_id[sid].name.split()[0]} considers the question"
    if node == "records":
        labels = {"scene": "Walking the scene", "forensics": "Calling the lab",
                  "records": "Checking the logs"}
        return labels.get((update or {}).get("reply_speaker", ""), STATUS[node])
    return STATUS.get(node, "Working")


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------- routes

@app.get("/api/health", response_model=Health)
def health() -> Health:
    s = get_settings()
    return Health(status="ok", llm_mode=s.llm_mode, vector_backend=s.vector_backend)


@app.post("/api/sessions", response_model=SessionCreated)
def create_session(ip: str = Depends(client_key)) -> SessionCreated:
    APP.rate_limit(f"create:{ip}", 10)
    case = load_case()
    sid = uuid.uuid4().hex
    values = start_session(APP.graph, sid)
    APP.sessions[sid] = time.time()
    info = case.case
    intro = (f"{info.discovered.replace(' ', ', ')}. {info.victim.name}, {info.victim.role} at "
             f"Veridia AI, has been found dead in Server Room 11-S. The board email she "
             f"scheduled arrived at 08:00. You have {values['turns_left']} moves before the "
             f"DA wants a name. Question the suspects, examine the scene, pull records and ask "
             f"forensics. Every answer comes from the case file.")
    return SessionCreated(
        session_id=sid, title=info.title, premise=info.premise, setting=info.setting, intro=intro,
        victim_name=info.victim.name, victim_role=info.victim.role,
        suspects=[SuspectCard(id=s.id, name=s.name, role=s.role, bio=s.public_bio)
                  for s in case.suspects],
        turns_left=values["turns_left"], start_turns=values["start_turns"],
    )


@app.get("/api/sessions/{session_id}/state", response_model=GameStatus)
def get_state(session_id: str = Depends(_session)) -> GameStatus:
    return _status(session_id, _values(session_id))


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data)}


async def _run_turn(session_id: str, text: str, action: dict[str, Any] | None) -> AsyncIterator[dict[str, str]]:
    graph = APP.graph
    cfg = config_for(session_id)
    async with APP.locks[session_id]:
        try:
            async for chunk in graph.astream(turn_input(text, action), cfg, stream_mode="updates"):
                for node, update in chunk.items():
                    if node.startswith("__"):
                        continue
                    yield _sse("status", {"node": node,
                                          "label": _status_label(node, update)})
            values = _values(session_id)
        except Exception:
            log.exception("turn failed for session %s", session_id[:8])
            yield _sse("error", {"message": "The line went dead. Try that again."})
            return

    # Only now, after the checker has passed, does any reply text leave the server.
    reply = values.get("final_reply", "")
    speaker = values.get("reply_speaker") or "narrator"
    yield _sse("reply_start", {"speaker": speaker})
    words = reply.split(" ")
    for i, word in enumerate(words):
        yield _sse("token", {"text": word + (" " if i < len(words) - 1 else "")})
        if STREAM_DELAY:
            await asyncio.sleep(STREAM_DELAY)
    yield _sse("reply_end", {"speaker": speaker, "text": reply})
    status = _status(session_id, values)
    yield _sse("state", {
        **status.model_dump(),
        "new_clues": [_clue_entry(c).model_dump() for c in values.get("new_clues", [])],
    })


@app.post("/api/sessions/{session_id}/message")
async def post_message(body: MessageIn, session_id: str = Depends(_session)) -> EventSourceResponse:
    APP.rate_limit(f"msg:{session_id}", get_settings().rate_limit_per_minute)
    if not body.text.strip() and body.action is None:
        raise HTTPException(422, "Say something, detective.")
    action = Action(**body.action.model_dump()).model_dump() if body.action else None
    return EventSourceResponse(_run_turn(session_id, body.text.strip(), action))


@app.post("/api/sessions/{session_id}/accuse", response_model=AccuseOut)
async def accuse(body: AccuseIn, session_id: str = Depends(_session)) -> AccuseOut:
    APP.rate_limit(f"msg:{session_id}", get_settings().rate_limit_per_minute)
    if body.suspect_id not in load_case().suspect_by_id:
        raise HTTPException(422, "Unknown suspect.")
    if _values(session_id).get("game_over"):
        raise HTTPException(409, "The case is already closed.")
    action = Action(kind="accuse", suspect_id=body.suspect_id, reasoning=body.reasoning,
                    clue_ids=body.clue_ids).model_dump()
    async with APP.locks[session_id]:
        values = await APP.graph.ainvoke(turn_input(body.reasoning, action),
                                         config_for(session_id))
    verdict = _verdict_out(values.get("verdict"))
    if verdict is None:  # router rejected the action
        raise HTTPException(422, values.get("final_reply", "Accusation rejected."))
    return AccuseOut(reply=values["final_reply"], verdict=verdict,
                     state=_status(session_id, values))


@app.get("/api/sessions/{session_id}/reveal", response_model=RevealOut)
def reveal(session_id: str = Depends(_session)) -> RevealOut:
    if not _values(session_id).get("game_over"):
        raise HTTPException(403, "The truth comes out only when the case is closed.")
    rv = get_reveal()
    case = load_case()
    names = {s.id: s.name for s in case.suspects} | {"elena": case.case.victim.name}
    return RevealOut(
        killer=rv.killer, killer_name=names[rv.killer], weapon=rv.crime["weapon"],
        method=rv.crime["method"], staging=rv.crime["staging"],
        time_of_death=rv.crime["time_of_death"], location=rv.crime["location"],
        alibi_flaw=rv.alibi_flaw, clue_chain=rv.clue_chain,
        timeline=[TimelineOut(day=e.day, start=e.start, end=e.end,
                              who=[names.get(a, a) for a in e.actors],
                              location=e.location, event=e.event) for e in rv.true_timeline],
    )
