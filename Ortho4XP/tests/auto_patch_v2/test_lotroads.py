"""ROADS INSIDE A LOT ARE THE LOT (owner RULINGS 2026-10-14a (2); issue #609):
a mapped road's stretch running ALONG a lot is minted as that lot; a road
across open ground between lots, or meeting a lot end-on, stays road
(``classify/lot_roads``, read by ``ribbon_mint._mint_spans``)."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import LineString, box

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.lot_roads import lot_stretches
from auto_patch_v2.classify.ribbon_mint import mint_osm_ribbons, mint_pad_roads
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.pipeline.stage_one_map import gap_free


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _cell(i, role, ref, rect, side):
    return Cell(i, role, ref, tuple(box(*rect).exterior.coords)[:-1], (), None, None,
                side, role, {})


def _mint(law, way, pads=(), lots=()):
    """Both mint passes over a runway along y = 0, ``pads`` and groundside
    ``lots`` (rects): the minted ``(role, ref, polygon, evidence)``."""
    cells = [Cell(0, "runway", "09/27", tuple(box(0, -15, 1060, 15).exterior.coords)[:-1],
                  (), 2, "B", "airside", "runway", {})]
    cells += [_cell(len(cells) + i, "building", f"pad{i}", r, "airside")
              for i, r in enumerate(pads)]
    cells += [_cell(len(cells) + i, "groundside_pavement", f"lot{i}", r, "groundside")
              for i, r in enumerate(lots)]
    out, first = [], {}
    args = (types.SimpleNamespace(osm_ways=(way,), dem=None),
            types.SimpleNamespace(pavement_union=box(0, -15, 1060, 15), truck_chains=()),
            cells, law, load_rules(),
            lambda role, ref, part, kind, cn, cl, ev: out.append((role, ref, part, ev)))
    mint_osm_ribbons(*args, first)
    mint_pad_roads(*args, first)
    return out


def _way(pts):
    return OsmWay(-3, "airport_small_roads", tuple(pts), False, {"highway": "service"})


#: the road runs from the patch (y = -40) east, then south to a pad outside it
WAY = ((600.0, -40.0), (900.0, -40.0), (900.0, -200.0))
PAD = (880.0, -260.0, 920.0, -180.0)
#: a lot along the road's east edge (the ribbon spans x 896..904)
LOT = (904.0, -170.0, 915.0, -70.0)


def test_a_pad_road_along_a_lot_is_the_lot(law):
    """SPJC building24's class: the stretch running along the lot is minted
    as the lot (its role, a ref of its own, ``lot_road``; never a pad road)
    and the rest of the road is road as before."""
    plain = _mint(law, _way(WAY), [PAD])
    mine = _mint(law, _way(WAY), [PAD], [LOT])
    lot = [(role, ref, p, ev) for role, ref, p, ev in mine if ev.get("lot_road")]
    assert [(role, ref) for role, ref, _p, _e in lot] == [("groundside_pavement", "lot0#road0")]
    _role, _ref, part, ev = lot[0]
    assert ev["lot_of"] == "lot0" and not ev.get("pad_road") and ev["lot_road_pad"] == 1.0
    assert part.distance(box(*LOT)) < 1e-6
    assert part.area > 0.9 * 8.0 * 100.0          # the 100 m along the lot, full width
    road_m2 = sum(p.area for _r, _f, p, ev in mine if not ev.get("lot_road"))
    plain_m2 = sum(p.area for _r, _f, p, _e in plain)
    assert road_m2 + part.area == pytest.approx(plain_m2, rel=0.02)
    assert any(ev.get("pad_road") for *_x, ev in mine)   # beyond the lot: still road


def test_a_patch_ribbon_along_a_lot_stays_road_for_now(law):
    """The patch's own ribbons are not read (their strips would re-solve
    stage 1 and move airside: HECA apron 0.62 m, KCLT pads 0.54 m) — the
    owner's question; this pins the shipped scope."""
    lot = (650.0, -50.0, 750.0, -44.0)            # south of the ribbon at y = -40
    mine = _mint(law, _way(WAY[:2]), (), [lot])
    assert mine and not any(ev.get("lot_road") for *_x, ev in mine)


def test_a_road_meeting_a_lot_end_on_or_crossing_open_ground_stays_road():
    line = LineString([(0.0, 0.0), (100.0, 0.0)])
    end_on = box(100.0, -10.0, 120.0, 10.0)
    assert lot_stretches(line, end_on, 4.05, 8.0) == []
    from shapely.ops import unary_union
    two = unary_union([box(-20.0, -10.0, 0.0, 10.0), end_on])
    assert lot_stretches(line, two, 4.05, 8.0) == []
    along = box(0.0, 4.0, 100.0, 10.0)
    [(a, b)] = lot_stretches(line, along, 4.05, 8.0)
    assert a == pytest.approx(0.0) and b == pytest.approx(100.0)


def test_the_lot_strip_stands_in_the_first_stage(law):
    """A lot is solved with the lots (stage 1), never as a last-stage pad
    road: ``gap_free`` keeps the strip and drops the pad roads."""
    mine = _mint(law, _way(WAY), [PAD], [LOT])
    cells = tuple(Cell(i, role, ref, tuple(p.exterior.coords)[:-1], (), None, None,
                       "groundside", role, ev) for i, (role, ref, p, ev) in enumerate(mine))
    base = gap_free(Classification(cells, (), {}, ()))
    kept = {c.ref for c in base.cells}
    assert "lot0#road0" in kept
    assert not any(c.evidence.get("pad_road") for c in base.cells)
