"""M3b twins: the mixed-pad groundside cut-back (09-01g/i), the near-miss
frontage law (08-08) as generator + verify reader, and the per-station
lateral-contiguity walk (08-02 clause 2 / 08-28 Amendment 2) as
generator + publication + verify reader.  One synthetic airport: an apron
with a pad WELDED to it, a second pad 0.7 m OFF it (the SPJC building29
class), a mixed pad touching the apron and a groundside lot, and a
service road running beside the apron.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine, _cut_back_groundside
from auto_patch_v2.classify import load_rules
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints import contiguity, pads, roads
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.verify import census


class _PlaneDem:
    provenance = {"synthetic": "plane 1 % up-slope in x, 2 m terrace at y > 260"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.01 * x + (2.0 if y > 260.0 else 0.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubB", _rect(-11.5, 22.5, 11.5, 103), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "apron", "apron1", _rect(-200, 103, 200, 250), (), None, None,
             "airside", "apron", {}),
        # welded pad on the apron's north edge
        Cell(3, "building", "pad_weld", _rect(-150, 250, -90, 290), (), None, None,
             "airside", "pad", {}),
        # near-miss pad: 0.7 m off the apron edge (SPJC building29 class)
        Cell(4, "building", "pad_near", _rect(-40, 250.7, 20, 290), (), None, None,
             "airside", "pad", {}),
        # mixed pad: touches the apron (south) and a groundside lot (north)
        Cell(5, "building", "pad_mixed", _rect(80, 250, 140, 290), (), None, None,
             "airside", "pad", {}),
        Cell(6, "groundside_pavement", "lot1", _rect(60, 290, 160, 340), (), None, None,
             "groundside", "groundside", {}),
        # a service road beside the apron's east edge, 6 m wide
        Cell(7, "service_road", "road1", _rect(200, 103, 206, 250), (), None, None,
             "groundside", "road", {}),
    ]


@pytest.fixture(scope="module")
def synthetic(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 694.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _PlaneDem(), law.ruleset_key)
    cells, n_cut = _cut_back_groundside(_cells(), law, load_rules())
    cuts = (CutLine("taxi_centerline", "stubB", ((0.0, 0.0), (0.0, 103.0))),
            CutLine("road_centerline", "road1", ((203.0, 103.0), (203.0, 250.0))))
    cl = Classification(tuple(cells), cuts, {"mixed_pad_cutbacks": n_cut}, ())
    pm, stats = build(airport, cl, law)
    return airport, pm, stats, cl


def test_mixed_pad_cuts_the_groundside_lot_back(synthetic, law):
    airport, pm, stats, cl = synthetic
    assert cl.stats["mixed_pad_cutbacks"] == 1
    back = law.tables.structures.building_pad.groundside_cutback_m
    lot = next(c for c in cl.cells if c.role == "groundside_pavement")
    # the lot is notched back from the mixed pad by the cut-back (its
    # corners outside the pad's span keep y = 290); the welded pad and the
    # near-miss pad (airside only) cut nothing
    from shapely.geometry import Polygon
    lot_poly = Polygon(lot.ring, lot.holes)
    mixed_c = next(c for c in cl.cells if c.ref == "pad_mixed")
    assert lot_poly.distance(Polygon(mixed_c.ring)) == pytest.approx(back, abs=1e-6)
    assert min(y for _x, y in lot.ring) == pytest.approx(290.0, abs=1e-6)
    assert sum(1 for c in cl.cells if c.role == "groundside_pavement") == 1
    mixed = next(f for f in pm.faces.values() if f.ref == "pad_mixed")
    lot_f = next(f for f in pm.faces.values() if f.role == "groundside_pavement")
    assert not set(pm.ring_vertices(mixed.ring)) & set(pm.ring_vertices(lot_f.ring))


def test_near_miss_frontage_rows_bind_the_offset_pad_only(synthetic, law):
    airport, pm, _s, _cl = synthetic
    rows = pads.frontage_near_miss(pm, law, airport)
    assert rows and all(isinstance(r, Diff) for r in rows)
    refs = {r.source.inputs[3] for r in rows}
    assert refs == {"pad_near"}                     # welded / mixed pads share identity
    near = law.tables.structures.building_pad.frontage_near_miss_m
    # the law is per ENDPOINT: the budget scales with each endpoint's own
    # distance, which exceeds the recognition radius on a long edge that
    # grazes the pad mid-span (the oracle's SPJC 49 m specimen)
    assert any(r.d <= near for r in rows) and all(r.d >= 0.0 for r in rows)
    assert all(r.cap == pytest.approx(law.tables.common.roles["apron"].longitudinal)
               for r in rows)


def test_station_walk_reads_the_apron_beside_the_road(synthetic, law):
    airport, pm, _s, _cl = synthetic
    by_face = contiguity.road_station_caps(pm, law, airport)
    road = [f for f in pm.faces.values() if f.role == "service_road"]
    assert road and all(f.id in by_face for f in road)
    apron_cap = law.tables.common.roles["apron"].longitudinal
    for f in road:
        sts = by_face[f.id]
        assert sts and all(st.cap == pytest.approx(apron_cap) for st in sts if st.cap is not None)
        assert any("apron" in st.roles for st in sts)
    caps = roads.road_law_caps(pm, law, airport)
    assert all(caps[f.id] == pytest.approx(apron_cap) for f in road)
    tags = face_tags(pm, law, airport)
    assert all(f.id in tags for f in road)


def test_round_trip_publishes_station_caps_and_reads_zero(synthetic, law, tmp_path):
    airport, pm, _s, _cl = synthetic
    cs, counts, _w = generate(pm, law, airport)
    assert counts["frontage_near_miss"] > 0 and counts["pad_flats"] == 3
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.OPTIMAL, sol.message
    pub = publication(pm, law, airport, sol.z)
    assert pub["station_caps"] and all(len(e) == 3 for e in pub["station_caps"])
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    rows = census(surf, law, pub, roads.road_law_caps(pm, law, airport))
    assert rows["lateral_contiguity"] == []
    assert rows["frontage_near_miss"] == []
    # the near-miss pad sits at its frontage level, not the DEM terrace
    near = next(f for f in pm.faces.values() if f.ref == "pad_near")
    apron = next(f for f in pm.faces.values() if f.ref == "apron1")
    zn = {round(sol.z[v], 3) for v in pm.ring_vertices(near.ring)}
    assert len(zn) == 1                              # one flat value
    za = [sol.z[v] for v in pm.ring_vertices(apron.ring)]
    assert min(za) - 0.05 <= zn.pop() <= max(za) + 0.05


def test_verify_reader_flags_a_published_cap_looser_than_the_walk(synthetic, law):
    airport, pm, _s, _cl = synthetic
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options())
    pub = publication(pm, law, airport, sol.z)
    loose = dict(pub)
    loose["station_caps"] = [[la, lo, 0.08] for la, lo, _c in pub["station_caps"]]
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    rows = census(surf, law, loose, {})             # no way-level cap either
    assert rows["lateral_contiguity"]
