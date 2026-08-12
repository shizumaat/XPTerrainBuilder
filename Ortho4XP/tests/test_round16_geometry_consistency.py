"""Round-16 twins — the geometry-consistency family.

Spec: ``docs/specs/round16-geometry-consistency-spec.md`` (FROZEN).

R16-1  ONE BOUNDARY, ONE SPELLING.  The chain-consistent needle removal
       runs in the frame that holds EVERY final chain — exterior ways
       AND interior hole rings — so a vertex the sliver-corner repair
       removed from a pad's exterior cannot survive in the hole ring
       spelling the same boundary (the zero-width constrained lens the
       +25+051 crash was minted by).
R16-2a THE ANCHOR IS THE PORTAL.  Per below-grade body the transition
       law anchors at the body's DEEPEST station, not at whichever
       station happens to lie nearest a governed ring vertex.
R16-2b THE WALL FACE IS OWNED GEOMETRY.  A tunnel wall's inner boundary
       IS the ramp's outer boundary (node identity, not proximity) and
       carries the ramp's values there, so no unowned strip is left for
       the mesh to drape at DEM/Z0.
R16-3  ONE FLOOR PER CONNECTED CLAIMED PLATE.  Adjacent claimed plates
       of one connected level surface share the joint depth.

Every assertion is made in the frame the law is measured in: R16-1 on
the EMITTED patch (canonical interning, the validity repair and the
weld all sit between ``layout.shapes`` and the emitted chains), the
others on the shapes the emitters produce.
"""
import math
import re
import tempfile
from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon, box

from auto_patch import bridges
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_SERVICE_JUNCTION,
)


# ── helpers ─────────────────────────────────────────────────────────

def _emit_and_parse(layout):
    """``(nodes, ways)`` of the emitted patch — ``nodes`` maps nid to
    (lat, lon) floats, ``ways`` is ``[(wid, [nid...], tags)]``."""
    with tempfile.NamedTemporaryFile(
            mode="r", suffix=".osm", delete=False) as handle:
        path = handle.name
    try:
        layout.to_osm(path)
        text = Path(path).read_text()
    finally:
        Path(path).unlink()
    node_re = re.compile(
        r"""<node id='(-?\d+)'[^>]*lat='([^']+)' lon='([^']+)'""")
    way_open_re = re.compile(r"""<way id='(-?\d+)'""")
    nd_re = re.compile(r"""<nd ref='(-?\d+)'""")
    tag_re = re.compile(r"""<tag k='([^']+)' v='([^']+)'""")
    nodes = {int(m.group(1)): (float(m.group(2)), float(m.group(3)))
             for m in node_re.finditer(text)}
    bodies = re.findall(r"<way id='-?\d+'[^>]*>(.*?)</way>",
                        text, flags=re.DOTALL)
    ways = []
    for i, m_open in enumerate(way_open_re.finditer(text)):
        ways.append((int(m_open.group(1)),
                     [int(x) for x in nd_re.findall(bodies[i])],
                     dict(tag_re.findall(bodies[i]))))
    return nodes, ways


def _pav(polygon, ref="pav", alt=100.0, role=ROLE_GROUNDSIDE_PAVEMENT):
    return BuiltShape(polygon=polygon, role=role, ref=ref, altitude=alt)


def _nids_near(layout, nodes, way_nids, point_m, tol_m=0.5):
    """The emitted nids of ``way_nids`` sitting within ``tol_m`` of the
    LOCAL-METRE point ``point_m``."""
    out = []
    for nid in way_nids:
        lat, lon = nodes[nid]
        x, y = layout.ll_to_m(lat, lon)
        if math.hypot(x - point_m[0], y - point_m[1]) <= tol_m:
            out.append(nid)
    return out


# ── R16-1: one boundary, one spelling ───────────────────────────────

#: The needle tip.  In the PAD's exterior it is a 1.15 deg spur tip
#: (below ``SLIVER_ANGLE_THRESHOLD_DEG`` = 2.0, so the sliver-corner
#: repair removes it); in the HOLE ring it is a mid-edge vertex exactly
#: on the chord joining its neighbours (perp 0 m, inside the 0.09 m
#: near-collinear predicate), which is what makes the pair a twin.
_TIP_M = (50.0, 20.0)


def _twin_ring_scene():
    layout = PavementLayout(icao="KFAKE", anchor=(30.12, 31.40))
    # The pad: a 100x50 plate with a thin spur reaching down to the tip.
    # Legs (60,50)->(50,20) and (59.2,50)->(50,20) subtend 1.15 deg.
    layout.shapes.append(_pav(
        Polygon([(0, 0), (100, 0), (100, 50), (60, 50), _TIP_M,
                 (59.2, 50), (0, 50)]), ref="pad"))
    # The cover: its HOLE runs straight through the tip — (40,20),
    # (50,20), (60,20) are collinear, so the tip is a near-collinear
    # partner vertex, never a real corner of this chain.
    layout.shapes.append(_pav(
        Polygon([(-20, -20), (120, -20), (120, 70), (-20, 70)],
                [[(40, 20), _TIP_M, (60, 20), (60, 5), (40, 5)]]),
        ref="cover", alt=101.0))
    return layout


def _hole_rings(ways):
    return [(wid, nds) for wid, nds, tags in ways
            if tags.get("o4_feature") == "shape_interior_ring"]


def test_r16_1_hole_ring_loses_the_vertex_its_pad_exterior_lost():
    """The twin: the sliver repair takes the tip out of the pad's
    exterior, and the hole ring spelling the same boundary must lose it
    too — otherwise the two chains spell ONE boundary TWICE, differing
    by a vertex on the chord, which is the zero-width lens Triangle
    answers with Steiner points.

    Mutation-checked: with the needle scan back in its pre-round-16
    frame (``pending`` only, before the hole dedup) the hole ring still
    carries the tip and this asserts 1 surviving nid.
    """
    layout = _twin_ring_scene()
    nodes, ways = _emit_and_parse(layout)
    rings = _hole_rings(ways)
    assert rings, [tags for _w, _n, tags in ways]
    survivors = []
    for _wid, nds in rings:
        survivors += _nids_near(layout, nodes, nds, _TIP_M)
    assert not survivors, (
        f"the hole ring kept the needle vertex the pad's exterior lost "
        f"({survivors}) — one boundary spelled twice")


def test_r16_1_exterior_partners_still_converge():
    """The direction that already worked stays working: a partner
    EXTERIOR way passing through the removed vertex near-collinearly
    loses it too (the pre-round-16 behaviour, unchanged)."""
    layout = _twin_ring_scene()
    layout.shapes.append(_pav(
        Polygon([(40, 20), _TIP_M, (60, 20), (60, 12), (40, 12)]),
        ref="partner", alt=99.0))
    nodes, ways = _emit_and_parse(layout)
    partner = [nds for _w, nds, tags in ways
               if tags.get("ref") == "partner"]
    assert partner, [tags for _w, _n, tags in ways]
    assert not _nids_near(layout, nodes, partner[0], _TIP_M), (
        "an exterior partner kept a vertex the sliver repair removed")


def test_r16_1_a_real_corner_is_never_deformed():
    """The existing guard, unchanged: a partner chain where the removed
    vertex is a REAL corner (far off its own neighbour chord) keeps it —
    the law converges spellings, it never deforms genuine geometry."""
    layout = PavementLayout(icao="KFAKE", anchor=(30.12, 31.40))
    layout.shapes.append(_pav(
        Polygon([(0, 0), (100, 0), (100, 50), (60, 50), _TIP_M,
                 (59.2, 50), (0, 50)]), ref="pad"))
    # The partner turns a genuine 90 deg corner at the tip.
    layout.shapes.append(_pav(
        Polygon([(30, 20), _TIP_M, (50, 0), (30, 0)]),
        ref="corner", alt=99.0))
    nodes, ways = _emit_and_parse(layout)
    corner = [nds for _w, nds, tags in ways
              if tags.get("ref") == "corner"]
    assert corner, [tags for _w, _n, tags in ways]
    assert _nids_near(layout, nodes, corner[0], _TIP_M), (
        "a real corner was deformed by the chain-consistent removal")


# ── R16-3: one floor per connected claimed plate ────────────────────

_CLAIM_ANCHOR = (35.215, -80.944)
_AMBIENT_M = 219.8
#: KCLT's triangle in miniature: two ADJACENT claimed plates whose own
#: regions carry floors 0.11 m apart — the measured 210.87 / 210.98.
_FLOOR_DEEP = 210.87
_FLOOR_SHALLOW = 210.98


def _portal_row(way_id, station, outward, mouth_grade, carriage_w=10.0):
    """One ``portal_data`` row with NO deck reference, so the mouth
    grade IS the floor (``_mouth_grade_with_clearance`` passes it
    through) and the twin can name both floors exactly."""
    return ("n" + way_id, way_id, [station, outward], "service",
            _AMBIENT_M, _AMBIENT_M, False, carriage_w, False,
            mouth_grade, [], None, None)


def _two_plate_scene(separate=False):
    """Two facing pairs 40 m apart, each covered by its own road plate.

    ``separate=False`` puts the plates edge to edge — ONE connected
    level surface.  ``separate=True`` leaves a 6 m gap between them:
    two surfaces, and the law must NOT join their floors.
    """
    layout = PavementLayout(icao="ZZZZ", anchor=_CLAIM_ANCHOR)
    y_split = 12.0 if not separate else 12.0
    plate_a = box(-6.0, -12.0, 62.0, y_split)
    plate_b = box(-6.0, y_split + (6.0 if separate else 0.0), 62.0, 46.0)
    for poly in (plate_a, plate_b):
        layout.shapes.append(BuiltShape(
            polygon=poly, role=ROLE_SERVICE_JUNCTION, ref="",
            node_altitudes=[_AMBIENT_M] * 5))
    rows = [_portal_row("W1", (0.0, 0.0), (56.0, 0.0), _FLOOR_DEEP),
            _portal_row("W2", (56.0, 0.0), (0.0, 0.0), _FLOOR_DEEP),
            _portal_row("W3", (0.0, 40.0), (56.0, 40.0), _FLOOR_SHALLOW),
            _portal_row("W4", (56.0, 40.0), (0.0, 40.0), _FLOOR_SHALLOW)]
    return layout, rows, [(0, 1), (2, 3)]


def test_r16_3_connected_claimed_plates_share_the_joint_depth():
    """Both plates of ONE level surface take the JOINT depth — the
    minimum of the members' own floors — so the level-plate bullet
    (spread <= 0.10 m) holds across the whole surface.

    Mutation-checked: with each plate taking its own region's floor
    this reads a 0.11 m spread (KCLT's 210.87 / 210.98).
    """
    layout, rows, pairs = _two_plate_scene()
    n, _claimed = bridges._claim_road_pavement(layout, rows, pairs, 0.6)
    assert n == 2, f"both plates must be claimed, got {n}"
    values = [v for shape in layout.shapes for v in shape.node_altitudes]
    assert max(values) - min(values) <= 0.10, (
        f"level-plate spread {max(values) - min(values):.3f} m across "
        f"two adjacent claimed plates")
    assert min(values) == pytest.approx(_FLOOR_DEEP, abs=0.02)
    assert max(values) == pytest.approx(_FLOOR_DEEP, abs=0.02)


def test_r16_3_disconnected_plates_keep_their_own_floors():
    """The control: the law is per CONNECTED plate.  Two level surfaces
    that do not touch answer with their own depths — joining them would
    sink pavement no bore runs under."""
    layout, rows, pairs = _two_plate_scene(separate=True)
    n, _claimed = bridges._claim_road_pavement(layout, rows, pairs, 0.6)
    assert n == 2
    floors = sorted(round(min(s.node_altitudes), 2) for s in layout.shapes)
    assert floors == [round(_FLOOR_DEEP, 2), round(_FLOOR_SHALLOW, 2)], (
        f"disconnected surfaces were joined: {floors}")


def test_r16_3_the_claim_still_never_raises_a_vertex():
    """R14 behaviour, unchanged: the joint depth can only DIG.  A plate
    already below the joint floor keeps its own value."""
    layout, rows, pairs = _two_plate_scene()
    layout.shapes[1].node_altitudes = [_FLOOR_DEEP - 3.0] * 5
    bridges._claim_road_pavement(layout, rows, pairs, 0.6)
    assert min(layout.shapes[1].node_altitudes) == pytest.approx(
        _FLOOR_DEEP - 3.0, abs=1e-6)


# ── R16-2a: the anchor is the portal (the DEEPEST station) ──────────

_CAP = 0.04


def _ramp(alt_at_x0, alt_at_x100, x0=0.0, x1=100.0):
    """One below-grade source: a 10 m wide quad whose profile dives
    along x.  Ring order is ``(x0,0) (x1,0) (x1,10) (x0,10)``, so the
    deepest station is hand-nameable."""
    ring = [(x0, 0.0), (x1, 0.0), (x1, 10.0), (x0, 10.0)]
    alts = [alt_at_x0, alt_at_x100, alt_at_x100, alt_at_x0]
    return (Polygon(ring), ring, alts)


def test_r16_2a_the_anchor_is_pinned_at_the_deepest_station():
    """Hand-computable: the body's deepest STATION is the cross-section
    at x = 100 (both (100, 0) and (100, 10) at -8.00 m); the governed
    ring's nearest vertex to it is (50, 12), a gap of hypot(50, 2) =
    50.04 m, so the anchor is pinned at -8.00 + 0.04 * 50.04 = -6.00 m.

    The pre-round-16 mechanism answered -4.42 m there: it minimised
    ``nearest profile + cap * d`` per vertex, and the nearest profile
    of (50, 12) is the ramp's SHALLOWEST station in reach (-4.50 at
    x = 50), which is the reading the law's own prose forbids.
    """
    from auto_patch.groundside import transition_law_altitudes
    ring = [(0.0, 12.0), (50.0, 12.0), (50.0, 30.0), (0.0, 30.0)]
    alts, touched = transition_law_altitudes(
        ring, [0.0] * 4, [_ramp(-1.0, -8.0)], _CAP)
    assert touched
    expected = -8.0 + _CAP * math.hypot(50.0, 2.0)
    assert alts[1] == pytest.approx(expected, abs=0.01), alts
    assert alts[1] < -5.0, (
        f"the anchor took a shallow-station floor: {alts[1]:.2f} m")


def test_r16_2a_out_of_the_portals_reach_the_crest_stands():
    """The mirror-collapse guard.  A body whose DEEPEST station is
    0.80 m above what the cap can reach from the nearest governed
    vertex pulls NOTHING down: -1.20 + 0.04 * 50.04 = +0.80 m, above
    the surrounding surface at 0.00 m.

    The pre-round-16 mechanism pinned -0.92 m here — the shallow
    station 2 m away — which is terrain hugging the ramp instead of
    standing beside it.
    """
    from auto_patch.groundside import transition_law_altitudes
    ring = [(0.0, 12.0), (50.0, 12.0), (50.0, 30.0), (0.0, 30.0)]
    alts, touched = transition_law_altitudes(
        ring, [0.0] * 4, [_ramp(-1.0, -1.2)], _CAP)
    assert touched == 0, alts
    assert alts == [0.0] * 4


def test_r16_2a_one_anchor_per_body_still():
    """Unchanged: a body contributes exactly ONE anchor, however many
    quads it is emitted as."""
    from auto_patch.groundside import (
        _BelowGradeIndex, transition_law_altitudes)
    sources = [_ramp(-1.0, -4.0, 0.0, 50.0), _ramp(-4.0, -8.0, 50.0, 100.0)]
    index = _BelowGradeIndex(sources)
    assert len(set(index.component_of)) == 1, index.component_of
    assert index.deepest_station[0][1] == pytest.approx(-8.0)
    ring = [(0.0, 12.0), (50.0, 12.0), (100.0, 12.0),
            (100.0, 40.0), (0.0, 40.0)]
    alts, _touched = transition_law_altitudes(ring, [0.0] * 5, index, _CAP)
    pinned = [i for i, v in enumerate(alts)
              if v == pytest.approx(-8.0 + _CAP * 2.0, abs=0.01)]
    assert len(pinned) == 1, (pinned, alts)


# ── R16-2b: the wall face is owned geometry ─────────────────────────

_WALL_GAP_M = 0.6
_WALL_W_M = 1.0


def _corridor_scene(floor_a=210.87, floor_b=210.87):
    layout = PavementLayout(icao="ZZZZ", anchor=_CLAIM_ANCHOR)
    rows = [_portal_row("W1", (0.0, 0.0), (56.0, 0.0), floor_a),
            _portal_row("W2", (56.0, 0.0), (0.0, 0.0), floor_b)]
    zones: list = []
    n = bridges._emit_facing_corridors(
        layout, rows, [(0, 1)], zones, _WALL_GAP_M, _WALL_W_M,
        lambda x, y: _AMBIENT_M)
    assert n == 1, n
    floor = [s for s in layout.shapes if s.ref == "tunnel_corridor"]
    walls = [s for s in layout.shapes if s.ref == "tunnel_wall"]
    assert len(floor) == 1 and len(walls) == 2, (
        [(s.ref, s.role) for s in layout.shapes])
    return layout, floor[0], walls


def _ring_open(polygon):
    ring = list(polygon.exterior.coords)
    return ring[:-1] if ring and ring[0] == ring[-1] else ring


def test_r16_2b_the_wall_inner_edge_is_the_pavement_boundary():
    """No unowned strip: the wall polygon TOUCHES the cut floor (gap
    0 m), and at least two of its vertices sit ON the floor's own
    boundary — the canonical join the emitter's vertex interning then
    welds into one node id.

    Mutation-checked: with the wall standing ``wall_gap_m`` outboard
    this reads a 0.60 m strip of ground no shape owns.
    """
    _layout, floor, walls = _corridor_scene()
    for wall in walls:
        assert wall.polygon.distance(floor.polygon) == pytest.approx(
            0.0, abs=1e-9), (
            f"a {wall.polygon.distance(floor.polygon):.3f} m strip "
            f"between the ramp and its wall is owned by nothing")
        on_edge = [v for v in _ring_open(wall.polygon)
                   if floor.polygon.exterior.distance(Point(v)) <= 1e-9]
        assert len(on_edge) >= 2, (
            f"the wall face does not spell the floor's boundary: "
            f"{_ring_open(wall.polygon)}")


def test_r16_2b_the_inner_edge_carries_the_ramps_values():
    """One node, one value: every vertex the wall shares with the cut
    floor carries the FLOOR's profile there (210.0 at the W1 station,
    212.0 at W2), and the crest keeps ambient — so the face spans the
    drop instead of a vertical glitch at a doubly-valued node."""
    _layout, floor, walls = _corridor_scene(floor_a=210.0, floor_b=212.0)
    shared = 0
    for wall in walls:
        ring = _ring_open(wall.polygon)
        alts = list(wall.node_altitudes)[:len(ring)]
        for (vx, vy), value in zip(ring, alts):
            if floor.polygon.exterior.distance(Point((vx, vy))) <= 1e-9:
                # the floor runs 210.0 at x=0 to 212.0 at x=56
                expect = 210.0 + 2.0 * (vx / 56.0)
                assert value == pytest.approx(expect, abs=0.01), (
                    f"wall vertex on the floor edge at x={vx:.1f} "
                    f"carries {value}, the floor carries {expect}")
                shared += 1
            else:
                assert value == pytest.approx(_AMBIENT_M, abs=0.11), (
                    f"a crest vertex took {value}")
    assert shared >= 4, shared


def test_r16_2b_the_crest_stays_where_it_was():
    """The face widened inward, never outward: the crest (the outer
    edge) still stands ``wall_gap + width`` = 1.6 m off the pavement,
    so nothing outside the wall moved."""
    _layout, floor, walls = _corridor_scene()
    for wall in walls:
        far = max(floor.polygon.exterior.distance(Point(v))
                  for v in _ring_open(wall.polygon))
        assert far == pytest.approx(_WALL_GAP_M + _WALL_W_M, abs=0.01), far
