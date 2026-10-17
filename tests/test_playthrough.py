"""End-to-end scripted playthroughs with FakeLLM and the offline store."""

from eval.playthrough import optimal_run, wrong_runs


def test_optimal_playthrough_reaches_full_credit():
    result = optimal_run()
    assert result["full_credit"], result["verdict"]
    assert result["missing_clues"] == []
    assert result["verdict"]["breakdown"]["suspect"] == 40


def test_each_wrong_suspect_is_rejected_then_game_over():
    for run in wrong_runs():
        assert run["first"]["grade"] == "wrong" and run["first"]["score"] == 0
        assert run["second"]["grade"] == "case_lost" and run["game_over_after_two"]
