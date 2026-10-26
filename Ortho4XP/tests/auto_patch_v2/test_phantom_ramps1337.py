"""Twins for issues #1337 / #1331 — which mapped ways may cut the ground as a
tunnel (``planar/structure_mouth.road_end_after_slide``,
``airport/deck_signature.is_tunnel_way``).

A slid mouth stays on its road: a bore whose portal stands under pavement
slides its mouth out along the approach (#971), and where the mapped road
ends sooner — the walk meets an at-grade road it will not turn into and
goes on as a straight line — the mouth would stand on no road at all, so
nothing is built (measured NZWN ``-2756``: a 13 m covered forecourt lane
meeting the at-grade ``-2745`` 6 m out, whose slid mouths cut 144 / 84 m
ramps into the forecourt).  The same portal on a road that goes on is a
real portal and keeps its ramp.  A culvert is never a bore.  Synthetic
airports; law values read from the tables, never retyped."""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structures import build_structures


class _Dem:
    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


_LANE = {"highway": "service", "lanes": "1"}
_STUB = 6.0          # the forecourt stub from each portal to the at-grade road


def _short_bore(road_goes_on: bool):
    """A 13 m bore at y = 0 whose stubs meet an at-grade cross road 6 m out
    at each end (the walk refuses its 90° turn); with ``road_goes_on`` the
    stubs continue straight across it for 900 m instead."""
    t = {**_LANE, "tunnel": "yes", "covered": "yes", "layer": "-1"}
    a = 6.5 + _STUB
    ways = [OsmWay(-101, "small_roads", ((-6.5, 0.0), (6.5, 0.0)), False, t),
            OsmWay(-201, "small_roads", ((6.5, 0.0), (a, 0.0)), False, _LANE),
            OsmWay(-202, "small_roads", ((-6.5, 0.0), (-a, 0.0)), False, _LANE),
            OsmWay(-301, "small_roads", ((a, -300.0), (a, 0.0), (a, 300.0)), False,
                   {"highway": "unclassified", "lanes": "2"}),
            OsmWay(-302, "small_roads", ((-a, -300.0), (-a, 0.0), (-a, 300.0)), False,
                   {"highway": "unclassified", "lanes": "2"})]
    if road_goes_on:
        ways += [OsmWay(-203, "small_roads", ((a, 0.0), (900.0, 0.0)), False, _LANE),
                 OsmWay(-204, "small_roads", ((-a, 0.0), (-900.0, 0.0)), False, _LANE)]
    return tuple(ways)


def _airport(law, ways):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 822.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 822.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), ways, (), (), pack, _Dem(), law.ruleset_key)


def _cells(over: tuple[float, float, float, float], role: str = "apron"):
    """The runway, and one airside pavement cell ``over`` the bore."""
    fam = "apron" if role == "apron" else "taxiway"
    return Classification((
        Cell(0, "runway", "09/27", _rect(-600, 800, 600, 845), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, role, "pav", _rect(*over), (), None, "D", "airside", fam, {})), (), {}, ())


def test_a_mouth_that_slides_past_its_road_end_builds_nothing(law):
    """NZWN's class: the portal stands under an apron reaching 40 m past it,
    the road meets an at-grade road 6 m out; the slid mouth would stand on
    the walk's straight extension, so no ramp is built and both ends are
    named."""
    _cl, tunnels, st = build_structures(_airport(law, _short_bore(False)),
                                        _cells((-40.0, -40.0, 40.0, 40.0)), law)
    assert tunnels == (), [t.id for t in tunnels]
    past = [r for r in st.refused if "#1337" in r]
    assert len(past) == 2, st.refused
    assert all("past the mapped road's end" in r for r in past)


def test_the_same_portal_on_a_road_that_goes_on_keeps_its_ramp(law):
    """The control: the same portal under the same apron, the road running
    on beyond the cross road — the slid mouth stands on its road and the
    ramps are built outside the pavement."""
    _cl, tunnels, st = build_structures(_airport(law, _short_bore(True)),
                                        _cells((-40.0, -40.0, 40.0, 40.0)), law)
    assert len(tunnels) == 2, st.refused
    assert not [r for r in st.refused if "#1337" in r]
    for t in tunnels:
        assert abs(t.axis[0][0]) > 40.0          # the mouth stands clear of the apron


@pytest.mark.parametrize("tags", [
    {"waterway": "drain", "tunnel": "culvert", "layer": "-1"},
    {"waterway": "stream", "tunnel": "yes", "layer": "-1"},
    {"highway": "service", "tunnel": "culvert", "layer": "-1"},
])
def test_a_culvert_under_a_taxiway_mints_no_ramp(law, tags):
    """A drain or stream culvert, or any ``tunnel=culvert``, under a taxiway
    is no bore: nothing is cut (``[tunnel] admitted_values``, highway /
    railway only)."""
    ways = (OsmWay(-101, "water", ((-60.0, 0.0), (60.0, 0.0)), False, tags),
            OsmWay(-201, "small_roads", ((60.0, 0.0), (900.0, 0.0)), False, _LANE),
            OsmWay(-202, "small_roads", ((-60.0, 0.0), (-900.0, 0.0)), False, _LANE))
    cl, tunnels, st = build_structures(_airport(law, ways),
                                       _cells((-80.0, -40.0, 80.0, 40.0), "stub"), law)
    assert tunnels == () and st.bores == 0
    assert not [c for c in cl.cells if c.role == "tunnel_ramp"]
