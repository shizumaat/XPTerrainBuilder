"""THE CENSUS CACHE'S TWIN — a hit is the fresh run, plus one line.

``tools/harness/census.py`` memoises its full report (see that file's
header, "THE CENSUS CACHE").  A cache over an INSTRUMENT is only safe if
two properties hold, and neither is checkable by reading the code:

  IDENTITY   a hit reproduces the fresh output BYTE FOR BYTE — stdout, the
             ``--json`` report, and the ``--rows-json`` / ``--sites-json``
             dumps — apart from exactly one added marker line;
  MISSING    anything that can move a row misses: the law knobs, the patch
             BODY, the patch's provenance HEADER (which the census prints
             and the body hash deliberately excludes), the sidecar bytes,
             and the option frame.

Both are asserted here against the census's own hand-built fixture patch
(``tests/test_census_instrument.py`` — one builder, not a second copy of
one), with the cache root pointed at ``tmp_path``.  Nothing here builds,
downloads, or touches the shared data repo.

The law's CODE VERSION is part of the key and is the run ledger's own tree
hash.  Taking it costs a git call and — being a hash of the live worktree —
would make every assertion here depend on nothing else editing the tree
mid-test, so the behavioural tests pin it and one test asserts, separately,
that the real one IS ``run_with_ledger.code_tree_hash`` and not a fork.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"
sys.path.insert(0, str(ROOT / "src"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cg():
    return _load("cache_twin_check_grade", ROOT / "tools" / "check_grade.py")


@pytest.fixture(scope="module")
def census(cg):
    return _load("cache_twin_census", HARNESS / "census.py")


@pytest.fixture(scope="module")
def instrument_twin():
    """The census instrument twin's PATCH BUILDER — imported, not copied.

    A second hand-built fixture would be a second frame, which is the
    census-wrapper defect one file down from where it usually appears.
    """
    return _load("cache_twin_fixture",
                 ROOT / "tests" / "test_census_instrument.py")


@pytest.fixture
def patch(cg, instrument_twin, tmp_path) -> Path:
    return instrument_twin._build_fixture(cg, tmp_path)


@pytest.fixture
def cache_dir(tmp_path, monkeypatch) -> Path:
    """A per-test, lane-local cache root."""
    root = tmp_path / "census_cache"
    monkeypatch.setenv("O4_CENSUS_CACHE_DIR", str(root))
    return root


@pytest.fixture
def pinned_law(census, monkeypatch):
    """Pin the law CODE hash so these tests measure the cache, not the
    worktree's git state (and so they cost no git calls)."""
    monkeypatch.setattr(census, "law_code_hash", lambda: "PINNED_TREE_HASH")


#: The marker, spelled out here rather than imported, so a rename of the
#: tool's constant has to come past this file (one test pins the two
#: together).
MARKER = "[CENSUS CACHE HIT]"


def _run(census, capsys, argv) -> str:
    assert census.main([str(a) for a in argv]) == 0
    return capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════
# §1 IDENTITY — a hit is the fresh output plus exactly one line
# ══════════════════════════════════════════════════════════════════════

def test_a_cache_hit_is_the_fresh_output_byte_for_byte_plus_the_marker(
        census, capsys, patch, cache_dir, pinned_law):
    """The whole promise, on the loudest report the tool can print (every
    optional section on).  The served run differs from the fresh run by
    ONE line — the marker — and that line is the FIRST line, immediately
    before the ``=== CENSUS <patch> ===`` header it belongs to."""
    assert census.CACHE_HIT_MARKER == MARKER
    argv = [patch, "--top", 5, "--bare", "--sites", "--zone-split",
            "--magnitude-bands"]
    fresh = _run(census, capsys, argv)
    assert MARKER not in fresh, "the first census must be a MISS"

    served = _run(census, capsys, argv)
    marker, _, rest = served.partition("\n")
    assert marker.startswith(MARKER)
    assert rest == fresh, "a served census is not the fresh census"
    assert served.count(MARKER) == 1
    # The marker names what it served and how to get around it.
    assert str(patch) in marker and "--no-cache" in marker


def test_the_json_report_and_both_dumps_are_the_fresh_bytes(
        census, capsys, patch, cache_dir, pinned_law, tmp_path):
    """Identity is not only stdout: the ``--json`` report and the two row/
    site dumps a hit re-writes must be the same bytes the fresh run wrote.
    The dumps are deleted between the arms, so the second run's files can
    only have come from the cache."""
    out = tmp_path / "out"
    argv = [patch, "--top", 5, "--sites",
            "--json", out / "rep.json",
            "--rows-json", out / "rows.json",
            "--sites-json", out / "sites.json"]
    _run(census, capsys, argv)
    fresh = {p.name: p.read_text() for p in sorted(out.glob("*.json"))}
    assert set(fresh) == {"rep.json", "rows.json", "sites.json"}
    for p in out.glob("*.json"):
        p.unlink()

    served = _run(census, capsys, argv)
    assert served.startswith(MARKER)
    assert {p.name: p.read_text()
            for p in sorted(out.glob("*.json"))} == fresh


def test_the_marker_is_printed_even_under_quiet(
        census, capsys, patch, cache_dir, pinned_law, tmp_path):
    """A number served from a cache that did not say so is the
    instrument-truth defect, so ``--quiet`` suppresses the table and never
    the marker."""
    argv = [patch, "--quiet", "--json", tmp_path / "q.json"]
    fresh = _run(census, capsys, argv)
    served = _run(census, capsys, argv)
    assert MARKER not in fresh
    assert served.startswith(MARKER)
    assert served.partition("\n")[2] == fresh


# ══════════════════════════════════════════════════════════════════════
# §2 MISSING — everything that can move a row
# ══════════════════════════════════════════════════════════════════════

def test_a_law_knob_change_misses(census, capsys, patch, cache_dir,
                                  pinned_law, monkeypatch):
    """``check_grade.LAW_TRUE_KNOBS`` is the numeric law the census binds.
    Moved in-process — the patch, the sidecar and the pinned code hash all
    unchanged — the second census must MISS, and the third, with the knob
    put back, must hit the ORIGINAL entry again: it is the knob that keys
    it, not the fact of being a second run."""
    argv = [patch, "--top", 5]
    first = _run(census, capsys, argv)
    assert MARKER not in first

    original = census.load_check_grade

    def _bumped():
        mod = original()
        mod.LAW_TRUE_KNOBS = dict(mod.LAW_TRUE_KNOBS, max_grade_pct=5.0)
        return mod

    monkeypatch.setattr(census, "load_check_grade", _bumped)
    moved = _run(census, capsys, argv)
    assert MARKER not in moved, "a knob change served a cached law"
    assert _knobs_line(moved) != _knobs_line(first)

    monkeypatch.setattr(census, "load_check_grade", original)
    back = _run(census, capsys, argv)
    assert back.startswith(MARKER)
    assert back.partition("\n")[2] == first


def _knobs_line(out: str) -> str:
    return next(ln for ln in out.splitlines()
                if ln.strip().startswith("law-true knobs:"))


def test_a_patch_body_change_misses(census, capsys, patch, cache_dir,
                                    pinned_law):
    """One altitude moved in the BODY — the population the law reads."""
    argv = [patch, "--top", 5]
    first = _run(census, capsys, argv)
    text = patch.read_text()
    changed = text.replace("v='1.20'", "v='3.40'", 1)
    assert changed != text, "the fixture no longer carries the edited tag"
    patch.write_text(changed)

    second = _run(census, capsys, argv)
    assert MARKER not in second, "a changed body served a stale census"
    assert second != first


def test_a_provenance_header_change_misses_too(
        cg, census, capsys, instrument_twin, cache_dir, pinned_law, tmp_path):
    """THE TRAP THE BODY HASH CANNOT SEE.  ``body_sha256`` is ``tail -n +3``
    — it deliberately excludes the provenance stamp, so two builds of the
    same geometry share a body hash.  But the census PRINTS that stamp
    (sha / dirty / built / gates), so a cache keyed on the body alone would
    serve one build's numbers under another build's frame — the
    frame-stamp law inverted.  The key carries the whole file's hash for
    exactly this case."""
    from auto_patch.provenance import provenance_tags

    def _with_sha(sha: str, where: Path) -> Path:
        tags = provenance_tags({
            "git": {"sha": sha, "dirty": False},
            "gates": {"on": [], "nondefault": [], "total": 7},
            "dem": {"raw": True}, "built": "2026-08-13T00:00:00",
            "icao": "TEST"})
        attrs = "".join(f" {k}='{v}'" for k, v in tags.items())
        return instrument_twin._build_fixture(cg, where, root_attrs=attrs)

    where = tmp_path / "prov"
    where.mkdir()
    a = _with_sha("aaaaaaaaaaaaaaaa", where)
    body = census.patch_body_sha256(a)
    first = _run(census, capsys, [a, "--top", 5])
    assert "sha=aaaaaaaaaaaaaaaa" in first

    # The SAME path, rewritten: same geometry, same sidecar, new stamp.
    b = _with_sha("bbbbbbbbbbbbbbbb", where)
    assert b == a
    assert census.patch_body_sha256(b) == body, (
        "the two builds must share a BODY hash — otherwise this test is "
        "not exercising the header at all")
    second = _run(census, capsys, [b, "--top", 5])
    assert MARKER not in second, "a new provenance stamp served an old frame"
    assert "sha=bbbbbbbbbbbbbbbb" in second


def test_a_sidecar_change_misses(census, capsys, patch, cache_dir,
                                 pinned_law):
    """The sidecar IS the law context (ruleset, axes, terrace joints, seam
    pins).  Keyed on its BYTES, so a key nobody thought to enumerate — the
    census-wrapper defect class — cannot slip through."""
    side = Path(str(patch) + ".axes.json")
    argv = [patch, "--top", 5]
    first = _run(census, capsys, argv)
    assert "ruleset: declared='icao'" in first

    doc = json.loads(side.read_text())
    doc["ruleset"] = "faa"
    side.write_text(json.dumps(doc))

    second = _run(census, capsys, argv)
    assert MARKER not in second, "a changed sidecar served a stale law"
    assert "ruleset: declared='faa'" in second


@pytest.mark.parametrize("extra", [
    ["--top", 3],            # the printed worst-N population
    ["--bare"],              # a whole extra frame in the report
    ["--frame", "base"],     # a DIFFERENT axis frame — different numbers
    ["--sites"],             # an extra section
    ["--magnitude-bands", "0.02,0.2"],
])
def test_an_option_change_misses(census, capsys, patch, cache_dir,
                                 pinned_law, extra):
    """Every flag that changes the report is in the key."""
    _run(census, capsys, [patch, "--top", 5])
    out = _run(census, capsys, [patch, "--top", 5] + extra)
    assert MARKER not in out


def test_the_dump_flags_are_in_the_key(census, capsys, patch, cache_dir,
                                       pinned_law, tmp_path):
    """An entry stored WITHOUT the row dump cannot serve a run that asks
    for one — it has no dump text to write.  So the request itself keys
    the entry, and the file always appears."""
    _run(census, capsys, [patch, "--top", 5])
    rows = tmp_path / "dump" / "rows.json"
    out = _run(census, capsys, [patch, "--top", 5, "--rows-json", rows])
    assert MARKER not in out
    assert rows.exists()


# ══════════════════════════════════════════════════════════════════════
# §3 THE ESCAPE HATCHES AND THE STORE
# ══════════════════════════════════════════════════════════════════════

def test_no_cache_neither_reads_nor_writes(census, capsys, patch, cache_dir,
                                           pinned_law):
    fresh = _run(census, capsys, [patch, "--top", 5, "--no-cache"])
    assert MARKER not in fresh
    assert not cache_dir.exists() or not list(cache_dir.glob("*.json")), (
        "--no-cache wrote an entry")
    # …and it still refuses to read one that exists.
    _run(census, capsys, [patch, "--top", 5])
    assert list(cache_dir.glob("*.json"))
    again = _run(census, capsys, [patch, "--top", 5, "--no-cache"])
    assert MARKER not in again
    assert again == fresh


def test_clear_cache_empties_the_store_and_then_censuses(
        census, capsys, patch, cache_dir, pinned_law):
    fresh = _run(census, capsys, [patch, "--top", 5])
    assert len(list(cache_dir.glob("*.json"))) == 1

    out = _run(census, capsys, [patch, "--top", 5, "--clear-cache"])
    first, _, rest = out.partition("\n")
    assert first == f"[CENSUS CACHE] cleared 1 entry from {cache_dir}"
    assert MARKER not in out, "--clear-cache served a cached census"
    assert rest == fresh
    # …and the run that cleared it re-populated it.
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_a_corrupt_entry_is_a_miss_and_never_a_crash(
        census, capsys, patch, cache_dir, pinned_law):
    fresh = _run(census, capsys, [patch, "--top", 5])
    entry = next(iter(cache_dir.glob("*.json")))
    entry.write_text("{ this is not json")
    out = _run(census, capsys, [patch, "--top", 5])
    assert MARKER not in out
    assert out == fresh


def test_a_foreign_cache_format_is_a_miss(census, capsys, patch, cache_dir,
                                          pinned_law):
    """The format version is IN the key and checked on read, so a stored
    shape from another version is never read with new eyes."""
    _run(census, capsys, [patch, "--top", 5])
    entry = next(iter(cache_dir.glob("*.json")))
    doc = json.loads(entry.read_text())
    doc["census_cache_format"] = census.CENSUS_CACHE_FORMAT + 1
    entry.write_text(json.dumps(doc))
    assert MARKER not in _run(census, capsys, [patch, "--top", 5])


# ══════════════════════════════════════════════════════════════════════
# §4 THE KEY'S COMPONENTS ARE THE REPO'S OWN, NOT A SECOND COPY
# ══════════════════════════════════════════════════════════════════════

def test_the_body_hash_is_the_harness_body_hash(census, patch):
    """``census.patch_body_sha256`` IS ``build_airport.body_sha256`` — the
    ``tail -n +3`` convention ``baselines/*/MANIFEST.txt`` is written in.
    A second implementation of "the patch body" is how two lanes end up
    comparing two different things."""
    build_airport = _load("cache_twin_build_airport",
                          HARNESS / "build_airport.py")
    expected = build_airport.body_sha256(patch)
    assert census.patch_body_sha256(patch) == expected
    tail = b"\n".join(patch.read_bytes().split(b"\n")[2:])
    assert expected == hashlib.sha256(tail).hexdigest()


def test_the_law_code_version_is_the_run_ledgers_own_tree_hash(census):
    """The key's ``law_code_tree`` is the ledger's hash, so an edit to
    ``check_grade.py`` (or to the census) misses.  Asserted by identity
    against the ledger's own function rather than by re-deriving it."""
    ledger = _load("cache_twin_run_ledger", ROOT / "tools" /
                   "run_with_ledger.py")
    assert census.law_code_hash() == ledger.code_tree_hash(str(ROOT))


def test_the_key_carries_every_component_and_moves_with_each(
        census, cg, patch, cache_dir, pinned_law):
    """The payload is the contract; every field is load-bearing."""
    opts = {"top": 5}
    payload = census.cache_key_payload(patch, cg, opts)
    assert set(payload) == {
        "census_cache_format", "patch", "patch_body_sha256",
        "patch_file_sha256", "sidecar_sha256", "law_code_tree",
        "law_true_knobs", "env", "options"}
    base = census.cache_key(payload)
    for field, value in (("patch_body_sha256", "0" * 64),
                         ("patch_file_sha256", "0" * 64),
                         ("sidecar_sha256", "0" * 64),
                         ("law_code_tree", "other"),
                         ("census_cache_format", 99),
                         ("patch", "/elsewhere/x.osm"),
                         ("env", {"O4_SOMETHING": "1"}),
                         ("law_true_knobs", {"max_grade_pct": 9.0}),
                         ("options", {"top": 6})):
        assert census.cache_key(dict(payload, **{field: value})) != base, (
            f"the key does not move with {field}")


def test_a_suite_that_did_not_ask_for_the_cache_never_gets_one(
        census, capsys, patch, monkeypatch):
    """No ``$O4_CENSUS_CACHE_DIR`` inside a pytest session ⇒ no cache: a
    suite must neither warm lane state nor assert on a SERVE it produced
    itself two tests earlier.  Note this test deliberately does NOT take
    the ``cache_dir`` fixture."""
    monkeypatch.delenv("O4_CENSUS_CACHE_DIR", raising=False)
    assert census.cache_enabled() is False
    before = sorted(census.DEFAULT_CENSUS_CACHE_DIR.glob("*.json"))
    first = _run(census, capsys, [patch, "--top", 5])
    second = _run(census, capsys, [patch, "--top", 5])
    assert MARKER not in first and MARKER not in second
    assert second == first
    assert sorted(census.DEFAULT_CENSUS_CACHE_DIR.glob("*.json")) == before, (
        "a suite run wrote the lane's default census cache")


def test_the_cache_refuses_to_live_in_the_shared_data_repo(
        census, monkeypatch):
    """A cache is a lane PRODUCT; lane products stay lane-local (root
    CLAUDE.md, RULINGS e9daef5).  A cache root inside the shared corpus is
    refused before anything is written."""
    guard = _load("cache_twin_shared_repo_guard",
                  HARNESS / "shared_repo_guard.py")
    monkeypatch.setenv("O4_CENSUS_CACHE_DIR",
                       str(Path(guard.DATA_REPO) / "census_cache"))
    with pytest.raises(SystemExit) as exc:
        census.cache_root()
    assert "REFUSING" in str(exc.value)
    assert "SHARED DATA REPO" in str(exc.value)
