"""The flat-site datum twins (RULINGS 2026-09-05k-2; spec
``docs/specs/auto-patch-v2/flat-site-datum-spec.md`` §4; lane v2flatsite).

1. the ``law/flat_site.toml`` register equals v1's ``FLAT_SITE_*``
   constants (v1 imported HERE ONLY), the loader refuses a malformed
   table, and the law digest CHANGES when a site is declared;
2. a synthetic airport with thresholds 100.0 / 100.2 and a 1 m DEM
   ripple → ``flat_candidate``, Z0 100.1, every apron vertex carries a
   ``flat_datum`` row and no runway vertex does;
3. the same with 8 m of DEM relief → ``not_flat``, zero rows;
4. a ``[declared]`` entry with ``source = "metres"`` overrides the
   verdict and records ``auto_verdict``;
5. the LP with the rows lands the apron at Z0 where the law allows and
   NOT where a hard taxi gradient forbids (the row is a preference);
6. the pipeline's weights carry the group from the table, and the
   dependency direction holds (airport / constraints import law + model).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import re
import shutil
from pathlib import Path

import pytest

from auto_patch_v2.airport import flat_site as F
from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import GENERATORS, generate
from auto_patch_v2.constraints import flat_site as C
from auto_patch_v2.law import DEFAULT_LAW_DIR, Law, LawError, law_tables_digest, load_tables
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.airport import (Airport, FlatVerdict, Pavement, Runway,
                                         RunwayEnd, SceneryPack, Surface)
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options
from auto_patch_v2.solve import solve_design

from auto_patch import config as v1  # noqa: E402  (the oracle side, test-only)

SRC = Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2"


# ── 1. the register ──────────────────────────────────────────────────────

def test_register_equals_v1_constants():
    det = load_tables(DEFAULT_LAW_DIR).flat_site.detector
    assert det.threshold_spread_max_m == v1.FLAT_SITE_THRESHOLD_SPREAD_M
    assert det.relief_floor_m.coarse == v1.FLAT_SITE_RELIEF_FLOOR_BY_CLASS["ge3arcsec"] \
        == v1.FLAT_SITE_RELIEF_FLOOR_BY_CLASS["1arcsec"]
    assert det.relief_floor_m.fine == v1.FLAT_SITE_RELIEF_FLOOR_BY_CLASS["sub10m"]
    bounds = dict((name, m) for m, name in v1.FLAT_SITE_SOURCE_CLASS_BOUNDS_M)
    assert det.lidar_credible_max_m == bounds["lidar"]
    assert det.fine_source_max_m == bounds["sub10m"]
    assert det.plane_slope_max == pytest.approx(v1.FLAT_SITE_MAX_SLOPE_PCT / 100.0)
    assert det.sea_band_max_m == v1.FLAT_SITE_SEA_BAND_MAX_M
    assert det.sea_band_min_z0_m == v1.FLAT_SITE_SEA_BAND_MIN_Z0_M
    assert det.dsm_trim_over_median_m == v1.FLAT_SITE_DSM_TRIM_FRACTION_OF_FLOOR
    assert det.seat_consensus_max_m == v1.FLAT_SITE_PACK_OFFSET_MAX_M
    assert det.seat_spread_max_m == v1.FLAT_SITE_PACK_SPREAD_MAX_M
    assert det.below_grade_base_y_m == -v1.FLAT_SITE_PACK_BELOW_GRADE_M
    assert det.margin_m == v1.FLAT_SITE_MARGIN_M
    law = Law.for_airport("OTHH")
    # the class mapping: base-tier postings (both arcsec classes) are coarse
    assert T.flat_source_class(law, v1.FLAT_SITE_BASE_COARSE_RESOLUTION_M) == "coarse"
    assert T.flat_source_class(law, v1.FLAT_SITE_BASE_FINE_RESOLUTION_M) == "coarse"
    assert T.flat_source_class(law, 5.0) == "fine" and T.flat_source_class(law, 1.0) == "lidar"
    assert T.flat_relief_floor_m(law, "lidar") is None
    d = law.tables.flat_site.datum
    assert d.source == "cifp" and d.preference == "flat_datum" and d.runway_pins_hard
    # ranked below the law ladder, above the seam
    assert d.weight > 0.0     # 08t: a weight, no ladder to rank it against
    assert law.tables.flat_site.declared == {}


def _copy_law(tmp_path: Path) -> Path:
    for f in os.listdir(DEFAULT_LAW_DIR):
        if f.endswith(".toml"):
            shutil.copy(DEFAULT_LAW_DIR / f, tmp_path / f)
    return tmp_path


@pytest.mark.parametrize("append, needle", [
    ("bogus", "unknown key"),
    ('\nOTH = { source = "cifp" }\n', "4-character"),
    ('\nVHHH = { source = "metres" }\n', "needs z0"),
    ('\nVHHH = { source = "guess", z0 = 5.5 }\n', "not in"),
])
def test_loader_refuses_malformed_flat_site(tmp_path, append, needle):
    d = _copy_law(tmp_path)
    p = d / "flat_site.toml"
    if append == "bogus":                     # an unknown [detector] key
        p.write_text(p.read_text().replace("margin_m                 = 200.0",
                                           "margin_m = 200.0\nbogus = 1"))
    else:
        p.write_text(p.read_text() + append)
    with pytest.raises(LawError, match=needle):
        load_tables(d)


def test_datum_source_and_negative_metres_are_validated(tmp_path):
    d = _copy_law(tmp_path)
    p = d / "flat_site.toml"
    text = p.read_text()
    p.write_text(text.replace('source     = "cifp"', 'source     = "metres"'))
    with pytest.raises(LawError, match="datum.source"):
        load_tables(d)
    p.write_text(text.replace("margin_m                 = 200.0", "margin_m = -1.0"))
    with pytest.raises(LawError, match=">= 0"):
        load_tables(d)
    # the ONE signed metre key loads
    assert load_tables(DEFAULT_LAW_DIR).flat_site.detector.below_grade_base_y_m < 0


def test_declaring_a_site_changes_the_law_digest(tmp_path):
    d = _copy_law(tmp_path)
    before = law_tables_digest(d)["sha256"]
    assert before == law_tables_digest()["sha256"]
    assert "flat_site.toml" in law_tables_digest(d)["files"]
    p = d / "flat_site.toml"
    p.write_text(p.read_text() + '\nVHHH = { z0 = 5.5, source = "metres" }\n')
    law = Law.load(d)
    assert T.flat_declared(law, "vhhh").z0 == 5.5
    assert law_tables_digest(d)["sha256"] != before


def test_no_numeric_literal_in_law_python_still_holds():
    for name in ("model.py", "tables.py"):
        body = "\n".join(l for l in (DEFAULT_LAW_DIR / name).read_text().splitlines()
                         if not l.strip().startswith("#"))
        floats = re.findall(r"(?<![\w.])\d+\.\d+(?![\w.])", body)
        assert set(floats) <= {"0.0", "0.2", "1.0"}, (name, floats)


# ── the synthetic airport (test_constraints' shape, two thresholds close) ─

class _RippleDem:
    """A 1 m ripple (amplitude 0.5 m) about ``base`` — relief under any
    floor; ``relief`` scales it (8 m: a hillside)."""

    def __init__(self, base: float, amplitude: float) -> None:
        self.base, self.amplitude = base, amplitude
        self.provenance = {"synthetic": f"ripple {amplitude} m about {base}"}

    def z(self, x: float, y: float) -> float:
        return self.base + self.amplitude * math.sin(x / 37.0) * math.cos(y / 53.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)

    def posting_m(self):
        return 10.0                        # the raster's own cells, 10 m


class _CoarseRipple(_RippleDem):
    """A sampler that states a coarse (30 m) source: floor 8 m."""

    def source_pixel_m(self):
        return 30.0, "inset"


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, dem, thr=(100.0, 100.2)):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, thr[0], "cifp"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, thr[1], "cifp"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    # the apt.dat pavements the detector's extent is built from (the
    # planar cells below trace the same rectangles)
    pav = (Pavement("taxiA", Surface.ASPHALT, _rect(-400, 80, 400, 103), ()),
           Pavement("stubB", Surface.ASPHALT, _rect(-11.5, 22.5, 11.5, 80), ()),
           Pavement("apron1", Surface.CONCRETE, _rect(-200, 103, 200, 250), ()))
    return Airport("ZZZZ", "Synthetic", frame, 100.0, (rw,), pav, (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key)


def _planar(airport, law):
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(-11.5, 22.5, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(-200, 103, 200, 250), (), None, None,
             "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5))),
            CutLine("taxi_centerline", "stubB", ((0.0, 0.0), (0.0, 91.5))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return pm


@pytest.fixture(scope="module")
def flat_site(law):
    airport = _airport(law, _CoarseRipple(100.1, 0.5))
    fv = F.detect(airport, law)
    airport = _dc.replace(airport, flat_site=fv)
    return airport, _planar(airport, law), fv


# ── 2. flat_candidate, rows on the apron, none on the runway ─────────────

def test_flat_candidate_verdict_and_rows(flat_site, law):
    airport, pm, fv = flat_site
    assert fv.verdict == fv.auto_verdict == "flat_candidate"
    assert fv.z0_m == pytest.approx(100.1)
    assert fv.source == "cifp"
    s = fv.signals
    assert s["s1_spread_m"] == pytest.approx(0.2) and s["s1_pass"] is True
    assert s["s2_pass"] is True and s["s2"]["relief_m"] <= 1.0
    assert s["s2_source_class"] == "coarse" and s["s2_source_whence"] == "inset"
    assert s["s4"]["pass"] is None                    # no objects: no_data, never a fail
    assert s["core"] is None and fv.region
    rows = C.flat_datum(pm, law, airport)
    # one preference group PER ROW (the assembler's slack is per group —
    # a shared group would free every row by the largest single relief)
    assert rows and all(isinstance(r, Linear) and r.soft == f"flat_datum:{r.terms[0][0]}"
                        and r.lo == r.hi == pytest.approx(100.1) for r in rows)
    assert len({r.soft for r in rows}) == len(rows)
    from auto_patch_v2.solve.assemble import preference_weight
    assert preference_weight(rows[0].soft, None) == 5.0e4
    assert {r.source.generator for r in rows} == {"flat_site"}
    from auto_patch_v2.constraints.precedence import view
    vw = view(pm, law)
    pinned = {r.terms[0][0] for r in rows}
    apron = next(f for f in pm.faces.values() if f.role == "apron")
    runway = next(f for f in pm.faces.values() if f.role == "runway")
    assert set(vw.rings[apron.id]) <= pinned
    assert not (set(vw.rings[runway.id]) & pinned)
    # registered in the generator run
    assert "flat_datum" in dict(GENERATORS)
    cs, counts, _w = generate(pm, law, airport)
    assert counts["flat_datum"] == len(rows)
    line = F.log_line("ZZZZ", fv)
    assert line.startswith("[flat-site] ZZZZ: flat_candidate — Z0 100.10 m")
    assert F.notes("ZZZZ", fv) and "core NONE" in F.notes("ZZZZ", fv)[0]


# ── 3. not_flat: zero rows ────────────────────────────────────────────────

def test_relief_refuses_and_mints_nothing(law):
    airport = _airport(law, _RippleDem(100.1, 4.0))       # p95 − p5 ≈ 7.5 m > 2 m? no: unknown class
    fv = F.detect(airport, law)
    # an UNKNOWN source class has no floor: S2 cannot pass → no_data, and
    # a no_data site mints nothing either
    assert fv.verdict == "no_data" and not fv.substitutes
    assert C.flat_datum(_planar(_dc.replace(airport, flat_site=fv), law), law,
                        _dc.replace(airport, flat_site=fv)) == []


def test_eight_metres_of_relief_is_not_flat(law):
    airport = _airport(law, _CoarseRipple(100.1, 5.0))     # p95 − p5 ≈ 9 m > 8 m floor
    fv = F.detect(airport, law)
    assert fv.auto_verdict == fv.verdict == "not_flat"
    assert fv.signals["s2_source_class"] == "coarse" and fv.signals["s2_relief_floor_m"] == 8.0
    assert fv.signals["s2"]["relief_m"] > 8.0
    airport = _dc.replace(airport, flat_site=fv)
    assert C.flat_datum(_planar(airport, law), law, airport) == []
    # and the same ripple under the floor IS flat under the coarse class
    ok = F.detect(_airport(law, _CoarseRipple(100.1, 0.5)), law)
    assert ok.verdict == "flat_candidate"
    # a wide threshold spread refuses S1
    wide = F.detect(_airport(law, _CoarseRipple(100.1, 0.5), thr=(100.0, 106.0)), law)
    assert wide.verdict == "not_flat" and wide.signals["s1_pass"] is False


class _LidarRipple(_RippleDem):
    def source_pixel_m(self):
        return 1.0, "inset"


def test_lidar_short_circuits(law):
    fv = F.detect(_airport(law, _LidarRipple(100.1, 0.1)), law)
    assert fv.verdict == "lidar_credible" and not fv.substitutes


# ── 4. the declared override ──────────────────────────────────────────────

def test_declared_metres_overrides_and_records_auto_verdict(tmp_path):
    d = _copy_law(tmp_path)
    p = d / "flat_site.toml"
    p.write_text(p.read_text() + '\nZZZZ = { z0 = 102.0, source = "metres" }\n')
    law2 = Law.load(d)
    fv = F.detect(_airport(law2, _CoarseRipple(100.1, 5.0)), law2)
    assert fv.verdict == "flat_declared" and fv.auto_verdict == "not_flat"
    assert fv.z0_m == 102.0 and fv.source == "metres" and fv.substitutes
    assert fv.signals["declared"] is True
    assert "[DECLARED metres; detector said not_flat]" in F.log_line("ZZZZ", fv)
    # a cifp declaration keeps the CIFP datum
    p.write_text(p.read_text().replace('z0 = 102.0, source = "metres"', 'source = "cifp"'))
    fv2 = F.detect(_airport(Law.load(d), _CoarseRipple(100.1, 5.0)), Law.load(d))
    assert fv2.verdict == "flat_declared" and fv2.z0_m == pytest.approx(100.1) and fv2.source == "cifp"


# ── 5. the LP: a preference, never a hard row ────────────────────────────

def test_lp_lands_the_apron_at_z0_where_the_law_allows(flat_site, law):
    airport, pm, fv = flat_site
    cs, counts, _w = generate(pm, law, airport)
    assert counts["flat_datum"] > 0
    w = None
    assert law.tables.flat_site.datum.weight > 0.0   # 08t: a law value, no ladder
    sol, _rep = solve_design(pm, cs, law)
    assert sol.status.value in ("optimal", "feasible")
    from auto_patch_v2.constraints.precedence import view
    vw = view(pm, law)
    apron = next(f for f in pm.faces.values() if f.role == "apron")
    tol = law.tables.emit.materiality.elevation_m
    # thresholds 100.0 / 100.2 and Z0 100.1: the whole apron reaches the
    # datum lawfully (stub 1.5 % × 57.5 m ≫ 0.1 m)
    off = [abs(sol.z[v] - 100.1) for v in vw.rings[apron.id]]
    assert max(off) <= tol, off
    # the runway keeps its CIFP pins
    z09 = sol.z[min(vw.rings[next(f.id for f in pm.faces.values() if f.role == "runway")],
                   key=lambda v: vw.xy[v][0])]
    assert abs(z09 - 100.0) <= tol


def _law_ceiling(pm, cs, v: int) -> float:
    """``max z_v`` under the set's hard ``Diff`` rows and ``Pin``s alone (the
    ``Linear`` rows dropped: an upper bound of the law's own ceiling)."""
    import numpy as np
    from scipy.optimize import linprog
    n = len(pm.vertices)
    diffs = [r for r in cs.diffs if r.soft is None]
    A = np.zeros((2 * len(diffs), n)); ub = np.zeros(2 * len(diffs))
    for k, r in enumerate(diffs):
        A[2 * k, r.a], A[2 * k, r.b] = 1.0, -1.0
        A[2 * k + 1, r.a], A[2 * k + 1, r.b] = -1.0, 1.0
        ub[2 * k] = ub[2 * k + 1] = r.bound_m
    pins = {p.v: p.z for p in cs.pins}
    bounds = [(pins[i], pins[i]) if i in pins else (-1e4, 1e4) for i in range(n)]
    c = np.zeros(n); c[v] = -1.0
    res = linprog(c, A_ub=A, b_ub=ub, bounds=bounds, method="highs")
    assert res.status == 0, res.message
    return float(-res.fun)


def test_lp_yields_the_datum_where_a_hard_taxi_gradient_forbids(tmp_path, law):
    """A declared datum 10 m over the thresholds: no airside vertex can
    reach it lawfully (the runway edge climbs at most 1.5 % from its
    pinned threshold, the stub mouth 1.5 % more over 3 m), so every datum
    row YIELDS — the solve stays hard-feasible (a preference never
    demotes the law), the thresholds hold, and the surface sits under
    the datum by the law's margin, never at it."""
    d = _copy_law(tmp_path)
    p = d / "flat_site.toml"
    p.write_text(p.read_text() + '\nZZZZ = { z0 = 110.0, source = "metres" }\n')
    law2 = Law.load(d)
    airport = _airport(law2, _CoarseRipple(100.1, 0.5))
    fv = F.detect(airport, law2)
    assert fv.verdict == "flat_declared" and fv.z0_m == 110.0
    airport = _dc.replace(airport, flat_site=fv)
    pm = _planar(airport, law2)
    cs, counts, _w = generate(pm, law2, airport)
    assert counts["flat_datum"] > 0
    sol, rep = solve_design(pm, cs, law2,
                                 Options(diagnose_iis=False))
    assert sol.status.value in ("optimal", "feasible")
    assert rep.mode == "hard", rep.line()           # a preference never demotes the law
    from auto_patch_v2.constraints.precedence import view
    vw = view(pm, law2)
    tol = law2.tables.emit.materiality.elevation_m
    runway = next(f for f in pm.faces.values() if f.role == "runway" and f.code_number)
    ring = vw.rings[runway.id]
    # the thresholds stay CIFP-absolute
    zs = sorted(sol.z[v] for v in ring if abs(abs(vw.xy[v][0]) - 600.0) < 1e-6
                and abs(vw.xy[v][1]) < 1e-6)
    assert zs and zs[0] == pytest.approx(100.0, abs=tol) and zs[-1] == pytest.approx(100.2, abs=tol)
    taxi = law2.ruleset.taxi.longitudinal.value(None, "D")
    rw_cap = law2.ruleset.runway.longitudinal.value(3, None)
    # the stub mouth (3 m off the runway edge) can stand at most the runway
    # edge's lawful climb from the threshold plus 3 m of taxi grade
    # (109.07 m) under the withdrawn chord law; under the CHAIN (RULINGS
    # 2026-09-05ac) its ceiling is the LP's own — the hard Diff / Pin rows
    # pushed as far as they go (the mouth's lateral hop, the stub's
    # centreline, the edge station's runway hop) — a little higher: the
    # preference lifts it to that ceiling and no further — under the
    # datum, the law's margin, never at it
    stub = next(f for f in pm.faces.values() if f.role == "stub")
    mouth = [v for v in vw.rings[stub.id] if abs(vw.xy[v][1] - 25.5) < 1e-6]
    assert mouth
    chord_ceiling = 100.2 + rw_cap * (600.0 - 11.5) + taxi * 3.0
    for v in mouth:
        ceiling = _law_ceiling(pm, cs, v)
        assert chord_ceiling - tol <= ceiling < 110.0 - tol
        assert sol.z[v] <= ceiling + tol
        assert 110.0 - sol.z[v] > 110.0 - ceiling - tol > tol
    # nothing overshoots the datum, and the datum rows are the ONLY soft
    # rows that yielded — no law row did
    datum_v = {r.terms[0][0] for r in cs.linears if r.source.generator == "flat_site"}
    assert all(sol.z[v] <= 110.0 + tol for v in datum_v)
    assert not rep.yielded


def test_provenance_line_carries_the_datum():
    from auto_patch.engine_v2 import format_provenance_line   # v1 driver, test-only
    kw = dict(sha="abc", law_sha256="f" * 64, ruleset="icao", dem_prov={}, status="optimal")
    assert " flat=3.96 " in format_provenance_line(
        "OTHH", flat_site={"substitutes": True, "z0_m": 3.96}, **kw)
    assert "flat=" not in format_provenance_line(
        "CYXY", flat_site={"substitutes": False, "z0_m": 697.3}, **kw)
    assert "flat=" not in format_provenance_line("CYXY", **kw)


# ── 6. plumbing ───────────────────────────────────────────────────────────

def test_weights_carry_the_group_from_the_table(law):
    w = None
    assert T.flat_datum_weight(law) == 5.0e4
    assert flat_datum_group(law) not in ("law", "seam")   # its own group, never a literal


def test_dependency_direction_of_the_new_modules():
    for rel, allowed in (("airport/flat_site.py", {"law", "model"}),
                         ("constraints/flat_site.py", {"law", "model"})):
        text = (SRC / rel).read_text()
        assert set(re.findall(r"from \.\.(\w+)", text)) <= allowed, rel
        assert "os.environ" not in text and "auto_patch." not in text.replace("auto_patch_v2", "")
        assert len(text.splitlines()) <= 500, rel


def test_flat_verdict_model_is_plain():
    fv = FlatVerdict("not_flat", "not_flat", None, "cifp", (), {})
    assert not fv.substitutes
    assert FlatVerdict("flat_declared", "not_flat", 3.96, "metres", (), {}).substitutes
    assert Airport.__dataclass_fields__["flat_site"].default is None


# ── structure faces take no datum row (05k-2 amendment) ───────────────────

def test_structure_faces_take_no_datum_row(law):
    from auto_patch_v2.law.tables import is_structure_role
    assert is_structure_role(law, "tunnel_ramp") and is_structure_role(law, "tunnel_trench") \
        and is_structure_role(law, "retaining_wall") and not is_structure_role(law, "apron")
    airport = _airport(law, _CoarseRipple(100.1, 0.5))
    fv = F.detect(airport, law)
    airport = _dc.replace(airport, flat_site=fv)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(-11.5, 22.5, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(-200, 103, 200, 250), (), None, None,
             "airside", "apron", {}),
        Cell(4, "tunnel_trench", "trench1", _rect(-60, 150, 60, 180), (), None, None,
             "airside", "none", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5))),
            CutLine("taxi_centerline", "stubB", ((0.0, 0.0), (0.0, 91.5))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    rows = C.flat_datum(pm, law, airport)
    from auto_patch_v2.constraints.precedence import view
    vw = view(pm, law)
    pinned = {r.terms[0][0] for r in rows}
    trench = next(f for f in pm.faces.values() if f.role == "tunnel_trench")
    apron = next(f for f in pm.faces.values() if f.role == "apron")
    assert not (set(vw.rings[trench.id]) & pinned)           # the structure's rim: no datum row
    assert set(vw.rings[apron.id]) - set(vw.rings[trench.id]) <= pinned   # the apron still has its rows

