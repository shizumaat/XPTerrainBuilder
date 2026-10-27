"""Twins for lane ``ltramp`` (``docs/findings/tunnel-ramps-ltramp.md``):
#1280 — where a credible lidar reads the road under the cover (a cut along
the bore), that road is the mouth's floor (``planar/lidar_road``); #807 — a
dual ramp's edges are its carriageways' edges station by station
(``planar/dual_width``).  Synthetic airports; law values read from the
tables, never retyped."""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.dual_width import dual_half_fn
from auto_patch_v2.planar.structures import build_structures
from shapely.geometry import LineString, Point, Polygon


class _Berm:
    """700 m ground; a taxiway BERM ``height`` m high for |x| < ``half``;
    with ``notch`` the survey reads the road through it (|y| < 5 m at 700)."""
    provenance = {"synthetic": "berm"}

    def __init__(self, height: float, half: float, notch: bool, lidar: bool = True):
        self.height, self.half, self.notch, self.lidar = height, half, notch, lidar

    def z(self, x: float, y: float) -> float:
        if abs(x) >= self.half or (self.notch and abs(y) < 5.0):
            return 700.0
        return 700.0 + self.height

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)

    def source_pixel_m(self):
        return (1.0, "inset") if self.lidar else (30.0, "inset")


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, dem, ways):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 822.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 822.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), ways, (), (), pack, dem, law.ruleset_key)


def _cells(twy_half: float):
    return Classification((
        Cell(0, "runway", "09/27", _rect(-600, 800, 600, 845), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, "stub", "twy", _rect(-twy_half, -40, twy_half, 40), (), None, "D",
             "airside", "taxiway", {})), (), {}, ())


def _bore_ways():
    t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    r = {"highway": "secondary", "lanes": "2"}
    return (OsmWay(-101, "big_roads", ((-30.0, 0.0), (30.0, 0.0)), False, t),
            OsmWay(-201, "big_roads", ((30.0, 0.0), (900.0, 0.0)), False, r),
            OsmWay(-202, "big_roads", ((-30.0, 0.0), (-900.0, 0.0)), False, r))


@pytest.mark.parametrize("twy_half", [30.0, 20.0])
def test_a_road_the_lidar_reads_under_the_berm_gets_no_ramp(law, twy_half):
    """#1280 / RULINGS 2026-10-27g: the survey reads the road through a 6 m
    taxiway berm at the surrounding ground's level — 6 m under the deck, so
    it clears ``clearance_m``.  Neither mouth builds a ramp (before: floored
    7.5 m under that road), whether the taxiway reaches the portal (the
    mouth would slide) or stops short of it; the refusal names the reading."""
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(6.0, 30.0, notch=True), _bore_ways()), _cells(twy_half), law)
    assert tunnels == ()
    assert len(st.refused) == 2 and all("#1280" in r and "700.00" in r for r in st.refused)


def test_a_surveyed_road_short_of_the_clearance_is_cut_only_the_depth_owed(law):
    """RULINGS 2026-10-27g: a 3.6 m berm over the surveyed road leaves it
    short of ``clearance_m``; only the depth owed is cut at the mouth and
    the ramp climbs from there at the design grade — never ``mouth_depth_m``
    under the surveyed road."""
    tn = law.tables.structures.tunnel
    height = 3.6
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(height, 30.0, notch=True), _bore_ways()), _cells(20.0), law)
    assert len(tunnels) == 2, st.refused
    owed = tn.clearance_m - height
    for t in tunnels:
        assert t.mouth_z == pytest.approx(700.0 - owed, abs=0.05), t.notes
        assert t.mouth_z > 700.0 - tn.mouth_depth_m + 1.0
        assert any("2026-10-27g" in n for n in t.notes)


@pytest.mark.parametrize("notch,lidar", [(False, True), (True, False)])
def test_without_the_lidar_reading_the_road_the_default_depth_stands(law, notch, lidar):
    """No notch (the survey reads the cover), or no credible survey: the
    floor is the ground over the mouth less ``mouth_depth_m``, as before."""
    tn = law.tables.structures.tunnel
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(6.0, 30.0, notch=notch, lidar=lidar), _bore_ways()),
        _cells(30.0), law)
    assert len(tunnels) == 2, st.refused
    for t in tunnels:
        assert t.mouth_z <= 700.0 + 6.0 - tn.mouth_depth_m + tn.ramp_grade * 5.0
    assert not any("#1280" in r for r in st.refused)


class _M:
    def __init__(self, approach, width):
        self.approach, self.width_m = approach, width


def test_a_dual_ramp_follows_its_carriageways_station_by_station():
    """#807: two 7 m carriageways 9 m apart at the mouth spreading to 25 m
    apart 50 m out.  Each station's half widths are the outer carriageway
    edges — never the one widest span."""
    west = [(0.0, 4.5), (20.0, 4.5), (50.0, 12.5)]
    east = [(0.0, -4.5), (20.0, -4.5), (50.0, -12.5)]
    fn = dual_half_fn(lambda s: (s, 0.0), [_M(west, 7.0), _M(east, 7.0)], 15.0)
    assert fn(10.0) == pytest.approx((8.0, 8.0), abs=1e-6)
    left, right = fn(45.0)
    edge = Point(45.0, 0.0).distance(LineString(west)) + 3.5
    assert left > 12.0 and right > 12.0 and left >= edge - 0.5
    assert dual_half_fn(lambda s: (s, 0.0), [_M(west, 7.0)], 3.5) is None


def test_a_built_dual_ramp_is_no_wider_than_its_carriageways_at_the_mouth(law):
    """The built dual: at its mouth the ramp spans the two carriageways
    (9 m apart, 7 m each) — 16 m — not their widest span further out."""
    t = {"highway": "tertiary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    r = {"highway": "tertiary", "lanes": "2"}
    ways = (OsmWay(-101, "big_roads", ((-30.0, 4.5), (30.0, 4.5)), False, t),
            OsmWay(-102, "big_roads", ((-30.0, -4.5), (30.0, -4.5)), False, t),
            OsmWay(-201, "big_roads", ((30.0, 4.5), (60.0, 4.5), (200.0, 16.0)), False, r),
            OsmWay(-202, "big_roads", ((30.0, -4.5), (60.0, -4.5), (200.0, -16.0)), False, r),
            OsmWay(-203, "big_roads", ((-30.0, 4.5), (-900.0, 4.5)), False, r),
            OsmWay(-204, "big_roads", ((-30.0, -4.5), (-900.0, -4.5)), False, r))
    cl, tunnels, st = build_structures(
        _airport(law, _Berm(0.0, 0.0, notch=False, lidar=False), ways), _cells(30.0), law)
    east = [tn for tn in tunnels if tn.axis[0][0] > 0]
    assert east, st.refused
    ramp = [Polygon(c.ring) for c in cl.cells if c.role == "tunnel_ramp" and c.ring[0][0] > 0]
    assert ramp
    x0 = east[0].axis[0][0] + 2.0
    across = LineString([(x0, -40.0), (x0, 40.0)])
    span = max(across.intersection(p).length for p in ramp)
    assert span == pytest.approx(16.0, abs=1.0)
