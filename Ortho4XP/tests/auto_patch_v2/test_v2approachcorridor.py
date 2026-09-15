"""§31 (2) / §29 (1) TWINS — THE APPROACH CORRIDOR, ONE DERIVATION
(owner RULINGS 2026-09-12al, answering 12ae-1: "if it would be visible
from an arriving or departing aircraft it should be cut, if not we can
leave it raw DEM").

What these pin:

* the corridor's SHAPE is the law's — ``approach_km`` beyond each
  threshold along the extended centreline, ``approach_half_width_m`` to
  each side — and both numbers are read from ``emit.toml [cockpit]``,
  never retyped here;
* a mouth INSIDE a corridor but far from the cover is BUILT and counted
  as on-approach; one outside both is DROPPED;
* the ENGINE (``planar/structure_approach``) and the HARNESS
  (``tools/check_grade``) read the SAME class on the SAME airport — the
  engine from the apt.dat thresholds, the harness from the emitted
  runway rings — and get the same rectangle;
* THE RETIRED BUFFER IS GONE: "within ``approach_km`` of a runway axis"
  admitted the whole airport and 5 km of country around it.  It is
  deleted, not gated, and a row 4 km ABEAM a runway — inside the old
  disc, outside every corridor — is beyond view.
"""
from __future__ import annotations

import inspect
import math

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.law.approach_corridor import (ApproachCorridor,
                                                 RunwayViewBand)
from auto_patch_v2.law import tables as _T
from auto_patch_v2.model.airport import (Airport, OsmWay, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar import structure_approach as _sa
from auto_patch_v2.planar.structures import build_structures


class _PlaneDem:
    provenance = {"synthetic": "plane 0.5 % up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.005 * x

    def bounds(self):
        return (-40000.0, -40000.0, 40000.0, 40000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def ck(law):
    return _T.cockpit(law)


TAGS_T = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
TAGS_R = {"highway": "secondary", "lanes": "2"}

#: the fixture runway 09/27: 1,200 m of centreline at y = 522.5, 45 m wide
RWY_A = (-600.0, 522.5)
RWY_B = (600.0, 522.5)


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(-80, -60, 80, 60), (), None, None,
             "airside", "apron", {}),
    ]


def _airport(law, ways=()):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", RWY_A, (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", RWY_B, (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), tuple(ways), (), (), pack, _PlaneDem(),
                   law.ruleset_key)


def _run(law, bore_pts, approaches=()):
    ways = [OsmWay(-101, "big_roads", tuple(bore_pts), False, TAGS_T)]
    ways += [OsmWay(-200 - i, "big_roads", tuple(a), False, TAGS_R)
             for i, a in enumerate(approaches)]
    cl = Classification(tuple(_cells()), (), {}, ())
    return build_structures(_airport(law, ways), cl, law)


# ── the shape of the region ──────────────────────────────────────────────

def test_the_corridor_is_the_law_beyond_each_threshold(law, ck):
    """§31 (2): per runway END, ``approach_km`` beyond the threshold along
    the EXTENDED centreline and ``approach_half_width_m`` to each side.
    Both numbers come from the tables; the corridor starts AT the
    threshold and reaches AWAY from the runway, never back over it."""
    corr = _sa.approach_corridor_of(_airport(law), law)
    length = float(ck.approach_km) * 1000.0
    half = float(ck.approach_half_width_m)
    assert len(corr) == 2                       # one runway, two ends
    assert {e.length_m for e in corr.ends} == {length}
    assert {e.half_width_m for e in corr.ends} == {half}

    # 1 km BEYOND the 27 threshold, on the centreline: in view
    assert corr.holds(RWY_B[0] + 1000.0, RWY_B[1])
    # the same 1 km BACK OVER the runway: not in a corridor at all (the
    # runway itself is the taxi range, not the approach one)
    assert not corr.holds(RWY_B[0] - 1000.0, RWY_B[1])
    # just inside and just outside each far edge
    assert corr.holds(RWY_B[0] + length - 1.0, RWY_B[1] + half - 1.0)
    assert not corr.holds(RWY_B[0] + length + 1.0, RWY_B[1])
    assert not corr.holds(RWY_B[0] + 1000.0, RWY_B[1] + half + 1.0)
    # and the report a dropped mouth is quoted with
    assert corr.distance_m(RWY_B[0] + 1000.0, RWY_B[1]) == 0.0
    assert corr.distance_m(RWY_B[0] + 1000.0,
                           RWY_B[1] + half + 500.0) == pytest.approx(500.0)


def test_an_airport_with_no_runway_has_no_corridor_and_holds_nothing(law):
    """The empty corridor is EMPTY, never vacuously true — a region that
    held everything is exactly the buffer this ruling retired."""
    ap = _airport(law)
    ap = type(ap)(**{**ap.__dict__, "runways": ()})
    corr = _sa.approach_corridor_of(ap, law)
    assert len(corr) == 0 and not corr
    assert not corr.holds(0.0, 0.0)
    assert corr.distance_m(0.0, 0.0) == float("inf")


def test_the_law_refuses_a_corridor_that_is_the_retired_disc(law):
    """The schema's own rule: a half-width at or over the corridor's
    length is the 5 km disc wearing a corridor's name."""
    from auto_patch_v2.law.cockpit_schema import check_cockpit
    import dataclasses as dc
    ck = _T.cockpit(law)
    fams = law.tables.families
    for bad, why in ((0.0, "a zero half-width"),
                     (float(ck.approach_km) * 1000.0, "the disc")):
        with pytest.raises(ValueError):
            check_cockpit(dc.replace(ck, approach_half_width_m=bad), fams,
                          ValueError, law.tables)
    # the shipped table passes
    check_cockpit(ck, fams, ValueError, law.tables)


# ── §29 (7) the runway lateral band ──────────────────────────────────────

def test_the_band_is_the_axis_grown_by_the_law(law, ck):
    """§29 (7) (Fable 2026-09-13; owner RULINGS 2026-09-13bm (ii)): each
    runway's AXIS grown by ``runway_view_half_width_m``.  It runs BESIDE
    the runway, over its whole length — which is exactly where the
    approach corridor never reaches — and it is ONE derivation with the
    corridor, from the SAME axes."""
    band = _sa.runway_band_of(_airport(law), law)
    half = float(ck.runway_view_half_width_m)
    assert len(band) == 1                       # one runway, ONE band
    assert band.ends[0].half_width_m == half
    assert band.ends[0].length_m == pytest.approx(RWY_B[0] - RWY_A[0])

    mid = ((RWY_A[0] + RWY_B[0]) / 2.0, RWY_A[1])
    corr = _sa.approach_corridor_of(_airport(law), law)
    # abeam mid-length, inside the band and in NO corridor — SPJC's own
    # class: 192 m from runway 16R/34L at mid-length, in plain view
    assert band.holds(mid[0], mid[1] + half - 1.0)
    assert not corr.holds(mid[0], mid[1] + half - 1.0)
    # just outside it, and off either end of the axis
    assert not band.holds(mid[0], mid[1] + half + 1.0)
    assert not band.holds(RWY_B[0] + 1.0, RWY_B[1])
    assert band.distance_m(mid[0], mid[1] + half + 500.0) == \
        pytest.approx(500.0)


def test_the_band_and_the_corridor_are_one_derivation(law, ck):
    """Both are ``law/approach_corridor``'s, built from ONE axis source,
    and the harness reads the SAME classes — two copies of a region are
    two regions."""
    import sys
    sys.path.insert(0, "tools")
    import check_grade as cg
    assert cg._RunwayViewBand is RunwayViewBand
    assert _sa.RunwayViewBand is RunwayViewBand

    cl = cg.cockpit_law(refresh=True)
    assert cl["runway_view_half_width_m"] == \
        pytest.approx(float(ck.runway_view_half_width_m))

    def ll_to_m(lat, lon):
        return (lon * 111320.0 * math.cos(math.radians(lat)),
                lat * 110540.0)
    axes = [((-600.0, 0.0), (600.0, 0.0), "09/27")]
    geo = {"boundary_rings": [], "runway_axes": axes, "ll_to_m": ll_to_m,
           "corridor": ApproachCorridor(axes, cl["approach_m"],
                                        cl["approach_half_width_m"]),
           "runway_band": RunwayViewBand(
               axes, cl["runway_view_half_width_m"])}

    def at(x, y):
        lat = y / 110540.0
        lon = x / (111320.0 * math.cos(math.radians(lat)))
        return cg.cockpit_in_view(geo, lat, lon)

    half = cl["runway_view_half_width_m"]
    assert at(0.0, half - 1.0) == (True, "runway")
    assert at(0.0, half + 1.0) == (False, "beyond")
    # the retired disc stays retired: 4 km abeam is still beyond
    assert at(0.0, 4000.0) == (False, "beyond")


def test_the_law_refuses_a_band_wider_than_the_corridor(law):
    """§29 (7): the band is what a pilot reads BESIDE the runway — a
    narrower thing than the corridor ahead of it.  A band at or over the
    corridor's half-width is the retired 5 km disc again."""
    from auto_patch_v2.law.cockpit_schema import check_cockpit
    import dataclasses as dc
    ck = _T.cockpit(law)
    fams = law.tables.families
    for bad in (0.0, float(ck.approach_half_width_m)):
        with pytest.raises(ValueError):
            check_cockpit(dc.replace(ck, runway_view_half_width_m=bad),
                          fams, ValueError, law.tables)
    check_cockpit(ck, fams, ValueError, law.tables)


def test_a_mouth_beside_the_runway_is_built(law, ck):
    """§29 (7)'s own case, synthetically: a portal abeam the runway at
    mid-length, outside ``mouth_standoff_m`` of every classified cell and
    in NO approach corridor, is BUILT — SPJC's −641/−2525 trunk tunnel
    dropped its south mouths 191 m off the cover while 192 m from runway
    16R/34L, and the bore went into the ground and never came out."""
    so = law.tables.structures.tunnel.mouth_standoff_m
    half = float(ck.runway_view_half_width_m)
    # abeam the runway, past the 150 m cover standoff of BOTH cells and
    # inside the 250 m band; the approach corridors are off the ends only
    y = RWY_A[1] - (so + 50.0)
    assert so + 50.0 < half and y - 60.0 > so
    cl2, tunnels, st = _run(law, ((0.0, y), (0.0, y + 30.0)))
    assert st.runway_bands == 1
    assert st.mouths >= 1
    named = " ".join(st.mouths_on_approach_named)
    assert "runway lateral band" in named
    # AMENDED for §34 (12) (1): the BAND admits the mouth (that is §29
    # (7), and it is unchanged); a bore under nothing is still not built.
    # The same bore run UNDER the apron is — one variable, two arms.
    assert st.tunnels == 0 and st.bores_no_service == 1
    _cl, t2, st2 = _run(law, ((0.0, y), (0.0, 0.0)))
    assert st2.bores_no_service == 0 and st2.tunnels >= 1 and t2


# ── the mouth gate (§29 (1)) ─────────────────────────────────────────────

def test_a_mouth_in_the_corridor_far_from_the_cover_is_built(law, ck):
    """OWNER 12al.  A portal 1 km beyond the 27 threshold stands
    kilometres off the classified cover — the 150 m standoff drops it —
    and an arriving aircraft looks straight at it.  It is BUILT, and
    counted as ON APPROACH, never as on the field."""
    so = law.tables.structures.tunnel.mouth_standoff_m
    x = RWY_B[0] + 1000.0
    cl2, tunnels, st = _run(law, ((x, 522.5), (x + 300.0, 522.5)))
    assert st.approach_corridors == 2
    assert st.mouths == 2 and st.mouths_off_field == 0
    assert st.mouths_on_approach == 2
    # AMENDED for §34 (12) (1) (owner RULINGS 2026-09-15f item 1): the
    # corridor's admission of the MOUTH is unchanged and is what this
    # twin measures; the BUILD now also needs the bore to serve the
    # field, and this one passes under nothing at all.
    assert st.bores_no_service == 1
    assert st.tunnels == 0 and tunnels == ()
    assert [c.role for c in cl2.cells].count("tunnel_ramp") == 0
    # the report names it as in view, with its true distance off the field
    assert st.mouths_on_approach_named
    assert "in view" in st.mouths_on_approach_named[0]
    # and it really is far outside the standoff
    assert x - RWY_B[0] > 4.0 * so


def test_a_mouth_outside_the_cover_and_every_corridor_is_dropped(law):
    """The other half of the ruling: outside both regions it is raw DEM.
    South of the apron the along-corridor station is negative at BOTH
    thresholds, so no corridor reaches there however wide it is."""
    # AMENDED for §34 (12) (1): the bore starts UNDER the apron so the
    # SECOND gate admits it and this twin measures the FIRST one alone.
    cl2, tunnels, st = _run(law, ((0.0, 0.0), (0.0, -3000.0)),
                            (((0.0, -3000.0), (0.0, -3900.0)),))
    assert st.mouths == 1 and st.mouths_off_field == 1
    assert st.mouths_on_approach == 0
    assert st.tunnels == 1
    assert "outside every approach corridor" in st.mouths_off_field_nearest[0]


def test_a_bore_with_no_mouth_on_the_field_or_in_view_emits_nothing(law):
    """§29 (2) under the amended region: admission still follows the
    mouth, and a bore with neither an on-field nor an in-view mouth is
    not built at all."""
    cl2, tunnels, st = _run(law, ((0.0, -3000.0), (0.0, -6000.0)))
    assert st.bores == 1 and st.bores_no_mouth == 1
    assert st.mouths == 0 and st.mouths_off_field == 2
    assert st.tunnels == 0 and tunnels == ()
    assert [c.role for c in cl2.cells] == [c.role for c in _cells()]


# ── ONE derivation, two readers ──────────────────────────────────────────

def test_the_engine_and_the_harness_read_one_corridor(law, ck):
    """THE ONE DERIVATION (12al).  The engine builds the corridor from the
    apt.dat thresholds; the harness builds it from the EMITTED runway
    rings' principal axis.  Same class, same law numbers, same rectangle
    — so a mouth the engine builds because a pilot sees it is a mouth the
    census also reads as in view."""
    import sys
    sys.path.insert(0, "tools")
    import check_grade as cg

    # the harness's own two objects
    assert cg._ApproachCorridor is ApproachCorridor
    assert _sa.ApproachCorridor is ApproachCorridor

    engine = _sa.approach_corridor_of(_airport(law), law)

    # the emitted ring of the same runway, as the patch carries it
    hw = 45.0 / 2.0
    ring = [(RWY_A[0], RWY_A[1] - hw), (RWY_B[0], RWY_B[1] - hw),
            (RWY_B[0], RWY_B[1] + hw), (RWY_A[0], RWY_A[1] + hw)]
    from auto_patch.grade_law import runway_axis_and_width
    ax = runway_axis_and_width(ring)
    harness = ApproachCorridor([(ax[0], ax[1], "09/27")],
                               float(ck.approach_km) * 1000.0,
                               float(ck.approach_half_width_m))
    assert len(harness) == len(engine) == 2
    for a, b in zip(sorted(engine.rings()), sorted(harness.rings())):
        for (ax_, ay_), (bx_, by_) in zip(a, b):
            assert math.hypot(ax_ - bx_, ay_ - by_) < 1.0


def test_the_five_km_runway_axis_buffer_is_deleted(law):
    """§31 (2): the first reading — "within ``approach_km`` of a runway
    axis" — admitted the whole airport and everything for 5 km around it.
    It is DELETED, not gated: the census's in-view test takes no radius
    argument any more, keeps no decimated runway point cloud, and a row
    4 km ABEAM a runway (well inside the retired disc) is BEYOND view."""
    import sys
    sys.path.insert(0, "tools")
    import check_grade as cg

    sig = inspect.signature(cg.cockpit_in_view)
    assert list(sig.parameters) == ["geometry", "lat", "lon"]
    src = inspect.getsource(cg.cockpit_geometry) + inspect.getsource(
        cg.cockpit_in_view)
    assert "runway_pts" not in src

    # a frame with ONE east-west runway and no boundary ring
    def ll_to_m(lat, lon):
        return (lon * 111320.0 * math.cos(math.radians(lat)),
                lat * 110540.0)
    cl = cg.cockpit_law(refresh=True)
    axes = [((-600.0, 0.0), (600.0, 0.0), "09/27")]
    geo = {"boundary_rings": [], "runway_axes": axes, "ll_to_m": ll_to_m,
           "corridor": ApproachCorridor(axes, cl["approach_m"],
                                        cl["approach_half_width_m"])}

    def at(x, y):
        lat = y / 110540.0
        lon = x / (111320.0 * math.cos(math.radians(lat)))
        return cg.cockpit_in_view(geo, lat, lon)

    # 4 km abeam the runway's middle: inside the retired 5 km disc, and
    # nowhere an arriving aircraft is looking
    assert at(0.0, 4000.0) == (False, "beyond")
    # 4 km off the 27 threshold, on the centreline: in view
    assert at(4600.0, 0.0) == (True, "approach")
    # 6 km off it: past the corridor's end
    assert at(6600.0, 0.0) == (False, "beyond")
