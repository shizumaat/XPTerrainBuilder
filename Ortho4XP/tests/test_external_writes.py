"""THE EXTERNAL WRITER'S DECLARATION (#159, RULINGS 2026-09-30bs/bw).

``SharedRepoWriteGuard`` patches the PYTHON level, so a write a CHILD
PROCESS makes never passes it: lane tx154's clip cutter spawned
``osmium extract --output <corpus>/...tmp-52850-....osm.pbf`` with the
guard armed and 10.5 MB landed in the shared
``OSM_data/_regional_extracts/clips/``, after which the Python ``os.remove``
that would have cleaned it up was the only call the guard ever saw.

These twins cover the two halves of the fix that live outside the cutter:
``src/O4_External_Writes.py`` (the engine-side helper, which must be a
no-op with no guard armed and must raise the HARNESS's own exception when
one refuses) and the guard's ``refuse_external_write`` /
``external_write_refusal`` pair.  The cutter's own behaviour — an armed run
leaves ZERO files in the shared clips dir — is twinned in
``tests/test_osm_extract_filter.py``.

No corpus and no network: every twin builds a tmp corpus.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"
SRC = ROOT / "src"

#: The data dir every twin writes its would-be corpus path under.
_CORPUS_DIR = "OSM_data"
#: A path no ``--refresh-data`` scope authorises on a plain build.
_CORPUS_REL = f"{_CORPUS_DIR}/_regional_extracts/clips/clip_+030-0095_ab.pbf"
#: What the engine calls the child in a declaration.
_WRITER = "osmium"


@pytest.fixture()
def guard_mod():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    return importlib.import_module("shared_repo_guard")


@pytest.fixture()
def extwrite():
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    return importlib.import_module("O4_External_Writes")


@pytest.fixture()
def corpus(tmp_path, guard_mod, monkeypatch):
    """A tmp corpus the guard treats as THE shared repo."""
    repo = tmp_path / "corpus"
    (repo / _CORPUS_DIR / "_regional_extracts" / "clips").mkdir(parents=True)
    monkeypatch.setattr(guard_mod, "DATA_REPO", repo)
    return repo


def _armed(guard_mod, corpus, lane, **kwargs):
    return guard_mod.SharedRepoWriteGuard(set(), str(lane), repo=corpus,
                                          **kwargs)


# ── the helper with NO guard armed: a no-op, which is every real build ──

def test_declaring_a_write_with_no_guard_armed_does_nothing(
        extwrite, tmp_path):
    """Every production run and every Qt-app run is this case."""
    extwrite.declare_external_write(tmp_path / "anything.pbf",
                                    writer=_WRITER)
    extwrite.declare_external_writes([tmp_path / "a", tmp_path / "b"],
                                     writer=_WRITER)
    assert extwrite.refusal_for(tmp_path / "anything.pbf") is None


def test_declaring_None_is_a_no_op(extwrite):
    """A caller with no output path to declare must not have to branch."""
    extwrite.declare_external_write(None, writer=_WRITER)


# ── the helper UNDER an armed guard ────────────────────────────────────

def test_an_armed_guard_refuses_the_declaration_and_RECORDS_it(
        extwrite, guard_mod, corpus, tmp_path):
    """THE FIX.  The child is never spawned, and the refusal is RECORDED —
    so a caller that swallows it is caught by the harness's
    swallowed-refusal detector exactly as a Python-level write would be."""
    guard = _armed(guard_mod, corpus, tmp_path / "lane")
    with guard:
        with pytest.raises(guard_mod.SharedRepoWriteBlocked) as excinfo:
            extwrite.declare_external_write(corpus / _CORPUS_REL,
                                            writer=_WRITER)
    assert [b["path"] for b in guard.blocked] == [_CORPUS_REL]
    assert guard.blocked[0]["via"] == guard_mod.EXTERNAL_WRITER_VIA % _WRITER
    assert guard.blocked[0]["scope"] == "osm_layers"
    assert _WRITER in str(excinfo.value) or _CORPUS_REL in str(excinfo.value)


def test_a_swallowed_declaration_refusal_FAILS_the_run(
        extwrite, guard_mod, corpus, tmp_path):
    """The whole reason the declaration RECORDS rather than merely asking:
    the measured cutter caught every exception and fell back."""
    guard = _armed(guard_mod, corpus, tmp_path / "lane")
    with guard:
        try:
            extwrite.declare_external_write(corpus / _CORPUS_REL,
                                            writer=_WRITER)
        except Exception:
            pass                        # exactly what _cut_clip used to do
    with pytest.raises(SystemExit):
        guard_mod.require_no_swallowed_write_block(guard.blocked)


def test_the_FIRST_refused_path_raises_so_the_child_never_starts(
        extwrite, guard_mod, corpus, tmp_path):
    lane = tmp_path / "lane"
    lane.mkdir()
    guard = _armed(guard_mod, corpus, lane)
    with guard:
        with pytest.raises(guard_mod.SharedRepoWriteBlocked):
            extwrite.declare_external_writes(
                [corpus / _CORPUS_REL, lane / "second.pbf"], writer=_WRITER)
    assert len(guard.blocked) == 1, (
        "the first refusal must stop the walk: a child that is never "
        "started cannot write the later paths")


def test_a_LANE_LOCAL_output_is_never_refused(
        extwrite, guard_mod, corpus, tmp_path):
    """The whole point of cutting into lane-local scratch: a declaration of
    a path outside the corpus passes under the same armed guard."""
    scratch = tmp_path / "lane" / "tmp" / "o4_osm_clip_cut-xyz"
    scratch.mkdir(parents=True)
    guard = _armed(guard_mod, corpus, tmp_path / "lane")
    with guard:
        extwrite.declare_external_write(scratch / "part0.osm.pbf",
                                        writer=_WRITER)
    assert guard.blocked == []


def test_asking_records_NOTHING(extwrite, guard_mod, corpus, tmp_path):
    """``refusal_for`` is the best-effort question: a caller using it to
    CHOOSE a lawful path (``auto_patch/dsf_reader``'s DSFTool dump) must
    not leave a recorded block behind, because a recorded block fails the
    run."""
    guard = _armed(guard_mod, corpus, tmp_path / "lane")
    with guard:
        hit = extwrite.refusal_for(corpus / _CORPUS_REL)
    assert hit == (_CORPUS_REL, "osm_layers")
    assert guard.blocked == []
    guard_mod.require_no_swallowed_write_block(guard.blocked)   # no raise


def test_an_AUTHORISED_scope_is_not_refused(
        extwrite, guard_mod, corpus, tmp_path):
    """``--refresh-data osm_layers`` is how a lane changes that family."""
    guard = guard_mod.SharedRepoWriteGuard({"osm_layers"},
                                           str(tmp_path / "lane"),
                                           repo=corpus)
    with guard:
        extwrite.declare_external_write(corpus / _CORPUS_REL, writer=_WRITER)
    assert guard.blocked == []


def test_a_record_only_guard_records_and_lets_the_spawn_run(
        extwrite, guard_mod, corpus, tmp_path):
    """The suite's own observing guard (suite-corpus-clean spec)."""
    guard = _armed(guard_mod, corpus, tmp_path / "lane", record_only=True)
    with guard:
        extwrite.declare_external_write(corpus / _CORPUS_REL, writer=_WRITER)
    assert [b["path"] for b in guard.blocked] == [_CORPUS_REL]


def test_the_guard_resolves_a_SYMLINKED_lane_mount(
        extwrite, guard_mod, corpus, tmp_path):
    """THE MEASURED SHAPE (#159): the lane writes ``OSM_data/...`` through
    a symlink into the corpus, so the string at the call site says
    lane-local.  The declaration must judge what the write REACHES."""
    lane = tmp_path / "lane"
    lane.mkdir()
    link = lane / _CORPUS_DIR
    try:
        link.symlink_to(corpus / _CORPUS_DIR, target_is_directory=True)
    except (OSError, NotImplementedError):          # Windows without privs
        pytest.skip("symlinks unavailable on this platform")
    guard = _armed(guard_mod, corpus, lane)
    through_the_link = link / "_regional_extracts" / "clips" / "x.osm.pbf"
    with guard:
        with pytest.raises(guard_mod.SharedRepoWriteBlocked):
            extwrite.declare_external_write(through_the_link, writer=_WRITER)
    assert guard.blocked[0]["path"].startswith(_CORPUS_DIR + "/")


def test_ANY_nested_guard_refusing_is_a_refusal(
        extwrite, guard_mod, corpus, tmp_path):
    """Nested guards, matched to what a PYTHON write meets: the inner guard
    authorises ``osm_layers``, but its wrapper hands the call to the outer
    guard's, which refuses — so the declaration must refuse too, and the
    record must land on the guard that refused."""
    outer = _armed(guard_mod, corpus, tmp_path / "lane")
    inner = guard_mod.SharedRepoWriteGuard({"osm_layers"},
                                           str(tmp_path / "lane"),
                                           repo=corpus)
    with outer:
        with inner:
            with pytest.raises(guard_mod.SharedRepoWriteBlocked):
                extwrite.declare_external_write(corpus / _CORPUS_REL,
                                                writer=_WRITER)
    assert inner.blocked == []
    assert [b["path"] for b in outer.blocked] == [_CORPUS_REL]


def test_a_mock_in_sys_modules_is_not_mistaken_for_the_harness(
        extwrite, monkeypatch):
    """The lookup needs BOTH the guard registry and the asker on one module
    object — the precedent ``_write_refused_by_armed_guard`` was written
    for (a mock parked in ``sys.modules`` is not a module)."""
    monkeypatch.setitem(sys.modules, "not_the_harness", object())
    extwrite.declare_external_write(os.devnull, writer=_WRITER)
