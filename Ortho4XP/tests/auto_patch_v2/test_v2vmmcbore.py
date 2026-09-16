"""§34 (12) (5) TWINS — A BORE THAT ENTERS A BUILDING IS THE BUILDING'S
RAMP, NOT A TERRAIN TUNNEL; THE SIM'S ELEVATED ROADS CARRY BRIDGES (owner
RULINGS 2026-09-16d; spec ``design-surface-spec.md`` §34 (12) (5)) —
lane `v2vmmcbore`.

The defect, read at VMMC after lane `v2vmmcshore` r6: thirteen tunnel
records still stood at VMMC, eleven of them car-park ramps under Taipa's
buildings — 22-37 m `highway=service tunnel=yes` bores passing under
NOTHING, admitted by their mouth alone (owner 12ab).  Owner
2026-09-16: "There should be no tunnels cut at VMMC because all of the
roads are above ground, all the bridges/overpasses/ramps are handled by
elevated roads provided by the sim, they don't need any trenches cut."

The measured separation the rule stands on (lane `v2vmmcbore`, VMMC dry
`--stage structures` pair): the nine refused bores read cover 0.0 m, no
crossing, ground +0.00 .. +0.33 m over their own ends and NO `layer`;
the two that survive are real Macau road tunnels — `-5994+-5993` (+1.36 m
of ground over it, two `primary` roads across it, `layer -2`) and `-2577`
(+10.53 m, two `primary` roads, `layer -1`).

One synthetic airport per case; every number is read from the law tables.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport.deck_signature import is_enclosure_way
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, OsmWay, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structures import build_structures


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _PlaneDem:
    provenance = {"synthetic": "flat 700 m"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-20000.0, -20000.0, 20000.0, 20000.0)


class _RidgeDem(_PlaneDem):
    """Flat at 700 m but for a ridge of ``rise`` metres over ``|x| <= 60``
    — the hill a real road tunnel is bored through."""

    def __init__(self, rise: float) -> None:
        self.rise = float(rise)

    def z(self, x: float, y: float) -> float:
        return 700.0 + (self.rise if abs(x) <= 60.0 else 0.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


TAGS_BORE = {"highway": "service", "tunnel": "yes", "lanes": "2"}
TAGS_ROAD = {"highway": "service", "lanes": "2"}


def _cells():
    """A runway (so the mouth gate has an approach corridor), an apron a
    bore may pass under, and a pad."""
    return [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(-80, -60, 80, 60), (), None, None,
             "airside", "apron", {}),
    ]


def _run(law, bore_pts, extra_ways=(), dem=None, bore_tags=None):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 700.0,
                      "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 700.0,
                      "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    ways = [OsmWay(-101, "big_roads", tuple(bore_pts), False,
                   dict(bore_tags or TAGS_BORE))]
    ways += list(extra_ways)
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), tuple(ways), (), (), pack,
                      dem or _PlaneDem(), law.ruleset_key)
    cl = Classification(tuple(_cells()), (), {}, ())
    return build_structures(airport, cl, law)


def _ring(wid, ring, tags):
    pts = tuple(ring) + (ring[0],)
    return OsmWay(wid, "airports", pts, True, dict(tags))


def _road(wid, pts, tags=None):
    return OsmWay(wid, "big_roads", tuple(pts), False, dict(tags or TAGS_ROAD))


# ── (5) (a) THE ENCLOSURE CLASS ─────────────────────────────────────────

def test_the_enclosure_predicate_is_one_spelling(law):
    """§34 (12) (5) (a)'s class, read once in ``deck_signature`` beside
    ``is_tunnel_way`` / ``is_bridge_way`` (§33 (6) census row 27: one
    predicate, never a second).  An AT-GRADE surface car park is not an
    enclosure; an underground one is."""
    vals = law.tables.structures.tunnel.enclosure_parking_values
    assert is_enclosure_way({"building": "yes"}, vals)
    assert is_enclosure_way({"building": "parking"}, vals)
    assert is_enclosure_way({"building:part": "roof"}, vals)
    assert is_enclosure_way({"covered": "yes"}, vals)
    assert is_enclosure_way({"amenity": "parking",
                             "parking": "underground"}, vals)
    assert is_enclosure_way({"amenity": "parking",
                             "parking": "multi-storey"}, vals)
    # the negatives
    assert not is_enclosure_way({"amenity": "parking"}, vals)
    assert not is_enclosure_way({"amenity": "parking",
                                 "parking": "surface"}, vals)
    assert not is_enclosure_way({"building": "no"}, vals)
    assert not is_enclosure_way({"covered": "no"}, vals)
    assert not is_enclosure_way({"highway": "service", "tunnel": "yes"}, vals)


def test_a_bore_ending_in_a_BUILDING_is_not_built(law):
    """§34 (12) (5) (a): the bore runs under the apron — so (c) would
    admit it outright — and one mapped end stands inside a building
    footprint.  It is that building's own ramp and NOTHING is built."""
    bld = _ring(-900, _rect(60, -20, 200, 40), {"building": "yes"})
    _cl, tunnels, st = _run(law, ((-40.0, 0.0), (120.0, 0.0)), (bld,))
    assert st.bores == 1
    assert st.tunnels == 0 and not tunnels
    assert st.mouths == 0


def test_a_bore_ending_in_an_UNDERGROUND_PARKING_is_not_built(law):
    """§34 (12) (5) (a), the second class: ``amenity=parking`` with an
    UNDERGROUND ``parking`` value.  A surface lot of the same shape is
    not an enclosure and the same bore is built — the two arms are the
    twin, so the test cannot pass on the ring's geometry alone."""
    box = _rect(60, -20, 200, 40)
    under = _ring(-901, box, {"amenity": "parking", "parking": "underground"})
    surface = _ring(-901, box, {"amenity": "parking", "parking": "surface"})
    _cl, _t, st_under = _run(law, ((-40.0, 0.0), (120.0, 0.0)), (under,))
    _cl2, _t2, st_surface = _run(law, ((-40.0, 0.0), (120.0, 0.0)), (surface,))
    assert st_under.tunnels == 0, "an underground parking carries its own ramp"
    assert st_surface.tunnels >= 1, "a surface lot is not an enclosure"


# ── (5) (c) A TERRAIN TUNNEL PASSES UNDER SOMETHING AT GRADE ────────────

def test_a_bore_under_pavement_with_a_mouth_on_the_field_IS_built(law):
    """§34 (12) (5) (c), the cover witness — and the guard on owner
    12ab's population.  The bore runs the width of the apron; its mouths
    stand on the field.  It is built, mouth and ramp."""
    _cl, tunnels, st = _run(law, ((-120.0, 0.0), (120.0, 0.0)))
    assert st.tunnels >= 1 and tunnels
    assert st.mouths >= 1


def test_a_bore_under_NOTHING_at_grade_is_not_built(law):
    """§34 (12) (5) (c) — THE VMMC DEFECT ITSELF.  A 40 m car-park ramp
    beside the field: its mouth is admitted by §29 (1), and it passes
    under no cover, no road and no rise.  ``mouths off-field`` does NOT
    move (the two reports are never one region) and the refusal is
    NAMED with its evidence."""
    _cl, tunnels, st = _run(law, ((-300.0, -200.0), (-260.0, -200.0)),
                            (_road(-201, ((-260.0, -200.0), (-100.0, -120.0))),))
    assert st.bores == 1
    assert st.tunnels == 0 and not tunnels
    named = [ln for ln in st.mouths_off_field_nearest
             if "NOT A TERRAIN TUNNEL" in ln]
    assert len(named) == 1, st.mouths_off_field_nearest
    assert "PASSES UNDER NOTHING AT GRADE" in named[0]
    assert "-101" in named[0]
    # §29 (1)'s own count is untouched: this mouth was ON the field
    assert st.mouths_off_field == 0


def test_the_same_bore_UNDER_A_ROAD_at_grade_IS_built(law):
    """The matched arm of the case above: ONE variable — a mapped road
    crossing the bore's interior at grade.  That is (5) (c)'s road
    witness and the bore is built."""
    across = _road(-210, ((-280.0, -240.0), (-280.0, -160.0)))
    _cl, tunnels, st = _run(law, ((-300.0, -200.0), (-260.0, -200.0)),
                            (across,
                             _road(-201, ((-260.0, -200.0), (-100.0, -120.0)))))
    assert st.tunnels >= 1, st.mouths_off_field_nearest


def test_a_road_ELEVATED_over_the_bore_is_the_SIMS_road_and_witnesses_nothing(law):
    """§34 (12) (5) (b): "all the bridges/overpasses/ramps are handled by
    elevated roads provided by the sim".  The SAME crossing way, tagged
    ``bridge=yes``, is not a crossing at grade — measured at LEMD, where
    bore ``-3958`` stands under two ``primary`` BRIDGES and nothing
    else, and is not built."""
    over = _road(-211, ((-280.0, -240.0), (-280.0, -160.0)),
                 {"highway": "primary", "bridge": "yes", "layer": "1"})
    _cl, tunnels, st = _run(law, ((-300.0, -200.0), (-260.0, -200.0)),
                            (over,
                             _road(-201, ((-260.0, -200.0), (-100.0, -120.0)))))
    assert st.tunnels == 0 and not tunnels
    # and a `layer >= 1` way with no `bridge` tag is equally elevated
    lifted = _road(-212, ((-280.0, -240.0), (-280.0, -160.0)),
                   {"highway": "primary", "layer": "2"})
    _cl2, _t2, st2 = _run(law, ((-300.0, -200.0), (-260.0, -200.0)),
                          (lifted,
                           _road(-201, ((-260.0, -200.0), (-100.0, -120.0)))))
    assert st2.tunnels == 0


def test_a_way_joined_AT_THE_MOUTH_is_the_approach_not_a_crossing(law):
    """(5) (c)'s crossing is of the bore's INTERIOR — the same
    distinction §34 (12) (4) draws between a deck over the span and one
    over the approach walk.  The approach road above is joined at the
    mouth node and touches nothing else; it is not a witness."""
    _cl, tunnels, st = _run(law, ((-300.0, -200.0), (-260.0, -200.0)),
                            (_road(-201, ((-260.0, -200.0), (-100.0, -120.0))),
                             _road(-202, ((-300.0, -200.0), (-420.0, -120.0)))))
    assert st.tunnels == 0, "a road meeting the mouth is the approach"


def test_the_GROUND_over_a_bore_is_the_fourth_witness(law):
    """(5) (c)'s DEM witness — the BORE's form of §34 (12) (4) (ii).  The
    same bore under the same nothing, twice: under flat ground it is not
    built; under a ridge of ``terrain_rise_m`` it is.  MEASURED at VMMC:
    the nine car-park ramps read +0.00 .. +0.33 m and the three real road
    tunnels +1.10 / +1.36 / +10.53 m."""
    rise = law.tables.structures.tunnel.terrain_rise_m
    pts = ((-100.0, -200.0), (100.0, -200.0))
    apr = (_road(-201, ((100.0, -200.0), (240.0, -120.0))),)
    _cl, _t, flat = _run(law, pts, apr, dem=_RidgeDem(0.0))
    _cl2, _t2, hill = _run(law, pts, apr, dem=_RidgeDem(rise + 0.5))
    assert flat.tunnels == 0
    assert hill.tunnels >= 1, hill.mouths_off_field_nearest


def test_the_bores_own_LAYER_is_the_tag_witness(law):
    """(5) (c)'s tag witness — §34 (12) (4) (i)'s form for a bore.  A
    ``layer <= terrain_layer_max`` is OSM's own statement that the way
    runs below what it crosses.  The SAME geometry that is refused
    untagged is built with ``layer=-1``; VMMC's three real road tunnels
    carry -1 / -2 and its nine car-park ramps carry none at all."""
    lay = law.tables.structures.tunnel.terrain_layer_max
    pts = ((-300.0, -200.0), (-260.0, -200.0))
    apr = (_road(-201, ((-260.0, -200.0), (-100.0, -120.0))),)
    _cl, _t, plain = _run(law, pts, apr)
    _cl2, _t2, deep = _run(law, pts, apr,
                           bore_tags=dict(TAGS_BORE, layer=str(lay)))
    assert plain.tunnels == 0
    assert deep.tunnels >= 1, deep.mouths_off_field_nearest
    # a layer ABOVE the bar states nothing
    _cl3, _t3, shallow = _run(law, pts, apr,
                              bore_tags=dict(TAGS_BORE, layer=str(lay + 1)))
    assert shallow.tunnels == 0


# ── the scoping ────────────────────────────────────────────────────────

def test_a_pack_stated_corridor_is_untouched_by_clause_5(law):
    """§34 (12) (5) is scoped to OSM-DERIVED bores — "pack-stated
    corridors are authored geometry and untouched".  The gate stands
    inside ``structure_approach.mouths()``, which sees ONLY the OSM bore
    chains: an object corridor, a wall corridor, a door ramp and a sunken
    road never pass through it at all.  MEASURED at OTHH: 9 object
    corridors, 73 wall corridors, 4 door wells and 10 basins byte-
    identical across the matched dry pair, and the ONE thing that moved
    is a pack corridor RETURNING — ``wall-corridor:OTHH_Terminal_
    Parking_VCN_004.obj@1``, which the base refused for overlapping the
    OSM parking-ramp bore ``-11191`` that (5) does not build."""
    import inspect

    from auto_patch_v2.planar import structure_approach as sa
    src = inspect.getsource(sa.mouths)
    assert "terrain(b)" in src
    # the witness is built from the BORES argument alone — no corridor,
    # plate or object reaches it
    sig = inspect.signature(sa.mouths)
    assert list(sig.parameters) == ["bores", "osm", "law", "reach_m",
                                    "on_field"]


def test_the_two_reports_are_never_one_region(law):
    """The r1 discipline (§34 (12)'s own census, row T2): §29 (1)'s
    ``mouths off-field`` and (5)'s refusals are separate populations and
    are never added.  A bore refused by (5) leaves ``mouths_off_field``
    exactly where it was, and one dropped by §29 (1) mints no (5) line."""
    # (5)'s refusal: the mouth WAS on the field
    _cl, _t, five = _run(law, ((-300.0, -200.0), (-260.0, -200.0)),
                         (_road(-201, ((-260.0, -200.0), (-100.0, -120.0))),))
    assert five.mouths_off_field == 0
    assert any("§34 (12) (5)" in ln for ln in five.mouths_off_field_nearest)
    # §29 (1)'s drop: 4 km out, nowhere near the field or a corridor
    _cl2, _t2, off = _run(law, ((-9000.0, -9000.0), (-8900.0, -9000.0)))
    assert off.mouths_off_field == 2 and off.tunnels == 0
    assert not any("§34 (12) (5)" in ln for ln in off.mouths_off_field_nearest)


def test_the_covered_tag_reaches_the_reader(law):
    """(5) (a) names ``covered=yes`` and the v2 feed reader's whitelist
    had DROPPED the tag, so the witness could not be read at all.  The
    key is in ``TAGS_OF_INTEREST``, and the drift guard against
    ``O4_Vector_Map.ROADS_TAGS_OF_INTEREST`` is
    ``test_v2othhdet.py``'s."""
    from auto_patch_v2.airport import osm as _osm
    assert "covered" in _osm.TAGS_OF_INTEREST
    for k in ("building", "building:part", "amenity", "parking"):
        assert k in _osm.TAGS_OF_INTEREST, k
