from src.models import load_case
from src.nodes.judge import sanitize_feedback, score_accusation
from src.truth_store import get_rubric
from tests.helpers import Game

R = get_rubric()
ALL = [c.id for c in load_case().clues]


def _score(accused, cited, discovered=ALL, motives=(), turns_left=15, wrong=0):
    return score_accusation(R, accused, cited, motives, discovered, turns_left, 30, wrong, 2)


def test_full_credit():
    v = _score("tobias", {"C21", "C12", "C16", "C20", "C04"})
    assert v.grade == "full_credit" and v.correct and v.game_over
    assert v.breakdown.model_dump() == {"suspect": 40, "alibi": 20, "eliminations": 20,
                                        "motive": 10, "turns": 5}
    assert v.score == 95 and set(v.cleared_suspects) == {"marisol", "grant", "sam"}


def test_two_eliminations_are_enough_for_full_credit():
    assert _score("tobias", {"C21", "C12", "C20", "C06"}).grade == "full_credit"


def test_undiscovered_clues_do_not_count():
    v = _score("tobias", {"C21", "C12", "C16", "C04"}, discovered=["C04", "C12", "C16"])
    assert v.breakdown.alibi == 0 and v.grade == "partial_credit"
    assert v.ignored_clues == ["C21"]


def test_partial_alibi_pair():
    assert _score("tobias", {"C09", "C22"}).breakdown.alibi == 10


def test_motive_from_extracted_element_requires_discovery():
    assert _score("tobias", set(), motives=["attestation"]).breakdown.motive == 10
    assert _score("tobias", set(), motives=["attestation"], discovered=["C01"]).breakdown.motive == 0


def test_partial_credit_motive_only():
    v = _score("tobias", {"C04"})
    assert v.grade == "partial_credit" and v.score == 40 + 10 + 5


def test_wrong_suspect_scores_zero_with_rubric_feedback():
    v = _score("sam", {"C10", "C11", "C13"})
    assert v.grade == "wrong" and v.score == 0 and not v.game_over
    assert v.feedback == R.wrong_suspect_feedback["sam"] and v.accusations_left == 1
    v2 = _score("grant", set(), wrong=1)
    assert v2.grade == "case_lost" and v2.game_over and v2.accusations_left == 0


def test_feedback_masks_unseen_time_of_death():
    fb = R.wrong_suspect_feedback["marisol"]
    assert "22:41:07" in fb
    assert "22:41:07" not in sanitize_feedback(fb, load_case(), ["F02", "F05"])
    assert "22:41:07" in sanitize_feedback(fb, load_case(), ["F04"])


def test_accuse_through_graph_is_free_and_ends_game():
    g = Game()
    g.play(kind="ask_forensics")
    s = g.play(kind="accuse", suspect_id="marisol", reasoning="She lied about the meeting.",
               clue_ids=[])
    assert s["verdict"]["grade"] == "wrong" and not s["game_over"] and s["turns_left"] == 29
    s = g.play("I accuse Grant Ostrowski, he lied about being home.")
    assert s["action"]["kind"] == "accuse" and s["verdict"]["grade"] == "case_lost"
    assert s["game_over"]
    s = g.play(kind="examine_scene")
    assert "case is closed" in s["final_reply"]


def test_judge_llm_never_sees_rubric_or_solution():
    g = Game()
    g.play(kind="ask_forensics")
    g.play(kind="accuse", suspect_id="marisol", reasoning="C01 and her retention offer",
           clue_ids=[])
    prompts = [sp for task, sp in g.llm.systems if task == "judge"]
    assert len(prompts) == 1
    for secret in (R.full_credit, R.wrong_suspect_feedback["marisol"], "killer",
                   "correct_suspect", "tobias", "C21"):
        assert secret not in prompts[0]
