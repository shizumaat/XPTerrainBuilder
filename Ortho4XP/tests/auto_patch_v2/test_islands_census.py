"""THE PAD'S HOLES IN THE FRONTAGE CENSUS (spec-author ruling 2026-09-28 (ii),
lane ``islands``; issues #77 / #73).

The census and verify frontage checks read pad HOLES: a vertex on a hole
ring is a pad vertex, a vertex in a hole is judged against the hole ring,
never the outer ring (KCLT sweep: 256 of 280 rows were island vertices ON a
hole ring read at ``d = 0`` against the outer ring; CRITICAL motion
237 -> 2 on the census fix alone)."""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path
from types import SimpleNamespace

import pytest
from shapely.geometry import Point

from auto_patch_v2.verify import frontage as vfront

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
