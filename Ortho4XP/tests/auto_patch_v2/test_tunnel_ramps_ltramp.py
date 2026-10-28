"""Twins for lane ``ltramp`` (``docs/findings/tunnel-ramps-ltramp.md``):
#1280 / RULINGS 2026-10-28k R1 — on a credible survey the mouth is measured
from the cover, never from ground already inside the cut
(``planar/lidar_road``); #807 — a
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


def _cells(twy_half: float, role: str = "stub"):
    """The runway, and a ``role`` cell over the bore (a taxiway stub by
    default — airside pavement, as an ``apron`` is; a ``graded_strip`` is
    ground, not pavement)."""
    return Classification((
        Cell(0, "runway", "09/27", _rect(-600, 800, 600, 845), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, role, "twy", _rect(-twy_half, -40, twy_half, 40), (), None, "D",
             "airside", "taxiway", {})), (), {}, ())


def _bore_ways(kind: str = "highway", value: str = "secondary"):
    t = {kind: value, "tunnel": "yes", "lanes": "2", "layer": "-1"}
    r = {kind: value, "lanes": "2"}
    return (OsmWay(-101, "big_roads", ((-30.0, 0.0), (30.0, 0.0)), False, t),
            OsmWay(-201, "big_roads", ((30.0, 0.0), (900.0, 0.0)), False, r),
            OsmWay(-202, "big_roads", ((-30.0, 0.0), (-900.0, 0.0)), False, r))


@pytest.mark.parametrize("twy_half", [30.0, 20.0])
def test_a_road_the_survey_reads_under_a_taxiway_goes_to_the_mouth_depth(law, twy_half):
    """RULINGS 2026-10-28k (231 b, replacing 27g's 5 m keep under a runway or
    taxiway): the survey reads the road through a 6 m taxiway berm.  The
    mouth is measured from the COVER (the berm, 706) — 7.5 m under it — so
    only 1.5 m is cut under the surveyed road, never 7.5 m under the road
    (the double cut), whether the taxiway reaches the portal or not."""
    tn = law.tables.structures.tunnel
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(6.0, 30.0, notch=True), _bore_ways()), _cells(twy_half), law)
    assert len(tunnels) == 2, st.refused
    for t in tunnels:
        # (a mouth sliding off the taxiway climbs on the road's profile, #1028)
        assert t.mouth_z == pytest.approx(706.0 - tn.mouth_depth_m, abs=tn.ramp_grade * 5.0)
        assert t.mouth_z < 700.0 - 1.0, t.notes
        # the ONE value the constraint ties the floor to its cap by
        assert t.depth_m == pytest.approx(t.mouth_dem_z - t.mouth_z, abs=1e-6)
        assert any("2026-10-28k" in n for n in t.notes)


def test_a_road_the_survey_reads_under_an_apron_goes_to_the_mouth_depth(law):
    """231 b: an apron is pavement too — 7.5 m under the cover."""
    tn = law.tables.structures.tunnel
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(6.0, 30.0, notch=True), _bore_ways()), _cells(20.0, "apron"), law)
    assert len(tunnels) == 2, st.refused
    for t in tunnels:
        assert t.mouth_z == pytest.approx(706.0 - tn.mouth_depth_m, abs=0.05), t.notes


def test_a_road_the_survey_reads_under_ground_clearing_5_m_is_kept(law):
    """232 a: away from pavement a surveyed road already clearing
    ``clearance_m`` under its cover is kept — refused by name, nothing cut."""
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(6.0, 30.0, notch=True), _bore_ways()), _cells(20.0, "graded_strip"),
        law)
    assert tunnels == ()
    assert len(st.refused) == 2 and all("carries the road" in r and "232 a" in r
                                        for r in st.refused)


class _Trench(_Berm):
    """A road in an open cut: ground 706 except a 20 m wide trench at 700
    along y = 0 out to |x| < 120, and the berm over the bore."""

    def z(self, x: float, y: float) -> float:
        if abs(y) < 10.0 and abs(x) < 120.0:
            return 700.0
        return 706.0


def test_a_kept_mouth_keeps_the_zones_off_the_surveyed_trench(law):
    """R2 (230 a): a mouth the survey carries builds no corridor, so its open
    approach — out to where the surveyed road comes up to the cover, never
    longer than the design ramp the old law built (``clearance /
    ramp_grade``) — is a keepout the adjacent-ground zones stop at."""
    tn = law.tables.structures.tunnel
    cl, tunnels, st = build_structures(
        _airport(law, _Trench(6.0, 30.0, notch=True), _bore_ways()),
        _cells(20.0, "graded_strip"), law)
    assert tunnels == () and st.survey_cuts == 2, st.refused
    ext = [max(abs(x) for x, _y in k) for k in cl.keepouts]
    assert len(ext) == 2 and all(110.0 <= e <= 125.0 for e in ext), ext
    cl, _t, st = build_structures(
        _airport(law, _Berm(6.0, 30.0, notch=True), _bore_ways()),
        _cells(20.0, "graded_strip"), law)
    ext = [max(abs(x) for x, _y in k) for k in cl.keepouts]
    assert ext and all(e <= 30.0 + 6.0 / tn.ramp_grade + 5.0 for e in ext), ext


def test_a_surveyed_road_short_of_the_clearance_is_cut_only_the_depth_owed(law):
    """27g's blend, kept by 232 a away from pavement: a 3.6 m berm of ground
    over the surveyed road leaves it short of ``clearance_m``; only the depth
    owed is cut at the mouth."""
    tn = law.tables.structures.tunnel
    height = 3.6
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(height, 30.0, notch=True), _bore_ways()),
        _cells(20.0, "graded_strip"), law)
    assert len(tunnels) == 2, st.refused
    owed = tn.clearance_m - height
    for t in tunnels:
        assert t.mouth_z == pytest.approx(700.0 - owed, abs=0.05), t.notes
        assert t.mouth_z > 700.0 - tn.mouth_depth_m + 1.0


def test_no_sign_of_a_cut_on_a_credible_survey_cuts_nothing(law):
    """232 a: a tagged tunnel where neither the survey nor a ground rise shows
    a cut (flat ground, a credible survey) is refused by name."""
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(0.0, 30.0, notch=False), _bore_ways()), _cells(20.0), law)
    assert tunnels == ()
    assert len(st.refused) == 2 and all("shows no cut" in r for r in st.refused)


def test_rail_follows_the_survey_and_is_never_deepened(law):
    """233 a: a railway the survey reads under the taxiway berm is never
    deepened to the road's mouth depth — the survey carries it."""
    _cl, tunnels, st = build_structures(
        _airport(law, _Berm(6.0, 30.0, notch=True), _bore_ways("railway", "rail")),
        _cells(20.0), law)
    assert tunnels == ()
    assert all("rail follows the survey" in r for r in st.refused), st.refused


def test_a_rail_ramp_on_coarse_elevation_is_longer_than_a_roads(law):
    """233 a: "where there's a tunnel mouth they need a longer ramp than a
    road" — on a coarse DEM a rail ramp is built at ``rail_ramp_grade``,
    never steeper than ``rail_ramp_max_grade``, and runs longer than the
    road's over the same berm."""
    tn = law.tables.structures.tunnel
    got = {}
    for kind, value in (("highway", "secondary"), ("railway", "rail")):
        _cl, tunnels, st = build_structures(
            _airport(law, _Berm(6.0, 30.0, notch=False, lidar=False), _bore_ways(kind, value)),
            _cells(30.0), law)
        assert len(tunnels) == 2, st.refused
        got[kind] = tunnels
    for t in got["railway"]:
        assert tn.rail_ramp_grade - 1e-9 <= t.design_grade <= tn.rail_ramp_max_grade + 1e-9
    assert min(t.top_s for t in got["railway"]) > max(t.top_s for t in got["highway"])


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
    assert not any("2026-10-28k" in r for r in st.refused)


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
