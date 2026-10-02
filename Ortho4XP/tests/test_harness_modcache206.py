"""THE AUTHORISED PACK-DUMP DERIVATION (``--refresh-data
airport_mod_cache``) and its RE-JUDGE — issue #206.

MEASURED 2026-10-02 (the owner's session, KGEG +47-118):
``build_airport.py KGEG --tag …`` refused on
``Airport_mod_cache/c_USA - 100_airport - KGEG …/+47-118.dsf.f9e323ec.text``
("the pack's DSF sha has NO cached text dump"), and the run that names
exactly that scope —
``KGEG --tile 47 -118 --refresh-only --refresh-data airport_mod_cache`` —
answered "refresh scope airport_mod_cache was authorised but wrote
NOTHING" and "frame re-judged CURRENT".  A FALSE CURRENT: the next build
refused on the very artifact the scope names.

Two defects, both pinned here:

1. NO DERIVATION.  No pass existed for the scope at all, so an authorised
   run held the lock, snapshotted, armed the guard — and derived nothing.
2. THE RE-JUDGE ASKED A DIFFERENT QUESTION FROM THE PRE-FLIGHT.  The
   predicate is :func:`pack_dsf_dump_state` and it needs the NAMED
   airport; ``--tile`` nulls the icao on the way into the re-judge, so the
   predicate stood down (``if not icao: return None``) and the frame read
   CURRENT.  The law is RULINGS 2026-10-02b: the refresh-only re-judge
   asks the SAME predicate the build's pre-flight asks, from ONE
   derivation site.

OFFLINE: there is no DSFTool binary here, so the engine's own wrapper
(``auto_patch.dsf_reader.ensure_dsf_text_path``) is pointed at a FAKE
``--dsf2text`` tool.  Everything else — the cache naming, the write
declaration, the guard, the snapshot/ledger audit — is the real code.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import stat
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"
sys.path.insert(0, str(ROOT / "src"))

#: The scope under test, spelled once (``REFRESH_SCOPES``).
SCOPE = "airport_mod_cache"
#: The data-repo directory that scope names.
MOD_CACHE_DIR = "Airport_mod_cache"
#: The pack folder name the fixture install carries.
PACK_NAME = "TestPack"
#: The fixture tile, and the airport that serves it.
TILE = (22, 113)
ICAO = "VHHH"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def build_mod():
    return _load("harness_modcache_build", HARNESS / "build_airport.py")


@pytest.fixture(scope="module")
def guard_mod(build_mod):
    return sys.modules["shared_repo_guard"]


class _Notes:
    def __init__(self):
        self.lines: list[str] = []

    def note(self, text):
        self.lines.append(text)

    @property
    def text(self):
        return "\n".join(self.lines)


def _fake_dsftool(tmp_path, calls_log):
    """An executable stand-in for DSFTool that writes the dump it is
    asked for and appends its argv to ``calls_log`` (a JSONL file)."""
    tool = tmp_path / "bin" / "DSFTool"
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys\n"
        f"open({str(calls_log)!r}, 'a', encoding='utf-8', newline='')"
        ".write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "assert sys.argv[1] == '--dsf2text', sys.argv\n"
        "open(sys.argv[3], 'w', encoding='utf-8', newline='').write("
        "'PROPERTY sim/west 113\\n')\n",
        encoding="utf-8", newline="\n")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    return tool


def _pack_frame(tmp_path, monkeypatch, build_mod):
    """A tmp X-Plane install holding one pack with one tile DSF, a tmp
    data repo for the shared ``Airport_mod_cache``, and an EMPTY lane
    overlay.  Returns ``(repo, dsf, shared_mod_cache)``."""
    import O4_File_Names as FNAMES
    import auto_patch_v2.airport.pack as _pack

    pack = tmp_path / "install" / "Custom Scenery" / PACK_NAME
    nav = pack / "Earth nav data" / "+20+110"
    nav.mkdir(parents=True)
    dsf = nav / f"{TILE[0]:+03d}{TILE[1]:+04d}.dsf"
    dsf.write_bytes(b"binary dsf bytes")
    repo = tmp_path / "repo"
    shared = repo / MOD_CACHE_DIR
    shared.mkdir(parents=True)
    (tmp_path / "lane" / "tmp" / "engine_caches").mkdir(parents=True)
    monkeypatch.setenv("XPLANE_ROOT", str(tmp_path / "install"))
    monkeypatch.setattr(_pack, "select_pack",
                        lambda root, icao: types.SimpleNamespace(
                            root=str(pack), name=PACK_NAME))
    monkeypatch.setattr(FNAMES, "airport_mod_cache_root", lambda: str(shared))
    monkeypatch.setattr(build_mod, "lane_cache_root",
                        lambda lane_root=None: tmp_path / "lane" / "tmp"
                        / "engine_caches")
    return repo, dsf, shared


def _expected_dump(dsf, shared):
    from auto_patch_v2.airport import dsf as _dsf
    return (Path(shared) / PACK_NAME
            / f"{dsf.name}.{_dsf.text_dump_tag(str(dsf))}.text")


# ══════════════════════════════════════════════════════════════════════
# (1) THE DERIVATION
# ══════════════════════════════════════════════════════════════════════

def test_an_authorised_airport_mod_cache_refresh_DERIVES_the_pack_dump(
        build_mod, guard_mod, tmp_path, monkeypatch):
    """#206's BAR: under an authorised ``airport_mod_cache`` scope the
    refresh derives the pack's DSF text dump THROUGH THE ENGINE'S OWN
    DSFTool wrapper, and the re-judge reads NOT-current before and
    CURRENT after."""
    from auto_patch import dsf_reader

    repo, dsf, shared = _pack_frame(tmp_path, monkeypatch, build_mod)
    calls_log = tmp_path / "dsftool_calls.jsonl"
    monkeypatch.setattr(dsf_reader, "_dsftool_path",
                        lambda: str(_fake_dsftool(tmp_path, calls_log)))
    ledger = tmp_path / "state" / "refresh_ledger.jsonl"
    monkeypatch.setattr(guard_mod, "REFRESH_LEDGER", ledger)
    # the engine's wrapper is what must be called -- spy, do not replace
    wrapper_calls = []
    real = dsf_reader.ensure_dsf_text_path

    def _spy(path, cache_dir=None):
        wrapper_calls.append(path)
        return real(path, cache_dir)

    monkeypatch.setattr(dsf_reader, "ensure_dsf_text_path", _spy)
    # nothing else about the frame is under test here
    monkeypatch.setattr(build_mod, "missing_shared_artifacts",
                        lambda *a, **kw: [])
    monkeypatch.setattr(build_mod, "approach_ring_problem",
                        lambda *a, **kw: None)

    want = _expected_dump(dsf, shared)

    # ── BEFORE: the pre-flight names it, and so does the re-judge ──
    missing = build_mod.missing_pack_dsf_dumps(repo, *TILE, ICAO)
    assert len(missing) == 1 and missing[0][0] == SCOPE, missing
    assert missing[0][1].endswith(want.name), missing
    with pytest.raises(SystemExit) as exc:
        build_mod.require_refreshed_frame(repo, *TILE, {SCOPE},
                                          icao=None, named_icao=ICAO,
                                          refresh_only=True)
    assert "STILL not current" in str(exc.value)
    assert want.name in str(exc.value)

    # ── THE WARM, with everything that makes a shared write lawful ──
    prog = _Notes()
    guard = guard_mod.SharedRepoWriteGuard([SCOPE], repo, repo=repo)
    before = guard_mod.shared_repo_snapshot(repo)
    with guard:
        summary = build_mod.refresh_airport_mod_cache(
            repo, *TILE, prog, icao=ICAO)
    changes = guard_mod.snapshot_diff(
        before, guard_mod.shared_repo_snapshot(repo))

    # the ENGINE's wrapper ran DSFTool --dsf2text on the pristine DSF
    assert wrapper_calls == [str(dsf)], wrapper_calls
    argv = [json.loads(line) for line in
            calls_log.read_text(encoding="utf-8").splitlines()]
    assert len(argv) == 1 and argv[0][0] == "--dsf2text", argv
    assert argv[0][1] == str(dsf) and argv[0][2] == str(want), argv
    # ...and the dump landed at the engine's own cache name
    assert want.is_file(), sorted(p.name for p in want.parent.glob("*"))
    assert summary["derived"] == str(want)
    assert summary["recycled"] is False
    assert summary["pack"] == PACK_NAME
    assert f"{MOD_CACHE_DIR}/{PACK_NAME}" in prog.text.replace(os.sep, "/")

    # ── THE LEDGER: the audit's own generic path stamps it ──
    in_scope = {k: [r for r in v if guard_mod.scope_of(r) == SCOPE]
                for k, v in changes.items()}
    assert in_scope["added"], changes
    rec = guard_mod.record_refresh(SCOPE, in_scope, {"tag": "twin206"},
                                   repo=repo)
    assert rec["added"] == 1
    line = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert line["scope"] == SCOPE
    assert any(want.name in f["path"] for f in line["files"]), line

    # ── AFTER: the SAME predicate now reads current ──
    assert build_mod.missing_pack_dsf_dumps(repo, *TILE, ICAO) == []
    build_mod.require_refreshed_frame(repo, *TILE, {SCOPE},
                                      icao=None, named_icao=ICAO,
                                      refresh_only=True)


def test_a_dump_already_cached_is_RECYCLED_not_re_dumped(
        build_mod, tmp_path, monkeypatch):
    """A refresh is not a re-derivation: the dump on disk under this
    DSF's own sha is recycled and DSFTool is never spawned."""
    from auto_patch import dsf_reader

    repo, dsf, shared = _pack_frame(tmp_path, monkeypatch, build_mod)
    want = _expected_dump(dsf, shared)
    want.parent.mkdir(parents=True, exist_ok=True)
    want.write_text("# dump\n", encoding="utf-8", newline="")
    calls_log = tmp_path / "dsftool_calls.jsonl"
    monkeypatch.setattr(dsf_reader, "_dsftool_path",
                        lambda: str(_fake_dsftool(tmp_path, calls_log)))
    prog = _Notes()
    summary = build_mod.refresh_airport_mod_cache(repo, *TILE, prog,
                                                 icao=ICAO)
    assert summary["recycled"] is True
    assert summary["derived"] is None
    assert not calls_log.exists(), "DSFTool must not be spawned"
    assert "RECYCLED" in prog.text


def test_a_refresh_that_derived_NOTHING_refuses_instead_of_reporting_CURRENT(
        build_mod, tmp_path, monkeypatch):
    """The whole point of #206: a pass that wrote nothing while the
    artifact is still owed must REFUSE, never print CURRENT.  Here the
    engine's wrapper fails the way it does with no DSFTool on PATH."""
    from auto_patch import dsf_reader

    repo, dsf, shared = _pack_frame(tmp_path, monkeypatch, build_mod)
    monkeypatch.setattr(dsf_reader, "_dsftool_path", lambda: None)
    with pytest.raises(SystemExit) as exc:
        build_mod.refresh_airport_mod_cache(repo, *TILE, _Notes(), icao=ICAO)
    assert "derived NOTHING" in str(exc.value)
    assert SCOPE in str(exc.value)
    assert _expected_dump(dsf, shared).name in str(exc.value)


# ══════════════════════════════════════════════════════════════════════
# (2) ONE PREDICATE, ASKED FROM BOTH SITES
# ══════════════════════════════════════════════════════════════════════

def test_the_refresh_only_rejudge_asks_the_SAME_predicate_as_the_preflight(
        build_mod, tmp_path, monkeypatch):
    """THE FALSE CURRENT.  ``--tile`` nulls the icao into the re-judge, so
    the dump predicate stood down and the frame read CURRENT while the
    next build refused on that very artifact.  The NAMED airport is
    carried separately and the predicate is asked with it."""
    repo, dsf, shared = _pack_frame(tmp_path, monkeypatch, build_mod)
    monkeypatch.setattr(build_mod, "missing_shared_artifacts",
                        lambda *a, **kw: [])
    monkeypatch.setattr(build_mod, "approach_ring_problem",
                        lambda *a, **kw: None)
    # exactly the owner's command shape: a tile named, an airport named
    with pytest.raises(SystemExit) as exc:
        build_mod.require_refreshed_frame(repo, *TILE, {SCOPE},
                                          icao=None, named_icao=ICAO,
                                          refresh_only=True)
    assert "STILL not current" in str(exc.value)
    # a scope NOT requested stays informational, as it always was
    build_mod.require_refreshed_frame(repo, *TILE, {"dem"},
                                      icao=None, named_icao=ICAO,
                                      refresh_only=True)
    # and the row is never counted twice when the icao came through both
    monkeypatch.setattr(
        build_mod, "missing_shared_artifacts",
        lambda *a, **kw: build_mod.missing_pack_dsf_dumps(repo, *TILE, ICAO))
    with pytest.raises(SystemExit) as exc:
        build_mod.require_refreshed_frame(repo, *TILE, {SCOPE},
                                          icao=ICAO, named_icao=ICAO,
                                          refresh_only=True)
    assert "1 artifact(s)" in str(exc.value), str(exc.value)


def test_there_is_ONE_pack_dump_predicate_site(build_mod):
    """A second copy of the predicate is the census-wrapper defect
    (CLAUDE.md).  Both consumers go through ``pack_dsf_dump_state``."""
    for fn in (build_mod.missing_pack_dsf_dumps,
               build_mod.refresh_airport_mod_cache):
        src = inspect.getsource(fn)
        assert "pack_dsf_dump_state(" in src, fn.__name__
        assert "select_pack(" not in src, (
            f"{fn.__name__} must not resolve the pack itself — "
            f"pack_dsf_dump_state is the one derivation site")
    # ...and the re-judge asks that one site too
    assert "missing_pack_dsf_dumps(" in inspect.getsource(
        build_mod.require_refreshed_frame)


def test_main_runs_the_pass_and_carries_the_named_airport(build_mod):
    """A source twin: the pass sits inside the try whose ``finally``
    stamps the ledger and releases the locks, BEFORE the re-judge, and
    the re-judge is handed the airport named on the command line
    regardless of ``--tile`` (RULINGS 2026-10-02b/2026-10-02e)."""
    src = inspect.getsource(build_mod.main)
    i_try = src.index("\n    try:\n", src.index("locks = [RefreshLock("))
    i_pass = src.index("refresh_airport_mod_cache(", i_try)
    i_judge = src.index("require_refreshed_frame(", i_try)
    assert i_pass > i_try and i_pass < i_judge
    assert "named_icao=args.icao" in src
    # step order (2026-10-02e) is untouched, and the new pass follows it
    order = [src.index(call, i_try) for call in (
        "refresh_stale_osm_layers(", "warm_airport_insets(",
        "refresh_shore_feed(", "refresh_tile_dem(",
        "refresh_approach_rings(", "refresh_airport_mod_cache(")]
    assert order == sorted(order), order
