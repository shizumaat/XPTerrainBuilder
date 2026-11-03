"""ROADS INSIDE A LOT ARE THE LOT (owner RULINGS 2026-10-14a (2); issue #609):
a mapped road's stretch running ALONG a lot is split off as a LOT CANDIDATE
— a ribbon still, settled at the ramp (``airport/lot_road_settle``); a road
across open ground between lots, or meeting a lot end-on, is no candidate
(``classify/lot_roads.split_lot_candidates``, issue #684: after every mint,
for the patch's ribbons and the pad roads alike)."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.lot_roads import _lot_stretches, split_lot_candidates
from auto_patch_v2.classify.ribbon_mint import mint_osm_ribbons, mint_pad_roads
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.planar import is_late_ref, is_osm_ribbon_ref
from auto_patch_v2.pipeline.stage_one_map import gap_free, ribbon_free
from shapely.geometry import LineString, box


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _cell(i, role, ref, rect, side):
    return Cell(i, role, ref, tuple(box(*rect).exterior.coords)[:-1], (), None, None,
                side, role, {})


def _mint(law, way, pads=(), lots=()):
    """Both mint passes over a runway along y = 0, ``pads`` and groundside
    ``lots`` (rects), then the split: the cells, in order."""
    cells = [Cell(0, "runway", "09/27", tuple(box(0, -15, 1060, 15).exterior.coords)[:-1],
                  (), 2, "B", "airside", "runway", {})]
    cells += [_cell(len(cells) + i, "building", f"pad{i}", r, "airside")
              for i, r in enumerate(pads)]
    cells += [_cell(len(cells) + i, "groundside_pavement", f"lot{i}", r, "groundside")
              for i, r in enumerate(lots)]
    first = {}
    airport = types.SimpleNamespace(osm_ways=(way,), dem=None)

    def add(role, ref, part, kind, cn, cl, ev):
        cells.append(Cell(len(cells), role, ref, tuple(part.exterior.coords)[:-1],
                          tuple(tuple(h.coords)[:-1] for h in part.interiors),
                          cn, cl, "groundside", kind, dict(ev or {})))
    args = (airport,
            types.SimpleNamespace(pavement_union=box(0, -15, 1060, 15), truck_chains=()),
            cells, law, load_rules(), add)
    mint_osm_ribbons(*args, first)
    mint_pad_roads(*args, first)
    out, _stats = split_lot_candidates(cells, airport, law, load_rules())
    return out


def _minted(cells):
    """The cells the mint and the split made: ``(role, ref, polygon, evidence)``."""
    from shapely.geometry import Polygon
    return [(c.role, c.ref, Polygon(c.ring, c.holes), c.evidence) for c in cells
            if c.evidence]


def _way(pts):
    return OsmWay(-3, "airport_small_roads", tuple(pts), False, {"highway": "service"})


#: the road runs from the patch (y = -40) east, then south to a pad outside it
WAY = ((600.0, -40.0), (900.0, -40.0), (900.0, -200.0))
PAD = (880.0, -260.0, 920.0, -180.0)
#: a lot along the road's east edge (the ribbon spans x 896..904)
LOT = (904.0, -170.0, 915.0, -70.0)


def test_a_pad_road_along_a_lot_is_a_candidate(law):
    """SPJC building24's class: the stretch running along the lot is a lot
    CANDIDATE — a ribbon of the road (role, ref serial, the ribbon's whole
    evidence, a LATE cell) naming its lot — and the rest of the road is road
    as before: a partition of the road's footprint."""
    plain = _minted(_mint(law, _way(WAY), [PAD]))
    mine = _minted(_mint(law, _way(WAY), [PAD], [LOT]))
    lot = [(role, ref, p, ev) for role, ref, p, ev in mine if ev.get("lot_candidate")]
    assert [role for role, _ref, _p, _e in lot] == ["service_road"]
    _role, ref, part, ev = lot[0]
    assert ev["lot_candidate"] == "lot0" and ev.get("pad_road") and ev["highway"] == "service"
    assert ref.startswith("small_roads:-3#") and is_osm_ribbon_ref(ref) and is_late_ref(ref)
    assert part.distance(box(*LOT)) < 1e-6
    assert part.area > 0.9 * 8.0 * 100.0          # the 100 m along the lot, full width
    road_m2 = sum(p.area for _r, _f, p, ev in mine if not ev.get("lot_candidate"))
    plain_m2 = sum(p.area for _r, _f, p, _e in plain)
    assert road_m2 + part.area == pytest.approx(plain_m2, abs=1e-6)
    assert any(ev.get("pad_road") for *_x, ev in mine)   # beyond the lot: still road


def test_a_patch_ribbon_along_a_lot_is_a_candidate(law):
    """Issue #684: the patch's own ribbons are read too (a candidate is a
    ribbon, so stage 1 never reads it); its footprint is the road's,
    partitioned."""
    from shapely.geometry import Polygon
    rib = box(600.0, -404.0, 900.0, -396.0)               # a ribbon of y = -400
    lot = (650.0, -410.0, 750.0, -404.0)                  # beside it, to the south
    cells = [Cell(0, "runway", "09/27", tuple(box(0, -15, 1060, 15).exterior.coords)[:-1],
                  (), 2, "B", "airside", "runway", {}),
             _cell(1, "groundside_pavement", "lot0", lot, "groundside"),
             Cell(2, "service_road", "small_roads:-3", tuple(rib.exterior.coords)[:-1], (),
                  None, None, "groundside", "service_road",
                  {"osm_ribbon": 1.0, "highway": "service", "pad_weld": 1.0}),
             _cell(3, "groundside_pavement", "gap:0", (500.0, -420.0, 540.0, -380.0),
                   "groundside")]
    airport = types.SimpleNamespace(
        osm_ways=(_way(((600.0, -400.0), (900.0, -400.0))),), dem=None)
    out, stats = split_lot_candidates(cells, airport, law, load_rules())
    strips = [c for c in out if c.evidence.get("lot_candidate")]
    assert [c.ref for c in strips] == ["small_roads:-3#2"] and stats["lot_candidates"] == 1
    s = strips[0]
    assert (s.role, s.kind, s.side) == ("service_road", "service_road", "groundside")
    assert s.evidence == {**cells[2].evidence, "lot_candidate": "lot0"}   # all kept
    roads = [c for c in out if c.role == "service_road" and c not in strips]
    assert sorted(c.ref for c in roads) == ["small_roads:-3", "small_roads:-3#1"]
    area = sum(Polygon(c.ring, c.holes).area for c in roads + strips)
    assert area == pytest.approx(rib.area, abs=1e-6)       # a partition
    assert [c.id for c in out] == list(range(len(out)))
    # the gap piece is read by no one here: byte-equal (bar its position)
    import dataclasses
    assert [dataclasses.replace(c, id=3) for c in out if c.ref == "gap:0"] == [cells[3]]
    # LATE: absent from the stage-1 map, kept in the last stage's base
    cl = Classification(tuple(out), (), {}, ())
    assert s.ref not in {c.ref for c in ribbon_free(cl).cells}
    assert s.ref in {c.ref for c in (gap_free(cl) or cl).cells}


def test_a_flush_ribbon_inside_the_bands_is_a_candidate_too(law):
    """Owner 2026-11-03 (#684 Q350, replacing Q3): no pavement gap, the lot —
    inside the airside bands' envelope as well (a candidate is late)."""
    lot = (650.0, -50.0, 750.0, -44.0)            # flush south of the ribbon at y = -40
    mine = _minted(_mint(law, _way(WAY[:2]), (), [lot]))
    assert [ev["lot_candidate"] for _r, _ref, _p, ev in mine
            if ev.get("lot_candidate")] == ["lot0"]


@pytest.mark.parametrize("gap, is_lot", [(0.0, True), (0.3, True), (0.5, True), (1.0, False)])
def test_the_pavement_gap_decides(law, gap, is_lot):
    """Owner 2026-11-03 (#684 Q350 / Q363 a): a road up to ``LOT_GAP_M``
    (0.5 m) of pavement gap from a lot is the lot; a wider gap is a road."""
    rib = box(600.0, -404.0, 900.0, -396.0)
    lot = (650.0, -410.0, 750.0, -404.0 - gap)
    cells = [_cell(0, "groundside_pavement", "lot0", lot, "groundside"),
             Cell(1, "service_road", "small_roads:-3", tuple(rib.exterior.coords)[:-1], (),
                  None, None, "groundside", "service_road", {"osm_ribbon": 1.0})]
    airport = types.SimpleNamespace(
        osm_ways=(_way(((600.0, -400.0), (900.0, -400.0))),), dem=None)
    out, stats = split_lot_candidates(cells, airport, law, load_rules())
    assert any(c.evidence.get("lot_candidate") for c in out) is is_lot
    assert stats["lot_candidates"] == int(is_lot)


def test_a_road_meeting_a_lot_end_on_or_crossing_open_ground_stays_road():
    line = LineString([(0.0, 0.0), (100.0, 0.0)])
    end_on = box(100.0, -10.0, 120.0, 10.0)
    assert _lot_stretches(line, end_on, 4.05, 8.0) == []
    from shapely.ops import unary_union
    two = unary_union([box(-20.0, -10.0, 0.0, 10.0), end_on])
    assert _lot_stretches(line, two, 4.05, 8.0) == []
    along = box(0.0, 4.0, 100.0, 10.0)
    [(a, b)] = _lot_stretches(line, along, 4.05, 8.0)
    assert a == pytest.approx(0.0) and b == pytest.approx(100.0)


def test_a_road_along_a_facade_strip_stays_road(law):
    """A §52 facade strip stands at its host pad's level: never a lot
    (MEASURED SPJC, the kerb roads beside the terminal canopies)."""
    rib = box(600.0, -404.0, 900.0, -396.0)
    cells = [_cell(0, "groundside_pavement", "facstrip:building1:0", (650.0, -410.0, 750.0, -404.0),
                   "groundside"),
             Cell(1, "service_road", "small_roads:-3", tuple(rib.exterior.coords)[:-1], (),
                  None, None, "groundside", "service_road", {"osm_ribbon": 1.0})]
    airport = types.SimpleNamespace(
        osm_ways=(_way(((600.0, -400.0), (900.0, -400.0))),), dem=None)
    out, stats = split_lot_candidates(cells, airport, law, load_rules())
    assert stats["lot_candidates"] == 0 and len(out) == 2
