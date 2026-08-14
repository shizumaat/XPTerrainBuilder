"""Twin for the SOLVE-STAGE REPRO CUTTER (perf P2 instrument 1).

Spec: ``docs/specs/perf-p2-instruments-and-cache-spec.md`` Lane B item 1.
Engine half ``src/auto_patch/solve_capture.py``, CLI ``tools/solve_cut.py``,
capture flag ``tools/harness/build_airport.py --solve-capture``.

The end-to-end assertion is the one the spec names: a synthetic airport
is BUILT with the capture armed and then REPLAYED from that capture, and
the two patch BODIES must be identical byte for byte (the body being the
file past the two provenance lines — ``build_airport.body_sha256``'s
rule, which is also the rule the frozen 1.0.245 manifest is written in).

The structural assertions are the ones that keep it true later: the
captured key set is checked against ``solve_and_finalize``'s own
signature, and the call site is checked to hand the capture the very
dict it then calls with.  Add a parameter to the boundary and forget the
capture, and these fail instead of a replay silently defaulting it.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SYNTHETIC_APT = FIXTURES / "synthetic_apt.dat"
SYNTHETIC_ICAO = "ZZZZ"
SYNTHETIC_TILE = (-13, -78)

for _p in (ROOT / "src", ROOT, ROOT / "tools", ROOT / "tools" / "harness"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ── the structural twins (fast) ──────────────────────────────────────

def test_the_capture_covers_every_kwarg_the_boundary_takes():
    """PICKLED + SCALAR + DERIVED == ``solve_and_finalize``'s parameters.

    A new solve input that nobody captured would be filled from the
    parameter's default at replay — a different solve wearing the
    capture's name.
    """
    from auto_patch import solve_capture as sc
    from auto_patch import pipeline

    params = set(inspect.signature(pipeline.solve_and_finalize).parameters)
    covered = set(sc.PICKLED_KEYS) | set(sc.SCALAR_KEYS) | set(sc.DERIVED_KEYS)
    assert covered == params, (
        f"capture/boundary drift: only-in-boundary={sorted(params - covered)} "
        f"only-in-capture={sorted(covered - params)}")


def test_every_boundary_parameter_is_keyword_only():
    """Positional parameters would let a re-order pass silently."""
    from auto_patch import pipeline
    sig = inspect.signature(pipeline.solve_and_finalize)
    positional = [n for n, p in sig.parameters.items()
                  if p.kind is not p.KEYWORD_ONLY]
    assert positional == [], positional


def test_the_call_site_hands_the_capture_the_dict_it_then_calls_with():
    """``maybe_capture(_tail)`` and ``solve_and_finalize(**_tail)``.

    One dict, both consumers — the only construction in which the
    captured set and the called set cannot disagree.
    """
    from auto_patch import pipeline
    src = Path(inspect.getsourcefile(pipeline)).read_text()
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef)
              and n.name == "build_airport_pavement")

    assign = [n for n in ast.walk(fn)
              if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "_tail"
                      for t in n.targets)]
    assert len(assign) == 1, "expected exactly one `_tail = dict(...)`"
    keys = {kw.arg for kw in assign[0].value.keywords}
    params = set(inspect.signature(pipeline.solve_and_finalize).parameters)
    assert keys == params, sorted(keys ^ params)

    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    captured = [c for c in calls
                if isinstance(c.func, ast.Attribute)
                and c.func.attr == "maybe_capture"]
    assert len(captured) == 1
    assert [a.id for a in captured[0].args if isinstance(a, ast.Name)] \
        == ["_tail"]
    solved = [c for c in calls
              if isinstance(c.func, ast.Name)
              and c.func.id == "solve_and_finalize"]
    assert len(solved) == 1
    assert [k.value.id for k in solved[0].keywords
            if k.arg is None and isinstance(k.value, ast.Name)] == ["_tail"]


def test_maybe_capture_is_a_no_op_unless_armed(monkeypatch):
    from auto_patch import solve_capture as sc
    monkeypatch.delenv(sc.CAPTURE_ENV, raising=False)
    assert sc.maybe_capture({"icao": "ZZZZ"}) is None


def test_env_drift_names_every_moved_flag(monkeypatch):
    from auto_patch import solve_capture as sc
    monkeypatch.setenv("O4_MADE_UP_LAW_FLAG", "1")
    manifest = {"env": {"O4_MADE_UP_LAW_FLAG": "0", "O4_GONE": "x"}}
    drift = sc.env_drift(manifest)
    assert drift["O4_MADE_UP_LAW_FLAG"] == ("0", "1")
    assert drift["O4_GONE"] == ("x", None)


def test_the_capture_env_key_is_exempt_from_drift(monkeypatch):
    """Arming the capture is not a change of law."""
    from auto_patch import solve_capture as sc
    monkeypatch.setenv(sc.CAPTURE_ENV, "/somewhere")
    monkeypatch.setenv("O4_ROUND_TAG", "a-round")
    # (the suite's own conftest exports engine-cache redirects, so the
    # assertion is about these two keys, not about an empty result)
    drift = sc.env_drift({"env": {}})
    assert sc.CAPTURE_ENV not in drift and "O4_ROUND_TAG" not in drift
    assert sc._env_snapshot().keys().isdisjoint(sc.ENV_DRIFT_EXEMPT)


# ── the refusal rails (fast) ─────────────────────────────────────────

def _fake_capture(tmp_path: Path) -> Path:
    """A capture directory with a real manifest and a real state blob."""
    import gzip
    import hashlib
    import pickle
    from auto_patch import solve_capture as sc

    d = tmp_path / "cap"
    d.mkdir()
    blob = d / sc.STATE_NAME
    with gzip.open(blob, "wb") as fh:
        pickle.dump({"icao": "ZZZZ"}, fh)
    sha = hashlib.sha256(blob.read_bytes()).hexdigest()
    (d / sc.MANIFEST_NAME).write_text(json.dumps({
        "capture_version": sc.CAPTURE_VERSION, "icao": "ZZZZ",
        "state_file": sc.STATE_NAME, "state_sha256": sha, "env": {}}))
    return d


def test_a_directory_that_is_not_a_capture_refuses(tmp_path):
    from auto_patch.solve_capture import CaptureError, read_manifest
    with pytest.raises(CaptureError, match="not a solve capture"):
        read_manifest(tmp_path)


def test_a_stale_capture_version_refuses(tmp_path):
    from auto_patch import solve_capture as sc
    d = _fake_capture(tmp_path)
    m = json.loads((d / sc.MANIFEST_NAME).read_text())
    m["capture_version"] = sc.CAPTURE_VERSION - 1
    (d / sc.MANIFEST_NAME).write_text(json.dumps(m))
    with pytest.raises(sc.CaptureError, match="capture version"):
        sc.load_capture(d)


def test_a_capture_edited_after_the_cut_refuses(tmp_path):
    from auto_patch import solve_capture as sc
    d = _fake_capture(tmp_path)
    (d / sc.STATE_NAME).write_bytes(b"\x1f\x8b" + b"tampered")
    with pytest.raises(sc.CaptureError, match="does not match its manifest"):
        sc.load_capture(d)


def test_a_missing_state_file_refuses(tmp_path):
    from auto_patch import solve_capture as sc
    d = _fake_capture(tmp_path)
    (d / sc.STATE_NAME).unlink()
    with pytest.raises(sc.CaptureError, match="state file missing"):
        sc.load_capture(d)


def test_the_frozen_baseline_manifest_parses_into_a_verdict():
    """``--baseline-manifest`` reads the real 1.0.245 MANIFEST.

    The acceptance is stated against that file, so the parse is part of
    the instrument, not a convenience.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_solve_cut", ROOT / "tools" / "solve_cut.py")
    solve_cut = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(solve_cut)

    manifest = ROOT / "baselines" / "1.0.245" / "MANIFEST.txt"
    assert solve_cut._baseline_from_manifest(manifest, "consol3heca") == (
        "f562cbfeb8f990461072587bc31ef60e86aa5759c4b46b17a1aa3661dee91369")
    assert solve_cut._baseline_from_manifest(manifest, "consol3cyxy") == (
        "61efa43c3aeb5fe2a20b9224367af0ba6e62c1645d73a929ecbb82f2dccb39ba")
    with pytest.raises(SystemExit, match="no body_sha256 for"):
        solve_cut._baseline_from_manifest(manifest, "consol3nowhere")


def test_a_replay_from_the_wrong_cwd_refuses(tmp_path, monkeypatch):
    """The BUILD-CWD LAW binds a replay too (S1d 2026-08-14).

    ``O4_File_Names.resource_path`` is ``os.path.abspath(".")``, so a
    replay launched from elsewhere loses the engine's read-only
    resources and DEGRADES instead of failing: measured at OTHH, the
    production-parity DEM prep raised FileNotFoundError, the run fell
    back to the standalone DEM with no cached airports layer, and the
    replay emitted 2,027 shapes against the build's 2,186 — reported as
    a DIVERGED body hash, i.e. an operator error wearing an engine
    defect's clothes.  The refusal must come BEFORE any of that work.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_solve_cut_cwd", ROOT / "tools" / "solve_cut.py")
    solve_cut = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(solve_cut)

    monkeypatch.chdir(tmp_path)               # lacks venv/ and OSM_data/
    with pytest.raises(SystemExit, match="REFUSING"):
        solve_cut.main(["--replay", str(tmp_path / "nowhere")])


def test_the_build_entry_refuses_solve_capture_with_tile():
    """A flag that quietly does nothing is worse than one that refuses."""
    import build_airport
    with pytest.raises(SystemExit, match="--solve-capture with --tile"):
        build_airport.main(["+30+031", "--tile", "30", "31",
                            "--solve-capture", "/tmp/nowhere"])


# ── the end-to-end twin: capture -> replay -> identical body ─────────

def _build_synthetic(dest: Path, capture_dir: Path | None):
    """Build the synthetic ZZZZ airport; return (layout, patch path).

    Standalone recipe, the same one ``tools/repro_cut.py --run`` uses:
    ``O4_FORCE_APT_DAT`` for the input, a local OSM directory so nothing
    reaches the network, and a CONSTANT DEM so no corpus read is needed.
    """
    import O4_File_Names as FNAMES
    from auto_patch.constant_dem import ConstantDEM
    from auto_patch.pipeline import build_airport_pavement

    osm = dest / "osm"
    osm.mkdir(parents=True, exist_ok=True)
    (dest / "xplane").mkdir(parents=True, exist_ok=True)
    old_osm_dir = FNAMES.OSM_dir
    old_force = os.environ.get("O4_FORCE_APT_DAT")
    old_cap = os.environ.get("O4_SOLVE_CAPTURE")
    FNAMES.OSM_dir = str(osm)
    os.environ["O4_FORCE_APT_DAT"] = str(SYNTHETIC_APT)
    if capture_dir is None:
        os.environ.pop("O4_SOLVE_CAPTURE", None)
    else:
        os.environ["O4_SOLVE_CAPTURE"] = str(capture_dir)
    try:
        layout = build_airport_pavement(
            SYNTHETIC_ICAO, str(dest / "xplane"), compute_elevations=True,
            tile_dem=ConstantDEM(100.0),
            current_tile_lat=SYNTHETIC_TILE[0],
            current_tile_lon=SYNTHETIC_TILE[1])
    finally:
        FNAMES.OSM_dir = old_osm_dir
        for k, v in (("O4_FORCE_APT_DAT", old_force),
                     ("O4_SOLVE_CAPTURE", old_cap)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    patch = dest / f"{SYNTHETIC_ICAO}.osm"
    layout.to_osm(str(patch))
    return layout, patch


def test_a_synthetic_airport_replays_byte_identically(tmp_path):
    """THE acceptance, in miniature: replay(capture(build)) == build.

    Byte-identity of the patch BODY is the perf phase's gate (RULINGS
    2026-08-13).  If the split of phases [5]+[6] out of
    ``build_airport_pavement`` lost so much as one variable, or the
    capture failed to carry it, this is the assertion that says so.
    """
    from build_airport import body_sha256
    from auto_patch import solve_capture as sc

    cap = tmp_path / "capture"
    _layout, built = _build_synthetic(tmp_path / "build", cap)
    capture_dir = cap / SYNTHETIC_ICAO
    assert (capture_dir / sc.MANIFEST_NAME).exists()

    tail, manifest = sc.load_capture(capture_dir)
    assert manifest["icao"] == SYNTHETIC_ICAO
    # The build-time model is never written by a replay.
    assert tail["_build_features"] is None
    # to_m is REBUILT, and it is the same projection, not an approximation.
    lat, lon = tail["layout"].anchor
    assert tail["to_m"](lon, lat) == pytest.approx((0.0, 0.0), abs=1e-9)

    import O4_File_Names as FNAMES
    old_osm_dir = FNAMES.OSM_dir
    FNAMES.OSM_dir = str(tmp_path / "build" / "osm")
    os.environ["O4_FORCE_APT_DAT"] = str(SYNTHETIC_APT)
    try:
        from auto_patch import pipeline
        replayed_layout = pipeline.solve_and_finalize(**tail)
    finally:
        FNAMES.OSM_dir = old_osm_dir
        os.environ.pop("O4_FORCE_APT_DAT", None)
    replayed = tmp_path / "replay.osm"
    replayed_layout.to_osm(str(replayed))

    assert len(replayed_layout.shapes) == len(_layout.shapes)
    assert body_sha256(replayed) == body_sha256(built), (
        "the replayed body differs from the built body — the solve stage "
        "is not fully captured at its boundary")
