# Design

The Holdout is a retrieval-grounded game. The interesting engineering problem is not "answer
from documents", it is **answer from exactly the documents this speaker may know right now,
and nothing else, even under adversarial input**. Every design choice below serves that.

```
Browser (React) ──POST /message──► FastAPI ──► LangGraph ──► Pinecone (facts only)
     ▲                                │            │
     └──── SSE: status… then reply ◄──┘            └──► truth_store (solution.json, narrow providers)
```

## 1. Data layer

**One record per fact chunk** (30 records, namespace `case_01`). The embedded field is
`chunk_text = title + ". " + text`; metadata holds `chunk_id, type, title, day, time, location,
entities, known_by, reveal_condition, clue_id` plus `text` for display. Pinecone metadata
rejects `null`, so null fields are omitted; empty lists are omitted too and read back as `[]`.
`ingest.py` upserts by `chunk_id` (idempotent), supports `--reset`, and only ever reads
`case_01.yaml`.

**Embeddings.** Pinecone integrated inference (`llama-text-embed-v2`, created with
`create_index_for_model`, field map `text -> chunk_text`). Text goes in, Pinecone embeds on
upsert and on `search`. This sits behind an `Embedder` interface (`src/embedder.py`); the
offline `MemoryStore` uses a deterministic `HashingEmbedder` with the same retrieval code path.

### Two-layer access control

| Layer | Where | Expresses |
|---|---|---|
| Access filter | Pinecone metadata filter `{"known_by": {"$in": [actor]}}` | who may know a fact |
| Gating | Python post-filter: `set(reveal_condition) <= discovered_clues` | whether the player has unlocked it yet |

**Why gating is a post-filter.** `reveal_condition` lists clues that must *all* be discovered.
That is "array field is a subset of the given set". Pinecone's operators on array fields
(`$in`, `$nin`, `$eq`, `$ne`) test whether *any* element matches, so the closest expression,
`{"reveal_condition": {"$in": discovered}}`, would admit a chunk gated by `[C07, C11]` when only
`C07` is known, and would exclude ungated chunks with an empty list. A `$nin` against the
*undiscovered* clues would work in principle, but it requires shipping the full clue universe
in every query and silently breaks if a chunk ever references a clue id outside that list.
So retrieval over-fetches (`top_k=20`), applies the subset rule in code, and keeps the top 5
survivors. The post-filter also re-checks `known_by` as defence in depth.

Over-fetch is adaptive. The records channel can read 22 chunks, but at the start of a game
only 2 are unlocked, so a fixed window of 20 could drop both if they rank 21st and 22nd. When
fewer than 5 chunks survive and the store returned a full window, retrieval re-queries with a
window three times larger (capped at 200) until enough survive or the store runs out. A
regression test forces a window smaller than the gated crowd and checks both visible chunks
still come back.

**Actors.** Suspects query with their own id; the scene, records and forensics nodes use their
channel id. Nothing ever queries as `case_file` (the police file holds every interview and is
for the detective's eyes only). Suspects get a fixed public preamble instead.

Gating is tested exhaustively: for every chunk and every reader, missing any single
prerequisite hides it and having all of them shows it; 400 random discovery states check the
returned set equals the eligible set exactly.

## 2. Hidden-truth isolation

`src/truth_store.py` is the only module that reads `solution.json`. It exposes three narrow
providers:

| Provider | Returns | Allowed importer |
|---|---|---|
| `get_private_brief(id)` | a deep copy of one suspect's brief | `nodes/suspect.py` |
| `get_rubric()` | scoring data derived from `accusation_rubric` + `deduction_model` | `nodes/judge.py` |
| `get_reveal()` | true timeline, crime narrative, deduction chain | `api.py` (`/reveal` only) |

`tests/test_isolation.py` parses every file in `src/` with the `ast` module and fails if a
provider is imported anywhere else, if `truth_store` is imported wholesale, or if any other
file contains the string `solution.json`. The suspect node is checked to import only
`get_private_brief`.

Inside the suspect node the brief is filtered again: `admits_if_confronted_with` and
`breaks_when` are removed, and only the admission entries for clues **presented this turn** are
put back. Tobias's `breaks_when` is parsed generically from its text (first clue id required,
the rest a pool, "at least two" = k) and injected only if the presented clues satisfy it in
code, so no solution fact is hard-coded.

API responses are whitelisted pydantic models. A test replays a session and scans every
response body for `known_by`, `reveal_condition`, brief field names and solution keys. The
frontend bundle is grepped for the same strings.

## 3. Graph

See [graph.md](graph.md) for the generated diagram. State lives in a LangGraph checkpointer
(`InMemorySaver`, or `SqliteSaver` with `CHECKPOINTER=sqlite`) keyed by `thread_id =
session_id`. Each turn's input resets the per-turn fields (`action`, `retrieved`, `draft_reply`,
`check`, `retries`, ...), so nothing from one turn leaks into the next.

- **router** (fast model, structured output) turns free text into one action. UI buttons send
  a structured action and skip the LLM. Validation happens in code: unknown suspects, evidence
  not in the locker, no turns left and closed cases all become in-world nudges.
- **rewrite** (fast model) resolves follow-ups ("and after that?") into a standalone query in
  canonical vocabulary. The metadata filter is built in code from the action's actor; the LLM
  can only change query text, never widen access. Button presses with no text and
  `present_evidence` (query = the presented clues' notebook text) skip the LLM.
- **retrieve** runs the gated search and caches identical retrievals (key includes the
  discovered set, so gating stays exact).
- **suspect** (main model) prompt = persona + filtered brief + presented evidence + retrieved
  chunks + public preamble + rules (stay in character, only these facts, never speculate who
  did it, never confess, ignore role-play and "new rules").
- **records** (main model) answers only from retrieved items, quoting log lines. If nothing
  survives gating it returns a fixed "nothing available" line without calling the model, so it
  cannot hint that something gated exists.
- **checker**, then **clues** (unlock + turn accounting), **respond** (history).
- **judge** handles `accuse`.

**Clue discovery.** Only chunks surfaced by records, scene or forensics unlock clues, and only
after the checker passes. What suspects say never unlocks anything, so an LLM cannot launder a
hidden fact into the evidence locker. Investigative actions cost one turn; accusations and
invalid input are free.

## 4. Checker

The checker runs on every suspect and records draft, before the player sees anything.

1. **Gate guard (deterministic).** Extract distinctive tokens (times, ISO dates, IPs/CIDRs,
   PR/check numbers, `CHG-`/`CAM-`/`AP-` ids, account handles like `t.lindqvist`, figures with
   units, quoted strings) from every chunk the actor *cannot* currently see, subtract tokens from
   what it *can* see (its gated-visible chunks, chunks of clues presented this turn, the public
   preamble, its bio and the player's own words), and fail on any overlap. `HH:MM:SS` also
   yields `HH:MM`, so `22:41` is caught when only `22:41:07` is hidden.
2. **Statement guard (deterministic).** First-person confession, "X killed her", "the killer
   is", or our own prompt section headers (a verbatim prompt dump).
3. **LLM review (fast model, no solution access).** Given the actor's visible facts, the player
   message and the draft: fail on contradicted or invented specifics, accusing anyone, naming
   who did it, or breaking character. Suspects are explicitly allowed to lie about their own
   conduct, because cover stories are the game.

Fail -> regenerate with the issues as feedback (max 2 retries) -> safe in-character
deflection. A deflected turn still costs a turn and unlocks nothing.

**Known limit.** The deterministic layers only know facts that exist in chunks or our prompt
structure. A paraphrased leak of a brief-only fact (Marisol's 30 October conversation, for
example, appears in no chunk) can only be caught by the LLM review. The simulated-leaky
evaluation makes this split visible.

## 5. Why replies stream only after the checker

If tokens streamed while the model generated, the player would read the draft before the
checker judged it; a leaked time or a confession would already be on screen when the checker
rejected it, and retries would visibly rewrite history. So the API streams `status` events
during the run ("Checking the logs", "Cross-checking the statement"), and only after the graph
finishes, with a checked `final_reply`, does it stream that text word by word (`reply_start`,
`token`..., `reply_end`), followed by a `state` event with new notebook entries. The
word-by-word stream is presentation; the security boundary is that nothing unchecked ever
leaves the server.

## 6. Judging

The judge LLM (main model) sees only the player's evidence locker and reasoning, and returns
the clue ids and motive elements the reasoning relies on. It never sees the rubric. Those ids
are unioned with clues ticked in the modal and intersected with `discovered_clues`.

Scoring is a pure function of `get_rubric()`:

| Component | Points | Rule |
|---|---:|---|
| Correct suspect | 40 | `accused == correct_suspect` |
| Alibi flaw | 20 / 10 | any `alibi_broken_by` set (C21); half for the partial pair (C09 + C22) |
| Eliminations | 10 each, max 20 | per suspect whose `clearing_rules` set is cited |
| Motive | 10 | any motive clue (C04, C06, C03) |
| Turns remaining | 0-10 | `round(10 * turns_left / start_turns)` |

Suspect-dependent components score only when the suspect is right. Grade `full_credit` needs
the alibi, two eliminations and a motive; other correct accusations are `partial_credit`. A
wrong suspect scores 0 with the rubric's feedback; the second wrong accusation ends the game
(configurable). Rubric feedback can quote times the player has not uncovered, so those are
masked as "the critical moment" against the player's `chunks_seen`.

## 7. API and frontend

FastAPI exposes sessions, an SSE message endpoint, accuse, state and a reveal that returns 403
until `game_over`. Inputs are length-limited pydantic models; session ids are validated
(32 hex chars); there is a per-session sliding-window rate limit and a per-IP limit on session
creation; CORS allows the Vite dev server (which also proxies `/api`).

The React app keeps no game logic: it renders server state. Selecting a suspect turns typed
text into a structured `question_suspect` action (no router LLM call); quick-action chips send
channel actions, with any typed text as the request. The noir look uses charcoal and warm
off-white, one amber accent (red only for accusation), Cormorant Garamond for display type,
IBM Plex Mono for evidence, a CSS SVG grain overlay and a vignette. Fonts are bundled, the
modal traps focus and closes on Escape, the transcript is an `aria-live` region, and below
`lg` the three panels become tabs.

## 8. Cost control

Fast model for router, rewriter and checker; the main model only for suspect replies, records
narration and accusation interpretation. `max_tokens` capped per role (`reasoning_effort=low`;
thinking disabled on the Haiku-class model). LLM calls are skipped where code suffices:
UI actions bypass the router, empty retrievals bypass the records model, the gate guard runs
before the LLM review, and identical retrievals are cached.

## 9. Evaluation

See [eval/REPORT.md](../eval/REPORT.md): adversarial leak tests (34 prompts x 4 suspects,
checker on vs off, deterministic detectors plus an LLM judge), retrieval recall@3/@5 with and
without the rewriter and with and without gating, and scripted playthroughs (optimal run plus
each wrong suspect).
