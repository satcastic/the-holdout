# First available of 3.12 / 3.13 / 3.11 / python3; override with `make install PYTHON=...`
PYTHON ?= $(shell command -v python3.12 || command -v python3.13 || command -v python3.11 || command -v python3)
PY := .venv/bin/python
ARGS ?=

.PHONY: install ingest api web test lint eval graph validate

install:
	$(PYTHON) -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.txt
	cd web && npm install

ingest:
	$(PY) -m src.ingest $(ARGS)

api:
	$(PY) -m uvicorn src.api:app --reload --port 8000

web:
	cd web && npm run dev

validate:
	cd case && ../$(PY) validate.py

lint:
	$(PY) -m ruff check src tests eval

test: lint
	LLM_MODE=fake VECTOR_BACKEND=memory $(PY) -m pytest -q
	@if [ -d web/node_modules ]; then cd web && npm run --silent typecheck && echo "web typecheck ok"; fi

eval:
	$(PY) -m eval.retrieval_eval $(ARGS)
	$(PY) -m eval.leak_tests $(ARGS)
	$(PY) -m eval.leak_tests --simulate-leaky $(ARGS)
	$(PY) -m eval.playthrough $(ARGS)
	$(PY) -m eval.report

graph:
	LLM_MODE=fake VECTOR_BACKEND=memory $(PY) -m src.graph --mermaid docs/graph.md
