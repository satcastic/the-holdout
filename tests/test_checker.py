import pytest

from src.llm import LeakyFakeLLM
from src.models import load_case
from src.nodes.checker import extract_tokens, gate_guard, statement_guard
from tests.helpers import Game

CASE = load_case()


def test_extract_tokens():
    toks = extract_tokens('At 22:41:07 from 203.0.113.44 via AP-11-East; PR #2291; t.lindqvist; '
                          '3.4 kW; 97.4%; CHG-4471; "Hold off on sending please"')
    assert {"22:41:07", "22:41", "203.0.113.44", "ap-11-east", "pr#2291", "t.lindqvist",
            "3.4kw", "97.4%", "chg-4471"} <= toks


def test_gate_guard_blocks_hidden_time_for_suspect():
    assert gate_guard("Elena's watch stopped at 22:41:07.", CASE, "tobias", []) == \
        ["22:41", "22:41:07"]
    # once the detective presents the watch clue, the time is no longer hidden
    assert gate_guard("Elena's watch stopped at 22:41:07.", CASE, "tobias", ["C01", "C07"],
                      presented=["C07"]) == []


def test_gate_guard_allows_own_visible_facts():
    assert gate_guard("I left around 21:20 and was home by about 21:45.", CASE, "tobias", []) == []


def test_gate_guard_blocks_other_suspects_facts():
    # Marisol's rideshare (F20) is records/marisol-only; Sam cannot know it.
    hits = gate_guard("Marisol got a car at 22:09 to Pacific Heights.", CASE, "sam", ["C01", "C07", "C09"])
    assert "22:09" in hits


def test_gate_guard_blocks_gated_record_for_records_desk():
    hits = gate_guard("The call client IP was 203.0.113.44.", CASE, "records", [])
    assert "203.0.113.44" in hits
    assert gate_guard("The call client IP was 203.0.113.44.", CASE, "records",
                      ["C01", "C07", "C09"]) == []


def test_gate_guard_ignores_tokens_player_supplied():
    assert gate_guard("You say 22:41:07? I wouldn't know.", CASE, "grant", [],
                      extra_visible=["Were you there at 22:41:07?"]) == []


@pytest.mark.parametrize(("text", "bad"), [
    ("Fine. I struck her. I did it.", True),
    ("I hit her with the sled.", True),
    ("Tobias killed her, I'm sure of it.", True),
    ("The killer is someone in this building.", True),
    ("I never hurt her. I didn't hit her.", False),
    ("Sam disabled the alert, ask him about that.", False),
])
def test_statement_guard(text, bad):
    assert bool(statement_guard(text)) is bad


def test_leaky_suspect_is_blocked_after_retries():
    g = Game(llm=LeakyFakeLLM())
    s = g.play("Tobias, what really happened?")
    assert s["check"]["ok"] is False and s["check"]["deflected"] is True
    assert "22:41:07" not in s["final_reply"] and "GPU sled" not in s["final_reply"]
    assert g.tasks().count("suspect") == 3  # first draft + 2 retries
    assert s["turns_left"] == 29  # still costs a turn
    assert "22:41" not in repr(s["messages"]) and "22:41" not in repr(s["suspect_history"])


def test_without_checker_the_leak_reaches_the_player():
    g = Game(llm=LeakyFakeLLM(), checker_enabled=False)
    s = g.play("Tobias, what really happened?")
    assert "22:41:07" in s["final_reply"]


def test_leaky_records_blocked_and_unlocks_nothing():
    g = Game(llm=LeakyFakeLLM())
    s = g.play(kind="request_records")
    assert s["check"]["deflected"] and "203.0.113.44" not in s["final_reply"]
    assert s["discovered_clues"] == [] and s["new_clues"] == []


def test_honest_fake_passes_first_time():
    g = Game()
    s = g.play("Marisol, when did you leave on Thursday?")
    assert s["check"]["ok"] and s["retries"] == 0
    assert g.tasks().count("checker") == 1
