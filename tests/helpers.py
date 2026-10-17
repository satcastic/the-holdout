"""Shared test fixtures: a fresh graph with an inspectable fake LLM."""

import uuid

from langgraph.checkpoint.memory import InMemorySaver

from src.graph import build_graph, play_turn, start_session
from src.llm import FakeLLM
from src.state import Runtime


class Game:
    def __init__(self, llm=None, checker_enabled=True, start_turns=None):
        self.llm = llm or FakeLLM()
        self.rt = Runtime(llm=self.llm, checker_enabled=checker_enabled)
        self.graph = build_graph(self.rt, checkpointer=InMemorySaver())
        self.sid = uuid.uuid4().hex
        self.state = start_session(self.graph, self.sid, start_turns)

    def play(self, text="", **action):
        self.state = play_turn(self.graph, self.sid, text, action or None)
        return self.state

    def tasks(self):
        return [t for t, _ in self.llm.calls]
