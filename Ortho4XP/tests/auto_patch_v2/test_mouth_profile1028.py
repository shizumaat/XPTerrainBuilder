"""Twins for issue #1028 — a SLID tunnel mouth continues the road's own
profile out of the mapped portal, the road that reaches grade under the
pavement builds no open ramp, and the ramp's run ends where its axis leaves
the mapped road (``planar/structure_mouth.road_profile``,
``planar/structure_approach.road_end_m``).  Synthetic airports; law values
read from the tables, never retyped."""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structure_approach import road_end_m, road_index
from auto_patch_v2.planar.structures import build_structures
from shapely.geometry import LineString


class _Dem:
    """700 m, or a PLATEAU ``top`` m higher for |x| < ``edge`` (the airport's
    fill; the ground falls to the road beyond its edge)."""
    provenance = {"synthetic": "plateau"}

    def __init__(self, top: float = 0.0, edge: float = 0.0):
        self.top, self.edge = top, edge

    def z(self, x: float, y: float) -> float:
        return 700.0 + (self.top if abs(x) < self.edge else 0.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ways():
    """One bore x in [-60, 60] at y = 0, a straight approach each way."""
    t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    r = {"highway": "secondary", "lanes": "2"}
    return (OsmWay(-101, "big_roads", ((-60.0, 0.0), (60.0, 0.0)), False, t),
            OsmWay(-201, "big_roads", ((60.0, 0.0), (900.0, 0.0)), False, r),
            OsmWay(-202, "big_roads", ((-60.0, 0.0), (-900.0, 0.0)), False, r))


def _airport(law, dem):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 822.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 822.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), _ways(), (), (), pack, dem, law.ruleset_key)


def _cells(twy_half: float, beside_half: float = 0.0):
    """The runway; a taxiway OVER the bore to |x| = ``twy_half``; and, to
    |x| = ``beside_half``, apron strips BESIDE the axis (y 5..15 m either
    side) — pavement the corridor's rim runs into, never over the road."""
    cells = [Cell(0, "runway", "09/27", _rect(-600, 800, 600, 845), (), 3, "D", "airside",
                  "runway", {}),
             Cell(1, "stub", "twy", _rect(-twy_half, -40, twy_half, 40), (), None, "D",
                  "airside", "taxiway", {})]
    if beside_half:
        for k, (y0, y1) in enumerate(((5.0, 15.0), (-15.0, -5.0))):
            cells.append(Cell(2 + k, "apron", f"strip{k}",
                              _rect(-beside_half, y0, beside_half, y1), (), None, "D",
                              "airside", "apron", {}))
    return Classification(tuple(cells), (), {}, ())


def test_under_a_taxiway_the_slid_mouth_keeps_the_bore_depth(law):
    """Flat ground, a taxiway OVER the bore 20 m past each portal: the
    mouths slide to its edge and the road stays at the bore's depth under
    it — the slide never thins the cover over a road under a taxiway."""
    tn = law.tables.structures.tunnel
    _cl, tunnels, st = build_structures(_airport(law, _Dem()), _cells(80.0), law)
    assert len(tunnels) == 2, st.refused
    for t in tunnels:
        assert abs(t.axis[0][0]) - 60.0 > 20.0
        # full depth to the taxiway's edge, the design grade only past it
        out = abs(t.axis[0][0]) - 80.0
        assert t.mouth_z == pytest.approx(700.0 - tn.mouth_depth_m + tn.ramp_grade * out,
                                          abs=1.01 * tn.ramp_grade)


def test_beside_the_pavement_the_slid_mouth_climbs_on_the_road_profile(law):
    """Pavement BESIDE the road (its rim runs into apron strips) slides the
    mouth out; the road under nothing climbs from the portal's floor at the
    design grade, so the mouth's floor is that profile — not a fresh full
    depth under the ground where it now stands."""
    tn = law.tables.structures.tunnel
    _cl, tunnels, st = build_structures(_airport(law, _Dem()), _cells(61.0, 100.0), law)
    assert len(tunnels) == 2, st.refused
    for t in tunnels:
        slide = abs(t.axis[0][0]) - 60.0
        assert slide > 40.0
        top = 700.0 - tn.mouth_depth_m + tn.ramp_grade * slide
        assert top - 0.1 < t.mouth_z <= top + 1e-6
        assert t.depth_m == pytest.approx(t.mouth_dem_z - t.mouth_z, abs=1e-6)


def test_a_road_that_reaches_grade_beside_the_pavement_builds_no_ramp(law):
    """The bore runs under a plateau whose edge stands 20 m past each
    portal; the road beyond it is at grade, and apron strips beside it
    reach 60 m past the portals.  The mouth would stand clear only where
    the road is long since at grade: no open ramp, named — never a
    full-depth trench dug where the road is already at the ground."""
    tn = law.tables.structures.tunnel
    _cl, tunnels, st = build_structures(_airport(law, _Dem(tn.mouth_depth_m, 80.0)),
                                        _cells(61.0, 120.0), law)
    assert tunnels == ()
    assert len(st.refused) == 2
    assert all("reaches grade" in r and "#1028" in r for r in st.refused)


def test_the_run_ends_where_the_axis_leaves_the_mapped_road():
    """The approach walk continues a road that ENDS as a straight line;
    that line is no road.  On a road throughout: no end."""
    ways = (OsmWay(-1, "small_roads", ((0.0, 0.0), (100.0, 0.0)), False,
                   {"highway": "service"}),
            OsmWay(-2, "small_roads", ((100.0, 0.0), (100.0, 80.0)), False,
                   {"highway": "service"}),
            OsmWay(-3, "small_roads", ((0.0, 50.0), (400.0, 50.0)), False,
                   {"highway": "service", "tunnel": "yes"}))
    ix = road_index(ways)
    end = road_end_m(LineString([(0.0, 0.0), (300.0, 0.0)]), ix, 3.5, 1.0)
    assert end == pytest.approx(103.0, abs=1.01)       # the road's end + the half width
    assert road_end_m(LineString([(0.0, 0.0), (90.0, 0.0)]), ix, 3.5, 1.0) is None
    # a TUNNEL way is no road the ramp may follow: no road at all, no road end
    assert road_end_m(LineString([(150.0, 50.0), (300.0, 50.0)]), ix, 3.5, 1.0) is None


def test_a_ramp_hosted_in_an_apron_stops_at_its_edge(law):
    """Clause 3: an apron the ramp lies within from its mouth HOSTS it (and
    is cut) — but the ramp never crosses OUT of it (#1028 Q32: never cross a
    pavement edge).  The design ramp would run ~150 m; the apron (off-centre,
    so no pavement traces the ramp's width from it) ends 100 m
    past the portal, and no ramp cell stands beyond that edge."""
    from shapely.geometry import Polygon as _P
    cells = (Cell(0, "runway", "09/27", _rect(-600, 800, 600, 845), (), 3, "D", "airside",
                  "runway", {}),
             Cell(1, "apron", "host", _rect(55, -12, 160, 40), (), None, "D", "airside",
                  "apron", {}))
    cl2, tunnels, st = build_structures(_airport(law, _Dem()),
                                        Classification(cells, (), {}, ()), law)
    east = [t for t in tunnels if t.axis[0][0] > 0]
    assert east, st.refused
    ramps = [_P(c.ring) for c in cl2.cells if c.role == "tunnel_ramp" and c.ring[0][0] > 0]
    assert ramps and max(x for p in ramps for x, _y in p.exterior.coords) <= 160.0 + 1e-6
