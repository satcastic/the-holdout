from src.ingest import build_record, build_records
from src.models import load_case

REQUIRED = {"_id", "chunk_text", "chunk_id", "type", "title", "text", "entities", "known_by"}


def test_one_record_per_chunk_upsert_by_chunk_id():
    case = load_case()
    records = build_records(case)
    assert len(records) == 30
    assert [r["_id"] for r in records] == [c.id for c in case.fact_chunks]
    assert all(r["_id"] == r["chunk_id"] for r in records)


def test_record_shape_and_no_nulls():
    for chunk in load_case().fact_chunks:
        r = build_record(chunk)
        assert r.keys() >= REQUIRED
        assert None not in r.values(), chunk.id
        assert r["chunk_text"] == f"{chunk.title}. {chunk.text}"
        for key in ("day", "time", "location", "clue_id"):
            assert (key in r) == (getattr(chunk, key) is not None)
        assert r.get("reveal_condition", []) == chunk.reveal_condition


def test_records_contain_no_solution_data():
    allowed = REQUIRED | {"day", "time", "location", "clue_id", "reveal_condition"}
    blob = repr(build_records(load_case())).lower()
    for record in build_records(load_case()):
        assert set(record) <= allowed
    # phrases that exist only in solution.json
    for phrase in ("east stairwell b", "garage level p2", "struck her", "killer"):
        assert phrase not in blob
