"""Twins of the terrace inside a gap piece (spec §55 (2)-(3), step S1; owner
RULINGS 2026-10-04u, 2026-10-06d): the step cut, the knife, the lot cut, the
floors, and determinism — on synthetic pieces."""
from __future__ import annotations

import pathlib
import pickle
import random

import pytest

from shapely.geometry import box

from auto_patch_v2.classify import gap_terrace as gt
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law

LAW, RULES = Law.for_airport("HECA"), load_rules()
CAP = 0.08
FLOOR = float(LAW.tables.emit.terrace.pad_terrace_floor_m)
FRAMES = pathlib.Path("/Users/noah/XPTerrainBuilderData/.harness/frames/gaps3")


def _run(x0, x1, y, z, cls, n=9, cap=CAP, knife=0.0):
    return [gt.Station((x0 + (x1 - x0) * k / (n - 1), y), z, cls, cap, knife, f"{cls}:r")
            for k in range(n)]


def _canon(cut):
    return sorted((p.suffix, p.kind, p.group, round(p.poly.area, 3),
                   tuple(round(v, 2) for v in p.poly.bounds)) for p in cut.parts)


def test_two_stations_the_cap_cannot_join_cut_the_piece_in_two_with_one_knife():
    piece = box(0, 0, 60, 40)
    st = [gt.Station((27.0, -1.5), 90.0, "pad", CAP, 0.0, "building:a"),
          gt.Station((33.0, -1.5), 95.0, "lot", CAP, 0.0, "parking_lot:b")]
    assert not gt.consistent(*st, CAP, FLOOR)          # 5 m over 6 m
    cut = gt.terrace_cut(piece, st, LAW, RULES, cap=CAP)
    assert len(cut.groups) == 2 and cut.knives == 1 and not cut.merged
    a, b = cut.parts
    assert {a.kind, b.kind} == {"step"} and {a.suffix, b.suffix} == {"/s0", "/s1"}
    assert a.group != b.group
    k = gt.knife_m(LAW)
    assert k <= a.poly.distance(b.poly) <= k + 4 * RULES.cells.snap_grid_m
    # half from each side of the midline x = 30
    assert abs(a.poly.area - b.poly.area) < 1.0
    assert abs((a.poly.area + b.poly.area) - (60 * 40 - a.poly.distance(b.poly) * 40)) < 1.0


def test_two_stations_under_the_floor_weld_and_the_piece_is_not_cut():
    # (i') 0.9 m over 6 m is 15 %: over the cap, under the terrace floor
    piece = box(0, 0, 60, 40)
    st = [gt.Station((27.0, -1.5), 90.0, "pad", CAP, 0.0, "building:a"),
          gt.Station((33.0, -1.5), 90.9, "lot", CAP, 0.0, "parking_lot:b")]
    assert gt.consistent(*st, CAP, FLOOR) and not gt.consistent(*st, CAP, 0.0)
    cut = gt.terrace_cut(piece, st, LAW, RULES, cap=CAP)
    assert len(cut.groups) == 1 and cut.knives == 0 and not cut.merged
    assert [(p.suffix, p.kind) for p in cut.parts] == [("", None)]


def test_a_ramp_short_by_less_than_the_floor_reaches_the_road_with_no_knife():
    # (ii') the owner's pair: 7.14 m over 87.7 m needs 89 m at the cap —
    # 0.12 m short, under the floor: ONE group, and on that line no lot
    piece = box(0, 0, 80, 86.2)
    st = _run(0, 80, 87.7, 99.7, "road") + _run(0, 80, 0.0, 92.56, "apron")
    assert not gt.consistent(st[0], st[9], CAP, 0.0)
    cut = gt.terrace_cut(piece, st, LAW, RULES, cap=CAP)
    assert len(cut.groups) == 1 and cut.knives == 0
    assert all(p.kind != "lot" for p in cut.parts)      # the ramp reaches the road
    assert abs(sum(p.poly.area for p in cut.parts) - piece.area) < 1e-3


def test_a_road_and_an_apron_at_two_levels_make_a_lot_and_a_ramp_on_one_breakline():
    piece = box(0, 0, 80, 100)
    st = _run(0, 80, 101.5, 97.0, "road") + _run(0, 80, 0.0, 92.0, "apron")
    cut = gt.terrace_cut(piece, st, LAW, RULES, cap=CAP)
    assert len(cut.groups) == 1 and cut.knives == 0     # the cap joins them: no step
    kinds = {p.kind: p for p in cut.parts}
    assert set(kinds) == {"lot", "ramp"}
    lot, ramp = kinds["lot"], kinds["ramp"]
    assert (lot.suffix, ramp.suffix) == ("/lot", "/ramp0")
    step = LAW.tables.emit.terrace.gap_cut_sample_m
    depth = ramp.poly.bounds[3] - ramp.poly.bounds[1]
    assert abs(depth - 5.0 / CAP) <= step               # 62.5 m, to a sample
    shared = lot.poly.boundary.intersection(ramp.poly.boundary)
    assert shared.length >= 80.0 - 1e-6                 # ONE breakline, shared
    assert abs(lot.poly.area + ramp.poly.area - piece.area) < 1e-3
    assert lot.poly.distance(box(0, 100, 80, 101)) == 0.0   # the lot is the road's side


def test_neighbours_at_one_level_do_not_cut_the_piece():
    piece = box(0, 0, 80, 100)
    st = _run(0, 80, 101.5, 92.5, "road") + _run(0, 80, 0.0, 92.0, "apron")
    cut = gt.terrace_cut(piece, st, LAW, RULES, cap=CAP)
    assert [(p.suffix, p.kind) for p in cut.parts] == [("", None)]
    assert cut.parts[0].poly.equals(piece)


def test_a_piece_too_small_for_a_lot_is_one_ramp():
    # 5 m of fall needs 62.5 m of ramp; the piece is 64 m deep: 1.5 m of lot
    piece = box(0, 0, 80, 64)
    st = _run(0, 80, 65.5, 97.0, "road") + _run(0, 80, 0.0, 92.0, "apron")
    cut = gt.terrace_cut(piece, st, LAW, RULES, cap=CAP)
    assert [(p.suffix, p.kind) for p in cut.parts] == [("", None)]


def test_a_piece_beside_roads_only_is_one_lot():
    piece = box(0, 0, 80, 40)
    cut = gt.terrace_cut(piece, _run(0, 80, 41.5, 97.0, "road"), LAW, RULES, cap=CAP)
    assert [(p.suffix, p.kind) for p in cut.parts] == [("/lot", "lot")]


def test_a_sliver_between_two_levels_is_merged_and_its_station_reported():
    piece = box(0, 0, 60, 40)
    st = _run(0, 60, -1.5, 90.0, "apron", n=11) \
        + [gt.Station((30.0, 41.5), 99.0, "pad", CAP, 0.0, "building:c")]
    cut = gt.terrace_cut(piece, st, LAW, RULES, cap=CAP)
    assert len(cut.groups) == 2
    # the pad's Voronoi cell is the far half of the piece: it stands
    assert cut.knives == 1 and len(cut.parts) == 2
    tiny = [gt.Station((30.0, 6.0), 99.0, "pad", CAP, 0.0, "building:c")]
    cut2 = gt.terrace_cut(box(0, 0, 60, 5), _run(0, 60, -1.5, 90.0, "apron", n=31) + tiny,
                          LAW, RULES, cap=CAP)
    assert cut2.knives == 0 and len(cut2.parts) == 1
    assert [m["ring"] for m in cut2.merged] == ["building:c"]


def test_the_knife_satisfies_the_three_laws_it_stands_between():
    k = gt.knife_m(LAW)
    em = LAW.tables.emit
    assert k >= em.terrace.separation_m                 # two SHAPES
    assert k >= em.identity.min_distinct_spacing_m      # two NODES at emit
    assert k < em.instrument.step_contact_tol_m         # a DECLARED gap joint


def test_the_cut_does_not_depend_on_the_order_of_its_stations():
    piece = box(0, 0, 120, 100)
    st = (_run(0, 120, 101.5, 97.0, "road") + _run(0, 60, 0.0, 92.0, "apron")
          + [gt.Station((110.0, -1.5), 84.0, "pad", CAP, 0.95, "building:d"),
             gt.Station((121.5, 20.0), 91.0, "lot", CAP, 0.0, "parking_lot:e")])
    want = _canon(gt.terrace_cut(piece, st, LAW, RULES, cap=CAP))
    assert len(want) > 1
    rnd = random.Random(7)
    for _ in range(4):
        sh = list(st)
        rnd.shuffle(sh)
        assert _canon(gt.terrace_cut(piece, sh, LAW, RULES, cap=CAP)) == want


def test_part_kind_reads_the_last_segment_of_the_ref():
    from auto_patch_v2.model.planar import gap_part_kind, is_gap_ref
    want = {"gap:7": None, "gap:7/lot": "lot", "gap:7/lot1": "lot",
            "gap:7/ramp0": "ramp", "gap:0/s4": "step", "gap:0/s4/lot": "lot",
            "gap:0/s12/ramp3": "ramp", "gap:0/s4/lot#2": "lot", "pav7/lot": None}
    assert {r: gap_part_kind(r) for r in want} == want
    assert all(is_gap_ref(r) for r in want if r.startswith("gap:"))


@pytest.mark.skipif(not (FRAMES / "HECA.pkl").exists()
                    or not (FRAMES / "BASE" / "solved.pkl").exists(),
                    reason="frames gaps3 (capture + solved base) not mounted")
def test_the_rule_read_on_a_real_map_gives_the_recorded_counts():
    """(vii) THE FRAME TWIN (spec §55 (7), (13)): the rule's reading of one
    recorded map — a change in these counts is a change in the rule."""
    import dataclasses as dc

    from auto_patch_v2.airport import frame_entry as fe
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.classify import classify
    from auto_patch_v2.pipeline.late_stage import cut_classification
    from auto_patch_v2.planar.cluster import clusters
    from shapely.geometry import Point, Polygon
    with open(FRAMES / "HECA.pkl", "rb") as fh:
        airport = pickle.load(fh)["airport"]
    law = Law.for_airport(airport.icao)
    airport = dc.replace(airport, clusters=clusters(airport, law))
    cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m, fe.quantum(law))
    cl = classify(airport, law, RULES, cache=cache)
    with open(FRAMES / "BASE" / "solved.pkl", "rb") as fh:
        base = pickle.load(fh)
    cl2, rep = cut_classification(cl, base["pm"], base["z"], law, RULES)
    dropped = sum(p["knife_dropped_m2"] for p in rep["pieces"])
    # RE-RECORDED (lane walls3, RULINGS 2026-10-07d): the pair test is the
    # piece's cap + the terrace floor, and the road / ramp cap rose 8 -> 10 %,
    # so fewer pairs cut — (93, 48, 66, 6) at 8 %.
    # RE-RECORDED (lane gapapron4, spec §59 / RULINGS 2026-10-08g): the 11
    # apron-classed pieces of this capture are stage-1 cells and are not cut
    # — (84, 34, 66, 9) with them in the last stage.
    assert (rep["parts"], rep["knives"], rep["merged"], int(dropped)) == (69, 34, 49, 9)
    to_xy = airport.frame.transformers()[0]
    # (the second site read gap:7/ramp0 at the 8 % cap: under 10 % the lot
    # reaches it and no ramp part is cut there)
    sites = {(30.1154841, 31.4105884): "gap:7/lot", (30.1159784, 31.4106264): "gap:7/lot",
             (30.1193169, 31.4085087): "gap:0/s4/lot"}
    for (lat, lon), ref in sites.items():
        pt = Point(*to_xy(lon, lat))
        hit = [c.ref for c in cl2.cells if str(c.ref).startswith("gap:")
               and Polygon(c.ring, c.holes).contains(pt)]
        assert hit == [ref]


def test_a_gap_part_bears_a_shape_by_kind_and_a_plain_groundside_face_does_not():
    """Spec §55 (13): the shapes reader admits a face by role OR by
    ``is_gap_ref`` — no standing groundside face changes."""
    import types

    from auto_patch_v2.model.planar import bears_shape
    roles = set(LAW.tables.emit.terrace.shape_roles)
    assert "groundside_pavement" not in roles
    face = lambda ref, role="groundside_pavement": types.SimpleNamespace(ref=ref, role=role)
    assert bears_shape(face("gap:7/s0"), roles) and bears_shape(face("gap:3"), roles)
    assert not bears_shape(face("dsf:pol10"), roles)
    assert bears_shape(face("pav37", "apron"), roles)
