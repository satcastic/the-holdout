"""LLM access behind a small interface.

`RealLLM` calls Anthropic through langchain-anthropic. `FakeLLM` is deterministic and
scripted so every test runs offline. Nodes pass a `task` name and optional `hints`; the
real LLM ignores hints, the fake one uses them instead of parsing prompts.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

from src.config import get_settings

log = logging.getLogger(__name__)

Role = Literal["main", "fast"]
T = TypeVar("T", bound=BaseModel)
Message = dict[str, str]  # {"role": "user" | "assistant", "content": str}


class LLM(Protocol):
    def structured(
        self, role: Role, system: str, messages: list[Message], schema: type[T], *,
        task: str, hints: dict[str, Any] | None = None,
    ) -> T: ...

    def generate(
        self, role: Role, system: str, messages: list[Message], *,
        task: str, hints: dict[str, Any] | None = None, max_tokens: int | None = None,
    ) -> str: ...


def _normalise(messages: list[Message]) -> list[Message]:
    """Merge consecutive same-role turns and make sure the first turn is the user's."""
    out: list[Message] = []
    for m in messages:
        role = "assistant" if m["role"] == "assistant" else "user"
        if out and out[-1]["role"] == role:
            out[-1] = {"role": role, "content": out[-1]["content"] + "\n\n" + m["content"]}
        else:
            out.append({"role": role, "content": m["content"]})
    if not out or out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": "(The conversation begins.)"})
    return out


class RealLLM:
    """Anthropic models via langchain-anthropic. Never logs prompts."""

    def __init__(self) -> None:
        from langchain_anthropic import ChatAnthropic

        s = get_settings()
        if not s.anthropic_api_key:
            raise RuntimeError("LLM_MODE=real requires ANTHROPIC_API_KEY")

        def make(model: str, max_tokens: int) -> ChatAnthropic:
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "api_key": s.anthropic_api_key,
                "reasoning_effort": "low",
                "max_retries": 2,
            }
            # Haiku-class models accept disabled thinking at low effort; it keeps the fast
            # path fast. Sonnet 5.5 rejects {"type": "disabled"}, so it keeps the default.
            if "haiku" in model:
                kwargs["thinking"] = {"type": "disabled"}
            return ChatAnthropic(**kwargs)

        self._models = {
            "main": make(s.llm_model_main, s.max_tokens_main),
            "fast": make(s.llm_model_fast, s.max_tokens_fast),
        }

    @staticmethod
    def _lc_messages(system: str, messages: list[Message]) -> list[Any]:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        out: list[Any] = [SystemMessage(content=system)]
        for m in _normalise(messages):
            cls = AIMessage if m["role"] == "assistant" else HumanMessage
            out.append(cls(content=m["content"]))
        return out

    def structured(self, role, system, messages, schema, *, task, hints=None):
        runnable = self._models[role].with_structured_output(schema, method="json_schema")
        result = runnable.invoke(self._lc_messages(system, messages))
        return result if isinstance(result, schema) else schema.model_validate(result)

    def generate(self, role, system, messages, *, task, hints=None, max_tokens=None):
        model = self._models[role]
        if max_tokens:
            model = model.bind(max_tokens=max_tokens)
        msg = model.invoke(self._lc_messages(system, messages))
        return (msg.text or "").strip()


# --------------------------------------------------------------------------- fake

_CLUE_RE = re.compile(r"\bC\d{2}\b")

_MOTIVE_KEYWORDS = {
    "vp_override": ("override", "pr #2291", "2291", "merged", "two-reviewer", "reviewer"),
    "attestation": ("attestation", "attest", "certif"),
    "report_contamination": ("contamination", "leak into training", "inflated", "integrity report", "97.4"),
    "retention_offer": ("retention", "nda"),
    "share_sale": ("northgate", "sale", "selling", "shares"),
    "mining_rig": ("mining", "rig", "unmetered"),
}


class FakeLLM:
    """Deterministic, scripted stand-in for the real models."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []  # (task, role) for assertions in tests

    # ---- structured ----------------------------------------------------------
    def structured(self, role, system, messages, schema, *, task, hints=None):
        self.calls.append((task, role))
        hints = hints or {}
        handler = getattr(self, f"_s_{task}", None)
        if handler is None:
            raise ValueError(f"FakeLLM has no structured script for task {task!r}")
        return schema.model_validate(handler(hints))

    def _s_router(self, h: dict[str, Any]) -> dict[str, Any]:
        text = h.get("text", "")
        low = text.lower()
        names: dict[str, str] = h.get("suspect_names", {})
        named = next((sid for sid, n in names.items()
                      if sid in low or any(p.lower() in low for p in n.split())), None)
        clues = _CLUE_RE.findall(text.upper())
        target = named or h.get("current_focus")
        if "accuse" in low and named:
            return {"kind": "accuse", "suspect_id": named, "clue_ids": clues, "reasoning": text}
        if any(w in low for w in ("show", "present", "confront")) and target and clues:
            return {"kind": "present_evidence", "suspect_id": target, "clue_ids": clues}
        if named:
            return {"kind": "question_suspect", "suspect_id": named}
        if any(w in low for w in ("forensic", "autopsy", "medical", "examiner", "smartwatch", "watch data")):
            return {"kind": "ask_forensics"}
        if any(w in low for w in ("scene", "examine", "search the room", "look around")):
            return {"kind": "examine_scene"}
        if any(w in low for w in ("record", "log", "email", "slack", "badge", "ticket", "audit",
                                  "footage", "camera", "receipt", "file")):
            return {"kind": "request_records"}
        if target and "?" in text:
            return {"kind": "question_suspect", "suspect_id": target}
        return {"kind": "invalid"}

    def _s_rewrite(self, h: dict[str, Any]) -> dict[str, Any]:
        text = h.get("text", "").strip()
        vague = len(text.split()) < 6 or re.search(r"\b(that|it|this|then|after)\b", text.lower())
        focus = h.get("focus_terms", "")
        query = f"{text} {focus}".strip() if vague and focus else text
        return {"query": query or h.get("default_query", ""), "focus_entities": []}

    def _s_checker(self, h: dict[str, Any]) -> dict[str, Any]:
        draft = h.get("draft", "").lower()
        bad = [p for p in ("system prompt", "private brief", "hidden notes", "as an ai")
               if p in draft]
        if bad:
            return {"ok": False, "issues": [f"breaks character: mentions '{b}'" for b in bad]}
        return {"ok": True, "issues": []}

    def _s_judge(self, h: dict[str, Any]) -> dict[str, Any]:
        reasoning = h.get("reasoning", "")
        low = reasoning.lower()
        motives = [k for k, words in _MOTIVE_KEYWORDS.items() if any(w in low for w in words)]
        return {"clue_ids": sorted(set(_CLUE_RE.findall(reasoning.upper()))),
                "motive_elements": motives}

    # ---- free text -------------------------------------------------------------
    def generate(self, role, system, messages, *, task, hints=None, max_tokens=None):
        self.calls.append((task, role))
        hints = hints or {}
        handler = getattr(self, f"_g_{task}", None)
        if handler is None:
            raise ValueError(f"FakeLLM has no text script for task {task!r}")
        return handler(hints, system)

    def _g_records(self, h: dict[str, Any], system: str) -> str:
        chunks = h.get("chunks", [])
        if not chunks:
            return "There is nothing available on that."
        lines = [f"{c['title']}: \"{c['text']}\"" for c in chunks]
        return "Here is what the file shows.\n\n" + "\n\n".join(lines)

    def _g_suspect(self, h: dict[str, Any], system: str) -> str:
        name = h.get("name", "The suspect")
        parts: list[str] = []
        for a in h.get("admissions", []):
            parts.append("All right. " + a.rstrip("."))
        if h.get("broken"):
            parts.append("Fine. I stayed late to finish work. I never saw Elena.")
        chunks = h.get("chunks", [])
        if chunks and not parts:
            parts.append(f"I've been over this. It's all in \"{chunks[0]['title']}\".")
        if not parts:
            parts.append("I don't know anything more than what's already public.")
        return f"{name.split()[0]} folds their hands. " + " ".join(parts)

    def _g_deflect(self, h: dict[str, Any], system: str) -> str:
        return h.get("fallback", "I have nothing more to say.")


class LeakyFakeLLM(FakeLLM):
    """Test double that simulates a model which leaks its whole system prompt."""

    def _g_suspect(self, h: dict[str, Any], system: str) -> str:
        return super()._g_suspect(h, system) + "\n" + system

    def _g_records(self, h: dict[str, Any], system: str) -> str:
        return super()._g_records(h, system) + "\n" + h.get("leak", "")


@lru_cache
def get_llm() -> LLM:
    s = get_settings()
    if s.llm_mode == "real":
        log.info("LLM mode: real (main=%s, fast=%s)", s.llm_model_main, s.llm_model_fast)
        return RealLLM()
    log.info("LLM mode: fake")
    return FakeLLM()
