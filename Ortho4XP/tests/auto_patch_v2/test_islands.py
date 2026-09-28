"""THE COURTYARD (spec-author ruling 2026-09-28, lane ``islands``; issues
#77 / #73).

(i)  An apron ISLAND inside a pad HOLE takes its level from the PAD RIM
     around it — a courtyard of the pad — not its own DEM plane and not the
     main apron's trend (``model.islands``, one derivation read by stage 1's
     population, the datum, the apron trend and the pad's frontage).
(ii) The census and verify frontage checks read pad HOLES: a vertex on a
     hole ring is a pad vertex, a vertex in a hole is judged against the
     hole ring, never the outer ring (KCLT sweep: 256 of 280 rows were
     island vertices ON a hole ring read at ``d = 0`` against the outer
     ring; CRITICAL motion 237 -> 2 on the census fix alone)."""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path
from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.apron_trend import _apron_bodies, with_apron_trend
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.taxi_trend import with_taxi_trend
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import airside_stage_roles, apron_roles
from auto_patch_v2.model.islands import courtyard_faces, courtyard_vertices
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design_roles import airside_stage_vertices
from auto_patch_v2.verify import frontage as vfront
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot
from tests.auto_patch_v2 import test_v2aprontrend as _tr

Y0 = 300.0
Y1 = Y0 + 200.0
HOLE = (0.0, Y0 + 40.0, 100.0, Y1 - 40.0)
BUMP_M = 3.0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _BumpDem:
    """Flat 700 m ground with a BUMP_M rise under the pad's hole — the
    island's own DEM plane stands 3 m off the pad rim around it."""

    provenance = {"synthetic": "bump under the courtyard"}

    def __init__(self) -> None:
        x0, y0, x1, y1 = HOLE
        self.hole = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]).buffer(30.0)

    def z(self, x: float, y: float) -> float:
        return 700.0 + (BUMP_M if self.hole.contains(Point(x, y)) else 0.0)

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _cells(r):
    hole = _rect(r, *HOLE)
    return (
        Cell(0, "runway", "09/27",
             _rect(r, -_tr.RUN_LEN / 2, -HALF_WIDTH, _tr.RUN_LEN / 2, HALF_WIDTH),
             (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(r, -400.0, Y0, -100.0, Y1),
             (), None, "D", "airside", "apron", {}),
        Cell(2, "building", "padA", _rect(r, -100.0, Y0, 200.0, Y1),
             (hole,), None, None, "airside", "pad", {}),
        Cell(3, "apron", "apronA", hole, (), None, "D", "airside", "apron", {}),
    )


@pytest.fixture(scope="module")
def solved(law):
    airport, r = _tr._airport(law, _BumpDem())
    pm, _st = build(airport, Classification(_cells(r), (), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    pm = with_taxi_trend(pm, law, airport)
    pm = with_apron_trend(pm, law, airport, {})
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    return pm, np.asarray(sol.z, float)


def _face(pm, role):
    return [f for f in pm.faces.values() if f.role == role]


def test_the_island_is_a_courtyard_and_leaves_stage_one(solved, law):
    pm, _z = solved
    court = courtyard_faces(pm, law)
    isl = [f for f in _face(pm, "apron") if f.id in court]
    assert len(isl) == 1 and len(court) == 1
    cv = courtyard_vertices(pm, law)
    assert cv and not (cv & airside_stage_vertices(pm, law))
    air = frozenset(apron_roles(law)) & airside_stage_roles(law)
    assert all(not (set(b) & cv) for b in _apron_bodies(pm, law, air))


def test_the_island_takes_the_pad_rim_level(solved, law):
    """0 step: every island vertex on the pad's own plane (the plate is
    soft, so within a centimetre), never 3 m up on its own DEM bump."""
    pm, z = solved
    pad = _face(pm, "building")[0]
    rim = [v for ring in (pad.ring, *pad.holes) for v in pm.ring_vertices(ring)]
    xy = np.array([pm.vertices[v].xy for v in rim])
    A = np.c_[xy, np.ones(len(rim))]
    coef, *_ = np.linalg.lstsq(A, z[rim], rcond=None)
    cv = sorted(courtyard_vertices(pm, law))
    pred = np.c_[np.array([pm.vertices[v].xy for v in cv]), np.ones(len(cv))] @ coef
    assert float(np.max(np.abs(z[cv] - pred))) < 0.02
    outer = [v for v in pm.ring_vertices(pad.ring)]
    assert abs(float(np.mean(z[cv])) - float(np.mean(z[outer]))) < 0.05


# ── (ii) the census twin ─────────────────────────────────────────────────
_ROOT = _Path(__file__).resolve().parents[2]


def _cg():
    for p in (_ROOT / "src", _ROOT, _ROOT / "tools"):
        if str(p) not in _sys.path:
            _sys.path.insert(0, str(p))
    spec = _ilu.spec_from_file_location("islands_twin_check_grade",
                                        _ROOT / "tools" / "check_grade.py")
    mod = _ilu.module_from_spec(spec)
    _sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _way(cg, wid, role, sid, pts, z, nodes, nid0, feature=None):
    nids = []
    for k, (x, y) in enumerate(pts):
        n = str(nid0 - k)
        nodes[n] = (y / 111320.0, x / 111320.0)
        nids.append(n)
    tags = {"shapeID": sid}
    if role:
        tags["role"] = role
    if feature:
        tags["o4_feature"] = feature
    return cg.Way(wid=wid, role=role, ref=f"r{wid}", aeroway=role, nids=nids + [nids[0]],
                  elevs=[z] * (len(nids) + 1), tags=tags)


def _rows(cg, island, island_z, *, holes=True):
    nodes: dict = {}
    hole = [(40.0, 40.0), (60.0, 40.0), (60.0, 60.0), (40.0, 60.0)]
    ways = [_way(cg, "-1", "building", "7",
                 [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
                 100.0, nodes, -1),
            _way(cg, "-2", "apron", "8", island, island_z, nodes, -100)]
    feats = [_way(cg, "-3", "", "7", hole, 100.0, nodes, -200,
                  feature="gap_interior_ring")]
    to_m = lambda la, lo: (lo * 111320.0, la * 111320.0)       # noqa: E731
    return cg._check_frontage_near_miss(
        ways, nodes, to_m, face_holes_m=({"7": [hole]} if holes else None),
        feature_ways=feats)


def test_census_reads_an_island_on_the_hole_ring_as_the_pads_own():
    cg = _cg()
    ring = [(40.0, 40.0), (60.0, 40.0), (60.0, 60.0), (40.0, 60.0)]
    # CONTROL: the frame before the fix — every island vertex "inside" the
    # pad at d = 0, judged against the OUTER ring
    assert len(_rows(cg, ring, 98.5, holes=False)) == 4
    assert _rows(cg, ring, 98.5) == []


def test_census_judges_a_vertex_in_a_hole_against_the_hole_ring():
    cg = _cg()
    inner = [(40.5, 40.5), (59.5, 40.5), (59.5, 59.5), (40.5, 59.5)]
    rows = _rows(cg, inner, 99.0)
    assert rows
    for r in rows:
        assert r.distance_m == pytest.approx(0.5, abs=1e-6)
        assert 39.9 <= r.pt_b[0] <= 60.1 and 39.9 <= r.pt_b[1] <= 60.1
        assert r.elev_b == pytest.approx(100.0)
    # within the apron cap over d: lawful
    assert _rows(cg, inner, 100.0) == []


# ── (ii) the verify twin ─────────────────────────────────────────────────
def test_verify_frontage_reads_the_pad_with_its_holes():
    xy = {1: (0.0, 0.0), 2: (100.0, 0.0), 3: (100.0, 100.0), 4: (0.0, 100.0),
          11: (40.0, 40.0), 12: (60.0, 40.0), 13: (60.0, 60.0), 14: (40.0, 60.0)}
    p = SimpleNamespace(xy=xy)
    pad = SimpleNamespace(xy=tuple(xy[v] for v in (1, 2, 3, 4)),
                          holes=((11, 12, 13, 14),),
                          vertex_ids=(1, 2, 3, 4, 11, 12, 13, 14))
    poly = vfront._holed(p, pad)
    assert poly.distance(Point(50.0, 50.0)) == pytest.approx(10.0)
    assert set(vfront._witnesses(p, pad, 50.0, 50.0)) == {11, 12, 13, 14}
    assert set(vfront._witnesses(p, pad, 10.0, 10.0)) == set(pad.vertex_ids)
