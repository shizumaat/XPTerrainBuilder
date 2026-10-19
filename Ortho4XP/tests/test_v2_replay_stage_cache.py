"""issue #844 (B3-12; stage-cache spec §7 ``tools/v2_solve_replay.py``
bullets, §8 replay twin) — THE CAPTURE'S FRONT HALF THROUGH THE STAGE
CACHE (``tools/replay_stage_cache.py``).

Synthetic, no corpus: a toy airport and toy stage functions in place of
classify / planar / flat site / road profile / shape stage, the real
``FrontCache``, store, law witness and capture-state record.

* a capture with ``--stage-cache`` writes every front-half record, and a
  second capture — or the read-only ``--replay-cache`` front half — is
  served them;
* the read-only mode writes nothing;
* ``--why-miss`` names the changed field: a code digest, an input, the law;
* a planar record whose registries record lost a field REFUSES by name.
"""
from __future__ import annotations

import dataclasses as _dc
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from auto_patch_v2.airport import stage_cache as SC
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.pipeline import capture_state as CS
from auto_patch_v2.pipeline import front_cache as FC

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "v2_solve_replay.py"
sys.path.insert(0, str(ROOT / "tools"))
import replay_stage_cache as R  # noqa: E402

ICAO = "TOYS"


class ToyDem:
    provenance = {"frame": "toy"}

    def z(self, x, y):
        return 100.0 + 0.01 * x

    def z_many(self, xs, ys):
        return 100.0 + 0.01 * np.asarray(xs, dtype=np.float64)

    def posting_m(self):
        return 30.0


@_dc.dataclass(frozen=True)
class ToyAirport:
    icao: str
    dem: object
    pack: object = None
    dsf_objects: tuple = ()
    partition: object = None
    flat_site: object = None


@_dc.dataclass(frozen=True)
class ToyRules:
    x: int = 1


@_dc.dataclass(frozen=True)
class ToyCl:
    cells: tuple
    grade: float
    z: float


@_dc.dataclass(frozen=True)
class ToyMap:
    registries: Registries
    preferred_z: object = None
    vertices: tuple = ()
    faces: tuple = ()


@_dc.dataclass(frozen=True)
class ToyStage:
    pm: ToyMap


@pytest.fixture
def toys(monkeypatch):
    """The toy stage functions in place of the engine's; ``calls`` counts
    the stages that RAN (a hit runs none)."""
    calls: list[str] = []

    def classify(airport, law, rules, cache=None):
        calls.append("classify")
        return ToyCl((1, 2), law.tables.common.pavement_max_grade,
                     float(airport.dem.z(0.0, 0.0)))

    def planar_stage(airport, cl, law, **kw):
        calls.append("planar")
        reg = Registries()
        reg.held["platform:1"] = {"unit": "u1", "k": 2}
        reg.terraces.append("terrace:1")
        return ToyMap(reg, vertices=(1, 2, 3), faces=(1,)), {"faces": 1}, CS.collect(reg)

    def verdict_for_build(airport, law, objects=(), land=None):
        calls.append("flat_site")
        return {"flat": True}, "toy"

    def preferred_road_z(airport, pm, law, grade, lane):
        calls.append("road_profile")
        return {1: 101.0}, {"profiles": {}}, {}

    def shape_stage(pm, law, airport, cl, out=print):
        calls.append("shapes")
        out("toy shape stage")
        return ToyStage(pm)

    import auto_patch_v2.airport.flat_site_read  # noqa: F401
    import auto_patch_v2.airport.road_profile  # noqa: F401
    import auto_patch_v2.classify as cls
    import auto_patch_v2.pipeline.build  # noqa: F401
    import auto_patch_v2.pipeline.shapes  # noqa: F401
    mods = sys.modules
    flat = mods["auto_patch_v2.airport.flat_site_read"]
    road = mods["auto_patch_v2.airport.road_profile"]
    build, shapes = mods["auto_patch_v2.pipeline.build"], mods["auto_patch_v2.pipeline.shapes"]
    monkeypatch.setattr(cls, "classify", classify)
    monkeypatch.setattr(CS, "planar_stage", planar_stage)
    monkeypatch.setattr(flat, "verdict_for_build", verdict_for_build)
    monkeypatch.setattr(build, "_classified_land", lambda cl: ())
    monkeypatch.setattr(road, "preferred_road_z", preferred_road_z)
    monkeypatch.setattr(shapes, "shape_stage", shape_stage)
    return calls


def _front(tmp_path, mode, *, law=None, rules=None, lines=None):
    inputs = types.SimpleNamespace(mod_cache_root=str(tmp_path / "mod"),
                                   road_grade_limit=0.05, lane_width_m=3.5)
    ocache = types.SimpleNamespace(thickness_m=1.0, input_quantum_m=None)
    out = lines.append if lines is not None else (lambda m: None)
    return R.front_half(ICAO, ToyAirport(ICAO, ToyDem()), law or Law.load(), inputs,
                        ocache=ocache, pack_objects=[], pack_report={},
                        rules=rules or ToyRules(), mode=mode, why_miss=True, out=out)


def _states(got) -> dict[str, str]:
    return {st: got["cache"]["stages"][st]["state"] for st in R.FRONT_STAGES}


def _records(tmp_path) -> list[Path]:
    return sorted((tmp_path / "mod").glob(f"o4_stage_{ICAO}_*.cache"))


def test_a_capture_writes_every_record_and_the_next_capture_is_served(tmp_path, toys):
    a = _front(tmp_path, "write")
    assert set(_states(a).values()) == {"miss"}
    assert len(_records(tmp_path)) == len(R.FRONT_STAGES)
    assert toys == list(R.FRONT_STAGES)
    del toys[:]
    b = _front(tmp_path, "write")
    assert set(_states(b).values()) == {"hit"}, _states(b)
    assert toys == [], "a hit runs no stage"
    assert b["cl"] == a["cl"] and b["stage"] == a["stage"] and b["pm"] == a["pm"]
    assert CS.collect(b["pm"].registries) == CS.collect(a["pm"].registries)
    assert isinstance(b["airport"].dem, ToyDem), "the capture keeps its own DEM"


def test_the_read_only_replay_is_served_and_writes_nothing(tmp_path, toys):
    cold = _front(tmp_path / "cold", "read")
    assert set(_states(cold).values()) == {"miss; not written: read-only"}
    assert not (tmp_path / "cold" / "mod").exists() or not _records(tmp_path / "cold")
    a = _front(tmp_path, "write")
    del toys[:]
    before = {p: p.stat().st_mtime_ns for p in _records(tmp_path)}
    r = _front(tmp_path, "read")
    assert set(_states(r).values()) == {"hit"} and toys == []
    assert {p: p.stat().st_mtime_ns for p in _records(tmp_path)} == before
    assert r["stage"] == a["stage"] and r["cl"] == a["cl"]


def test_off_runs_every_stage_and_touches_no_cache(tmp_path, toys):
    got = _front(tmp_path, "off")
    assert got["cache"]["state"] == "bypass: off"
    assert toys == list(R.FRONT_STAGES) and not _records(tmp_path)


def test_the_capture_shape_record_is_never_the_build_s(tmp_path, toys):
    _front(tmp_path, "write")
    (shape,) = [p for p in _records(tmp_path) if "_shapes_" in p.name]
    assert SC.peek(str(shape))["recipe"]["inputs"]["targets"] == R.CAPTURE_SHAPES


def test_why_miss_names_a_changed_code_digest(tmp_path, toys, monkeypatch):
    _front(tmp_path, "write")
    real = FC._code.runtime_digests()
    monkeypatch.setattr(FC._code, "runtime_digests",
                        lambda: {**real, "classify": "0" * 64})
    lines: list[str] = []
    got = _front(tmp_path, "read", lines=lines)
    st = _states(got)
    assert st["classify"].startswith("miss")
    # the same output: every later stage still hits (output-digest chaining)
    assert all(st[s] == "hit" for s in R.FRONT_STAGES[1:]), st
    assert any("recipe:code.classify" in ln for ln in lines), lines


def test_why_miss_names_a_changed_input(tmp_path, toys):
    _front(tmp_path, "write")
    lines: list[str] = []
    _front(tmp_path, "read", rules=ToyRules(2), lines=lines)
    assert any("recipe:inputs.rules" in ln for ln in lines), lines


def test_why_miss_names_the_law_a_record_read(tmp_path, toys):
    _front(tmp_path, "write")
    law = Law.load()
    common = _dc.replace(law.tables.common, pavement_max_grade=0.123)
    lines: list[str] = []
    got = _front(tmp_path, "read", law=_dc.replace(
        law, tables=_dc.replace(law.tables, common=common)), lines=lines)
    state = _states(got)["classify"]
    assert state.startswith("refused: law"), state
    assert any("why-miss classify: refused: law" in ln for ln in lines), lines
    assert any(ln.endswith("same key") for ln in lines), lines


def test_a_planar_record_without_its_registries_refuses_by_field_name(tmp_path, toys):
    _front(tmp_path, "write")
    (path,) = [p for p in _records(tmp_path) if "_planar_" in p.name]
    head = SC.peek(str(path))
    _h, witness, load = SC.read(str(path), head["key"])
    pm, pstats, record = load()
    del record["fields"]["terraces"]
    blob, digest = SC.encode((pm, pstats, record))
    head = {k: v for k, v in head.items() if k != "payload_sha256"}   # write re-stamps it
    assert SC.write(str(path), {**head, "output_digest": digest, "bytes": len(blob)},
                    witness, blob)
    with pytest.raises(SystemExit) as exc:
        _front(tmp_path, "read")
    assert "carries no terraces" in str(exc.value), exc.value


def test_first_difference_reads_the_recipe_in_order():
    recipe = {"inputs": {"a": "1", "b": "2"}, "code": {"classify": "c"}, "env": "e"}
    head = {"stage": "classify", "version": SC.CACHE_VERSION,
            "recipe": {**recipe, "inputs": {"a": "1", "b": "3"}}}
    assert SC.first_difference(head, "classify", recipe) == "inputs.b"
    assert SC.first_difference({**head, "version": 0}, "classify", recipe) == "version"
    assert SC.first_difference({**head, "recipe": recipe}, "classify", recipe) is None
    assert SC.first_difference(None, "classify", recipe) == "format"


@pytest.mark.parametrize("argv,needle", [
    (["--replay", "X.pkl", "--stage-cache"], "--stage-cache writes"),
    (["--replay", "X.pkl", "--why-miss"], "--why-miss reads"),
    (["--replay-cache", "TOYS", "--from", "planar"], "--replay-cache ICAO is"),
])
def test_the_cli_refuses_a_cache_flag_out_of_its_mode(argv, needle):
    got = subprocess.run([sys.executable, str(TOOL), *argv], capture_output=True,
                         text=True, cwd=str(ROOT), timeout=120)
    assert got.returncode != 0 and needle in got.stderr, got.stderr
