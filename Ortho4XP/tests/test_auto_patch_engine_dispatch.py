"""auto_patch_engine = v1 | v2 — the tile build's engine dispatch (RULINGS
2026-09-03d: v2 beside v1; 2026-09-04 lane v2app: the owner sim-reads v2
patches from the app).

Twins:

1. the settings key round-trips: registry entry → a per-tile cfg line →
   ``Tile.read_from_config`` → ``resolved_auto_patch_engine``; a typo
   REFUSES rather than building v1 quietly;
2. with ``engine: v2`` on the task, ``_run_build_tasks`` (the real driver
   loop, the real ``_build_write_verify_one``) places the v2 patch and
   sidecar at ``auto_patch_file``, prints the ``[provenance] … engine=v2
   law=…`` line, and writes the v2 verify census into the verify debug
   log — through a STUB v2 pipeline (the real one is the harness's
   closing test);
3. a straddler's CURRENT-tile piece is what lands (never the whole-airport
   patch, never another tile's piece);
4. a non-optimal solve is a named ``solve``-stage FAILURE with the IIS in
   the verify debug log and an ``AutoPatchFailed`` event — never a skip;
5. a v2 refusal (a cold frame, a law error) is a named ``build``-stage
   failure;
6. a patch one engine wrote is never "current" for the other
   (``o4_ap_engine`` compared, readable back from the root);
7. the freeze spec bundles the v2 law tables and pins the v2 modules.
"""
import json
import os
import re
import sys
import types
from pathlib import Path

import pytest

from auto_patch import driver as DRIVER            # noqa: E402
from auto_patch import engine_v2 as E2              # noqa: E402
from auto_patch import provenance as PROV           # noqa: E402
import O4_UI_Utils as UI                            # noqa: E402

ENGINE_ROOT = Path(__file__).resolve().parents[1]


# ── fixtures ────────────────────────────────────────────────────────────


class _Tile:
    dem = None
    lat = 30
    lon = 31


def _task(tmp_path, icao, **overrides):
    task = {
        "icao": icao, "xp_root": str(tmp_path), "taxiway_data": None,
        "boundary": None, "tile_lat": 30, "tile_lon": 31,
        "auto_patch_file": str(tmp_path / "Patches" / "+30+030" / "+30+031"
                               / (icao + "_auto.patch.osm")),
        "verify_log_path": str(tmp_path / (icao + ".part")),
        "freshness": None, "engine": "v2", "cifp_path": str(tmp_path),
        "apt_dat_path": None,
    }
    task.update(overrides)
    return task


@pytest.fixture(autouse=True)
def _serial(monkeypatch, tmp_path):
    from auto_patch import config as CFG
    monkeypatch.setattr(CFG, "PARALLEL_AIRPORTS", False, raising=False)
    monkeypatch.setattr(DRIVER, "_WORKER_DEM", None, raising=False)
    monkeypatch.setattr(E2, "_scratch_dir",
                        lambda task: str(tmp_path / "scratch" / task["icao"]))


@pytest.fixture
def console(monkeypatch):
    """Every line the driver's main loop printed (lvprint + vprint)."""
    seen = []
    monkeypatch.setattr(UI, "lvprint", lambda lvl, *a: seen.append(" ".join(map(str, a))))
    monkeypatch.setattr(UI, "vprint", lambda lvl, *a: seen.append(" ".join(map(str, a))))
    return seen


@pytest.fixture
def failed_events(monkeypatch):
    seen = []
    monkeypatch.setattr(UI, "auto_patch_failed",
                        lambda icao, stage, error: seen.append((icao, stage, error)))
    return seen


def _stub_v2(monkeypatch, *, status="optimal", pieces_tiles=None, raise_exc=None):
    """The v2 pipeline as stub modules.  ``build`` writes what the real
    adapter writes into ``out_dir`` (and, for ``pieces_tiles``, one piece
    per tile at the adapter's own ``<block>/<tile>/`` path) and returns
    the fields ``build_write_verify_one_v2`` reads."""
    class _Status:
        def __init__(self, v): self.value = v

    class _Sol:
        def __init__(self, v):
            self.status = _Status(v); self.message = f"stub {v}"

    class _Paths:
        def __init__(self, patch, side, ways):
            self.patch, self.sidecar, self.ways, self.nodes = patch, side, ways, ways * 3

    class _Res:
        pass

    class _Config:
        def __init__(self, header_extra=None): self.header_extra = header_extra

    class _Inputs:
        def __init__(self, **kw): self.kw = kw

    class _Law:
        ruleset_key = "icao"

        @classmethod
        def for_airport(cls, icao): return cls()

    calls = {}

    def build(icao, inputs, out_dir, config=None, law=None, out=print):
        calls["inputs"] = inputs.kw
        calls["header_extra"] = dict(config.header_extra or {})
        if raise_exc is not None:
            raise raise_exc
        for stage in ("load", "planar", "constraints", "solve"):
            out(f"[{icao}] {stage} 0.10 s  stub")
        d = Path(out_dir); d.mkdir(parents=True, exist_ok=True)

        def _write(where, ways, tag):
            where.mkdir(parents=True, exist_ok=True)
            patch = where / f"{icao}_auto.patch.osm"
            hdr = " ".join(f"{k}='{v}'" for k, v in calls["header_extra"].items())
            patch.write_text(f"<?xml version='1.0'?>\n<osm generator='auto_patch_v2' "
                             f"o4_stub='{tag}' {hdr}>\n</osm>\n")
            side = Path(str(patch) + ".axes.json")
            side.write_text(json.dumps({"ruleset": "icao", "axes": [], "tag": tag}))
            return _Paths(patch, side, ways)

        r = _Res()
        r.solution = _Sol(status)
        r.paths = _write(d, 5, "whole") if status == "optimal" else None
        r.pieces = None
        if status == "optimal" and pieces_tiles:
            r.pieces = {}
            for n, (la, lo) in enumerate(pieces_tiles):
                block = f"{(la // 10) * 10:+03d}{(lo // 10) * 10:+04d}"
                r.pieces[(la, lo)] = _write(d / block / f"{la:+03d}{lo:+04d}",
                                            10 + n, f"piece{la:+03d}{lo:+04d}")
        r.report = {
            "load": {"dem_provenance": {"frame": "production",
                                        "tile:N30E031": "host-seeded: grid 2x2, "
                                        "insets=OTHH:lidar"}},
            "solve": {"status": status, "message": f"stub {status}",
                      "iis": [{"row": "z[1]-z[2] <= 0.01", "generator": "taxi_long",
                               "ruling": "08-21b", "inputs": ["e1"]}]},
            "verify": {"by_family": {"strip_seam_tear": 1, "transverse": 0},
                       "rows": {"strip_seam_tear": [{"family": "strip_seam_tear",
                                                     "site": [30.1, 31.2]}]}},
        }
        r.wall = {"total": 0.4}
        r.lp_size = {"rows": 1}
        (d / f"{icao}.report.json").write_text(json.dumps(r.report))
        return r

    mods = {
        "auto_patch_v2": types.ModuleType("auto_patch_v2"),
        "auto_patch_v2.airport": types.ModuleType("auto_patch_v2.airport"),
        "auto_patch_v2.airport.load": types.ModuleType("auto_patch_v2.airport.load"),
        "auto_patch_v2.pipeline": types.ModuleType("auto_patch_v2.pipeline"),
        "auto_patch_v2.pipeline.build": types.ModuleType("auto_patch_v2.pipeline.build"),
        "auto_patch_v2.law": types.ModuleType("auto_patch_v2.law"),
    }
    mods["auto_patch_v2.airport.load"].Inputs = _Inputs
    mods["auto_patch_v2.pipeline.build"].build = build
    mods["auto_patch_v2.pipeline.build"].Config = _Config
    mods["auto_patch_v2.law"].Law = _Law
    mods["auto_patch_v2.law"].law_tables_digest = lambda law_dir=None: {
        "dir": "stub", "files": ["emit.toml"], "sha256": "feedfacecafebeef" * 4}
    for name, m in mods.items():
        monkeypatch.setitem(sys.modules, name, m)
    return calls


def _run(tasks, tmp_path):
    return DRIVER._run_build_tasks(tasks, _Tile(), [], str(tmp_path / "verify.log"))


# ── 1. the settings key ─────────────────────────────────────────────────


def test_the_key_is_registered_with_the_tile_scope_and_two_values():
    import O4_Cfg_Vars as CV
    spec = CV.cfg_tile_vars["auto_patch_engine"]
    assert spec["type"] is str and spec["default"] == "v1"
    assert tuple(spec["values"]) == ("v1", "v2") == E2.ENGINES
    assert set(spec["value_labels"]) == {"v1", "v2"}
    assert "auto_patch_engine" in CV.list_tile_vars, \
        "not in list_tile_vars: the per-tile cfg writer would drop it"
    assert "auto_patch_engine" in CV.cfg_vars


def test_the_key_round_trips_through_a_per_tile_cfg(tmp_path):
    import O4_Config_Utils as CFG
    build_dir = tmp_path / "zOrtho4XP_+30+031"
    build_dir.mkdir()
    (build_dir / "Ortho4XP_+30+031.cfg").write_text(
        "auto_patch=ICAO\nauto_patch_engine=v2\n")
    tile = CFG.Tile(30, 31, str(build_dir))
    assert tile.read_from_config() == 1
    assert tile.auto_patch_engine == "v2"
    assert E2.resolved_auto_patch_engine(tile) == "v2"


def test_the_resolver_defaults_to_v1_and_refuses_a_typo():
    assert E2.resolved_auto_patch_engine(_Tile()) == "v1"

    class _T:
        auto_patch_engine = " V2 "
    assert E2.resolved_auto_patch_engine(_T()) == "v2"

    class _Bad:
        auto_patch_engine = "v3"
    with pytest.raises(ValueError) as exc:
        E2.resolved_auto_patch_engine(_Bad())
    assert "auto_patch_engine='v3'" in str(exc.value)


# ── 2. the dispatch places the patch, the provenance line, the verify log ──


def test_v2_dispatch_places_patch_sidecar_provenance_and_verify_log(
        tmp_path, monkeypatch, console, failed_events):
    calls = _stub_v2(monkeypatch)
    task = _task(tmp_path, "OTHH", freshness={"o4_cfg": "abc", "o4_dem": "d",
                                              "o4_cifp": "c", "o4_pack": "p",
                                              "o4_engine": "1.50.0",
                                              "o4_ap_engine": "v2"})
    built = []
    DRIVER._run_build_tasks([task], _Tile(), built, str(tmp_path / "verify.log"))

    assert built == ["OTHH"] and failed_events == []
    patch = Path(task["auto_patch_file"])
    assert patch.is_file() and Path(str(patch) + ".axes.json").is_file()
    assert "o4_stub='whole'" in patch.read_text()
    # THE HOST'S FRAME, REUSED: the worker's tile DEM is seeded into the
    # loader as the current tile, core-hosted (no CLI cwd assertions).
    assert calls["inputs"]["core_hosted"] is True
    assert calls["inputs"]["dem_frame"] == "production"
    assert calls["inputs"]["xplane_root"] == str(tmp_path)
    # the freshness block the driver's gate reads back, all-or-nothing
    hdr = calls["header_extra"]
    assert hdr["o4_fresh_v"] == PROV.FRESHNESS_SCHEMA_VERSION
    assert hdr["o4_ap_engine"] == "v2" and hdr["o4_dsf_tiles"] == "30,31"
    assert set(PROV.FRESHNESS_KEYS) <= set(hdr)
    prov = [ln for ln in console if "[provenance] OTHH" in ln]
    assert len(prov) == 1, console
    assert "engine=v2" in prov[0] and "law=feedfacecafe" in prov[0] \
        and "ruleset=icao" in prov[0] and "solve=optimal" in prov[0] \
        and "insets=OTHH:lidar" in prov[0], prov[0]
    log = (tmp_path / "verify.log").read_text()
    assert "OTHH v2 verify: 1 row(s)" in log and "[v2:strip_seam_tear]" in log
    assert not Path(task["verify_log_path"]).exists(), "part concatenated, removed"
    assert any("[v2] [OTHH] solve" in ln for ln in console), \
        "v2's stage lines are printed by the MAIN process"


# ── 3. a straddler: the CURRENT tile's piece lands ─────────────────────


def test_a_straddler_places_the_current_tiles_piece(tmp_path, monkeypatch,
                                                    console, failed_events):
    _stub_v2(monkeypatch, pieces_tiles=[(30, 31), (30, 32)])
    task = _task(tmp_path, "OTHH")
    _run([task], tmp_path)
    assert failed_events == []
    text = Path(task["auto_patch_file"]).read_text()
    assert "o4_stub='piece+30+031'" in text, text
    assert json.loads(Path(task["auto_patch_file"] + ".axes.json").read_text())[
        "tag"] == "piece+30+031"


def test_a_straddler_with_no_face_on_this_tile_fails_named(tmp_path, monkeypatch,
                                                           console, failed_events):
    _stub_v2(monkeypatch, pieces_tiles=[(30, 32)])
    task = _task(tmp_path, "OTHH")
    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run([task], tmp_path)
    assert raised.value.failures[0]["stage"] == "write"
    assert "+30+031" in raised.value.failures[0]["error"]
    assert not Path(task["auto_patch_file"]).exists()


# ── 4. a non-optimal solve is a FAILURE with its IIS ───────────────────


def test_an_infeasible_solve_is_a_named_failure_with_the_iis_logged(
        tmp_path, monkeypatch, console, failed_events):
    _stub_v2(monkeypatch, status="infeasible")
    task = _task(tmp_path, "OTHH")
    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run([task], tmp_path)
    f = raised.value.failures
    assert [(x["icao"], x["stage"]) for x in f] == [("OTHH", "solve")]
    assert "infeasible" in f[0]["error"] and "report.json" in f[0]["error"]
    assert failed_events == [("OTHH", "solve", f[0]["error"])]
    assert not Path(task["auto_patch_file"]).exists(), "no patch on infeasible"
    log = (tmp_path / "verify.log").read_text()
    assert "IIS taxi_long [08-21b]" in log and "z[1]-z[2]" in log, log
    assert any("v2 solve FAILED for OTHH" in ln for ln in console)


# ── 5. a v2 refusal is a build-stage failure ───────────────────────────


def test_a_v2_refusal_is_a_named_build_failure(tmp_path, monkeypatch, console,
                                               failed_events):
    _stub_v2(monkeypatch, raise_exc=RuntimeError(
        "REFUSING: the production DEM frame for N30E031 is COLD"))
    task = _task(tmp_path, "OTHH")
    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run([task], tmp_path)
    f = raised.value.failures[0]
    assert f["stage"] == "build" and "[v2]" in f["error"] and "COLD" in f["error"]
    assert "COLD" in (tmp_path / "verify.log").read_text()


def test_missing_law_tables_refuse_loudly_never_fall_back(tmp_path, monkeypatch,
                                                          console, failed_events):
    """A frozen engine without the TOML datas: ``law_tables_digest`` has no
    sha, and the worker refuses BEFORE any v2 code runs."""
    _stub_v2(monkeypatch)
    sys.modules["auto_patch_v2.law"].law_tables_digest = \
        lambda law_dir=None: {"dir": "/frozen/_internal/auto_patch_v2/law",
                              "files": [], "sha256": None}
    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run([_task(tmp_path, "OTHH")], tmp_path)
    err = raised.value.failures[0]["error"]
    assert "law tables are MISSING" in err and "never falls back" in err


# ── 6. a patch one engine wrote is never current for the other ─────────


def test_engine_is_a_compared_freshness_stamp_readable_from_the_root(tmp_path):
    from auto_patch.layout import read_patch_source
    assert "o4_ap_engine" in PROV.FRESHNESS_COMPARED_KEYS
    stamped = {k: "x" for k in PROV.FRESHNESS_COMPARED_KEYS}
    live = dict(stamped, o4_ap_engine="v2")
    stamped["o4_ap_engine"] = "v1"
    assert PROV.freshness_mismatch(stamped, live) == "o4_ap_engine"
    assert PROV.freshness_mismatch(live, dict(live)) is None
    p = tmp_path / "X_auto.patch.osm"
    hdr = " ".join(f"{k}='v'" for k in PROV.FRESHNESS_KEYS)
    p.write_text(f"<?xml version='1.0'?>\n<osm o4_apt_dat='a' {hdr}>\n</osm>\n")
    assert read_patch_source(str(p))["freshness"]["o4_ap_engine"] == "v"


def test_the_driver_stamps_the_engine_into_every_task_and_freshness_block():
    """Source-level: the resolved engine rides on the task record and in
    ``_freshness_stamps_now`` (the writer of ``o4_ap_engine``)."""
    import inspect
    src = inspect.getsource(DRIVER.generate_auto_patches)
    assert '"engine": engine' in src and '"cifp_path": cifp_path' in src \
        and '"apt_dat_path": apt_dat_selected' in src
    assert "resolved_auto_patch_engine(tile)" in inspect.getsource(
        DRIVER._freshness_stamps_now)
    assert 'task.get("engine") == _engine_v2.ENGINE_V2' in inspect.getsource(
        DRIVER._build_write_verify_one)


# ── 7. the freeze bundles the law ──────────────────────────────────────


def test_the_freeze_spec_bundles_the_v2_law_tables_and_modules():
    spec = (ENGINE_ROOT / "Ortho4XP.spec").read_text()
    assert re.search(r'auto_patch_v2.*law.*\*\.toml', spec), \
        "the six law tables must be PyInstaller datas"
    assert re.search(r'auto_patch_v2.*classify.*\*\.toml', spec)
    assert "collect_submodules('auto_patch_v2')" in spec
    assert "v2_law_datas" in spec and "raise SystemExit" in spec, \
        "a freeze without the tables must fail at freeze time"
    tables = sorted(p.name for p in (ENGINE_ROOT / "src/auto_patch_v2/law").glob("*.toml"))
    assert len(tables) == 6, tables
    assert (ENGINE_ROOT / "src/auto_patch_v2/classify/rules.toml").is_file()


def test_the_real_law_digest_names_every_table_and_is_none_when_absent(tmp_path):
    from auto_patch_v2.law import law_tables_digest
    real = law_tables_digest()
    assert len(real["files"]) == 6 and len(real["sha256"]) == 64
    assert law_tables_digest(tmp_path)["sha256"] is None
    (tmp_path / "a.toml").write_text("x = 1\n")
    one = law_tables_digest(tmp_path)["sha256"]
    (tmp_path / "a.toml").write_text("x = 2\n")
    assert law_tables_digest(tmp_path)["sha256"] != one
