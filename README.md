# The Holdout

A detective game built on retrieval-augmented generation and an agentic LangGraph workflow,
for the course *RAG Systems and Agentic Workflows with Pinecone and LangGraph*.

Elena Voss, lead systems architect at a clinical-AI startup, is found dead in a latched server
room hours before she was due to blow the whistle. You question four suspects, show them
evidence, examine the scene, pull records and call the lab, then accuse someone and prove it.
Every answer is grounded in case facts retrieved from Pinecone, filtered to what that speaker
may know **right now**, and checked before you see it.

## Setup

Prerequisites: Python 3.11+ (3.12 used), Node 20+, a Pinecone API key and an Anthropic API key.

```bash
cp .env.example .env      # then fill in ANTHROPIC_API_KEY and PINECONE_API_KEY
make install              # Python venv + web dependencies
make ingest               # creates the serverless index if needed and upserts 30 fact chunks
```

Run it (two terminals), then open http://localhost:5173:

```bash
make api                  # FastAPI on :8000
make web                  # Vite dev server on :5173 (proxies /api)
```

**No keys?** Everything also runs offline with a deterministic fake LLM and an in-memory vector
store: `LLM_MODE=fake VECTOR_BACKEND=memory make api`. The fake model gives terse scripted
replies, but the whole game loop, gating, checker and scoring are real.

## Commands

| Command | What it does |
|---|---|
| `make ingest` | Upsert chunks (idempotent). `make ingest ARGS=--reset` wipes the namespace first. |
| `make api` / `make web` | Backend / frontend dev servers. |
| `make test` | ruff, the offline pytest suite (gating, isolation, checker, judge, API contract, end-to-end playthrough, `validate.py`) and the web typecheck. |
| `make eval` | Retrieval, leak and playthrough evals -> `eval/results/*.json` and `eval/REPORT.md`. Uses whatever `.env` configures; set `LLM_MODE=real` for real leak rates. Add `ARGS=--limit 5` for a cheap smoke run. |
| `make graph` | Regenerate the Mermaid diagram in `docs/graph.md`. |
| `make validate` | Run `case/validate.py` on the case files. |

Offline mechanism test of the checker: `python -m eval.leak_tests --simulate-leaky`.

## How it works

```
player ─► router ─► rewrite ─► retrieve ─► suspect | records ─► checker ─► clues ─► respond
            │                    │                               │  ▲
            └─► judge (accuse)   │                               └──┘ retry ×2, then deflect
                                 └─ Pinecone: known_by filter + gating post-filter in code
```

- **Who knows what.** Each chunk lists `known_by` (suspects or channels) and a
  `reveal_condition` (clues that must *all* be discovered). Pinecone filters on `known_by`;
  gating is enforced in Python because Pinecone filters can't express "array is a subset of".
- **Hidden truth.** Only `src/truth_store.py` reads `solution.json`, through three narrow
  providers. An AST test enforces who may import them.
- **The checker** runs before any text leaves the server: a deterministic gate guard (hidden
  times, IPs, ids, quotes), a statement guard (confessions, naming a killer, prompt dumps) and a
  fast-model review. Replies stream to the browser only after it passes.
- **Judging** is deterministic from the rubric; the LLM only extracts which clues your
  reasoning cites. Only clues you actually discovered count.

Details: [docs/DESIGN.md](docs/DESIGN.md) · graph: [docs/graph.md](docs/graph.md) ·
decisions: [docs/DECISIONS.md](docs/DECISIONS.md) · evaluation: [eval/REPORT.md](eval/REPORT.md)

## Stack

FastAPI + SSE, LangGraph 1.2 (checkpointer per session), `langchain-anthropic`
(`claude-sonnet-5-5` for suspects, records and accusations; `claude-haiku-5-5` for routing,
rewriting and checking), Pinecone serverless with integrated `llama-text-embed-v2` embeddings,
Vite + React 19 + TypeScript + Tailwind 4.

## Layout

```
case/       case_01.yaml (public facts), solution.json (hidden), validate.py
src/        config, models, llm (real + fake), embedder, ingest, retrieval, truth_store,
            state, graph, api; nodes/ router rewrite retrieve suspect records checker clues judge
web/        React frontend
eval/       leak_tests, retrieval_eval, playthrough, report; results/ and REPORT.md
tests/      offline pytest suite
docs/       PLAN, DECISIONS, DESIGN, graph
```
