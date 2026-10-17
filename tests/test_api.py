import json

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

import src.api as api
from src.graph import build_graph
from src.llm import FakeLLM
from src.state import Runtime

HIDDEN = ("known_by", "reveal_condition", "admits_if_confronted_with", "cover_story",
          "what_you_did", "what_you_know", "breaks_when", "knowledge_boundaries",
          "accusation_rubric", "deduction_model", "true_timeline", "solution")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "STREAM_DELAY", 0)
    api.APP.__init__()
    api.APP.graph = build_graph(Runtime(llm=FakeLLM()), checkpointer=InMemorySaver())
    with TestClient(api.app) as c:
        c.bodies = []
        yield c
    for body in c.bodies:
        for word in HIDDEN:
            assert word not in body, word


def _record(c, resp):
    c.bodies.append(resp.text)
    return resp


def parse_sse(text):
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        ev, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if ev:
            events.append((ev, data))
    return events


def new_session(c):
    r = _record(c, c.post("/api/sessions"))
    assert r.status_code == 200
    return r.json()


def turn(c, sid, text="", action=None):
    r = _record(c, c.post(f"/api/sessions/{sid}/message", json={"text": text, "action": action}))
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def test_health(client):
    r = _record(client, client.get("/api/health"))
    assert r.json() == {"status": "ok", "llm_mode": "fake", "vector_backend": "memory"}
    assert "api_key" not in r.text.lower()


def test_create_session_contract(client):
    body = new_session(client)
    assert set(body) == {"session_id", "title", "premise", "setting", "intro", "victim_name",
                         "victim_role", "suspects", "turns_left", "start_turns"}
    assert [s["id"] for s in body["suspects"]] == ["tobias", "marisol", "grant", "sam"]
    assert set(body["suspects"][0]) == {"id", "name", "role", "bio"}
    assert body["turns_left"] == 30


def test_message_sse_order_and_state(client):
    sid = new_session(client)["session_id"]
    events = turn(client, sid, action={"kind": "ask_forensics"})
    kinds = [e for e, _ in events]
    assert kinds[0] == "status" and kinds[-1] == "state"
    first_token = kinds.index("token")
    # all status events (including the checker) come before any reply text
    assert "checker" in [d["node"] for e, d in events if e == "status"]
    assert all(k == "status" for k in kinds[:kinds.index("reply_start")])
    assert first_token > kinds.index("reply_start")
    text = "".join(d["text"] for e, d in events if e == "token")
    assert text == next(d["text"] for e, d in events if e == "reply_end")
    state = events[-1][1]
    assert state["turns_left"] == 29
    assert [c["id"] for c in state["new_clues"]] == ["C01"]
    assert set(state["new_clues"][0]) == {"id", "notebook", "source_title", "source_type"}


def test_state_endpoint(client):
    sid = new_session(client)["session_id"]
    turn(client, sid, "Marisol, where were you at 21:00?")
    r = _record(client, client.get(f"/api/sessions/{sid}/state"))
    body = r.json()
    assert body["suspects_questioned"] == ["marisol"] and body["current_focus"] == "marisol"
    assert body["game_over"] is False and body["verdict"] is None


def test_validation_and_unknown_session(client):
    assert client.get("/api/sessions/" + "0" * 32 + "/state").status_code == 404
    assert client.get("/api/sessions/../etc/state").status_code == 404
    sid = new_session(client)["session_id"]
    assert client.post(f"/api/sessions/{sid}/message", json={"text": ""}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/message",
                       json={"text": "x" * 1001}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/message",
                       json={"action": {"kind": "invalid"}}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/accuse",
                       json={"suspect_id": "elena"}).status_code == 422


def test_reveal_locked_until_game_over_then_available(client):
    sid = new_session(client)["session_id"]
    assert client.get(f"/api/sessions/{sid}/reveal").status_code == 403
    r = _record(client, client.post(f"/api/sessions/{sid}/accuse",
                                    json={"suspect_id": "sam", "reasoning": "He came back."}))
    assert r.json()["verdict"]["grade"] == "wrong"
    assert client.get(f"/api/sessions/{sid}/reveal").status_code == 403
    r = client.post(f"/api/sessions/{sid}/accuse", json={"suspect_id": "grant"})
    assert r.json()["state"]["game_over"] is True
    rv = client.get(f"/api/sessions/{sid}/reveal")
    assert rv.status_code == 200 and rv.json()["timeline"]
    assert client.post(f"/api/sessions/{sid}/accuse", json={"suspect_id": "tobias"}).status_code == 409


def test_rate_limit(client, monkeypatch):
    sid = new_session(client)["session_id"]
    monkeypatch.setattr(api.get_settings(), "rate_limit_per_minute", 2)
    turn(client, sid, action={"kind": "examine_scene"})
    turn(client, sid, action={"kind": "examine_scene"})
    r = client.post(f"/api/sessions/{sid}/message", json={"action": {"kind": "examine_scene"}})
    assert r.status_code == 429


def test_cors_allows_vite(client):
    r = client.options("/api/sessions", headers={"Origin": "http://localhost:5173",
                                                 "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
