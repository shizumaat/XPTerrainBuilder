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


def _run(law, tmp_path, garage, main=None, roads=None, extra=(), lots=(), kept=None):
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
    if kept is not None:
        seeds = tuple(s._replace(road=kept, kerb_zone=kept.buffer(40.0)) for s in seeds)
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


SKIRT = (100.0, 0.0, 116.0, 60.0)        # a skirt beside the garage, walls deeper still


def _kerb(x0, y0, x1, y1, y):
    k = _wall(x0, y0, x1, y1, y, 20)
    k.height_m = 0.5                     # a slab, no wall
    return k


def test_parts_on_the_main_floors_plane_keep_the_main_floor(law, tmp_path):
    """§19 (owner RULINGS 2026-11-11e, "the road under the departures
    roadway stays level with the kerbside"): a kerbside the object authors
    on the main floor's plane stands on the main floor even where a deeper
    skirt walls it into the seed's footprint; the covered road kept at the
    main floor stays out of the level too (MEASURED KMCI unit 20: the
    kerbside at y -8.0 over a skirt walled to -12.72 fell into the garage's
    level at -10.36)."""
    road = box(115.0, -5.0, 121.0, 75.0)
    seeds, out, reg, _c = _run(law, tmp_path, _garage() + [_wall(*SKIRT, -12.7, 40),
                                                           _kerb(*SKIRT, -8.2)], kept=road)
    (s,) = seeds
    SK = box(*SKIRT)
    assert s.footprint.intersection(SK).area > 0.95 * SK.area
    ref = next(k for k, v in reg.landings.items() if v.get("witness") == "passage")
    lvl = unary_union([r.polygon for r in out if str(r.ref) == ref])
    assert lvl.intersection(box(*GARAGE)).area > 0.8 * box(*GARAGE).area
    assert lvl.intersection(SK).area < 0.05 * SK.area
    assert lvl.intersection(road).area < 1e-6
    main = unary_union([r.polygon for r in out if str(r.ref) == "term/p1"])
    assert main.intersection(SK).area > 0.8 * SK.area
    # without the kerb the skirt's ground is the level's
    _s, out2, reg2, _c2 = _run(law, tmp_path, _garage() + [_wall(*SKIRT, -12.7, 40)], kept=road)
    lvl2 = unary_union([r.polygon for r in out2 if str(r.ref) == ref])
    assert lvl2.intersection(SK).area > 0.5 * SK.area


def test_a_piece_a_kept_floor_cuts_off_the_frontage_is_the_level(law):
    """§19 S2: a piece of the host the level and another floor's ground (a
    road kept at the main floor) cut off from the airside frontage grows
    into the level (``low_level._with_orphans``)."""
    from auto_patch_v2.geom.valid_area import valid_area
    Pd = box(0.0, 0.0, 100.0, 100.0)
    air = box(-40.0, 0.0, 0.0, 100.0)                    # the hall's airside frontage
    L = box(60.0, 0.0, 100.0, 100.0)                     # the garage
    road = box(30.0, 0.0, 40.0, 100.0)                   # kept at the main floor
    grown = LL._with_orphans(L, Pd, air, road, 2.0, 3.0, 0.5, True)
    aisle = box(43.0, 5.0, 57.0, 95.0)                   # between road and garage
    assert grown.intersection(aisle).area > 0.95 * aisle.area
    assert grown.intersection(road).area < 1e-6
    assert grown.intersection(box(0.0, 0.0, 28.0, 100.0)).area < 1e-6  # the hall side stays
    same = LL._with_orphans(L, Pd, air, None, 2.0, 3.0, 0.5, True)
    assert valid_area(same).intersection(aisle).area < 1e-6  # no kept floor: one block
