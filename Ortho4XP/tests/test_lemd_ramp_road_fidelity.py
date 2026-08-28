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


# ── F3 ───────────────────────────────────────────────────────────────
#
# The ramp chain's station profile, driven through the REAL emitter
# (``bridges._emit_corridor_ramp_chain``) over a DEM whose only feature
# is a bump on the walk.  The intervention is the bump: with the law OFF
# the emitted quads carry it as an interior local maximum, which is the
# owner's "up-and-down humps and valleys in the ramp".

from shapely.geometry import LineString                        # noqa: E402

_PORTAL_FLOOR_M = 603.3
_WALK = LineString([(0.0, 0.0), (240.0, 0.0)])
_BUMP_AT_M = 160.0
_BUMP_HEIGHT_M = 8.0
_BUMP_SIGMA_M = 15.0


def _bumpy_ground(x):
    """Grade rising 603.3 -> 610 over the walk, with ONE bump on it."""
    base = 603.3 + (610.0 - 603.3) * min(1.0, max(0.0, x / 240.0))
    bump = _BUMP_HEIGHT_M * math.exp(
        -((x - _BUMP_AT_M) ** 2) / (2.0 * _BUMP_SIGMA_M ** 2))
    return base + bump


class _BumpDem:
    """The seam ``_sample_dem`` reads, in the frame the emitter uses."""

    def alt(self, offset):
        """``_sample_dem`` calls ``dem.alt((lon - tile_lon,
        lat - tile_lat))`` — the tile-frame offset pair, not two args."""
        longitude_offset, _latitude_offset = offset
        longitude = longitude_offset + (-4)
        return _bumpy_ground((longitude - _ANCHOR[1]) * 111320.0
                             * math.cos(math.radians(_ANCHOR[0])))


def _chain_profile(monkeypatch, monotone: str):
    monkeypatch.setenv("O4_RAMP_MONOTONE", monotone)
    layout = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)

    def _meters_to_lat_lon(x, y):
        cos_anchor = math.cos(math.radians(_ANCHOR[0]))
        return (_ANCHOR[0] + y / 111320.0,
                _ANCHOR[1] + x / (111320.0 * cos_anchor))

    emitted = bridges._emit_corridor_ramp_chain(
        layout, _BumpDem(), 40, -4, _meters_to_lat_lon,
        _WALK, _WALK.length, _PORTAL_FLOOR_M, 7.0, 20.0,
        refuse_inverted=False, ramp_ref="tunnel_ramp")
    assert emitted, "the chain emitted nothing to measure"
    ramps = [s for s in layout.shapes if s.ref == "tunnel_ramp"]
    # Order the quads by station along the walk and read the profile off
    # the emitted altitudes themselves — the values the sim renders.
    rows = []
    for shape in ramps:
        station = _WALK.project(shape.polygon.centroid)
        low = (shape.altitude if shape.altitude is not None
               else shape.altitude_low)
        high = (shape.altitude if shape.altitude is not None
                else shape.altitude_high)
        rows.append((station, low, high))
    rows.sort()
    return rows


def _station_profile(rows):
    """The chain's STATION profile, reconstructed from the emitted quads.

    A quad ships as an unordered ``(altitude_low, altitude_high)`` pair,
    so the station values are recovered by continuity: each quad's NEAR
    value is the element of its pair closest to the previous quad's far
    value.  This is the profile the sim renders — read off the emitted
    altitudes, never off the solver's internals.
    """
    profile: list = []
    previous = None
    for _station, low, high in rows:
        pair = (float(low), float(high))
        if previous is None:
            near = min(pair) if rows[-1][2] >= rows[0][2] else max(pair)
            profile.append(near)
        else:
            near = (pair[0] if abs(pair[0] - previous)
                    <= abs(pair[1] - previous) else pair[1])
        far = pair[1] if near == pair[0] else pair[0]
        profile.append(far)
        previous = far
    return profile


def _worst_interior_local_max(rows):
    """How far an interior station stands above the LOWEST station after
    it — the PROMINENCE frame, which is what an "up-and-down hump" is."""
    values = _station_profile(rows)
    worst = 0.0
    for index in range(1, len(values) - 1):
        after = min(values[index + 1:])
        worst = max(worst, values[index] - max(after, values[0]))
    return worst


def test_f3_off_arm_reproduces_the_ramp_humps(monkeypatch):
    """THE INTERVENTION.  The profile is a linear blend to the DEM AT
    EACH STATION, so a bump on the walk becomes an interior local
    maximum in the emitted road.  With the law OFF the bump reproduces;
    without this arm the ON arm below proves nothing."""
    rows = _chain_profile(monkeypatch, "0")
    worst = _worst_interior_local_max(rows)
    assert worst >= 0.5, (
        f"the OFF arm's worst interior local maximum is {worst:.3f} m — "
        f"the hump class did not reproduce on this scene")


def test_f3_the_ramp_descends_monotonically(monkeypatch):
    """LAW 3.  One monotone run between the portal floor and grade: no
    interior local maximum beyond the 0.01 m materiality floor."""
    rows = _chain_profile(monkeypatch, "1")
    worst = _worst_interior_local_max(rows)
    assert worst <= 0.01, (
        f"worst interior local maximum {worst:.3f} m over "
        f"{len(rows)} quad(s)")


def test_f3_both_ends_stay_pinned(monkeypatch):
    """The conform is a re-shaping, never a re-datuming: the portal floor
    and the ground tie are exactly where the OFF arm put them."""
    off = _chain_profile(monkeypatch, "0")
    on = _chain_profile(monkeypatch, "1")
    assert min(off[0][1], off[0][2]) == pytest.approx(
        min(on[0][1], on[0][2]), abs=0.05)
    assert max(off[-1][1], off[-1][2]) == pytest.approx(
        max(on[-1][1], on[-1][2]), abs=0.05)


def test_f3_an_already_monotone_profile_is_untouched():
    """The materiality floor: a profile already monotone to 0.01 m is
    returned VERBATIM, so the law rewrites nothing it would not change."""
    straight = [100.0, 101.0, 102.0, 103.0]
    assert bridges._monotone_ramp_profile(straight) is straight
    dipped = [100.0, 101.0, 100.5, 103.0]
    conformed = bridges._monotone_ramp_profile(dipped)
    assert conformed != dipped
    assert conformed == sorted(conformed)
    assert conformed[0] == dipped[0] and conformed[-1] == dipped[-1]


def test_f3_the_descending_direction_is_the_same_law():
    """A corridor falling to a portal is conformed by the same rule —
    direction comes from the profile, never from a caller flag."""
    humped = [110.0, 108.0, 109.5, 106.0, 104.0]
    conformed = bridges._monotone_ramp_profile(humped)
    assert conformed == sorted(conformed, reverse=True)
    assert conformed[0] == humped[0] and conformed[-1] == humped[-1]


def test_f3_ships_default_on(monkeypatch):
    monkeypatch.delenv("O4_RAMP_MONOTONE", raising=False)
    assert bridges.ramp_monotone_law_enabled() is True
    monkeypatch.setenv("O4_RAMP_MONOTONE", "0")
    assert bridges.ramp_monotone_law_enabled() is False


def _fill_chain_rows(monkeypatch, monotone: str):
    monkeypatch.setenv("O4_RAMP_MONOTONE", monotone)
    layout = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)

    def _meters_to_lat_lon(x, y):
        cos_anchor = math.cos(math.radians(_ANCHOR[0]))
        return (_ANCHOR[0] + y / 111320.0,
                _ANCHOR[1] + x / (111320.0 * cos_anchor))

    assert bridges._emit_corridor_ramp_chain(
        layout, _BumpDem(), 40, -4, _meters_to_lat_lon,
        _WALK, _WALK.length, 620.0, 7.0, 20.0,
        refuse_inverted=False, ramp_ref="tunnel_ramp",
        fill_grade=0.04)
    rows = []
    for shape in [s for s in layout.shapes if s.ref == "tunnel_ramp"]:
        rows.append((round(_WALK.project(shape.polygon.centroid), 3),
                     shape.altitude, shape.altitude_low,
                     shape.altitude_high))
    rows.sort()
    return rows


def test_f3_the_bridge_ramp_fill_law_is_out_of_scope(monkeypatch):
    """SCOPE.  The bridge-ramp FILL profile (``fill_grade``, owner ruling
    2026-07-31) is ``max(ground, deck_end - grade * s)`` — fill-only by
    construction and deliberately NOT monotone: it rides the ground where
    the ground comes up.  §F3 must leave it BYTE-IDENTICAL, or the
    conform would cut through the rise that ``max`` exists to preserve.
    """
    assert (_fill_chain_rows(monkeypatch, "1")
            == _fill_chain_rows(monkeypatch, "0"))
