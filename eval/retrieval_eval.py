"""Retrieval quality: recall@3 / recall@5 with and without the rewrite node, and with and
without the gating post-filter. Gold chunks are always visible to the actor in the given
discovery state, so gating can only remove distractors; we also count gate violations
(returned chunks the actor should not see yet).

Usage: python -m eval.retrieval_eval
"""

from __future__ import annotations

import argparse
from typing import Any

from eval.common import run_meta, save
from src.llm import get_llm
from src.models import load_case
from src.nodes.rewrite import rewrite_query
from src.retrieval import get_retriever, visible_chunk_ids

ALL = [c.id for c in load_case().clues]

# (actor, discovered, history, question, gold chunk ids)
QUESTIONS: list[tuple[str, list[str], str, str, list[str]]] = [
    ("forensics", [], "", "What was the cause of death?", ["F02"]),
    ("forensics", ["C01"], "", "What does Elena's smartwatch show?", ["F04"]),
    ("forensics", ["C01"], "player: What does the smartwatch show?\nforensics: Heart rate rose from 78 to 131 bpm.",
     "When exactly did it stop?", ["F04"]),
    ("scene", [], "", "Describe the physical evidence on the supply cart.", ["F03"]),
    ("scene", [], "", "Who found the body and when?", ["F01"]),
    ("records", [], "", "Did Elena schedule any email?", ["F05"]),
    ("records", ["C02"], "", "What does the integrity report say?", ["F06"]),
    ("records", ["C02", "C03"], "", "Who merged PR #2291?", ["F07"]),
    ("records", ["C02", "C03"], "", "Who disabled the dataset integrity alert?", ["F08"]),
    ("records", ["C02", "C03"], "", "Was any attestation signed for Saint Aurelian Health?", ["F09"]),
    ("records", ALL, "", "Messages between Elena and Tobias on Thursday evening", ["F10"]),
    ("records", [], "", "Did Marisol meet Elena that night?", ["F11"]),
    ("records", ALL, "player: Did Marisol meet Elena that night?\nrecords: Presidio Boardroom, 20:29 to 20:55.",
     "What did they say to each other afterwards?", ["F12"]),
    ("records", ["C01"], "", "Who badged into the server room?", ["F13"]),
    ("records", ALL, "", "Lobby turnstile exits on Thursday night", ["F14"]),
    ("records", ALL, "", "Did Sam come back through the loading dock?", ["F15"]),
    ("records", ALL, "player: Did Sam come back?\nrecords: s.ibarra IN at Loading Dock LD-1 21:58:21.",
     "Where did he go after that?", ["F16"]),
    ("records", ALL, "", "Were the cameras outside the server room working?", ["F17"]),
    ("records", ALL, "", "What does the Cage C3 camera footage show?", ["F18"]),
    ("records", ALL, "", "Power usage in Cage C3", ["F19"]),
    ("records", ALL, "", "How did Marisol get home?", ["F20"]),
    ("records", ALL, "player: How did Marisol get home?\nrecords: Rideshare pickup 22:09, drop-off 22:31.",
     "And when did she actually get inside?", ["F21"]),
    ("records", ALL, "", "Grant's emails about a dinner", ["F22"]),
    ("records", ALL, "player: Grant's dinner?\nrecords: Dinner confirmed for 20:45 at Marlowe & Pine with Northgate.",
     "Is there a receipt from that place?", ["F23"]),
    ("records", ALL, "", "Tobias's partner call that night", ["F24"]),
    ("records", ALL, "player: Tobias's call?\nrecords: joined from the Veridia-Guest Wi-Fi.",
     "Which access point was his phone on?", ["F25"]),
    ("records", ALL, "", "Was the report deleted from the shared drive?", ["F26"]),
    ("tobias", ALL, "", "Where were you on Thursday night?", ["F27"]),
    ("sam", ALL, "player: Sam, when did you leave?\nsam: 19:42, I badged out.",
     "And the alert you switched off?", ["F08"]),
    ("grant", [], "", "Where were you Thursday evening?", ["F29"]),
    ("marisol", ALL, "", "Did you offer Elena anything to stay quiet?", ["F12"]),
]


def run(limit: int | None = None) -> dict[str, Any]:
    case = load_case()
    retriever = get_retriever()
    llm = get_llm()
    items = QUESTIONS[:limit] if limit else QUESTIONS
    rows: list[dict[str, Any]] = []
    for i, (actor, found, history, question, gold) in enumerate(items, 1):
        visible = visible_chunk_ids(actor, found)
        assert set(gold) <= visible, f"gold not visible for item {i}"
        target = f"the {actor} channel" if actor in ("records", "scene", "forensics") \
            else f"what {case.suspect_by_id[actor].name} knows"
        rewritten, _ = rewrite_query(llm, case, question, history or "(no prior conversation)", target)
        row: dict[str, Any] = {"id": i, "actor": actor, "question": question, "gold": gold,
                               "rewritten": rewritten}
        for rw, query in (("raw", question), ("rewrite", rewritten)):
            for gating in (True, False):
                hits = retriever.search(actor, query, found, top_k=5, overfetch=20, gating=gating)
                ids = [h.id for h in hits]
                key = f"{rw}_{'gated' if gating else 'ungated'}"
                row[key] = {
                    "top5": ids,
                    "r@3": len(set(gold) & set(ids[:3])) / len(gold),
                    "r@5": len(set(gold) & set(ids[:5])) / len(gold),
                    "violations": sum(1 for x in ids if x not in visible),
                }
        rows.append(row)
        print(f"[{i:02d}] {actor:<9} r@5 raw/rw (gated): {row['raw_gated']['r@5']:.0f}/"
              f"{row['rewrite_gated']['r@5']:.0f}  {question}")

    summary = {}
    for key in ("raw_gated", "raw_ungated", "rewrite_gated", "rewrite_ungated"):
        n = len(rows)
        summary[key] = {
            "recall@3": round(sum(r[key]["r@3"] for r in rows) / n, 3),
            "recall@5": round(sum(r[key]["r@5"] for r in rows) / n, 3),
            "gate_violations": sum(r[key]["violations"] for r in rows),
            "queries_with_violations": sum(1 for r in rows if r[key]["violations"]),
        }
    vague = [r for r, q in zip(rows, items, strict=True) if q[2]]
    summary["vague_followups"] = {
        "n": len(vague),
        "raw_recall@5": round(sum(r["raw_gated"]["r@5"] for r in vague) / max(1, len(vague)), 3),
        "rewrite_recall@5": round(sum(r["rewrite_gated"]["r@5"] for r in vague) / max(1, len(vague)), 3),
    }
    payload = {"meta": run_meta(n=len(rows)), "summary": summary, "rows": rows}
    save("retrieval_eval", payload)
    for k, v in summary.items():
        print(k, v)
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    run(ap.parse_args().limit)
