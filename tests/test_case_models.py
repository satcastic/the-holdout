from src.models import load_case


def test_case_loads_and_links():
    case = load_case()
    assert len(case.fact_chunks) == 30
    assert len(case.clues) == 24
    assert case.suspect_ids == ["tobias", "marisol", "grant", "sam"]
    for clue in case.clues:
        assert case.chunk_by_id[clue.source_chunk].clue_id == clue.id
    assert case.chunk_for_clue("C21").id == "F24"


def test_embed_text_is_title_plus_text():
    chunk = load_case().chunk_by_id["F01"]
    assert chunk.embed_text.startswith(chunk.title + ". ")
