"""LEMD ramp/road fidelity round 2 — Amendment 1's two authorised laws.

Spec: ``docs/specs/lemd-ramp-road-fidelity-spec.md``, AMENDMENT 1
(rulings 1 and 2, on lane/lemdfidelity's measured report).

F4  THE ENVELOPE OF EVERY SPELLING.  A portal's corridor centre and width
    cover every spelling of the crossing road — the OSM/feed line we
    derive from AND the DSF vector chain X-Plane actually draws.  One
    spelling's centre is never authority over the other's ribbon.
F5  THE WIDTH THE SOURCE STATES.  A service-road course takes the width
    its own OSM way states (``lanes=`` / ``width=``); a course that
    states none keeps ``config.SERVICE_ROAD_WIDTH_M``, so an untagged
    network is byte-identical.

Both are twinned INTERVENTIONALLY: the arm with the law OFF reproduces
the measured defect on the same scene, so each twin proves a mechanism
and not merely a fix.
"""
import math

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch import bridges
from auto_patch.pavement import service_roads


# ── the measured LEMD item-1 geometry ────────────────────────────────
#: The owner's probe, and the two spellings of the road under it as
#: measured on the control patch: the feed/OSM line the corridor was
#: centred on, and the DSF chain 2.75 m west of it that X-Plane draws.
_ANCHOR = (40.4984622, -3.5850476)
_SPELLING_OFFSET_M = 2.75
_LANES_2_WIDTH_M = 7.0


class _Point:
    def __init__(self, lon, lat, level=0.0):
        self.longitude = lon
        self.latitude = lat
        self.level = level
        self.draped = abs(level) < 0.5


class _Segment:
    def __init__(self, points):
        self.shape_points = points

    @property
    def is_fully_draped(self):
        return all(p.draped for p in self.shape_points)


class _Network:
    def __init__(self, segments):
        self.segments = segments


class _Layout:
    """Only what ``_spelling_edges`` reads."""

    def __init__(self, networks):
        self.anchor = _ANCHOR
        setattr(self, bridges._OBJECT_BRIDGE_ROAD_NETWORKS_ATTRIBUTE,
                networks)


def _chain_at(offset_m: float, level: float = 0.0) -> _Network:
    """A north-south DSF chain standing ``offset_m`` EAST of the anchor."""
    to_m, back = bridges._local_meter_projections(_ANCHOR)
    points = []
    for dy in (-60.0, 0.0, 60.0):
        lat, lon = back(offset_m, dy)
        points.append(_Point(lon, lat, level))
    return _Network([_Segment(points)])


def _envelope(layout, half=_LANES_2_WIDTH_M / 2.0):
    """``(centre, half_width)`` of the cluster envelope at the origin.

    The OSM spelling is the single known member centred on the origin —
    exactly the LEMD cluster, which has one member at ``lanes=2``.
    """
    perp = (1.0, 0.0)            # walk runs north; perpendicular is east
    known = [(-half, half)]
    edges = known + bridges._spelling_edges(
        layout, (0.0, 0.0), perp, half, known)
    low = min(e[0] for e in edges)
    high = max(e[1] for e in edges)
    return 0.5 * (low + high), 0.5 * (high - low)


# ── F4 ───────────────────────────────────────────────────────────────

def test_f4_off_arm_leaves_the_rendered_ribbon_off_centre(monkeypatch):
    """THE INTERVENTION.  With the law OFF the envelope is the OSM
    spelling alone, so the DSF ribbon X-Plane draws stands 2.75 m off the
    cut's centre and its far edge overhangs the wall — the owner's "not
    centered on the road"."""
    monkeypatch.setenv("O4_PORTAL_SPELLING_ENVELOPE", "0")
    layout = _Layout([_chain_at(-_SPELLING_OFFSET_M)])
    centre, half = _envelope(layout)
    assert centre == pytest.approx(0.0, abs=1e-9)
    assert half == pytest.approx(_LANES_2_WIDTH_M / 2.0, abs=1e-9)
    # The rendered ribbon's own far edge, against the cut's edge:
    ribbon_far = -_SPELLING_OFFSET_M - _LANES_2_WIDTH_M / 2.0
    assert ribbon_far < centre - half, (
        f"the ribbon's far edge {ribbon_far:.2f} m already fits inside "
        f"the cut — the defect did not reproduce")


def test_f4_the_cut_covers_every_spelling(monkeypatch):
    """LAW 1 (Amendment 1).  With the law ON the envelope spans from the
    westmost spelling's outer edge to the eastmost's, and its centre is
    the envelope's midpoint — so BOTH ribbons sit inside the cut."""
    monkeypatch.setenv("O4_PORTAL_SPELLING_ENVELOPE", "1")
    layout = _Layout([_chain_at(-_SPELLING_OFFSET_M)])
    centre, half = _envelope(layout)
    assert centre == pytest.approx(-_SPELLING_OFFSET_M / 2.0, abs=0.01)
    assert half == pytest.approx(
        (_LANES_2_WIDTH_M + _SPELLING_OFFSET_M) / 2.0, abs=0.01)
    for spelling_centre in (0.0, -_SPELLING_OFFSET_M):
        assert spelling_centre - _LANES_2_WIDTH_M / 2.0 >= \
            centre - half - 1e-9
        assert spelling_centre + _LANES_2_WIDTH_M / 2.0 <= \
            centre + half + 1e-9


def test_f4_agreeing_sources_widen_nothing(monkeypatch):
    """A tile whose two sources spell the road in the SAME place emits
    byte-identically: a spelling already inside the envelope adds no
    edge at all."""
    monkeypatch.setenv("O4_PORTAL_SPELLING_ENVELOPE", "1")
    layout = _Layout([_chain_at(0.0)])
    assert bridges._spelling_edges(
        layout, (0.0, 0.0), (1.0, 0.0), _LANES_2_WIDTH_M / 2.0,
        [(-3.5, 3.5)]) == []


def test_f4_an_elevated_chain_is_not_in_the_cut(monkeypatch):
    """A chain at draping LEVEL 1+ flies over on its own structure — it
    is not in the cut and must not widen it (the same discrimination
    ``_draped_road_centerlines_meters`` makes)."""
    monkeypatch.setenv("O4_PORTAL_SPELLING_ENVELOPE", "1")
    layout = _Layout([_chain_at(-_SPELLING_OFFSET_M, level=1.0)])
    assert bridges._spelling_edges(
        layout, (0.0, 0.0), (1.0, 0.0), _LANES_2_WIDTH_M / 2.0,
        [(-3.5, 3.5)]) == []


def test_f4_a_far_road_is_a_different_road(monkeypatch):
    """Matching is within a small radius: a chain beyond
    ``_SPELLING_MATCH_M`` is another road, not another spelling, and
    never widens this portal's cut."""
    monkeypatch.setenv("O4_PORTAL_SPELLING_ENVELOPE", "1")
    layout = _Layout([_chain_at(-(bridges._SPELLING_MATCH_M + 5.0))])
    assert bridges._spelling_edges(
        layout, (0.0, 0.0), (1.0, 0.0), _LANES_2_WIDTH_M / 2.0,
        [(-3.5, 3.5)]) == []


def test_f4_no_network_is_not_an_error(monkeypatch):
    monkeypatch.setenv("O4_PORTAL_SPELLING_ENVELOPE", "1")
    assert bridges._spelling_edges(
        _Layout([]), (0.0, 0.0), (1.0, 0.0), 3.5, []) == []


def test_f4_ships_default_on(monkeypatch):
    monkeypatch.delenv("O4_PORTAL_SPELLING_ENVELOPE", raising=False)
    assert bridges.portal_spelling_envelope_enabled() is True
    monkeypatch.setenv("O4_PORTAL_SPELLING_ENVELOPE", "0")
    assert bridges.portal_spelling_envelope_enabled() is False


# ── F5 ───────────────────────────────────────────────────────────────

_DEFAULT_W = 6.0
_LANES_4_W = 14.0


def _straight_course(length=120.0, y=0.0):
    return LineString([(0.0, y), (length, y)])


def _minted(entries, width=_DEFAULT_W):
    rects, junctions = service_roads.build_service_road_network(
        entries, None, width=width, min_len=10.0, mouth_join=False)
    return rects, junctions


def _rect_width(rect: Polygon) -> float:
    """The short side of a rect — the corridor width it was built at."""
    ring = list(rect.exterior.coords)[:-1]
    sides = [math.hypot(ring[i][0] - ring[(i + 1) % len(ring)][0],
                        ring[i][1] - ring[(i + 1) % len(ring)][1])
             for i in range(len(ring))]
    return min(sides)


def test_f5_off_arm_mints_the_default_width():
    """THE INTERVENTION.  An entry that states NO width mints at the
    global 6.0 m — the measured LEMD item-3 rect (5.93 m) against a
    ``lanes=4`` way, which is the "about half the width" the owner read
    and the reason its other 8 m drapes on raw DEM."""
    rects, _j = _minted([(_straight_course(), "road")])
    assert rects
    for rect, _axis, _role, _name in rects:
        assert _rect_width(rect) == pytest.approx(_DEFAULT_W, abs=0.01)


def test_f5_a_stated_width_governs_its_own_course():
    """LAW 2 (Amendment 1).  ``lanes=4`` → 14.0 m, minted at 14.0 m."""
    rects, _j = _minted([(_straight_course(), "road", _LANES_4_W)])
    assert rects
    for rect, _axis, _role, _name in rects:
        assert _rect_width(rect) == pytest.approx(_LANES_4_W, abs=0.01)


def test_f5_the_default_is_unchanged_for_an_untagged_network():
    """THE RULING'S OWN CONDITION.  A network where nothing states a
    width emits exactly what it emitted before the channel existed —
    same rect count, same geometry, same axes."""
    courses = [(_straight_course(), "road"),
               (_straight_course(y=40.0), "road")]
    plain = _minted(courses)
    widened = _minted([(c[0], c[1], 0.0) for c in courses])   # 0 → default
    assert len(plain[0]) == len(widened[0])
    for (ra, aa, _r1, _n1), (rb, ab, _r2, _n2) in zip(plain[0], widened[0]):
        assert ra.equals(rb)
        assert aa.equals(ab)


def test_f5_widths_are_per_course_not_per_network():
    """Two courses, two widths, one call — the channel is per ENTRY."""
    rects, _j = _minted([(_straight_course(), "road", _LANES_4_W),
                         (_straight_course(y=60.0), "road")])
    widths = sorted({round(_rect_width(r), 1)
                     for r, _a, _ro, _n in rects})
    assert widths == [_DEFAULT_W, _LANES_4_W], widths


def test_f5_the_width_reader_takes_both_dialects():
    class _Centerline:
        line = None
        name = "x"
        width_m = 9.0
    assert service_roads._width_of(_Centerline(), _DEFAULT_W) == 9.0
    assert service_roads._width_of((None, "x", 14.0), _DEFAULT_W) == 14.0
    assert service_roads._width_of((None, "x"), _DEFAULT_W) == _DEFAULT_W
    assert service_roads._width_of((None, "x", 0.0), _DEFAULT_W) == _DEFAULT_W
    assert service_roads._width_of((None, "x", "junk"),
                                   _DEFAULT_W) == _DEFAULT_W


def test_f5_the_stated_width_comes_from_the_engines_own_tag_reader():
    """No second tag parser: the number ``lanes=4`` resolves to here is
    the number ``bridges._carriageway_width_from_tags`` states."""
    assert bridges._carriageway_width_from_tags(
        "service", {"highway": "service", "lanes": "4"}, 0.0) == \
        pytest.approx(_LANES_4_W)


def _feed(ways, nodes):
    class _F:
        source = "regional_extract"
    f = _F()
    f.ways = ways
    f.nodes = nodes
    return f


def _project(lon, lat):
    cos_anchor = math.cos(math.radians(_ANCHOR[0]))
    return ((lon - _ANCHOR[1]) * 111320.0 * cos_anchor,
            (lat - _ANCHOR[0]) * 111320.0)


def test_f5_the_association_is_geometric_and_the_widest_wins():
    """The courses carry no tags, so the feed's way is re-associated by
    geometry — the same re-association a portal footprint makes."""
    lat0, lon0 = _ANCHOR
    dlon = 200.0 / (111320.0 * math.cos(math.radians(lat0)))
    nodes = {"a": (lat0, lon0), "b": (lat0, lon0 + dlon)}
    ways = [("-2096", ["a", "b"],
             {"highway": "service", "lanes": "4"})]
    course = LineString([_project(lon0, lat0),
                         _project(lon0 + dlon, lat0)])
    out = service_roads.attach_course_widths(
        [(course, "road")], _feed(ways, nodes), _project,
        default=_DEFAULT_W)
    assert out[0][2] == pytest.approx(_LANES_4_W)


def test_f5_a_course_far_from_every_tagged_way_keeps_the_default():
    lat0, lon0 = _ANCHOR
    dlon = 200.0 / (111320.0 * math.cos(math.radians(lat0)))
    nodes = {"a": (lat0 + 0.01, lon0), "b": (lat0 + 0.01, lon0 + dlon)}
    ways = [("-2096", ["a", "b"],
             {"highway": "service", "lanes": "4"})]
    course = LineString([_project(lon0, lat0),
                         _project(lon0 + dlon, lat0)])
    out = service_roads.attach_course_widths(
        [(course, "road")], _feed(ways, nodes), _project,
        default=_DEFAULT_W)
    assert out[0][2] == pytest.approx(_DEFAULT_W)


def test_f5_off_arm_attaches_no_width(monkeypatch):
    monkeypatch.setenv("O4_SERVICE_ROAD_WAY_WIDTH", "0")
    lat0, lon0 = _ANCHOR
    dlon = 200.0 / (111320.0 * math.cos(math.radians(lat0)))
    nodes = {"a": (lat0, lon0), "b": (lat0, lon0 + dlon)}
    ways = [("-2096", ["a", "b"],
             {"highway": "service", "lanes": "4"})]
    course = LineString([_project(lon0, lat0),
                         _project(lon0 + dlon, lat0)])
    out = service_roads.attach_course_widths(
        [(course, "road")], _feed(ways, nodes), _project,
        default=_DEFAULT_W)
    assert out[0][2] == pytest.approx(_DEFAULT_W)


def test_f5_no_feed_is_not_an_error():
    course = _straight_course()
    out = service_roads.attach_course_widths(
        [(course, "road")], None, _project, default=_DEFAULT_W)
    assert out == [(course, "road", _DEFAULT_W)]


def test_f5_ships_default_on(monkeypatch):
    monkeypatch.delenv("O4_SERVICE_ROAD_WAY_WIDTH", raising=False)
    assert service_roads.way_width_channel_enabled() is True
    monkeypatch.setenv("O4_SERVICE_ROAD_WAY_WIDTH", "0")
    assert service_roads.way_width_channel_enabled() is False
