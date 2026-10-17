"""Hidden-truth isolation, enforced statically over src/ with the AST."""

import ast
from pathlib import Path

import pytest

from src.config import ROOT
from src.truth_store import get_private_brief, get_reveal, get_rubric

SRC = ROOT / "src"
TRUTH = "src/truth_store.py"

# provider -> files allowed to import it
ALLOWED = {
    "get_private_brief": {"src/nodes/suspect.py"},
    "get_rubric": {"src/nodes/judge.py"},
    "get_reveal": {"src/api.py"},
}


def _py_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _truth_imports(tree: ast.AST) -> tuple[set[str], bool]:
    """Names imported from truth_store, and whether the module itself is imported."""
    names, module_import = set(), False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("truth_store"):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module in ("src", None):
            if any(a.name == "truth_store" for a in node.names):
                module_import = True
        elif isinstance(node, ast.Import):
            if any(a.name.endswith("truth_store") for a in node.names):
                module_import = True
    return names, module_import


def test_providers_imported_only_where_allowed():
    problems = []
    for path in _py_files():
        rel = _rel(path)
        if rel == TRUTH:
            continue
        names, module_import = _truth_imports(ast.parse(path.read_text()))
        if module_import:
            problems.append(f"{rel} imports the truth_store module wholesale")
        for name in names:
            if rel not in ALLOWED.get(name, set()):
                problems.append(f"{rel} imports {name}")
    assert not problems, problems


def test_suspect_node_imports_only_private_brief():
    if not (SRC / "nodes/suspect.py").exists():
        pytest.skip("suspect node not written yet")
    names, module_import = _truth_imports(ast.parse((SRC / "nodes/suspect.py").read_text()))
    assert names == {"get_private_brief"}
    assert not module_import


def test_no_other_file_references_solution_json():
    offenders = []
    for path in _py_files():
        if _rel(path) == TRUTH:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and "solution" in node.value.lower() and ".json" in node.value.lower():
                offenders.append(_rel(path))
        if "solution.json" in path.read_text():
            offenders.append(_rel(path))
    assert not offenders, offenders


def test_frontend_never_mentions_solution():
    web = ROOT / "web" / "src"
    if not web.exists():
        pytest.skip("frontend not built yet")
    for path in web.rglob("*"):
        if path.is_file():
            text = path.read_text(errors="ignore")
            assert "solution.json" not in text and "private_brief" not in text, path


def test_private_brief_is_only_that_suspect():
    brief = get_private_brief("marisol")
    blob = repr(brief).lower()
    assert "marisol" in blob
    assert "killer" not in brief and "accusation_rubric" not in brief
    # another suspect's secrets are not in her brief
    assert "mining rig" not in blob.replace("sam's mining rig", "")
    with pytest.raises(KeyError):
        get_private_brief("elena")


def test_brief_is_a_copy():
    get_private_brief("sam")["cover_story"] = "tampered"
    assert get_private_brief("sam")["cover_story"] != "tampered"


def test_rubric_derivation():
    r = get_rubric()
    assert r.alibi_rules == [["C21"]]
    assert r.partial_alibi_rules == [["C09", "C22"]]
    assert set(r.clearing_rules) == {"marisol", "grant", "sam"}
    assert set(r.motive_clues) == {"C04", "C06", "C03"}


def test_reveal_has_timeline_but_no_briefs():
    rv = get_reveal()
    assert rv.true_timeline and rv.crime["location"] == "Server Room 11-S"
    dumped = rv.model_dump_json()
    assert "cover_story" not in dumped and "admits_if_confronted_with" not in dumped
