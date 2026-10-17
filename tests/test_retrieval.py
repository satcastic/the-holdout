"""Access filter and gating. Gating must be 100% correct, so these tests are exhaustive."""

import itertools
import random

import pytest

from src.ingest import build_records
from src.models import load_case
from src.retrieval import (
    MemoryStore,
    Retriever,
    build_filter,
    is_unlocked,
    matches_filter,
    valid_actors,
    visible_chunk_ids,
)

CASE = load_case()
ALL_CLUES = [c.id for c in CASE.clues]


@pytest.fixture(scope="module")
def retriever():
    store = MemoryStore()
    store.upsert(build_records(CASE))
    return Retriever(store)


def test_build_filter_shape():
    assert build_filter("sam") == {"known_by": {"$in": ["sam"]}}


def test_matches_filter_list_semantics():
    f = {"known_by": ["records", "sam"]}
    assert matches_filter(f, build_filter("sam"))
    assert not matches_filter(f, build_filter("tobias"))
    assert matches_filter(f, {"$and": [build_filter("sam"), {"known_by": {"$nin": ["grant"]}}]})
    assert not matches_filter({}, build_filter("sam"))


@pytest.mark.parametrize(("rc", "found", "expected"), [
    ([], set(), True),
    (None, set(), True),
    (["C01"], set(), False),
    (["C01"], {"C01"}, True),
    (["C07", "C11"], {"C07"}, False),
    (["C07", "C11"], {"C11"}, False),
    (["C07", "C11"], {"C07", "C11", "C02"}, True),
])
def test_is_unlocked_requires_all(rc, found, expected):
    assert is_unlocked(rc, found) is expected


def _all(retriever, actor, found):
    return retriever.search(actor, "evidence", found, top_k=30, overfetch=30)


def test_every_chunk_hidden_until_every_prereq_found(retriever):
    """For each chunk and each of its readers: missing any single prereq hides it,
    having all prereqs shows it."""
    for chunk in CASE.fact_chunks:
        for actor in chunk.known_by:
            full = set(chunk.reveal_condition)
            assert chunk.id in {c.id for c in _all(retriever, actor, full)}
            for missing in chunk.reveal_condition:
                ids = {c.id for c in _all(retriever, actor, full - {missing})}
                assert chunk.id not in ids, (chunk.id, actor, missing)


def test_random_states_sound_and_complete(retriever):
    """Returned set == exactly the eligible set, for 400 random discovery states."""
    rng = random.Random(7)
    for _ in range(400):
        found = {c for c in ALL_CLUES if rng.random() < 0.4}
        for actor in valid_actors():
            got = {c.id for c in _all(retriever, actor, found)}
            assert got == visible_chunk_ids(actor, found), (actor, sorted(found))


def test_suspects_only_get_chunks_listing_them(retriever):
    """A suspect never receives a chunk unless its own id is in known_by
    (so no channel-only chunk and no chunk reserved for another suspect)."""
    for suspect in CASE.suspect_ids:
        got = _all(retriever, suspect, ALL_CLUES)
        assert got
        for chunk in got:
            assert suspect in CASE.chunk_by_id[chunk.id].known_by
        channel_only = {c.id for c in CASE.fact_chunks if suspect not in c.known_by}
        assert not ({c.id for c in got} & channel_only)


def test_suspect_sees_only_own_interview(retriever):
    interviews = {s.id: s.interview_chunk for s in CASE.suspects}
    for suspect in CASE.suspect_ids:
        ids = {c.id for c in _all(retriever, suspect, ALL_CLUES)}
        assert interviews[suspect] in ids
        assert not (ids & (set(interviews.values()) - {interviews[suspect]}))


def test_top_k_and_scores(retriever):
    res = retriever.search("records", "badge door log", ALL_CLUES)
    assert len(res) == 5
    assert [r.score for r in res] == sorted((r.score for r in res), reverse=True)


def test_gating_off_returns_gated_chunks(retriever):
    gated = {c.id for c in retriever.search("records", "log", [], top_k=30, overfetch=30, gating=False)}
    assert gated - visible_chunk_ids("records", [])


def test_unknown_actor_rejected(retriever):
    with pytest.raises(ValueError):
        retriever.search("elena", "anything", [])


def test_cache_hit_returns_equal_copy(retriever):
    a = retriever.search("forensics", "cause of death", [])
    a.clear()
    b = retriever.search("forensics", "cause of death", [])
    assert b


def test_free_start_matches_case():
    free = {c.id for c in CASE.fact_chunks if not c.reveal_condition}
    seen = set(itertools.chain.from_iterable(visible_chunk_ids(a, []) for a in valid_actors()))
    assert seen == free
