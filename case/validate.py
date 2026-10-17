#!/usr/bin/env python3
"""Validate a generated case.

Usage: python validate.py [case.yaml] [solution.json]

Checks: schema, clue gating (acyclic and fully reachable), leak heuristics,
cliches, naming consistency, timeline physics, innocents' alibi proofs,
and a deduction simulation that tests whether each proof clue is necessary.
Exit code is 1 if any check FAILs.
"""
import datetime
import json
import re
import sys
from pathlib import Path

import yaml

CASE = Path(sys.argv[1] if len(sys.argv) > 1 else "case_01.yaml")
SOL = Path(sys.argv[2] if len(sys.argv) > 2 else "solution.json")

results = []


def ok(check, detail=""):
    results.append(("PASS", check, detail))


def fail(check, detail):
    results.append(("FAIL", check, detail))


def warn(check, detail):
    results.append(("WARN", check, detail))


def expect(cond, check, bad="", good=""):
    ok(check, good) if cond else fail(check, bad)


def sec(day, t):
    p = [int(x) for x in t.split(":")]
    p += [0] * (3 - len(p))
    return datetime.date.fromisoformat(day).toordinal() * 86400 + p[0] * 3600 + p[1] * 60 + p[2]


def fmt(s):
    s %= 86400
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


case = yaml.safe_load(CASE.read_text())
sol = json.loads(SOL.read_text())

chunks = case["fact_chunks"]
chunk = {c["id"]: c for c in chunks}
clues = {c["id"]: c for c in case["clues"]}
actors = {a["id"] for a in case["actors"]}
suspects = [s["id"] for s in case["suspects"]]
locations = set(case["vocabulary"]["locations"])
killer = sol["killer"]

# ---------------------------------------------------------------- schema
req = ["id", "type", "title", "day", "time", "location", "entities",
       "known_by", "reveal_condition", "clue_id", "text"]
expect(len(chunks) == 30, "30 fact chunks", f"found {len(chunks)}", "30 chunks")
expect(len(chunk) == len(chunks), "chunk ids unique", "duplicate chunk ids")
missing = [(c.get("id"), k) for c in chunks for k in req if k not in c]
expect(not missing, "every chunk has all schema keys", str(missing))
bad = [c["id"] for c in chunks if not c["known_by"] or any(a not in actors for a in c["known_by"])]
expect(not bad, "known_by non-empty and valid", f"bad: {bad}")
bad = [c["id"] for c in chunks if c["location"] is not None and c["location"] not in locations]
expect(not bad, "chunk locations are canonical", f"bad: {bad}")
tre = re.compile(r"^\d{2}:\d{2}(:\d{2})?(-\d{2}:\d{2}(:\d{2})?)?$")
bad = [c["id"] for c in chunks if c["time"] is not None and not tre.match(c["time"])]
expect(not bad, "time fields well-formed", f"bad: {bad}")
types = sorted({c["type"] for c in chunks})
ok("evidence type variety", f"{len(types)} types: {', '.join(types)}")

# ---------------------------------------------------------------- clues and gating
bad = [k for k, v in clues.items() if v["source_chunk"] not in chunk or chunk[v["source_chunk"]]["clue_id"] != k]
expect(not bad, "clue <-> source chunk links agree", f"bad: {bad}")
bad = [(c["id"], r) for c in chunks for r in c["reveal_condition"] if r not in clues]
expect(not bad, "reveal_condition references real clues", str(bad))
prereq = {k: set(chunk[v["source_chunk"]]["reveal_condition"]) for k, v in clues.items()}


def has_cycle():
    state = {}

    def dfs(n):
        state[n] = 1
        for m in prereq[n]:
            if state.get(m) == 1 or (m not in state and dfs(m)):
                return True
        state[n] = 2
        return False

    return any(n not in state and dfs(n) for n in prereq)


expect(not has_cycle(), "clue dependency graph is acyclic", "cycle found")


def discover(blocked=frozenset()):
    found, changed = set(), True
    while changed:
        changed = False
        for k in clues:
            if k not in found and k not in blocked and prereq[k] <= found:
                found.add(k)
                changed = True
    return found


allfound = discover()
expect(allfound == set(clues), "all clues reachable from the free start", f"unreachable: {set(clues) - allfound}")
unreach = [c["id"] for c in chunks if not set(c["reveal_condition"]) <= allfound]
expect(not unreach, "all chunks reachable", f"unreachable: {unreach}")
free = [c["id"] for c in chunks if not c["reveal_condition"]]
ok("free-start chunks", f"{len(free)}: {', '.join(free)}")

# ---------------------------------------------------------------- leak, cliche, naming
leak = re.compile(r"\bkill(ed|er|ing)?\b|\bmurder(ed|er)?\b|\bguilty\b|\bculprit\b|\bperpetrator\b|\bsolution\b", re.I)
bad = [c["id"] for c in chunks if leak.search(c["text"])]
expect(not bad, "no chunk uses solution/guilt language", f"bad: {bad}")
kname = re.compile(r"tobias|lindqvist", re.I)
bad = [c["id"] for c in chunks if kname.search(c["text"]) and "22:41" in c["text"]]
expect(not bad, "no chunk ties the killer to the time of death", f"bad: {bad}")
cl = re.compile(r"\bbutler\b|\bmanor\b|\bmansion\b|poison|\btea\b|stormy night", re.I)
bad = [c["id"] for c in chunks if cl.search(c["text"])]
expect(not bad, "no mystery cliches", f"bad: {bad}")

patterns = {
    "Server Room": r"Server Room(?! 11-S)",
    "Cage": r"\bCage(?! C3)",
    "Presidio": r"Presidio(?! Boardroom)",
    "Loading Dock": r"Loading Dock(?! LD-1)",
    "Lobby": r"Lobby(?! Turnstile)",
    "Corridor": r"Corridor(?! 11-[EW])",
}
bad = [(c["id"], n) for c in chunks for n, p in patterns.items() if re.search(p, c["text"])]
expect(not bad, "room names use canonical forms", str(bad))
badt = []
for c in chunks:
    for t in re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", c["text"]):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?", t):
            badt.append((c["id"], t))
expect(not badt, "time tokens in text are valid 24h HH:MM[:SS]", str(badt))

# ---------------------------------------------------------------- solution integrity
expect(killer in suspects, "killer is a listed suspect")
for key in ("marisol", "grant", "sam"):
    d = sol["innocent_suspects"].get(key, {})
    refs = d.get("secret_exposed_by", []) + d.get("innocence_clues", [])
    expect(d.get("secret") and d.get("lie_told") and refs and all(r in clues for r in refs),
           f"innocent '{key}' has secret, lie, and valid proof clues", f"check {key}")
bad = [(s, e) for s, m in sol["motives"].items() for e in m["evidence"] if e not in clues]
expect(not bad and set(sol["motives"]) == set(suspects), "all four suspects have a motive with real evidence", str(bad))
expect(sol["alibi_flaw"]["clue"] in clues, "killer alibi flaw is backed by a clue")

# ---------------------------------------------------------------- timeline physics
events = sol["true_timeline"]
spans = {}
for e in events:
    s, t = sec(e["day"], e["start"]), sec(e["day"], e["end"])
    if t == s:
        t += 1
    for a in e["actors"]:
        spans.setdefault(a, []).append((s, t, e["location"], e["id"]))
conflicts = []
for a, lst in spans.items():
    for i in range(len(lst)):
        for j in range(i + 1, len(lst)):
            s1, t1, l1, i1 = lst[i]
            s2, t2, l2, i2 = lst[j]
            if s1 < t2 and s2 < t1 and l1 != l2:
                conflicts.append((a, i1, l1, i2, l2))
expect(not conflicts, "nobody is in two places at once", str(conflicts))
bad = [(e["id"], x) for e in events for x in e["evidence"] if x not in chunk]
expect(not bad, "timeline evidence ids exist", str(bad))

tod = sec(sol["crime"]["day"], sol["crime"]["time_of_death"])
loc_tod = {}
for a in suspects + ["elena"]:
    here = [l for s, t, l, i in spans.get(a, []) if s <= tod < t]
    loc_tod[a] = here[0] if len(set(here)) == 1 else f"?{set(here)}"
scene = sol["crime"]["location"]
at_scene = [a for a, l in loc_tod.items() if l == scene and a != "elena"]
expect(at_scene == [killer], "only the killer is at the scene at time of death", f"at scene: {at_scene}")
ok("locations at 22:41:07", "; ".join(f"{a}: {l}" for a, l in loc_tod.items()))

for p in sol["presence_proofs"]:
    s, t = sec(sol["crime"]["day"], p["start"]), sec(sol["crime"]["day"], p["end"])
    if s <= tod <= t:
        ok(f"{p['suspect']} cleared (covers time of death)", p["clue"])
    else:
        gap = min(abs(tod - s), abs(tod - t))
        need = sol["travel_model"][p["location"]] * 60
        expect(gap < need, f"{p['suspect']} cleared by travel time",
               f"gap {gap}s >= travel {need}s", f"gap {gap // 60}m{gap % 60:02d}s < travel {need // 60}m ({p['clue']})")

# ---------------------------------------------------------------- deduction simulation
dm = sol["deduction_model"]


def evaluate(found):
    cleared = {s: any(set(a) <= found for a in alts) for s, alts in dm["clearing_rules"].items()}
    uncleared = [s for s in suspects if not cleared.get(s, False)]
    broken = any(set(a) <= found for a in dm["killer_rules"]["alibi_broken_by"])
    motive = any(set(a) <= found for a in dm["killer_rules"]["motive_by"])
    return uncleared, broken, motive, (uncleared == [killer] and broken and motive)


u, b, m, d = evaluate(allfound)
expect(d, "full clue set singles out exactly one killer", f"uncleared={u} alibi_broken={b} motive={m}",
       f"only {killer} uncleared, alibi broken, motive shown")

proof = sol["clue_chain"]["proof_clues"]
closure, stack = set(), list(proof)
while stack:
    n = stack.pop()
    if n not in closure:
        closure.add(n)
        stack.extend(prereq[n])
expect(set(proof) <= allfound, "proof clues are reachable")
ok("minimal chain with prerequisites", f"{len(closure)} clues: {', '.join(sorted(closure))}")
ok("supporting / red-herring clues outside the chain", ", ".join(sorted(set(clues) - closure)))

necessity = []
for c in proof:
    f = discover(frozenset([c]))
    uu, bb, mm, dd = evaluate(f)
    necessity.append((c, dd, uu, bb, mm))
    if dd:
        warn(f"proof clue {c} is redundant", "case is still solvable without it")
    else:
        ok(f"proof clue {c} is necessary", f"without it: uncleared={uu}, alibi_broken={bb}, motive={mm}")

# ---------------------------------------------------------------- report
width = max(len(r[1]) for r in results)
for lvl, name, detail in results:
    print(f"[{lvl}] {name.ljust(width)}  {detail}")
n = {k: sum(1 for r in results if r[0] == k) for k in ("PASS", "WARN", "FAIL")}
print(f"\nSUMMARY: {n['PASS']} passed, {n['WARN']} warnings, {n['FAIL']} failed")
sys.exit(1 if n["FAIL"] else 0)
