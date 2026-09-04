"""The ``runway_crown`` twins (lane v2crown, 2026-09-04).

A runway OFF the axes (heading 142°, LEMD's 14/32 pair) keeps its
``runway_profile`` breakline through ``planar.build`` — every station
chord matched, nothing dropped; the crown generator states a floor on
every off-ridge runway vertex and the publication declares the BUILT
drop; v2's ``runway_crown`` reader and the v1 oracle both read ZERO on
the emitted patch and agree that every runway shape carries a
declaration.  The precedent: ``set_precision`` left a 0.5 m precision
model on the snapped source line, the 0.3 m match buffer collapsed to an
empty polygon off the axes, and LEMD's two diagonal runways lost their
profile, pins and crown (2,185 oracle rows priced against the other
pair's ridges 0.3–4.8 km away)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, roads, runway_profile
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.constraints import Linear, Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.chords import stations
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.verify import census

ROOT = Path(__file__).resolve().parents[2]
HEADING_DEG = 142.0          # LEMD 14R/32L, the runway the buffer lost
HALF_WIDTH = 22.5


class _PlaneDem:
    provenance = {"synthetic": "plane 1 % up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.01 * x + 0.002 * y

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rot(heading_deg: float):
    """Frame rotation taking the +x axis onto ``heading_deg`` (compass)."""
    a = math.radians(90.0 - heading_deg)
    c, s = math.cos(a), math.sin(a)
    return lambda p: (round(p[0] * c - p[1] * s, 3), round(p[0] * s + p[1] * c, 3))


def _rect(r, x0, y0, x1, y1):
    return tuple(r(p) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def build_diagonal(law):
    """The M2 synthetic airport rotated to LEMD's 14/32 heading: one
    runway with CIFP pins, a parallel taxiway, a stub, an apron with a
    pad, a service road."""
    r = _rot(HEADING_DEG)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("14", r((-600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("32", r((600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("14/32", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _PlaneDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "14/32", _rect(r, -600, -HALF_WIDTH, 600, HALF_WIDTH), (),
             3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(r, -200, 103, 200, 250), (), None, None,
             "airside", "apron", {}),
        Cell(4, "building", "pad1", _rect(r, -60, 200, 60, 250), (), None, None,
             "airside", "pad", {}),
        Cell(5, "service_road", "road1", _rect(r, 200, 103, 230, 250), (), None,
             None, "groundside", "road", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", (r((-400.0, 91.5)), r((400.0, 91.5)))),
            CutLine("taxi_centerline", "stubB", (r((0.0, 0.0)), r((0.0, 91.5)))),
            CutLine("road_centerline", "road1", (r((215.0, 103.0)), r((215.0, 250.0)))))
    cl = Classification(cells, cuts, {}, ())
    pm, stats = build(airport, cl, law)
    return airport, pm, stats


@pytest.fixture(scope="module")
def diagonal(law):
    return build_diagonal(law)


def test_diagonal_runway_keeps_its_profile_breakline(diagonal, law):
    airport, pm, stats = diagonal
    prof = [b for b in pm.breaklines.values() if b.kind == "runway_profile"]
    assert prof and {b.ref for b in prof} == {"14/32"}
    # every station chord of the source line is a breakline edge: the
    # source has ``stations(spacing)`` points, the chains together carry
    # one edge per station chord plus the edges the ring/centreline
    # crossings split them into — never fewer
    rw = airport.runways[0]
    n_stations = len(stations([rw.ends[0].xy, rw.ends[1].xy],
                              law.tables.emit.chords.station_spacing_m))
    n_edges = sum(len(b.edges) for b in prof)
    assert n_edges >= n_stations - 1, (n_edges, n_stations)
    assert stats.dropped_source_edges == 0
    # the two other breakline kinds survive the rotation too
    kinds = {b.kind for b in pm.breaklines.values()}
    assert {"runway_profile", "taxi_centerline", "road_centerline"} <= kinds


def test_crown_generator_declares_the_built_drop(diagonal, law):
    airport, pm, _ = diagonal
    rows = runway_profile.runway_profile(pm, law, airport)
    assert sorted(p.z for p in rows if isinstance(p, Pin)) == [700.0, 706.0]
    crown = runway_profile.runway_crown(pm, law, airport)
    assert crown and all(isinstance(r, Linear) and r.lo is None for r in crown)
    designed = runway_profile.crown_drops(pm, law, airport)
    rate = law.tables.common.runway_crown_transverse
    # the rotated ring corners snap to the identity grid, so an edge
    # vertex's lateral offset is HALF_WIDTH within one grid cell
    grid = law.tables.emit.identity.min_distinct_spacing_m
    assert max(designed.values()) == pytest.approx(rate * HALF_WIDTH, abs=rate * grid + 1e-3)
    # the BUILT declaration equals the surface's own fall at every vertex
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    built = runway_profile.crown_drops(pm, law, airport, sol.z)
    assert set(built) == set(designed)
    edge = [v for v, d in designed.items() if d > 0.0]
    assert edge and all(built[v] >= designed[v] - 1e-6 for v in edge)


def _emit(diagonal, law, out_dir):
    airport, pm, _ = diagonal
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    paths = write_patch(surf, law, out_dir, pub, face_tags=face_tags(pm, law))
    return pm, surf, pub, paths


def test_verify_reader_and_oracle_read_zero_crown_rows(diagonal, law, tmp_path):
    pm, surf, pub, paths = _emit(diagonal, law, tmp_path)
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))
    assert rows["runway_crown"] == []
    assert rows["drainage_minimum"] == []
    # the oracle: the same patch, the same declaration, zero rows, and
    # EVERY runway shape declared (an undeclared shape is judged against
    # the ruleset floor and the nearest ridge of ANY runway — the LEMD class)
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    ctx = cg.law_context_from_sidecar(paths.patch)
    feats: dict = {}
    nodes, ways = cg._parse_osm(paths.patch, feature_out=feats)
    ll_to_m = cg._ll_to_m_factory(nodes)
    crown = cg._crown_drops_by_nid(nodes, ctx["crown_drops_ll"] or [])
    assert crown, "the sidecar declares no crown drops"
    viol, n_nodes, n_no_ridge, n_undeclared = cg._check_runway_crown(
        ways, nodes, ll_to_m, crown, feats.get("crown_spine", []))
    assert len(feats.get("crown_spine", [])) == 1
    assert (len(viol), n_no_ridge, n_undeclared) == (0, 0, 0)
    assert n_nodes > 0
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    assert len(fam.get("runway_crown", [])) == len(rows["runway_crown"]) == 0
