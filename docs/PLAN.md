# Plan

## Understanding of the inputs

**Case** (`case/case_01.yaml`, public). Elena Voss, Lead Systems Architect at Veridia AI,
is found dead in Server Room 11-S on the morning of 2026-11-13. Four suspects: Tobias
(VP Eng), Marisol (CEO), Grant (board director) and Sam (security head). 30 fact chunks
(F01-F30), 24 clues (C01-C24). Each chunk declares who can retrieve it (`known_by`) and
which clues must already be discovered before it is retrievable (`reveal_condition`, all
required). Free-start chunks: F01, F02, F03, F05, F11, F27-F30.

**Clue dependency graph** (from `reveal_condition`):

```
C01 (F02 forensics) -> C07 (F04 watch), C08 (F13 door log)
C02 (F05 email)     -> C03 (F06 report) -> C04 (F07), C05 (F08), C06 (F09), C19 (F22)
C04 -> C24 (F10)          C17 (F11) -> C18 (F12)
C07 -> C09 (F14 turnstile), C10 (F15 loading dock)
C10 -> C11 (F16 cage door) -> C13 (F19 PDU);  C07 + C11 -> C12 (F18 cage footage)
C08 -> C14 (F17 camera)   C09 -> C15 (F20 rideshare) -> C16 (F21 smart lock)
C09 -> C21 (F24 call log) -> C22 (F25 wifi)
C19 + C07 -> C20 (F23 restaurant)     C03 + C07 -> C23 (F26 drive audit)
```

**Hidden truth** (`case/solution.json`). The killer, the true timeline, per-suspect private
briefs, a deduction model (clearing rules, alibi and motive rules) and an accusation rubric.
The minimal proof chain is 14 clues; the proof clues are C04, C07, C12, C16, C20, C21.

**How clues are discovered.** Only chunks surfaced by the records, scene and forensics
channels unlock clues. What a suspect says never unlocks a clue (prevents laundering hidden
facts through an LLM). Presenting a discovered clue to a suspect can make them admit their
secret (`admits_if_confronted_with`).

## Assumptions
- One case (case_01) and one namespace; the code is case-agnostic where cheap.
- "Surfaced" means the top-5 survivors that the records/scene/forensics node returned and
  that passed the checker. All of them unlock their clue.
- Investigative actions (question, present, examine, records, forensics) each cost one turn.
  Accusations and invalid input are free. Starting budget: 30 turns (configurable).
- With no turns left the only allowed action is `accuse`.
- Without API keys the whole system runs offline (`LLM_MODE=fake`, `VECTOR_BACKEND=memory`).
  Real-mode results (Pinecone ingest, leak eval with the real model) need keys.

## Phases
| # | Phase | Exit criteria |
|---|-------|---------------|
| 0 | Read inputs, write PLAN and DECISIONS | docs written |
| 1 | Scaffold, config, models, FakeLLM, Makefile | `make test` green, validate.py as a test |
| 2 | Embedder, ingest, retrieval with gating post-filter | record-shape, filter, gating (100%) tests |
| 3 | truth_store + AST isolation test | isolation test green |
| 4 | Graph core: router, rewrite, retrieve, suspect, records, clues | unlock, turn and router-bypass tests |
| 5 | Checker (gate guard + LLM) and retry loop | leaky-LLM test proves the checker blocks |
| 6 | Judge with deterministic scoring | rubric tests, wrong-accusation game over |
| 7 | FastAPI + SSE | API contract tests, hidden-field scan |
| 8 | Frontend | `npm run build` and typecheck clean |
| 9 | Evaluation + REPORT.md | leak/retrieval/playthrough results saved |
| 10 | README, DESIGN, graph diagram | docs complete |

Each phase's plan lives in the table above; the technical details are in `DESIGN.md`.
