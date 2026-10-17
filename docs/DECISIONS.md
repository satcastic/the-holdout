# Decisions log

| # | Decision | Why |
|---|----------|-----|
| D1 | Python 3.12 venv (`.venv`), not uv | uv is not installed on the dev machine; brief allows venv. 3.12 rather than 3.14 for wheel availability. |
| D2 | Main model `claude-sonnet-5-5`, fast model `claude-haiku-5-5` | Current Sonnet- and Haiku-class models. |
| D3 | Structured output via `with_structured_output(method="json_schema")` | Sonnet 5.5 rejects forced `tool_choice`; Anthropic structured outputs avoids it. |
| D4 | No `temperature` set on Claude models | Sonnet 5.5 / Haiku 5.5 reject non-default sampling params. Fast model uses `reasoning_effort="low"`, main model `"low"` for replies. |
| D5 | Pinecone integrated index `llama-text-embed-v2`, field map `text -> chunk_text`, cosine, aws/us-east-1 | Hosted embeddings, no local model. Wrapped behind `Embedder`/`VectorStore` so it can be swapped. |
| D6 | Offline `MemoryStore` + `HashingEmbedder` | All tests and offline evals run without network. Same post-filter code path as Pinecone. |
| D7 | `validate.py` is run with cwd=`case/` | Its default paths are cwd-relative; the provided file is left untouched. |
| D8 | Phase plans live in the `docs/PLAN.md` phase table | One place to track scope and exit criteria for every phase. |
| D9 | Investigative actions cost 1 turn; accuse and invalid cost 0; 30 starting turns | Optimal play needs about 12 turns; the rest is budget for interrogation. |
| D10 | All top-5 survivors from records/scene/forensics unlock their clues, only after the checker passes | "Surfaced" = shown to the player. A failed draft shows nothing, so it unlocks nothing. |
| D11 | The metadata filter is built in code from the action's actor; the rewriter only produces the query text (plus focus entities appended to it) | An LLM must never be able to widen access. |
| D12 | `admits_if_confronted_with` and `breaks_when` use only clues presented **in the current turn** | Literal reading of the brief. The suspect's own history keeps admissions consistent later. |
| D13 | `breaks_when` is parsed generically from the brief text (first clue id = required, the rest = pool, number word = k) | Keeps solution knowledge out of code. |
| D14 | Rubric clue sets are derived from `deduction_model` plus clue ids in `accusation_rubric` text | Data-driven: alibi = `alibi_broken_by`; eliminations = `clearing_rules`; motive = remaining ids in `full_credit` plus `motive_by`; partial alibi = non-primary ids in the second partial-credit line (C09 + C22). |
| D15 | Scoring: suspect 40; alibi 20 (C21) or 10 (C09+C22); eliminations 10 each, max 20; motive 10; turns `round(10*left/start)` only if the suspect is right. Wrong suspect scores 0. | Brief's weights; full credit needs 2 of 3 eliminations, so 2 earn the full 20. |
| D16 | Clues ticked in the accuse modal and clue ids extracted from the reasoning are unioned, then intersected with `discovered_clues` | "Only clues the player has actually discovered count." |
| D17 | Gate guard visible set = actor-visible chunks + chunks of clues presented this turn + public preamble + persona + the player's message | The player already holds presented clues; only facts the actor could not see are leaks. |
| D18 | Deterministic confession/solution-statement regex runs alongside the gate guard | Cheap backstop that needs no solution access. |
| D19 | Sync LangGraph nodes, `astream(stream_mode="updates")` in the API | Status events per node; final text streamed only after the graph finishes (checker passed). |
| D20 | Checkpointer: `InMemorySaver` default, `CHECKPOINTER=sqlite` opt-in | Brief's default. |
| D21 | Retrieval cache per session keyed by (actor, query, discovered set) | Brief's cost-control requirement; the key includes the discovered set so gating stays exact. |
| D22 | Eval may call `truth_store.get_reveal()` for solution-naming detection | Rule 1 is about reading the file; eval goes through the truth store and lives outside `src/`. |
| D23 | Fonts bundled via `@fontsource` (Cormorant Garamond display, Source Sans 3 body, IBM Plex Mono evidence) | No third-party requests at runtime. |
