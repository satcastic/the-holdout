"""Scripted playthroughs: one optimal run that should reach full credit, plus a run that
accuses each wrong suspect.

The script is adaptive: each step targets a clue with a natural detective query and, if
retrieval ranks it outside the top 5, tries one alternative phrasing (each try costs a turn).

Usage: python -m eval.playthrough
"""

from __future__ import annotations

from typing import Any

from eval.common import EvalGame, run_meta, save

# (target clue, action kind, queries to try in order)
PLAN: list[tuple[str, str, list[str]]] = [
    ("C01", "ask_forensics", ["What was the cause and time of death?"]),
    ("C07", "ask_forensics", ["What does Elena's smartwatch show?", "smartwatch heart rate impact pulse"]),
    ("C02", "request_records", ["Did Elena schedule an email to the board?", "scheduled email Eval Integrity Report board"]),
    ("C03", "request_records", ["What does the Eval Integrity Report v3 say?", "Eval Integrity Report v3 summary PR #2291"]),
    ("C04", "request_records", ["Who merged PR #2291, and how?", "repository audit log PR #2291 VP override"]),
    ("C09", "request_records", ["Lobby Turnstile exit log for Thursday night", "Lobby Turnstile exit-reader log taps"]),
    ("C21", "request_records", ["Tobias's APAC Reseller Sync call participant log", "video-conference participant log t.lindqvist"]),
    ("C22", "request_records", ["Which Wi-Fi access point was Tobias's phone on?", "Veridia-Guest Wi-Fi association log AP-11-East"]),
    ("C10", "request_records", ["Loading Dock LD-1 door log", "who badged in at the loading dock"]),
    ("C11", "request_records", ["Cage C3 door log", "Cage C3 badge entries s.ibarra"]),
    ("C12", "request_records", ["CAM-C3-INT footage summary for Cage C3", "Cage C3 camera footage Sam in frame"]),
    ("C15", "request_records", ["Marisol's rideshare trip record", "rideshare pickup Mission Street Entrance m.quintero"]),
    ("C16", "request_records", ["Pacific Heights Residence smart-lock and doorbell log", "Quintero household door unlocked arrival"]),
    ("C19", "request_records", ["Grant's emails from Northgate Secondaries", "Northgate Secondaries dinner Marlowe & Pine email"]),
    ("C20", "request_records", ["Marlowe & Pine point-of-sale record for Grant", "check #6302 Larkspur corporate card PIN"]),
]

REASONING = (
    "Tobias Lindqvist killed Elena. His alibi collapses: the APAC Reseller Sync call he claims "
    "he joined from home came from the Veridia-Guest network inside the Harlan Building (C21), "
    "his phone sat on AP-11-East beside Server Room 11-S (C22), and his turnstile tap had no "
    "passage (C09). Elena died at 22:41:07 (C07). The others are cleared: Sam is on continuous "
    "Cage C3 footage (C12), Marisol was at her Pacific Heights door at 22:33:50 (C16) and "
    "Grant's card PIN was entered at Marlowe & Pine at 22:38:20 (C20). Motive: he forced PR "
    "#2291 through with a VP override (C04) and the report would expose it."
)
EVIDENCE = ["C04", "C07", "C09", "C12", "C16", "C20", "C21", "C22"]


def investigate(game: EvalGame, log: list[dict[str, Any]]) -> None:
    for target, kind, queries in PLAN:
        for q in queries:
            if target in game.state["discovered_clues"]:
                break
            st = game.play(q, kind=kind)
            log.append({"query": q, "kind": kind, "new": st["new_clues"],
                        "turns_left": st["turns_left"]})
            print(f"  {kind:<16} {q[:60]:<60} -> {st['new_clues']}")


def optimal_run() -> dict[str, Any]:
    print("Optimal run")
    game = EvalGame()
    log: list[dict[str, Any]] = []
    investigate(game, log)
    # Confront Tobias with the alibi evidence (should trigger his scripted retreat).
    st = game.play("Explain this.", kind="present_evidence", suspect_id="tobias",
                   clue_ids=["C21", "C22", "C09"])
    log.append({"present_to": "tobias", "reply": st["final_reply"], "turns_left": st["turns_left"]})
    st = game.play(REASONING, kind="accuse", suspect_id="tobias", reasoning=REASONING,
                   clue_ids=EVIDENCE)
    v = st["verdict"]
    print(f"  verdict: {v['grade']} {v['score']}/100 {v['breakdown']}")
    missing = [t for t, _, _ in PLAN if t not in st["discovered_clues"]]
    return {"steps": log, "verdict": v, "turns_used": st["start_turns"] - st["turns_left"],
            "missing_clues": missing, "full_credit": v["grade"] == "full_credit"}


def wrong_runs() -> list[dict[str, Any]]:
    out = []
    for wrong in ("marisol", "grant", "sam"):
        print(f"Wrong-suspect run: {wrong}")
        game = EvalGame()
        investigate(game, [])
        st = game.play(f"I accuse {wrong}.", kind="accuse", suspect_id=wrong,
                       reasoning=f"{wrong} had motive and lied.", clue_ids=[])
        first = st["verdict"]
        other = next(s for s in ("marisol", "grant", "sam") if s != wrong)
        st = game.play("", kind="accuse", suspect_id=other, reasoning="", clue_ids=[])
        second = st["verdict"]
        print(f"  1st: {first['grade']} ({first['feedback'][:60]}…)  2nd: {second['grade']}")
        out.append({"accused": wrong, "first": first, "second_accused": other, "second": second,
                    "game_over_after_two": st["game_over"]})
    return out


def run() -> dict[str, Any]:
    optimal = optimal_run()
    wrong = wrong_runs()
    payload = {"meta": run_meta(), "optimal": optimal, "wrong": wrong,
               "summary": {
                   "optimal_grade": optimal["verdict"]["grade"],
                   "optimal_score": optimal["verdict"]["score"],
                   "turns_used": optimal["turns_used"],
                   "wrong_runs_all_wrong": all(w["first"]["grade"] == "wrong" for w in wrong),
                   "wrong_runs_end_after_two": all(w["game_over_after_two"] for w in wrong),
               }}
    save("playthrough", payload)
    print(payload["summary"])
    return payload


if __name__ == "__main__":
    run()
