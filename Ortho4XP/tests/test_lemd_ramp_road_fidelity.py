"""LEMD ramp/road fidelity twins.

Spec: ``docs/specs/lemd-ramp-road-fidelity-spec.md`` (owner sim read of
1.0.265, items 1 and 3).

F1  WALL TOP IS FLAT ACROSS ITS WIDTH.  At every station the perimeter
    band's inner and outer top nodes carry ONE value; along its run the
    top follows the wall's own law.  No per-node independent DEM sample
    across the band.
F2  CORRIDOR WIDTH AND CENTER COME FROM THE WHOLE CROSSING ROAD.  Where
    the road source states a width (``width=`` / ``lanes=``), the bore
    corridor, ramp fan and wall bands take it — no invented default.

Each law is twinned INTERVENTIONALLY: the arm with the law OFF
reproduces the measured defect on the same synthetic scene, so the twin
proves the mechanism and not merely the fix.
"""
import math

import pytest
from shapely.geometry import Point, Polygon

from auto_patch import bridges
from auto_patch.layout import BuiltShape, PavementLayout


_ANCHOR = (40.4984622, -3.5850476)          # the owner's item-1 probe
_WALL_GAP_M = 0.6
_WALL_W_M = 1.0
_RAMP = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 12.0), (0.0, 12.0)])
_RAMP_ALT = 603.4
_AMBIENT_M = 610.0

#: The interventional DEM: a plane tilted ACROSS the band's width (the
#: y axis, which is the axis the two long wall bands stand apart on).
#: 0.5 m/m is the local cut-wall gradient the LEMD site actually carries
#: — the owner measured cross-band pairs 0.5-1.6 m apart over a
#: 1-1.5 m band, which is this slope read off two independent samples.
_DEM_SLOPE_PER_M = 0.5


def _tilted_dem(x, y):
    return _AMBIENT_M + _DEM_SLOPE_PER_M * y


def _band_scene(monkeypatch, station_law: str):
    """One ramp body walled by the perimeter band over a TILTED DEM.

    ``station_law`` is what ``O4_WALL_TOP_STATION`` is set to for the
    arm.  The §T5 foot stays at its shipped default (OFF) so the band
    ships as the single ``tunnel_wall`` piece the owner read in the sim.
    """
    monkeypatch.setenv("O4_WALL_TOP_STATION", station_law)
    monkeypatch.delenv("O4_RAMP_WALL_FOOT", raising=False)
    layout = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)
    ramp = BuiltShape(polygon=_RAMP, role=bridges.ROLE_TUNNEL_RAMP,
                      ref="tunnel_ramp",
                      node_altitudes=[_RAMP_ALT] * 5)
    layout.shapes.append(ramp)
    zones: list = []
    bridges.emit_wall_band(layout, zones, [_RAMP], [ramp], [],
                           _WALL_GAP_M, _WALL_W_M,
                           _tilted_dem, _AMBIENT_M)
    faces = [s for s in layout.shapes if s.ref == "tunnel_wall"]
    return layout, faces


def _ring_open(polygon):
    ring = list(polygon.exterior.coords)
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring


#: A band vertex is INNER when its gap to the walled body is under the
#: band's own mid-width and OUTER when it is over it.  The gaps are not
#: exactly ``wall_gap`` / ``wall_gap + width``: a mitre-joined buffer
#: puts a corner vertex out on the diagonal (0.849 m and 2.263 m for
#: this 0.6/1.0 band), and those corners are the pairs a rectangular
#: ramp actually HAS.
_BAND_MID_GAP_M = _WALL_GAP_M + _WALL_W_M / 2.0


def _cross_band_pairs(face):
    """``[(inner_value, outer_value, station_gap_m)]`` across the band.

    A pair is an inner and an outer vertex at ONE STATION — matched by
    their projection onto the walled body's own ring, which is the read
    the owner's patch measurement made (west band node against east band
    node at one latitude) stated in a frame that survives a corner.
    """
    ring = _ring_open(face.polygon)
    alts = list(face.node_altitudes or [])[:len(ring)]
    inner: list = []
    outer: list = []
    for (vx, vy), value in zip(ring, alts):
        gap = _RAMP.exterior.distance(Point(vx, vy))
        station = _RAMP.exterior.project(Point(vx, vy))
        (inner if gap <= _BAND_MID_GAP_M else outer).append(
            (station, value))
    pairs = []
    for station, value in inner:
        best = None
        for other_station, other_value in outer:
            gap = abs(station - other_station)
            if best is None or gap < best[0]:
                best = (gap, other_value)
        if best is not None and best[0] <= 0.25:
            pairs.append((value, best[1], best[0]))
    return pairs


# ── F1 ───────────────────────────────────────────────────────────────

def test_f1_off_arm_reproduces_the_twisted_wall_top(monkeypatch):
    """THE INTERVENTION.  With the law OFF every band vertex samples the
    DEM at its own position, so a cross-band pair differs by the DEM's
    own rise across the band's width.  This is the defect the owner read
    in the sim, reproduced on a scene whose only variable is the slope.
    """
    _layout, faces = _band_scene(monkeypatch, "0")
    assert faces, "the perimeter band emitted no tunnel_wall face"
    worst = 0.0
    for face in faces:
        for inner, outer, _gap in _cross_band_pairs(face):
            worst = max(worst, abs(inner - outer))
    # The DEM rises _DEM_SLOPE_PER_M across _WALL_W_M of band; the
    # emitted values are rounded to 0.1 m, so the bar sits under that
    # product rather than on it.
    assert worst >= 0.3, (
        f"the OFF arm's worst cross-band delta is {worst:.3f} m — the "
        f"defect this law exists to close did not reproduce, so the ON "
        f"arm below proves nothing")


def test_f1_the_wall_top_carries_one_value_per_station(monkeypatch):
    """LAW 1.  With the law ON the crest is a function of STATION on the
    walled body, so the two vertices facing each other across the band
    carry ONE value — exactly, by construction, not within a tolerance.
    """
    _layout, faces = _band_scene(monkeypatch, "1")
    assert faces, "the perimeter band emitted no tunnel_wall face"
    measured = 0
    worst = 0.0
    for face in faces:
        for inner, outer, _gap in _cross_band_pairs(face):
            measured += 1
            worst = max(worst, abs(inner - outer))
    assert measured >= 4, (
        f"only {measured} cross-band pair(s) found — the scene did not "
        f"produce a band to measure")
    assert worst == pytest.approx(0.0, abs=1e-9), (
        f"worst cross-band delta {worst:.4f} m over {measured} pair(s)")


def test_f1_the_crest_profile_is_the_bodys_own_station_curve():
    """The unit the law is built on: two points that project to ONE
    station on the walled body read ONE crest value, whatever their own
    DEM samples are."""
    profile = bridges._CrestProfile(
        _RAMP, _tilted_dem, _AMBIENT_M, None, 0.05)
    assert profile, "the crest profile degenerated on a plain rectangle"
    # Two points on one normal of the ramp's south edge, 1 m apart.
    near = profile.at((30.0, -_WALL_GAP_M))
    far = profile.at((30.0, -(_WALL_GAP_M + _WALL_W_M)))
    assert near is not None and far is not None
    assert near == pytest.approx(far, abs=1e-9), (
        f"one station gave two crest values: {near} vs {far}")
    # And the profile still VARIES along the run — a law that flattened
    # the whole wall would pass the test above for the wrong reason.
    assert profile.at((30.0, -_WALL_GAP_M)) != pytest.approx(
        profile.at((30.0, 12.0 + _WALL_GAP_M)), abs=1e-6)


def test_f1_off_is_byte_identical_to_the_pre_law_emitter(monkeypatch):
    """The gate's OFF arm is the control: it must reproduce the values
    the emitter carried before §F1, node for node."""
    monkeypatch.setenv("O4_WALL_TOP_STATION", "0")
    assert bridges.wall_top_station_law_enabled() is False
    monkeypatch.setenv("O4_WALL_TOP_STATION", "1")
    assert bridges.wall_top_station_law_enabled() is True
    monkeypatch.delenv("O4_WALL_TOP_STATION", raising=False)
    assert bridges.wall_top_station_law_enabled() is True, (
        "§F1 ships DEFAULT ON")


# ── F2 ───────────────────────────────────────────────────────────────

def test_f2_the_stated_width_beats_the_type_default():
    """LAW 2.  ``lanes=4`` on the way IS a stated width: 4 x 3.5 m, not
    the 6 m the ``service`` row of the type table invents.

    The measured case: LEMD item 3, road-feed way -2096
    (``highway=service``, ``lanes=4``) under the owner's probe, emitted
    at the 6 m default — "about half the width" of the real dual
    carriageway.
    """
    stated = bridges._carriageway_width_from_tags(
        "service", {"highway": "service", "lanes": "4"}, 0.0)
    invented = bridges._carriageway_width_for("service", 0.0)
    assert stated == pytest.approx(14.0), stated
    assert invented == pytest.approx(6.0), invented
    assert stated > invented


def test_f2_the_feed_is_a_width_source(monkeypatch):
    """The tagged source the width resolver must read.

    At LEMD the tile carries no small-roads extract and ``big_roads`` is
    empty at both sites, so ``_mapped_osm_carriageway_width_m`` used to
    resolve NOTHING and the ramp fell back to the portal's own face.  The
    per-airport ROAD FEED — the source ``_load_tunnel_road_network``
    already merges for the tunnel walk — carries the ways WITH their
    ``lanes=`` tags, and the resolver now reads it too.
    """
    layout = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)

    class _Feed:
        source = "regional_extract"
        nodes = {"a": (40.49846, -3.58520), "b": (40.49846, -3.58480)}
        node_tags: dict = {}
        ways = [("-2070", ["a", "b"],
                 {"highway": "service", "lanes": "2"})]

    layout.airport_road_network = _Feed()

    def _to_meters(lon, lat):
        cos_anchor = math.cos(math.radians(_ANCHOR[0]))
        return ((lon - _ANCHOR[1]) * 111320.0 * cos_anchor,
                (lat - _ANCHOR[0]) * 111320.0)

    footprint = Polygon([(-5.0, -5.0), (5.0, -5.0), (5.0, 5.0),
                         (-5.0, 5.0)])
    width = bridges._mapped_osm_carriageway_width_m(
        layout, footprint, _to_meters)
    assert width == pytest.approx(7.0), (
        f"the feed's lanes=2 way resolved to {width}, not 2 x 3.5 m — "
        f"the width the source states")
