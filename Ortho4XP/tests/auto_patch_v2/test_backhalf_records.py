"""#843 step 9a — the back half's first records: one per constraint
generator, the assembly, the jetway strips (``pipeline/back_cache``,
``pipeline/constraint_records``; spec ``v2-stage-cache-spec.md`` §4b.1,
§4b.2, §6 back half, §8 T6/T8/T9/T10/T11/T12).

Synthetic, no corpus: the small airport of ``test_constraints.py`` (a
runway, a parallel, a stub, an apron with a pad, a service road) through
its planar map and shape stage, then the constraint stage three ways —
COLD (no cache: ``shapes.shape_constraints`` exactly), the MISS arm (every
record written) and the HIT arm (every record served) — compared row for
row and count for count.  No full ``build()`` runs here: a synthetic
airport build needs the pack and the inputs a corpus carries; the closing
HECA / CYXY byte identity is the master's."""
from __future__ import annotations

import ast
import json
import os
import pickle
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from auto_patch_v2.airport import stage_cache as SC
from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import GENERATORS
from auto_patch_v2.law import Law
from auto_patch_v2.model import constraint_codec as CODEC
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline import constraint_records as CR
from auto_patch_v2.pipeline import front_cache as FC
from auto_patch_v2.pipeline.shapes import shape_stage
from auto_patch_v2.planar.build import build as build_planar

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ICAO = "ZZZZ"


class PlaneDem:
    provenance = {"synthetic": "plane 1 % up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.01 * x + 0.002 * y

    def z_many(self, xs, ys):
        import numpy as np
        return 700.0 + 0.01 * np.asarray(xs, float) + 0.002 * np.asarray(ys, float)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def synthetic():
    """``(law, airport, classification)`` — ``test_constraints``'s airport."""
    law = Law.for_airport(ICAO)
    frame = Frame(ICAO, origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport(ICAO, "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, PlaneDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(-11.5, 22.5, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(-200, 103, 200, 250),
             (_rect(-60, 200, 60, 250),), None, None, "airside", "apron", {}),
        Cell(4, "building", "pad1", _rect(-60, 200, 60, 250), (), None, None,
             "airside", "pad", {}),
        Cell(5, "service_road", "road1", _rect(200, 103, 230, 250), (), None,
             None, "groundside", "road", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5))),
            CutLine("taxi_centerline", "stubB", ((0.0, 0.0), (0.0, 91.5))),
            CutLine("road_centerline", "road1", ((215.0, 103.0), (215.0, 250.0))))
    return law, airport, Classification(cells, cuts, {}, ())


@pytest.fixture(scope="module")
def world():
    law, airport, cl = synthetic()
    pm, _stats = build_planar(airport, cl, law)
    return law, airport, cl, pm


INPUTS = {"pm": "synthetic-shapes-digest", "airport": "synthetic-airport-digest"}


def _arm(world, root: Path | None, **fc_kw):
    """One constraint stage + the strips: ``(cs, counts, stage fields,
    yielded rows, strips, the cache report)``; ``root`` None is COLD."""
    law, airport, cl, pm = world
    fc = None
    if root is not None:
        fc = FC.FrontCache(ICAO, airport, law, enabled=True, mod_cache_root=str(root),
                           **fc_kw)
        airport = fc.airport(airport)
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    yielded: list = []
    con = CR.constraints_stage(fc, stage.pm, law, airport, stage, INPUTS, yielded)
    strips = CR.strips_stage(fc, stage.pm, law, airport, con, INPUTS).value
    rep = fc.finish() if fc is not None else {}
    fields = (dict(stage.dropped), stage.flats_straddling, stage.bands_withdrawn)
    return con.cs, con.counts, fields, yielded, strips, rep


def _states(rep: dict) -> dict[str, str]:
    return {k: v.get("state") for k, v in rep.get("stages", {}).items()}


def _same(a, b) -> None:
    """Two arms equal row for row (and by the columnar digest)."""
    assert CODEC.digest(a[0]) == CODEC.digest(b[0])
    assert a[0].rows() == b[0].rows()
    assert a[1] == b[1] and list(a[1]) == list(b[1])        # counts, in order
    assert a[2] == b[2]                                     # the ShapeStage fields
    assert a[3] == b[3]                                     # seam-yielded rows
    assert a[4] == b[4]                                     # strips


@pytest.fixture(scope="module")
def warm(world, tmp_path_factory):
    """A cache root holding every record (one miss arm), and that arm."""
    root = tmp_path_factory.mktemp("warm")
    return root, _arm(world, root)


def _copy(src: Path, dst: Path) -> Path:
    import shutil
    shutil.copytree(src, dst)
    return dst


NAMES = [f"constraints.gen.{n}" for n, _f in GENERATORS]


# ── T8: hit == cold ─────────────────────────────────────────────────────

def test_t8_every_record_hit_equals_cold(world, warm, tmp_path):
    cold = _arm(world, None)
    root, miss = warm
    assert set(_states(miss[5]).values()) == {"miss"}
    assert set(_states(miss[5])) == {*NAMES, "constraints.assembly", "jetway_strip"}
    _same(cold, miss)
    hit = _arm(world, _copy(root, tmp_path / "c"))
    assert set(_states(hit[5]).values()) == {"hit"}
    _same(cold, hit)


def test_t8_the_miss_arm_reports_its_cost(warm):
    rep = warm[1][5]["stages"]
    for name in (*NAMES, "constraints.assembly", "jetway_strip"):
        r = rep[name]
        assert {"key", "encode_s", "digest_s", "write_s", "written_bytes"} <= set(r), name
        assert r["written_bytes"] > 0 and len(r["key"]) == 16


def test_t8_the_records_are_the_codec_never_a_pickle_of_rows(warm):
    """RULINGS 2026-10-18e: a generator record's payload holds the columns."""
    root = warm[0]
    path = next(p for p in root.rglob("o4_stage_*constraints.gen.taxi_chain_*.cache"))
    head, _wit, load = SC.read(path, SC.read_header(path)["key"], decode=lambda b: b)
    assert head["payload_sha256"] and head["output_digest"] != head["payload_sha256"]
    enc, _runs, _stats = pickle.loads(load())
    assert isinstance(enc, CODEC.ColumnarSet)


# ── T9: planted stale entries ───────────────────────────────────────────

def _rewrite(path: Path, header=None, payload=None) -> None:
    raw = path.read_bytes()
    at = len(SC.MAGIC)
    (n,) = struct.unpack("<Q", raw[at:at + 8])
    head = json.loads(raw[at + 8:at + 8 + n])
    rest = raw[at + 8 + n:]
    (m,) = struct.unpack("<Q", rest[:8])
    wit, body = rest[8:8 + m], rest[8 + m:]
    head = header(head) if header else head
    body = zlib.compress(payload(zlib.decompress(body))) if payload else body
    h = json.dumps(head, sort_keys=True).encode()
    path.write_bytes(SC.MAGIC + struct.pack("<Q", len(h)) + h + struct.pack("<Q", m) + wit + body)


def _record(root: Path, stage: str) -> Path:
    return next(root.rglob(f"o4_stage_{ICAO}_{stage}_*.cache"))


def test_t9a_a_recipe_differing_in_one_field_is_refused_by_name(world, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")

    def older(h):
        h["recipe"]["code"] = {k: "0" * 64 for k in h["recipe"]["code"]}
        return h
    _rewrite(_record(root, "constraints.gen.taxi_chain"), header=older)
    rep = _arm(world, root)[5]
    assert _states(rep)["constraints.gen.taxi_chain"] == \
        "refused: recipe:code.constraints.taxi_chain"
    assert _states(rep)["constraints.gen.taxi_box"] == "hit"

    def other_law(h):
        h["recipe"]["inputs"]["law"] = "1" * 64
        return h
    _rewrite(_record(root, "jetway_strip"), header=other_law)
    assert _states(_arm(world, root)[5])["jetway_strip"] == "refused: recipe:inputs.law"


def test_t9b_an_altered_payload_under_an_intact_header_is_refused(world, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")
    _rewrite(_record(root, "constraints.assembly"), payload=lambda b: b + b"\0")
    cold = _arm(world, None)
    got = _arm(world, root)
    assert _states(got[5])["constraints.assembly"] == "refused: payload_sha256"
    _same(cold, got)


def test_t9f_an_evicted_generator_reruns_and_the_assembly_holds(world, warm, tmp_path):
    root = _copy(warm[0], tmp_path / "c")
    _record(root, "constraints.gen.taxi_chain").unlink()
    got = _arm(world, root)
    st = _states(got[5])
    assert st["constraints.gen.taxi_chain"] == "miss"
    assert st["constraints.assembly"] == "hit" and st["jetway_strip"] == "hit"
    _same(_arm(world, None), got)


def test_t9f_the_assembly_does_not_hold_over_a_generator_that_changed(
        world, warm, tmp_path, monkeypatch):
    """The generator's record is gone and its rows differ today (its key is
    the same): the assembly misses, never serves the old delta."""
    root = _copy(warm[0], tmp_path / "c")
    _record(root, "constraints.gen.taxi_chain").unlink()
    gens = tuple((n, (lambda pm, law, ap, fn=fn: fn(pm, law, ap)[:-1]) if n == "taxi_chain"
                  else fn) for n, fn in GENERATORS)
    monkeypatch.setattr(CR, "GENERATORS", gens)
    st = _states(_arm(world, root)[5])
    assert st["constraints.gen.taxi_chain"] == "miss"
    assert st["constraints.assembly"] == "miss" and st["jetway_strip"] == "miss"


# ── T10 / T11: code and environment ─────────────────────────────────────

def _with_code(monkeypatch, entry: str) -> None:
    real = FC._code.runtime_digests

    def patched():
        d = real()
        d[entry] = "f" * 64
        return d
    monkeypatch.setattr(FC._code, "runtime_digests", patched)


def test_t10_a_generator_code_change_with_the_same_rows_stops_there(
        world, warm, tmp_path, monkeypatch):
    root = _copy(warm[0], tmp_path / "c")
    _with_code(monkeypatch, "constraints.water_pins")
    got = _arm(world, root)
    st = _states(got[5])
    assert st.pop("constraints.gen.water_pins") == "miss"
    assert set(st.values()) == {"hit"}       # early cutoff: the assembly and after hit
    _same(_arm(world, None), got)


def test_t10_a_generator_whose_rows_change_reruns_everything_after(
        world, warm, tmp_path, monkeypatch):
    root = _copy(warm[0], tmp_path / "c")
    _with_code(monkeypatch, "constraints.taxi_chain")
    gens = tuple((n, (lambda pm, law, ap, fn=fn: fn(pm, law, ap)[:-1]) if n == "taxi_chain"
                  else fn) for n, fn in GENERATORS)
    monkeypatch.setattr(CR, "GENERATORS", gens)
    st = _states(_arm(world, root)[5])
    assert st.pop("constraints.gen.taxi_chain") == "miss"
    assert st.pop("constraints.assembly") == "miss" and st.pop("jetway_strip") == "miss"
    assert set(st.values()) == {"hit"}


@pytest.mark.parametrize("entry", ["constraints.assembly", "jetway_strip"])
def test_t10_an_assembly_or_strip_code_change(world, warm, tmp_path, monkeypatch, entry):
    root = _copy(warm[0], tmp_path / "c")
    _with_code(monkeypatch, entry)
    got = _arm(world, root)
    st = _states(got[5])
    assert all(st.pop(n) == "hit" for n in NAMES)
    # the strips name the assembly by its KEY (RULINGS 18e): it re-runs too
    assert st == ({"constraints.assembly": "miss", "jetway_strip": "miss"}
                  if entry == "constraints.assembly" else
                  {"constraints.assembly": "hit", "jetway_strip": "miss"})
    _same(_arm(world, None), got)


def test_t11_a_changed_environment_misses_every_record(world, warm, tmp_path, monkeypatch):
    root = _copy(warm[0], tmp_path / "c")
    real = FC._xplat.environment
    monkeypatch.setattr(FC._xplat, "environment", lambda: {**real(), "numpy": "0.0.0"})
    assert set(_states(_arm(world, root)[5]).values()) == {"miss"}


def test_t12_the_xplat_dump_bypasses_every_record(world, tmp_path):
    cold = _arm(world, None)
    got = _arm(world, tmp_path / "c", bypass="xplat")
    assert set(_states(got[5]).values()) == {"bypass: xplat"}
    assert set(_states(got[5])) == {*NAMES, "constraints.assembly", "jetway_strip"}
    assert not list((tmp_path / "c").rglob("*.cache")) if (tmp_path / "c").exists() else True
    _same(cold, got)


def test_a_changed_dem_answer_refuses_the_generators_that_asked(world, warm, tmp_path):
    """The DEM is named by its answers (``back_cache``): a record that asked
    the DEM is refused by its witness when the DEM moves."""
    root = _copy(warm[0], tmp_path / "c")
    law, airport, cl, pm = world

    class Moved(PlaneDem):
        def z(self, x, y):
            return super().z(x, y) + 0.5

        def z_many(self, xs, ys):
            return super().z_many(xs, ys) + 0.5
    import dataclasses as dc
    st = _states(_arm((law, dc.replace(airport, dem=Moved()), cl, pm), root)[5])
    asked = [k for k, v in st.items() if v.startswith("refused: dem")]
    assert asked == ["constraints.gen.road_within_shape"]      # it samples the DEM
    order = list(st)
    first = order.index(asked[0])
    # before it: hits; after it: misses — their ``dem_before`` names its
    # questions, so a memo it filled can hide nothing from them
    assert {st[k] for k in order[:first]} == {"hit"}
    assert {st[k] for k in order[first + 1:] if k in NAMES} == {"miss"}
    # the same rows: the assembly (keyed on them, it asks no DEM) still hits
    assert st["constraints.assembly"] == "hit" and st["jetway_strip"] == "miss"


def test_one_last_used_per_stage_run(warm):
    idx = json.loads(next(warm[0].rglob("o4_stage.index.json")).read_text(encoding="utf-8"))
    stamps = {v for k, v in idx.items() if "constraints." in k or "jetway_strip" in k}
    assert len(stamps) == 1


# ── T6: generator independence ──────────────────────────────────────────

_ALONE = r"""
import json, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
import test_backhalf_records as T
from auto_patch_v2.constraints import GENERATORS
from auto_patch_v2.pipeline.shapes import shape_stage
from auto_patch_v2.planar.build import build
law, airport, cl = T.synthetic()
pm, _ = build(airport, cl, law)
stage = shape_stage(pm, law, airport, cl, out=lambda m: None)
names = sys.argv[3].split(",")
fns = dict(GENERATORS)
print(json.dumps({n: T.gen_digest(fns[n], stage.pm, law, airport) for n in names}))
"""


def gen_digest(fn, pm, law, airport) -> str:
    """The columnar digest of one generator's record."""
    from auto_patch_v2.constraints import run_generator
    blob, digest = CR.GEN_CODEC.encode(CR.GenRows.of(*run_generator(fn, pm, law, airport)))
    return digest()


def _alone(names: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", _ALONE, str(SRC), str(Path(__file__).parent), ",".join(names)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT),
        env={**os.environ, "PYTHONHASHSEED": "random"})


def test_t6_every_generator_alone_in_order_and_shuffled_agrees(world):
    """Every generator's rows (columnar digest) are the same (a) in
    ``GENERATORS`` order, (b) ALONE in a fresh process with every memo cold
    and (c) in a shuffled order."""
    import random
    law, airport, cl, pm = world
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    in_order = {n: gen_digest(fn, stage.pm, law, airport) for n, fn in GENERATORS}
    shuffled = list(GENERATORS)
    random.Random(843).shuffle(shuffled)
    assert {n: gen_digest(fn, stage.pm, law, airport) for n, fn in shuffled} == in_order
    procs = [_alone([n]) for n, _f in GENERATORS]
    alone: dict[str, str] = {}
    for p in procs:
        out, err = p.communicate(timeout=600)
        assert p.returncode == 0, err[-2000:]
        alone.update(json.loads(out.strip().splitlines()[-1]))
    assert alone == in_order


#: Every ``id(...)`` argument in ``constraints/`` and ``solve/``: a MAP, a law,
#: an airport or a report — never a row kept across a record (spec §8 T6:
#: the codec returns equal rows, not the same objects).  ``p``:
#: ``road_ramp.pad_weld_release`` drops pins of ONE set by their identity in
#: that same set, inside one call — never across a record.
_ID_OF = frozenset({"planar", "pm", "law", "airport", "airside", "ps.stations",
                    "out[1]", "rep_y", "p"})


def test_t6_no_reader_keys_a_row_by_its_identity():
    found = set()
    for pkg in ("constraints", "solve"):
        for p in (SRC / "auto_patch_v2" / pkg).rglob("*.py"):
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "id" and node.args):
                    found.add(ast.unparse(node.args[0]))
    assert found <= _ID_OF, sorted(found - _ID_OF)


# ── §4b.3: the prefix re-runs go through the records ────────────────────

def test_a_prefix_rerun_goes_through_every_record_and_equals_cold(tmp_path):
    """A ``Deriver`` holding the build's cache runs the WHOLE prefix through
    the records (front half included), reported as ``<stage>@prefix<n>``;
    the second build serves all of it, equal to a run with no cache."""
    import types

    from auto_patch_v2.pipeline.prefix import Deriver, PackRead
    law, airport, cl = synthetic()
    inputs = types.SimpleNamespace(road_grade_limit=0.08, lane_width_m=3.5)
    pack = PackRead(None, None, None)
    cold = Deriver(airport, law, inputs, pack)(cl)
    for want in ("miss", "hit"):
        fc = FC.FrontCache(ICAO, airport, law, enabled=True, mod_cache_root=str(tmp_path))
        derive = Deriver(fc.airport(airport), law, inputs, pack, cache=fc,
                         common=fc.common_inputs(None, None))
        got = derive(cl)
        st = _states(fc.finish())
        assert set(st.values()) == {want}
        assert {"planar@prefix1", "shapes@prefix1", "constraints.assembly@prefix1",
                "jetway_strip@prefix1"} <= set(st)
        assert got[1] == cold[1] and got[2] == cold[2]
        assert fc.tag == ""
