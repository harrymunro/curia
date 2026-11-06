"""The fence: the mechanism repo must not name any estate, its products or its
principal. The denylist comes from the estates registered on this machine, so
the mechanism never has to contain the words it is forbidden to contain."""
import pathlib
import re
import tomllib
import warnings

import pytest

MECH = pathlib.Path(__file__).resolve().parent.parent
ESTATES = pathlib.Path.home() / ".config" / "curia" / "estates.toml"
SCAN_SUFFIXES = {".py", ".md", ".toml", ".plist", ".json", ".jsonl", ".html", ""}


# The copyright line in LICENSE names who wrote the software, not whom an
# estate serves; it is the same whichever estate runs. So LICENSE may name a
# principal, and nothing else: an estate's name, denylist or repos in it still fail.
PRINCIPAL_MAY_APPEAR = {"LICENSE"}


def denylist(registry: pathlib.Path = ESTATES) -> tuple[set[str], set[str]]:
    """(every forbidden word, those that are only a principal's name: a word of
    one, or a phrase an estate's denylist spells from nothing else). A repo an
    estate registers that IS the mechanism gives no word: its name is this
    repo's own. An estate registered here and absent from this machine cannot
    be read, so its words go unscreened; that is said, never skipped silently."""
    words: set[str] = set()
    principals: set[str] = set()
    if not registry.exists():
        return words, principals
    with open(registry, "rb") as f:
        estates = tomllib.load(f).get("estates", {})
    for key, e in estates.items():
        p = pathlib.Path(e["path"]).expanduser()
        mechanism = {MECH}
        if (p / "estate.toml").exists():
            with open(p / "estate.toml", "rb") as f:
                m = tomllib.load(f)
            words.update(m.get("denylist", []))
            words.add(m.get("name", ""))
            principals.update(m.get("principal", "").split())
            if m.get("mechanism"):   # a fleet home or a worktree of this repo is not at the path it registers
                mechanism.add(pathlib.Path(m["mechanism"]).expanduser().resolve())
        else:
            warnings.warn(f"estate '{key}' is registered at {p} but absent here: its words are not screened "
                          "on this machine", stacklevel=2)
        if (p / "repos.toml").exists():
            with open(p / "repos.toml", "rb") as f:
                repos = tomllib.load(f).get("repos", {})
            words.update(k for k, r in repos.items()
                         if (p.parent / r.get("path", k)).resolve() not in mechanism)
    words = {w for w in words | principals if len(w) > 2}
    names = {w.lower() for w in principals}
    return words, {w for w in words if set(w.lower().split()) <= names}


def forbidden_in(rel: pathlib.Path, words: set[str], principals: set[str]) -> set[str]:
    return words - principals if rel.as_posix() in PRINCIPAL_MAY_APPEAR else words


def test_license_may_name_a_principal_and_nothing_else():
    words, principals = {"acme", "ada", "lovelace", "Ada Lovelace"}, {"ada", "lovelace", "Ada Lovelace"}
    assert forbidden_in(pathlib.Path("LICENSE"), words, principals) == {"acme"}
    assert forbidden_in(pathlib.Path("bin/curia"), words, principals) == words
    assert forbidden_in(pathlib.Path("docs/LICENSE"), words, principals) == words


def test_a_repo_that_is_the_mechanism_is_no_forbidden_word(tmp_path):
    est = tmp_path / "ws" / "estate"
    est.mkdir(parents=True)
    elsewhere = tmp_path / "mech-checkout"
    (est / "estate.toml").write_text(f'name = "Acme"\nprincipal = "Ada Lovelace"\nmechanism = "{elsewhere}"\n')
    (est / "repos.toml").write_text(f'[repos.acmeapp]\npath = "app"\n'
                                    f'[repos.ownname]\npath = "{MECH}"\n'
                                    f'[repos.checkout]\npath = "{elsewhere}"\n')
    reg = tmp_path / "estates.toml"
    reg.write_text(f'[estates.acme]\npath = "{est}"\n')
    words, principals = denylist(reg)
    assert {"acmeapp", "Acme", "Ada", "Lovelace"} <= words and {"Ada", "Lovelace"} == principals
    assert "ownname" not in words and "checkout" not in words


def test_an_absent_estate_is_said_not_skipped(tmp_path):
    reg = tmp_path / "estates.toml"
    reg.write_text(f'[estates.gone]\npath = "{tmp_path / "nowhere"}"\n')
    with pytest.warns(UserWarning, match="estate 'gone' is registered .* but absent"):
        assert denylist(reg) == (set(), set())


def test_mechanism_names_no_estate():
    words, principals = denylist()
    if not words:
        pytest.skip("no estates registered; nothing to fence against")
    hits = []
    for f in MECH.rglob("*"):
        if not f.is_file() or ".git" in f.parts or "__pycache__" in f.parts:
            continue
        if f.suffix not in SCAN_SUFFIXES:
            continue
        rel = f.relative_to(MECH)
        text = f.read_text(errors="ignore")
        for w in sorted(forbidden_in(rel, words, principals)):
            if re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE):
                hits.append(f"{rel}: {w}")
    assert not hits, "mechanism names an estate:\n" + "\n".join(hits)
