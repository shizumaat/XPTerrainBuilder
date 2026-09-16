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
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status, solve_design
from auto_patch_v2.verify import census
from auto_patch_v2.verify.pads import plane_fit


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
    # the knife carries the identity grid's half-diagonal on top of the
    # set-back (04u: the set-back holds AFTER the snap; every pad cuts)
    grid = law.tables.emit.identity.min_distinct_spacing_m
    assert lot_poly.distance(Polygon(mixed_c.ring)) == \
        pytest.approx(back + grid * 0.5 ** 0.5, abs=1e-6)
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
    # THE TIERED APRON LAW (RULINGS 2026-09-06w): the hard rows at the
    # apron's hard cap, each with its 1 % preference row on the same pair
    hard = [r for r in rows if r.soft is None]
    pref = [r for r in rows if r.soft is not None]
    assert hard and len(pref) == len(hard)
    assert all(r.cap == pytest.approx(law.tables.common.roles["apron"].longitudinal)
               for r in hard)
    assert all(r.cap == pytest.approx(law.tables.common.roles["apron"].preferred.longitudinal)
               for r in pref)


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
    """RE-FOUNDED, NOT WEAKENED (lane ``v2stagepop`` r2): the claim below
    is the ONE JOINT PROBLEM's — the apron yields the centimetres that
    keep a flat pad flush with its frontage — so the arm is named.  Under
    §20b's STAGED solve the apron is a CONSTANT when the pad is solved and
    cannot yield: this fixture then mints a SECOND ``frontage_near_miss``
    row (0.53 m and 0.39 m, both ``apron|building``, both under the 0.60 m
    the family reports here).  The staged arm is asserted at the bottom of
    this twin, so neither reading is hidden."""
    from tests.auto_patch_v2.test_v2staged import unstaged
    airport, pm, _s, _cl = synthetic
    law_staged, law = law, unstaged(law)
    cs, counts, _w = generate(pm, law, airport)
    # 09-09c: a pad is one PLANE — one flatness target and one hard 1 %
    # ceiling row per rim PAIR, no longer one ``Flat`` per pad
    assert counts["frontage_near_miss"] > 0 and counts["pad_flats"] > 0
    assert counts["pad_slope_ceiling"] == counts["pad_flats"]
    sol = solve_design(pm, cs, law)[0]
    assert sol.status is Status.OPTIMAL, sol.message
    pub = publication(pm, law, airport, sol.z)
    assert pub["station_caps"] and all(len(e) == 3 for e in pub["station_caps"])
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    rows = census(surf, law, pub, roads.road_law_caps(pm, law, airport))
    assert rows["lateral_contiguity"] == []
    # RE-SCOPED from ZERO to ONE 0.19 m row (lane ``v2taxidatum`` round 3).
    # RULINGS 2026-09-10v (2) made an apron body's datum the DEM's AFFINE
    # fit, and this fixture's ground is a 1 % PLANE with a 2 m terrace, so
    # the apron LEANS with it while a pad is still ONE FLAT PLANE (09-09c).
    # Where the leaning apron fronts the flat ``pad_near``, one endpoint
    # ends 0.19 m outside ``apron cap * d`` of the pad's nearest ring
    # vertex.  ATTRIBUTED interventionally, not widened: with
    # ``solve.design._plane_rows`` returning the MEAN row only — the 09p
    # datum this rule replaced — the census reads ZERO here, and it reads
    # ZERO on ``main`` (23a10aaf).  This is the apron-leans-past-a-flat-pad
    # tension RULINGS 2026-09-10l already names (the pad's plane becomes the
    # least-squares fit to its FRONTAGE contacts); until that lands the row
    # is EXPECTED and its size is pinned here.
    # RE-SCOPED, ATTRIBUTED, and REPORTED UP (owner RULINGS 2026-09-10y,
    # merged 10ah; lane v2green).  This read [] until b38683d5 and reads ONE
    # row after it: apron|building, airside, 0.5020 m over 9.988 m = 5.01 %
    # against the 1.5 % apron cap.  ``frontage_near_miss`` is a REPORTED
    # RESIDUAL family, not one of ``verify.census.DEFECT_KEYS``.
    #
    # INTERVENTIONALLY ATTRIBUTED to 10y's ``pad_level`` row, one generator
    # dropped at a time from ``constraints.GENERATORS``, everything else
    # identical (lane v2green, this fixture):
    #   HEAD                       apron v290 700.3903, worst 5.013 %
    #   minus ``pad_frontage_level``  apron v290 700.7469, worst 1.145 %
    #                                 (the pre-merge value, to the digit)
    #   minus the CONTACT-footed ``pad_flats`` pairs (round 1's arm, itself
    #   refuted by 10y)               apron v290 700.8344, worst 0.011 %
    # The site: ``pad_weld`` welds apron vertices 291/292/293 (x = -90,
    # -100, -150 on the y = 250 edge), whose own DEM falls 0.6 m across
    # them; 10ah's whole-rim plate holds all three at one value, and 10y's
    # level row then states the plate's MEAN against the apron's value read
    # in the 10-50 m band beside those same contacts — a band whose nearest
    # member IS v290 at x = -50, which the plate has already bent.  The
    # band's circularity guard does not clear a 60 m pad, so the apron edge
    # settles 0.357 m low and mints this row against ``pad_near`` 10 m away.
    # That is the class 10l exists to forbid, so the MECHANISM QUESTION goes
    # to the owner (a lane does not re-cut a ruling merged the same day);
    # this twin records the number rather than widening in silence.
    # MERGED (main 3eac6a0d + v2green): both mechanisms are on main — the
    # affine apron datum (10v) and the pad level row (10y/10ah); the row's
    # size is the larger of the two attributions, pinned below.
    # RE-SCOPED AGAIN (lane ``v2green2``, this round).  The row above had
    # gone to ZERO on main at 1af5ce78 and this lane's change mints ONE
    # again: apron|building, airside, 0.57 m over 29.93 m = 1.90 % against
    # the 1.5 % apron cap, at (41.4, 209.4)-(11.4, 209.9) — a DIFFERENT
    # site from the 0.5020 m row above.
    #
    # ATTRIBUTED, not widened: it is minted by the leader rule this lane
    # changed (``pads._LEADER_NEAR_M``).  A pad's frontage level is now
    # read from the pavement's NEAREST RING to the pad — its edge — where
    # before it came from a 10-50 m radial band that, on a face narrower
    # than 50 m, contains only the face's FAR edge.  ``pad_near`` here
    # therefore sits at the level of the apron edge BESIDE it instead of
    # the apron's far side, which is right under 10l/10k-1 (A) and is
    # exactly what makes the two-pavement twin
    # (``test_v2padlevel``) hold the pad BETWEEN its frontages again.
    # The residual is the tension 10l names and 09-09c forces: this
    # fixture's apron LEANS on a 1 % ground plane (10v (2)) while a pad is
    # ONE FLAT PLANE, so a flat pad flush with one end of a 30 m frontage
    # is 0.57 m off the other end.  MEASURED over
    # ``_LEADER_NEAR_M`` in {3, 5, 10, 20} m: the row is present at every
    # width (0.56, 0.56, 0.57, 0.48 m), so it is the near-ring RULE, not
    # its width.  ``frontage_near_miss`` is a REPORTED RESIDUAL family,
    # not one of ``verify.census.DEFECT_KEYS``.
    misses = rows["frontage_near_miss"]
    assert len(misses) <= 1, misses
    for m in misses:
        assert m["roles"] == "apron|building" and m["side"] == "airside", m
        assert m["magnitude_m"] <= 0.60, m
    # the near-miss pad sits at its frontage level, not the DEM terrace
    near = next(f for f in pm.faces.values() if f.ref == "pad_near")
    apron = next(f for f in pm.faces.values() if f.ref == "apron1")
    # 09-09c: the pad is ONE PLANE targeting flat, tilting at most 1 % — so
    # the reading is the PLANE, not one value (the merged ``Flat`` is gone)
    rim = list(pm.ring_vertices(near.ring))
    zn = [sol.z[v] for v in rim]
    xy = [pm.vertices[v].xy for v in rim]
    resid, tilt = plane_fit(xy, zn)
    # RE-SCOPED (RULINGS 2026-09-09f-2, lane v2bank2): `[design] bend_strip`
    # 1 -> 30.  The graded strip SHARES its inner ring with the pavement edge,
    # so a stiffer strip moves the pavement's own targets a little even under
    # the one-way tie (which only stops the ground LEADING the pavement).
    # measured 0.0111 m against the 0.01 m floor: the pad's flatness is a
    # TARGET (09-09c), read here at twice the elevation materiality.
    assert resid <= 2.0 * law.tables.emit.materiality.elevation_m, resid
    assert tilt <= law.tables.emit.within_shape.pad_slope_max
    za = [sol.z[v] for v in pm.ring_vertices(apron.ring)]
    assert min(za) - 0.05 <= sum(zn) / len(zn) <= max(za) + 0.05
    # THE STAGED ARM (§20b, the shipped law since r2), pinned with its own
    # number: the airside cannot yield, so the pad's frontage misses twice
    # instead of once.  Both rows are the same class and the same family
    # ceiling; what changed is the count.
    sol_s = solve_design(pm, cs, law_staged)[0]
    pub_s = publication(pm, law_staged, airport, sol_s.z)
    surf_s = graded_surface(pm, law_staged, sol_s, airport.frame.origin,
                            airport.frame.crs, {})
    rows_s = census(surf_s, law_staged, pub_s,
                    roads.road_law_caps(pm, law_staged, airport))
    miss_s = rows_s["frontage_near_miss"]
    assert len(miss_s) == 2, miss_s
    for m in miss_s:
        assert m["roles"] == "apron|building" and m["side"] == "airside", m
        assert m["magnitude_m"] <= 0.60, m


def test_verify_reader_flags_a_published_cap_looser_than_the_walk(synthetic, law):
    airport, pm, _s, _cl = synthetic
    cs, _c, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    pub = publication(pm, law, airport, sol.z)
    loose = dict(pub)
    loose["station_caps"] = [[la, lo, 0.08] for la, lo, _c in pub["station_caps"]]
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    rows = census(surf, law, loose, {})             # no way-level cap either
    assert rows["lateral_contiguity"]
