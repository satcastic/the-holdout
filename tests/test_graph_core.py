from src.nodes.suspect import breaks_satisfied, build_system_prompt, parse_breaks_when
from src.state import Runtime
from src.truth_store import get_private_brief
from tests.helpers import Game


def test_session_starts_clean():
    g = Game()
    graph_state = g.graph.get_state({"configurable": {"thread_id": g.sid}})
    assert graph_state.next == ()
    assert g.state["turns_left"] == 30 and g.state["discovered_clues"] == []


def test_ui_action_bypasses_router_llm():
    g = Game()
    g.play(kind="ask_forensics")
    assert "router" not in g.tasks()
    g.play("What did the medical examiner find?")
    assert "router" in g.tasks()


def test_forensics_unlocks_clue_and_costs_a_turn():
    g = Game()
    s = g.play(kind="ask_forensics")
    assert "C01" in s["discovered_clues"] and s["new_clues"] == ["C01"]
    assert s["turns_left"] == 29
    assert "F02" in s["chunks_seen"]


def test_suspect_speech_never_unlocks_clues():
    g = Game()
    # F05 (clue C02) is known_by tobias, so his retrieval surfaces it; it must not unlock.
    s = g.play("Tobias, tell me about the board email and the integrity report")
    assert any(c["id"] == "F05" for c in s["retrieved"])
    assert s["discovered_clues"] == []
    assert s["turns_left"] == 29 and s["suspects_questioned"] == ["tobias"]


def test_gated_clue_needs_prerequisite():
    g = Game()
    s = g.play("smartwatch heart rate", kind="ask_forensics")
    assert "C07" not in s["discovered_clues"]  # F04 needs C01 first
    s = g.play("smartwatch heart rate", kind="ask_forensics")
    assert "C07" in s["discovered_clues"]


def test_invalid_is_free_and_nudges():
    g = Game()
    s = g.play("what's the weather like?")
    assert s["action"]["kind"] == "invalid"
    assert s["turns_left"] == 30 and "Stay on the case" in s["final_reply"]


def test_out_of_turns_only_accuse():
    g = Game(start_turns=1)
    g.play(kind="examine_scene")
    s = g.play(kind="request_records")
    assert s["turns_left"] == 0 and "accusation" in s["final_reply"].lower()


def test_present_requires_discovered_clue():
    g = Game()
    s = g.play(kind="present_evidence", suspect_id="marisol", clue_ids=["C17"])
    assert "don't have that evidence" in s["final_reply"]
    assert s["turns_left"] == 30


def test_follow_up_uses_current_focus():
    g = Game()
    g.play("Sam, when did you leave?")
    s = g.play("And after that?")
    assert s["action"] == {"kind": "question_suspect", "suspect_id": "sam", "clue_ids": [],
                           "reasoning": None}
    assert "Sam Ibarra" in s["rewritten_query"]


def test_history_records_only_final_text():
    g = Game()
    s = g.play("Grant, where were you on Thursday?")
    assert s["messages"][-1] == {"role": "grant", "content": s["final_reply"]}
    assert s["suspect_history"]["grant"][-1]["content"] == s["final_reply"]


# ---- brief injection ----------------------------------------------------------------

def _prompt(sid, kind="question_suspect", clue_ids=()):
    state = {"action": {"kind": kind, "suspect_id": sid, "clue_ids": list(clue_ids)},
             "retrieved": [], "retries": 0}
    return build_system_prompt(state, Runtime())


def test_admissions_only_for_presented_clues():
    brief = get_private_brief("marisol")["admits_if_confronted_with"]
    prompt, admissions, _ = _prompt("marisol")
    assert admissions == [] and brief["C17"] not in prompt and brief["C18"] not in prompt
    prompt, admissions, _ = _prompt("marisol", "present_evidence", ["C17"])
    assert admissions == [brief["C17"]] and brief["C18"] not in prompt


def test_hidden_brief_keys_never_dumped():
    for sid in ("tobias", "marisol", "grant", "sam"):
        prompt, _, _ = _prompt(sid)
        assert "admits_if_confronted_with" not in prompt and "breaks_when" not in prompt


def test_breaks_when_parsed_and_enforced_in_code():
    text = get_private_brief("tobias")["breaks_when"]
    required, pool, k, instruction = parse_breaks_when(text)
    assert (required, pool, k) == ("C21", {"C22", "C09", "C23"}, 2)
    assert instruction.startswith("stop claiming")
    assert breaks_satisfied(text, {"C21", "C22", "C09"})
    assert breaks_satisfied(text, {"C21", "C23", "C09"})
    assert not breaks_satisfied(text, {"C21", "C22"})
    assert not breaks_satisfied(text, {"C22", "C09", "C23"})
    _, _, broken = _prompt("tobias", "present_evidence", ["C21", "C22"])
    assert not broken
    prompt, _, broken = _prompt("tobias", "present_evidence", ["C21", "C22", "C23"])
    assert broken and "stop claiming you were home" in prompt
