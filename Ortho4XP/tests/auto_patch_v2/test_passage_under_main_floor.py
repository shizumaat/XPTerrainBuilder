"""TWO FLOORS ONE OBJECT WITNESSES (owner RULINGS 2026-11-10h;
``planar/level_regions._upper_floors``).

A terminal's hall stands on its main floor a storey under the apron (the
lower level ``<block>/p1``, ``planar/low_level``); the garage beside it
stands lower still, its walls at the lot, and the roads run along its base.
The passage level is cut out of the main floor where the garage's walls
stand -- the main floor keeps the hall, a riser between the two -- never
read as "no pad" because the main floor took the block; a level already at
the walls' floor, or of another zero, hosts nothing.  The unit's parts set
down outside its pads beside a lot (a garden) stand in a COURT of the
passage level (``planar/passage_court``): the ground under and around them
at the lot's floor, the lot untouched.
"""
from __future__ import annotations

import dataclasses as _dc
import types

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar import level_regions as LR
from auto_patch_v2.planar import low_level as LL
from auto_patch_v2.planar.low_extent import AirRegion
from auto_patch_v2.planar.overlay import Region
from shapely.geometry import box
from shapely.ops import unary_union
from test_two_pads1214 import AIR, P, _airport, _terminal, _wall

GARAGE = (120.0, 0.0, 200.0, 60.0)
GARDEN = (206.0, 42.0, 226.0, 58.0)      # planters outside the pad, at the main floor
LOT = box(204.0, 61.0, 250.0, 90.0)      # the lot at the garage's foot


@pytest.fixture(scope="module")
def law():
    return Law.load(ruleset="faa")


def _cls():
    ring = tuple(AIR.exterior.coords)[:-1]
    return types.SimpleNamespace(cells=[types.SimpleNamespace(ring=ring, holes=(), role="apron")])


def _road(y=30.0):
    return types.SimpleNamespace(id=-1, points=[(100.0, y), (260.0, y)],
                                 tags={"highway": "service"})


def _garage(y=-10.4):
    return [_wall(*GARAGE, y, 200)]


def _garden():
    return [_wall(GARDEN[0] + 5.0 * i, GARDEN[1], GARDEN[0] + 5.0 * i + 4.0, GARDEN[3], -8.1, 4)
            for i in range(4)]


def _run(law, tmp_path, garage, main=None, roads=None, extra=(), lots=()):
    A = _airport(_terminal() + garage + list(extra), tmp_path)
    A.osm_ways = [_road()] if roads is None else list(roads)
    A.frame.transformers = lambda: ((lambda lon, lat: (lon, lat)), (lambda x, y: (y, x)))
    H, L, S, rec = LL.plan_low(P, AIR, A, law, 0.5)
    if main is not None:
        rec = {**rec, **main}
    tmpl = Region(role="building", ref="term", polygon=P, code_number=None, code_letter=None,
                  side="airside", source="cell")
    regs = [_dc.replace(tmpl, polygon=H), _dc.replace(tmpl, ref="term/p1", polygon=L),
            _dc.replace(tmpl, ref="term/p1#strip", polygon=S)]
    reg = Registries()
    reg.held["term"] = {"unit": "term", "datum_pred": 30.0}
    reg.landings["term/p1"] = {"block": "term", "y": rec["y_lo"], "deck": None,
                               "kind": LL.LOW_KIND, **rec}
    seeds, _n = LR.level_seeds(A, _cls(), law)
    counts: dict = {}
    out = LR.seed_levels(regs, reg, seeds, [AirRegion(AIR, "cell")], A, law, 0.5, counts,
                         lots=list(lots))
    return seeds, out, reg, counts


def _area(out, ref):
    return sum(r.polygon.area for r in out if str(r.ref) == ref)


def test_the_passage_is_cut_out_of_the_main_floor(law, tmp_path):
    seeds, out, reg, _c = _run(law, tmp_path, _garage())
    (s,) = seeds
    assert s.depth == pytest.approx(4.6) and s.passage is not None
    (ref, rec), = ((k, v) for k, v in reg.landings.items() if v.get("witness") == "passage")
    assert ref == "term/p2" and rec["block"] == "term" and rec["y_lo"] == pytest.approx(-4.6)
    G = box(*GARAGE)
    lvl = unary_union([r.polygon for r in out if str(r.ref) == ref])
    assert lvl.intersection(G).area > 0.8 * G.area          # the garage's floor is the passage
    # the main floor keeps the hall, never the garage; a riser between them
    main = unary_union([r.polygon for r in out if str(r.ref) == "term/p1"])
    assert main.intersection(G).area < 0.05 * G.area
    assert _area(out, "term/p1") > 0.5 * (100.0 * 70.0 - G.intersection(box(0, 0, 200, 70)).area)
    assert _area(out, ref + "#strip") > 0.0
    # no region overlaps another
    polys = [r.polygon for r in out]
    assert sum(p.area for p in polys) == pytest.approx(unary_union(polys).area, rel=1e-6)


def test_a_level_at_the_walls_floor_already_hosts_nothing(law, tmp_path):
    _s, out, reg, _c = _run(law, tmp_path, _garage(), main={"y_lo": -4.4})
    assert not any(v.get("witness") == "passage" for v in reg.landings.values())
    assert {str(r.ref) for r in out} == {"term", "term/p1", "term/p1#strip"}


def test_a_level_of_another_zero_hosts_nothing(law, tmp_path):
    _s, _out, reg, _c = _run(law, tmp_path, _garage(), main={"top_y": -1.0})
    assert not any(v.get("witness") == "passage" for v in reg.landings.values())


def test_the_garden_beside_the_lot_stands_in_a_court_at_the_lot_floor(law, tmp_path):
    _s, out, reg, _c = _run(law, tmp_path, _garage(), extra=_garden(), lots=[LOT])
    court = [(k, v) for k, v in reg.landings.items() if v.get("piece_of") == "term/p2"]
    assert court, reg.landings.keys()
    ref, rec = court[0]
    assert rec["y_lo"] == pytest.approx(-4.6) and rec["block"] == "term"
    C = unary_union([r.polygon for r in out if str(r.ref) == ref])
    G = box(*GARDEN)
    assert C.intersection(G).area > 0.95 * G.area           # under the garden
    assert C.area > G.area                                   # and around it
    # the lot keeps its own ground: no level, no riser on it, no riser
    # vertex on its edge; the court meets no other floor but across a riser
    assert all(r.polygon.intersection(LOT).area < 1e-6 for r in out)
    assert all(r.polygon.distance(LOT) > 1e-6 for r in out if str(r.ref) == ref + "#strip")
    others = unary_union([r.polygon for r in out if str(r.ref) in ("term", "term/p1")])
    assert C.distance(others) > 1e-6


def test_a_garden_beside_no_lot_has_no_court(law, tmp_path):
    _s, _out, reg, _c = _run(law, tmp_path, _garage(), extra=_garden())
    assert not any(v.get("piece_of") for v in reg.landings.values())


def _slab(x0, y0, x1, y1, y):
    """A footless slab (a road plate, a kerb): no walls, ``height_m`` 0.5."""
    return types.SimpleNamespace(**{**vars(_wall(x0, y0, x1, y1, y, 1)), "feet": (),
                                    "height_m": 0.5})


def _run_beside(law, tmp_path, extra):
    """The garage at the block's east end with a lot's pad north of a band
    of the main floor beside it (RULINGS 2026-11-10n): ``extra`` stands on
    the band."""
    lot = box(165.0, 39.0, 200.0, 100.0)
    A = _airport([*_terminal()[:-1], _wall(0.0, 0.0, 100.0, 70.0, -8.2, 300),
                  _wall(110.0, 0.0, 165.0, 70.0, -10.4, 200),
                  _slab(168.0, 0.0, 200.0, 38.0, -10.4), *extra], tmp_path)
    A.osm_ways = [_road()]
    A.frame.transformers = lambda: ((lambda lon, lat: (lon, lat)), (lambda x, y: (y, x)))
    H, L, S, rec = LL.plan_low(P, AIR, A, law, 0.5)
    tmpl = Region(role="building", ref="term", polygon=P, code_number=None, code_letter=None,
                  side="airside", source="cell")
    regs = [_dc.replace(tmpl, polygon=H.difference(lot)),
            _dc.replace(tmpl, ref="term/p1", polygon=L.difference(lot)),
            _dc.replace(tmpl, ref="term/p1#strip", polygon=S.difference(lot)),
            _dc.replace(tmpl, ref="lotpad", polygon=lot)]
    reg = Registries()
    reg.held["term"] = {"unit": "term", "datum_pred": 30.0}
    reg.landings["term/p1"] = {"block": "term", "y": rec["y_lo"], "deck": None,
                               "kind": LL.LOW_KIND, **rec}
    seeds, _n = LR.level_seeds(A, _cls(), law)
    counts: dict = {}
    out = LR.seed_levels(regs, reg, seeds, [AirRegion(AIR, "cell")], A, law, 0.5, counts)
    return out, reg, counts


def test_a_main_floor_band_no_main_floor_part_stands_on_is_the_passage(law, tmp_path):
    """The band between the garage and the lot's pad holds no part at the
    main floor: its ground is the passage's, at the garage's base."""
    out, reg, counts = _run_beside(law, tmp_path, ())
    (ref, rec), = ((k, v) for k, v in reg.landings.items() if v.get("witness") == "passage")
    band = box(172.0, 2.0, 198.0, 30.0)
    lvl = unary_union([r.polygon for r in out if str(r.ref) == ref])
    assert lvl.intersection(band).area > 0.9 * band.area, counts.get("level_seed_list")
    main = unary_union([r.polygon for r in out if str(r.ref) == "term/p1"])
    assert main.intersection(band).area < 1e-6
    assert main.intersection(box(5.0, 5.0, 95.0, 65.0)).area > 0.9 * 90.0 * 60.0


def test_a_main_floor_band_its_parts_stand_on_keeps_the_main_floor(law, tmp_path):
    """A road plate at the main floor on the band: the author's level there
    is the main floor's, and the band keeps it."""
    out, reg, _c = _run_beside(law, tmp_path, [_slab(172.0, 2.0, 198.0, 30.0, -8.1)])
    (ref, _rec), = ((k, v) for k, v in reg.landings.items() if v.get("witness") == "passage")
    band = box(172.0, 2.0, 198.0, 30.0)
    lvl = unary_union([r.polygon for r in out if str(r.ref) == ref])
    assert lvl.intersection(band).area < 0.05 * band.area
    main = unary_union([r.polygon for r in out if str(r.ref) == "term/p1"])
    assert main.intersection(band).area > 0.9 * band.area

