"""ISSUE #156 TWIN: a capture on a LANE-LOCAL data overlay is a DECLARED,
RECORDED input.

Two provider lanes (``las130``, ``cwcb154``) needed a capture on an inset
a provider had just produced lane-locally, and took it by temporarily
REPLACING the worktree's ``Elevation_data`` symlink with their overlay
directory and putting it back afterwards.  That capture is
indistinguishable from one taken on the shared corpus: the swap left no
trace in the pickle, the frame or the log, so the pickle another lane
replays says "shared corpus" when it was nothing of the kind.

``tools/v2_solve_replay.py --capture`` grew ``--data-overlay DIR`` for
it: the corpus directories the overlay PROVIDES are read from the
overlay, everything else stays on the shared corpus, and the overlay is
RECORDED in the capture under :data:`CAPTURE_OVERLAY_KEY` so the replay
reads it back and says so.

WHY NOT ``--corpus snapshot:DIR`` (``harness/build_airport.py``'s
spelling).  A snapshot is a hash-stamped, manifest-VERIFIED cut that
REPLACES the whole corpus: ``corpus_snapshot.verify`` refuses one whose
manifest does not carry a complete read set for the airport, and
``mount`` re-points every corpus dir of the worktree at it.  A provider's
fresh inset has no manifest and no complete read set -- it is a handful
of files that must be read BEFORE the shared corpus, with the rest of the
corpus untouched.  Different act, different flag; both are recorded.

Offline and synthetic: fixture directories only, no corpus, no network,
no engine import.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import os
import pickle
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "v2_solve_replay.py"


def _load():
    spec = importlib.util.spec_from_file_location("_v2_solve_replay_ovl", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def R():
    return _load()


@dataclasses.dataclass(frozen=True)
class _Inputs:
    """The fields of ``airport/load.Inputs`` the overlay touches, so the
    twin stays an offline unit (no engine import)."""

    osm_root: str = "/shared/OSM_data"
    elevation_root: str = "/shared/Elevation_data"
    mod_cache_root: str = "/shared/Airport_mod_cache"


def _overlay(tmp_path: Path, *names: str) -> Path:
    """An overlay dir providing ``names``, each with one witness file."""
    d = tmp_path / "overlay"
    for name in names:
        sub = d / name
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "N39W107.hgt.txt").write_text("lane-local inset\n",
                                             encoding="utf-8", newline="\n")
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- the flag

def test_the_flag_and_keys_are_named_constants(R):
    assert R.DATA_OVERLAY_FLAG == "--data-overlay"
    assert R.DATA_OVERLAY_ENV == "O4_DATA_OVERLAY"
    assert R.CAPTURE_OVERLAY_KEY == "data_overlay"
    assert "Elevation_data" in R.OVERLAY_DIRS


def test_no_flag_means_no_overlay(R):
    assert R.resolve_data_overlay(None, environ={}) is None


def test_an_overlay_is_resolved_to_the_dirs_it_provides(R, tmp_path):
    d = _overlay(tmp_path, "Elevation_data")
    frame = R.resolve_data_overlay(str(d), environ={})
    assert frame["dir"] == str(d.resolve())
    assert set(frame["provides"]) == {"Elevation_data"}
    assert frame["provides"]["Elevation_data"] == str((d / "Elevation_data").resolve())


def test_the_env_default_is_honoured(R, tmp_path):
    d = _overlay(tmp_path, "Elevation_data")
    frame = R.resolve_data_overlay(None, environ={R.DATA_OVERLAY_ENV: str(d)})
    assert frame and frame["dir"] == str(d.resolve())


def test_a_missing_overlay_refuses(R, tmp_path):
    with pytest.raises(SystemExit) as e:
        R.resolve_data_overlay(str(tmp_path / "nope"), environ={})
    assert "--data-overlay" in str(e.value)


def test_an_overlay_providing_nothing_refuses(R, tmp_path):
    bare = tmp_path / "bare"
    (bare / "Something_else").mkdir(parents=True)
    with pytest.raises(SystemExit) as e:
        R.resolve_data_overlay(str(bare), environ={})
    assert "Elevation_data" in str(e.value)


def test_resolution_reads_and_writes_nothing(R, tmp_path):
    """A READ-side declaration: it authorises no write, of the overlay or
    of anything else (the standing note on ``--allow-degraded-dem``)."""
    d = _overlay(tmp_path, "Elevation_data", "OSM_data")
    before = sorted(p.relative_to(tmp_path).as_posix()
                    for p in tmp_path.rglob("*"))
    env = dict(os.environ)
    R.resolve_data_overlay(str(d), environ=os.environ)
    assert dict(os.environ) == env, "the overlay must not arm the environment"
    after = sorted(p.relative_to(tmp_path).as_posix()
                   for p in tmp_path.rglob("*"))
    assert after == before


# ------------------------------------------------- the inputs it rewrites

def test_only_the_provided_dirs_move_off_the_shared_corpus(R, tmp_path):
    d = _overlay(tmp_path, "Elevation_data")
    frame = R.resolve_data_overlay(str(d), environ={})
    out = R.overlay_inputs(_Inputs(), frame)
    assert out.elevation_root == frame["provides"]["Elevation_data"]
    assert out.osm_root == "/shared/OSM_data"              # untouched
    assert out.mod_cache_root == "/shared/Airport_mod_cache"


def test_an_overlay_providing_two_dirs_moves_both(R, tmp_path):
    d = _overlay(tmp_path, "Elevation_data", "OSM_data")
    frame = R.resolve_data_overlay(str(d), environ={})
    out = R.overlay_inputs(_Inputs(), frame)
    # Compare as PATHS, not as strings: a hard-coded "/" in the expected
    # tail makes this assertion fail on Windows for the separator rather
    # than for the overlay (it did, on the windows-latest leg).
    assert Path(out.elevation_root) == d / "Elevation_data"
    assert Path(out.osm_root) == d / "OSM_data"


def test_no_frame_leaves_the_inputs_alone(R):
    base = _Inputs()
    assert R.overlay_inputs(base, None) is base


def test_the_overlay_dir_really_holds_what_the_capture_would_read(R, tmp_path):
    """The declared overlay's own file is what a read through the rewritten
    root reaches -- the point of the declaration."""
    d = _overlay(tmp_path, "Elevation_data")
    frame = R.resolve_data_overlay(str(d), environ={})
    root = Path(R.overlay_inputs(_Inputs(), frame).elevation_root)
    assert (root / "N39W107.hgt.txt").read_text(encoding="utf-8") == \
        "lane-local inset\n"


# --------------------------------------------------- recorded, and read back

def test_the_overlay_is_recorded_in_the_capture_and_read_back(R, tmp_path):
    """A capture taken on an overlay can never be mistaken for one taken
    on the shared corpus."""
    d = _overlay(tmp_path, "Elevation_data")
    frame = R.resolve_data_overlay(str(d), environ={})
    pkl = tmp_path / "ICAO.pkl"
    with pkl.open("wb") as fh:
        pickle.dump({"icao": "KHDN", R.CAPTURE_OVERLAY_KEY: frame}, fh)
    with pkl.open("rb") as fh:
        cap = pickle.load(fh)
    assert R.capture_data_overlay(cap) == frame
    line = R.overlay_line("KHDN", frame)
    assert str(d.resolve()) in line and "Elevation_data" in line


def test_a_capture_without_the_flag_records_none(R, tmp_path):
    pkl = tmp_path / "shared.pkl"
    with pkl.open("wb") as fh:
        pickle.dump({"icao": "KHDN", R.CAPTURE_OVERLAY_KEY: None}, fh)
    with pkl.open("rb") as fh:
        assert R.capture_data_overlay(pickle.load(fh)) is None


def test_a_capture_predating_the_flag_reads_as_no_overlay(R):
    assert R.capture_data_overlay({"icao": "KHDN"}) is None


# ------------------------------------------------------------- the CLI path

def test_the_cli_hands_the_overlay_to_the_GUARDED_capture(R, tmp_path,
                                                          monkeypatch):
    """The overlay is a read-side declaration: the shared-repo write guard
    stays armed, so the flag must arrive through ``_capture_guarded`` --
    never by a path that skips it."""
    d = _overlay(tmp_path, "Elevation_data")
    seen = {}

    def _fake(icao, out, mod_cache_root=None, placement=None, rule=None,
              cifp_dir=None, data_overlay=None):
        seen.update(icao=icao, out=out, data_overlay=data_overlay)

    monkeypatch.setattr(R, "_capture_guarded", _fake)
    monkeypatch.setattr(sys, "argv", [
        "v2_solve_replay.py", "--capture", "khdn",
        "--out", str(tmp_path / "KHDN.pkl"),
        R.DATA_OVERLAY_FLAG, str(d)])
    assert R.main() == 0
    assert seen["icao"] == "KHDN"
    assert seen["data_overlay"] == str(d)


def test_the_cli_without_the_flag_declares_no_overlay(R, tmp_path,
                                                      monkeypatch):
    seen = {}
    monkeypatch.setattr(R, "_capture_guarded",
                        lambda *a, **k: seen.update(kw=k, args=a))
    monkeypatch.setattr(sys, "argv", [
        "v2_solve_replay.py", "--capture", "khdn",
        "--out", str(tmp_path / "KHDN.pkl")])
    assert R.main() == 0
    assert seen["kw"].get("data_overlay", None) is None or \
        seen["args"][-1] is None


def test_the_tool_is_in_the_index_with_the_flag():
    """RULINGS ``7e90032``: the flag lands with its index entry in the
    same change."""
    index = ROOT.parent / "tools" / "INDEX.md"
    if not index.exists():                      # a lane worktree mirror
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    rows = [ln for ln in index.read_text(encoding="utf-8").splitlines()
            if ln.startswith("| `Ortho4XP/tools/v2_solve_replay.py`")]
    assert len(rows) == 1, f"{len(rows)} v2_solve_replay.py rows, expected one"
    assert "--data-overlay" in rows[0]
    assert "test_v2_solve_replay_overlay.py" in rows[0]


# ---- lane tools321 (2026-10-05): the Elevation_data half cannot take effect
def test_an_elevation_overlay_refuses_before_the_load(R, tmp_path):
    """MEASURED at CYXY: an overlay providing ``Elevation_data`` died
    mid-load in ``dem_production._check_corpus`` ("two corpora, refused") —
    the production frame reads the core's own data root.  The tool now
    refuses up front, by name, and says what does work."""
    frame = R.resolve_data_overlay(str(_overlay(tmp_path, "Elevation_data")))
    why = R.overlay_refusal(_Inputs(), frame)
    assert why.startswith("REFUSED: --data-overlay")
    assert "Elevation_data" in why and "e9daef5" in why
    assert "--corpus snapshot:DIR" in why and "--witness" in why


def test_an_osm_overlay_and_no_overlay_are_not_refused(R, tmp_path):
    frame = R.resolve_data_overlay(str(_overlay(tmp_path, "OSM_data")))
    assert R.overlay_refusal(_Inputs(), frame) is None
    assert R.overlay_refusal(_Inputs(), None) is None


def test_the_same_corpus_under_another_name_is_not_a_second_corpus(R, tmp_path):
    shared = tmp_path / "shared" / "Elevation_data"
    shared.mkdir(parents=True)
    ovl = tmp_path / "ovl"
    ovl.mkdir()
    (ovl / "Elevation_data").symlink_to(shared, target_is_directory=True)
    frame = R.resolve_data_overlay(str(ovl))
    inp = _Inputs(elevation_root=str(shared))
    assert R.overlay_refusal(inp, frame) is None


def test_an_authored_dem_frame_reads_the_overlay(R, tmp_path):
    """The corpus check is the PRODUCTION frame's; the authored frame reads
    ``elevation_root`` directly."""
    @dataclasses.dataclass(frozen=True)
    class _Authored(_Inputs):
        dem_frame: str = "authored"
    frame = R.resolve_data_overlay(str(_overlay(tmp_path, "Elevation_data")))
    assert R.overlay_refusal(_Authored(), frame) is None


# ---- issue #420: an overlay inside the shared repo; refuse before the arm
sys.path.insert(0, str(ROOT / "tools" / "harness"))     # shared_repo_guard

def test_an_overlay_inside_the_shared_data_repo_refuses_by_name(R, tmp_path):
    """A directory of the shared data repo is the shared corpus under
    another name, not a lane-local overlay (a tmp path stands in for
    ``/Users/noah/XPTerrainBuilderData``)."""
    repo = tmp_path / "XPTerrainBuilderData"
    inner = _overlay(repo / "lane_inset", "OSM_data")
    for d in (inner, repo):            # judged before what it provides
        with pytest.raises(SystemExit) as exc:
            R.resolve_data_overlay(str(d), data_repo=repo)
        msg = str(exc.value)
        assert msg.startswith("REFUSING: --data-overlay ")
        assert f"inside the SHARED data repo {repo.resolve()}" in msg
    # a symlink INTO the repo is judged where it lands
    link = tmp_path / "looks_local"
    link.symlink_to(inner, target_is_directory=True)
    with pytest.raises(SystemExit):
        R.resolve_data_overlay(str(link), data_repo=repo)
    # a sibling of the repo (a name prefix, not a child) is lane-local
    sib = _overlay(tmp_path / "XPTerrainBuilderData_lane", "OSM_data")
    assert R.resolve_data_overlay(str(sib), data_repo=repo)["dir"] == str(sib.resolve())


def test_the_default_shared_repo_is_the_guards(R, tmp_path, monkeypatch):
    """No ``data_repo``: the judge is ``shared_repo_guard.DATA_REPO``."""
    import shared_repo_guard
    monkeypatch.setattr(shared_repo_guard, "DATA_REPO", tmp_path)
    with pytest.raises(SystemExit) as exc:
        R.resolve_data_overlay(str(_overlay(tmp_path / "x", "OSM_data")))
    assert "SHARED data repo" in str(exc.value)
