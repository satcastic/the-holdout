from pydantic import BaseModel

from src.llm import FakeLLM, _normalise


class _Judge(BaseModel):
    clue_ids: list[str]
    motive_elements: list[str]


def test_fake_llm_is_deterministic():
    llm = FakeLLM()
    h = {"reasoning": "C21 shows the call came from the building; he signed the override (C04)."}
    a = llm.structured("fast", "", [], _Judge, task="judge", hints=h)
    b = llm.structured("fast", "", [], _Judge, task="judge", hints=h)
    assert a == b
    assert a.clue_ids == ["C04", "C21"]
    assert "vp_override" in a.motive_elements


def test_normalise_merges_and_starts_with_user():
    out = _normalise([{"role": "assistant", "content": "a"}, {"role": "user", "content": "b"},
                      {"role": "user", "content": "c"}])
    assert out[0]["role"] == "user"
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert out[-1]["content"] == "b\n\nc"
