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
from shapely.ops import unary_union

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

#: The R16-4b hole-ring needle tip (a 1.56 deg spur INTO a valid hole).
_HOLE_TIP_M = (45.0, 15.0)


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
    n, _claimed, _corr = bridges._claim_road_pavement(layout, rows, pairs, 0.6)
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
    n, _claimed, _corr = bridges._claim_road_pavement(layout, rows, pairs, 0.6)
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


def _corridor_feet(layout):
    return [s for s in layout.shapes
            if s.ref == bridges.TUNNEL_WALL_FOOT_REF]


def _wall_structure(layout):
    """Every piece of the wall STRUCTURE — face and foot alike.  §T5's
    "the annulus is owned by the wall" is a claim about this set, not
    about the ``tunnel_wall`` ref alone."""
    return [s for s in layout.shapes
            if s.ref in bridges._WALL_BAND_REFS]


def _ring_open(polygon):
    ring = list(polygon.exterior.coords)
    return ring[:-1] if ring and ring[0] == ring[-1] else ring


def test_r16_2b_the_wall_inner_edge_is_the_pavement_boundary():
    """No unowned strip: the wall STRUCTURE touches the cut floor (gap
    0 m), and at least two of its vertices sit ON the floor's own
    boundary — the canonical join the emitter's vertex interning then
    welds into one node id.

    SUPERSEDED PREMISE, REWRITTEN: this twin used to assert
    ``_corridor_feet(layout) == []`` because spec Amendment 1 ruling 1
    scoped §T5 to the PERIMETER band and left the facing-corridor waller
    on its prior single-band shared-node weld.  Amendment 2 attributed
    the 3 SPJC foot∩face pairs to the perimeter band's own post-solve
    conformance weld (``bridges.reclip_wall_feet_against_faces``) and
    §T5 was extended to EVERY waller with the gate default-ON
    (2026-08-29, lane/tunneldockets; the shipped state RULINGS
    2026-08-31k reports as "walls/feet 16/16").  So the piece that
    spells the floor's boundary is now the FOOT, and R16-2b's law —
    the structure's inner boundary IS the ramp's outer boundary — is
    asserted where it now lives.  The FACE standing off by ``wall_gap``
    is RULINGS 2026-08-28c item 1 ("there must be a small gap").

    Mutation-checked: with the foot deleted (``O4_RAMP_WALL_FOOT=0``)
    the structure reads a 0.60 m strip of ground no shape owns.
    """
    layout, floor, walls = _corridor_scene()
    feet = _corridor_feet(layout)
    assert len(feet) == len(walls) == 2, (
        f"{len(feet)} foot / {len(walls)} face piece(s) — the corridor "
        f"waller must emit both under §T5 (Amendment 2)")
    for foot in feet:
        assert foot.polygon.distance(floor.polygon) == pytest.approx(
            0.0, abs=1e-9), (
            f"a {foot.polygon.distance(floor.polygon):.3f} m strip "
            f"between the corridor and its wall foot is owned by nothing")
        on_edge = [v for v in _ring_open(foot.polygon)
                   if floor.polygon.exterior.distance(Point(v)) <= 1e-9]
        assert len(on_edge) >= 2, (
            f"the wall foot does not spell the floor's boundary: "
            f"{_ring_open(foot.polygon)}")
    foot_u = unary_union([f.polygon for f in feet])
    for wall in walls:
        assert wall.polygon.distance(floor.polygon) >= _WALL_GAP_M - 0.01, (
            f"the rising face stands only "
            f"{wall.polygon.distance(floor.polygon):.3f} m off the "
            f"corridor — RULINGS 2026-08-28c item 1")
        assert not [v for v in _ring_open(wall.polygon)
                    if floor.polygon.exterior.distance(Point(v)) <= 1e-9], (
            "the rising face is welded to the corridor floor")
        # face ∪ foot leaves nothing between: the whole gap is the foot's.
        assert wall.polygon.distance(foot_u) == pytest.approx(0.0, abs=1e-9)


def test_r16_2b_the_inner_edge_carries_the_ramps_values():
    """One node, one value: every vertex the wall STRUCTURE shares with
    the cut floor carries the FLOOR's profile there (210.0 at the W1
    station, 212.0 at W2), and the crest keeps ambient.

    SUPERSEDED PREMISE, REWRITTEN: under Amendment 1 the single
    ``tunnel_wall`` band carried both (floor on its inner pair, crest on
    its outer).  §T5 reaching this emitter (Amendment 2, gate default-ON
    2026-08-29; RULINGS 2026-08-31k) split that band, so the FLOOR is
    now the FOOT's — a flat shelf, one value per station across its
    whole width, per §F1 — and the FACE carries the crest on BOTH edges.
    R16-2b's law is unchanged and is asserted over the structure.
    """
    layout, floor, walls = _corridor_scene(floor_a=210.0, floor_b=212.0)
    feet = _corridor_feet(layout)
    assert feet, "no foot — see the sibling twin"
    shared = 0
    for foot in feet:
        ring = _ring_open(foot.polygon)
        alts = list(foot.node_altitudes)[:len(ring)]
        for (vx, vy), value in zip(ring, alts):
            # §F1: the shelf is FLAT across its width, so the outer pair
            # repeats its station's floor value — every foot vertex reads
            # the floor profile at its own station.
            expect = 210.0 + 2.0 * (vx / 56.0)
            assert value == pytest.approx(expect, abs=0.01), (
                f"foot vertex at x={vx:.1f} carries {value}, the floor "
                f"carries {expect}")
            if floor.polygon.exterior.distance(Point((vx, vy))) <= 1e-9:
                shared += 1
    assert shared >= 4, shared
    for wall in walls:
        ring = _ring_open(wall.polygon)
        alts = list(wall.node_altitudes)[:len(ring)]
        for (vx, vy), value in zip(ring, alts):
            assert floor.polygon.exterior.distance(Point((vx, vy))) > 1e-9, (
                f"a face vertex at ({vx:.1f}, {vy:.1f}) sits on the floor")
            assert value == pytest.approx(_AMBIENT_M, abs=0.11), (
                f"a crest vertex took {value}")


# ── §T5: THE RAMP-WALL FOOT, at the PERIMETER BAND (its whole scope) ──
# Driven through ``bridges.emit_wall_band`` directly — the one waller the
# law applies to this round, and the same function ``_emit_portal_cluster``
# calls with a cluster's ramp union.

_T5_RAMP = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 12.0), (0.0, 12.0)])


def _band_scene(ramp_alt=210.0):
    """One ramp body, walled by the perimeter band with ends WRAPPED.

    Reads whatever ``O4_RAMP_WALL_FOOT`` currently says.  The SHIPPED
    default is ON (``bridges.ramp_wall_foot_enabled``, default-ON since
    2026-08-29 when the face-inflation was attributed to the post-solve
    conformance weld); the flag-ON twins below still set it explicitly so
    they keep testing the arm they name, and the fallback twin sets "0".
    """
    layout = PavementLayout(icao="ZZZZ", anchor=_CLAIM_ANCHOR)
    ramp = BuiltShape(polygon=_T5_RAMP, role=bridges.ROLE_TUNNEL_RAMP,
                      ref="tunnel_ramp",
                      node_altitudes=[ramp_alt] * 5)
    layout.shapes.append(ramp)
    zones: list = []
    bridges.emit_wall_band(layout, zones, [_T5_RAMP], [ramp], [],
                           _WALL_GAP_M, _WALL_W_M,
                           lambda x, y: _AMBIENT_M, _AMBIENT_M)
    feet = [s for s in layout.shapes
            if s.ref == bridges.TUNNEL_WALL_FOOT_REF]
    faces = [s for s in layout.shapes if s.ref == "tunnel_wall"]
    return layout, ramp, feet, faces


def test_t5_the_perimeter_band_emits_a_foot_and_a_face(monkeypatch):
    monkeypatch.setenv("O4_RAMP_WALL_FOOT", "1")
    _layout, _ramp, feet, faces = _band_scene()
    assert feet and faces, (
        f"{len(feet)} foot / {len(faces)} face piece(s) — the perimeter "
        f"band must emit both")


def test_t5_the_face_stands_off_the_ramp_and_shares_no_node(monkeypatch):
    """RULINGS 2026-08-28c item 1: "there must be a small gap".  The
    rising ``tunnel_wall`` stands ``wall_gap`` (0.6 m) off the road
    surface and shares NOT ONE vertex with it — measured before on OTHH:
    84 node ids shared over 22 pairs at 0.0000 m."""
    monkeypatch.setenv("O4_RAMP_WALL_FOOT", "1")
    _layout, ramp, _feet, faces = _band_scene()
    ring = ramp.polygon.exterior
    for face in faces:
        assert face.polygon.distance(ramp.polygon) >= _WALL_GAP_M - 0.01, (
            f"the face stands {face.polygon.distance(ramp.polygon):.3f} m "
            f"off the ramp")
        shared = [v for v in _ring_open(face.polygon)
                  if ring.distance(Point(v)) <= 1e-9]
        assert not shared, (
            f"the face is welded to the ramp at {shared} — the defect "
            f"the owner read in the sim as a broken ramp")


def test_t5_the_foot_owns_the_annulus_r16_2b_re_measured(monkeypatch):
    """R16-2b under §T5's composition: face ∪ foot ∪ ramp leaves no
    unowned ground in the ``wall_gap + width`` annulus.

    Mutation-checked: delete the foot band and this reads a 0.60 m strip
    of ground no shape owns — the exact defect R16-2b was minted for.
    """
    monkeypatch.setenv("O4_RAMP_WALL_FOOT", "1")
    _layout, ramp, feet, faces = _band_scene()
    assert feet
    covered = unary_union([ramp.polygon]
                          + [s.polygon for s in feet + faces])
    annulus = ramp.polygon.buffer(_WALL_GAP_M).difference(ramp.polygon)
    unowned = annulus.difference(covered).area
    # THE SLIT KNIFE is the whole allowance and it PREDATES §T5: the
    # band is a ring, and to_osm drops interior rings, so each band is
    # cut open by a 0.02 m radial knife (``_knife``, buffer 0.02).  That
    # kerf is unowned in every arm this emitter has ever had — measured
    # here at 0.026 m² for a 60x12 m ramp.  The bar is the kerf, not a
    # tolerance on the law: a foot that failed to cover the annulus
    # would read in whole square metres.
    assert unowned <= 0.05, (
        f"{unowned:.3f} m² between the ramp and its wall is owned by "
        f"nothing — far beyond the 0.02 m slit kerf")
    for foot in feet:
        assert foot.polygon.distance(ramp.polygon) == pytest.approx(
            0.0, abs=1e-9)


def test_t5_the_foot_is_flat_at_the_ramp_edge_elevation(monkeypatch):
    """The shelf has no rise across its own width: every foot vertex
    carries the ramp-edge value, which is what lets the face rise from
    the shelf's OUTER edge alone."""
    monkeypatch.setenv("O4_RAMP_WALL_FOOT", "1")
    _layout, _ramp, feet, _faces = _band_scene(ramp_alt=210.0)
    assert feet
    for foot in feet:
        vals = [v for v in (foot.node_altitudes or ()) if v is not None]
        assert vals
        assert max(vals) - min(vals) <= 0.11, (
            f"the shelf rises {max(vals) - min(vals):.2f} m across its "
            f"own width — it is not flat")
        assert vals[0] == pytest.approx(210.0, abs=0.11)


def test_t5_the_articulation_chain_is_ramp_then_foot_then_face(monkeypatch):
    """THE MESH ARTICULATION THE OWNER ASKED FOR, as one assertion:
    the face shares ZERO vertices with the ramp, reaches it ONLY THROUGH
    the foot, and the foot is the shape touching the ramp at 0 m."""
    monkeypatch.setenv("O4_RAMP_WALL_FOOT", "1")
    _layout, ramp, feet, faces = _band_scene()
    assert feet
    ring = ramp.polygon.exterior
    foot_u = unary_union([f.polygon for f in feet])
    for face in faces:
        for v in _ring_open(face.polygon):
            p = Point(v)
            assert ring.distance(p) > 1e-9, (
                f"a face vertex at {v} sits ON the ramp — welded again")
            if ring.distance(p) <= _WALL_GAP_M + 1e-6:
                assert foot_u.covers(p) or \
                    foot_u.boundary.distance(p) <= 1e-6, (
                    f"a face vertex at {v} reaches into the wall gap "
                    f"without standing on the foot — unowned ground")
    assert foot_u.distance(ramp.polygon) == pytest.approx(0.0, abs=1e-9)


def test_t5_the_foot_and_face_never_overlap(monkeypatch):
    """``test_no_self_overlap`` has ZERO tolerance and no per-airport
    exceptions; the two bands are built from independently mitre-joined
    buffers, which do not nest exactly at a sharp corner."""
    monkeypatch.setenv("O4_RAMP_WALL_FOOT", "1")
    _layout, _ramp, feet, faces = _band_scene()
    for foot in feet:
        for face in faces:
            assert foot.polygon.intersection(face.polygon).area \
                == pytest.approx(0.0, abs=1e-9), (
                f"foot ∩ face = "
                f"{foot.polygon.intersection(face.polygon).area:.4f} m²")


def test_t5_the_shipped_default_is_the_foot_and_face():
    """THE SHIPPED CONTRACT.

    SUPERSEDED PREMISE, REWRITTEN: this twin was written as
    ``test_t5_the_shipped_default_is_the_plain_g0_standoff`` and pinned
    spec Amendment 2 ruling 2's *fallback* as the shipped state — foot
    OFF, unowned annulus accepted as the lesser defect — because the 3
    SPJC foot∩face pairs had not been root-caused.  They were, on
    2026-08-29 (lane/tunneldockets): the partition is disjoint AT EMIT
    (0.0000 m² measured for all 6 SPJC pieces) and it is
    ``conformance.enforce_conformance``'s post-solve T-vertex weld that
    bows a face inboard over its foot, which
    ``bridges.reclip_wall_feet_against_faces`` now settles LAST-WORD.
    The gate went default-ON with that attribution; RULINGS 2026-08-31k
    reports the shipped state as "walls/feet 16/16".

    So: no flag set ⇒ the foot SHIPS, the face still stands ``wall_gap``
    off the ramp and shares NOT ONE vertex with it (RULINGS 2026-08-28c
    item 1 / the owner's item 9: 84 shared node ids at 0.0000 m), and the
    foot is the piece that touches the ramp.
    """
    _layout, ramp, feet, faces = _band_scene()
    assert feet, "the foot does NOT ship by default — the gate flipped OFF"
    assert faces
    ring = ramp.polygon.exterior
    for face in faces:
        assert face.polygon.distance(ramp.polygon) >= _WALL_GAP_M - 0.01, (
            f"the shipped band stands only "
            f"{face.polygon.distance(ramp.polygon):.3f} m off the ramp")
        assert not [v for v in _ring_open(face.polygon)
                    if ring.distance(Point(v)) <= 1e-9], (
            "the shipped band still WELDS to the ramp — item 9 unfixed")
    for foot in feet:
        assert foot.polygon.distance(ramp.polygon) == pytest.approx(
            0.0, abs=1e-9)


def test_t5_the_shipped_default_owns_the_annulus_and_off_does_not(
        monkeypatch):
    """Named, not hidden — BOTH arms measured in one place.

    SUPERSEDED PREMISE, REWRITTEN: as
    ``test_t5_the_accepted_lesser_defect_is_the_unowned_annulus`` this
    twin asserted the unowned annulus was what SHIPPED.  With the gate
    default-ON (2026-08-29 attribution; RULINGS 2026-08-31k) the shipped
    arm OWNS the annulus and the unowned strip is what the explicitly
    selected fallback (``O4_RAMP_WALL_FOOT=0``) buys.  Keeping both
    numbers asserted is the point of the original twin: the fallback's
    cost stays a measured fact, and the shipped arm cannot silently
    regress back onto it.
    """
    def _unowned(ramp, pieces):
        covered = unary_union([ramp.polygon] + [p.polygon for p in pieces])
        annulus = ramp.polygon.buffer(_WALL_GAP_M).difference(ramp.polygon)
        return annulus.difference(covered).area

    _layout, ramp, feet, faces = _band_scene()
    assert feet
    # THE SLIT KNIFE is the whole allowance (see
    # ``test_t5_the_foot_owns_the_annulus_r16_2b_re_measured``): each band
    # is cut open by a 0.02 m radial kerf so ``to_osm`` need not carry an
    # interior ring.  Measured 0.026 m² for this 60x12 m ramp.
    shipped = _unowned(ramp, feet + faces)
    assert shipped <= 0.05, (
        f"{shipped:.3f} m² between the ramp and its wall is owned by "
        f"nothing at the SHIPPED default — far beyond the 0.02 m kerf")

    monkeypatch.setenv("O4_RAMP_WALL_FOOT", "0")
    _layout, ramp, feet, faces = _band_scene()
    assert feet == [], "the fallback still emits a foot"
    fallback = _unowned(ramp, faces)
    assert fallback > 1.0, (
        f"only {fallback:.2f} m² unowned with the foot OFF — if the "
        f"fallback also covers the annulus this twin is stale")



def test_r16_2b_the_crest_stays_where_it_was():
    """The structure widened inward, never outward: the crest (the wall
    face's outer edge) still stands ``wall_gap + width`` = 1.6 m off the
    pavement, so nothing outside the wall moved."""
    _layout, floor, walls = _corridor_scene()
    for wall in walls:
        far = max(floor.polygon.exterior.distance(Point(v))
                  for v in _ring_open(wall.polygon))
        assert far == pytest.approx(_WALL_GAP_M + _WALL_W_M, abs=0.01), far


# ── AMENDMENT 1 ─────────────────────────────────────────────────────
# R16-1b  the hole adopts the pad's chain (the MEASURED generator)
# R16-4b  interior rings are sliver-repair SOURCES
# R16-2b  the tunnel_cap face joins the wall-face weld law

def _dense_hole_scene(extra_offset_m=0.002):
    """A pad, and a covering shape whose HOLE spells the pad's boundary
    DENSER: an extra vertex ``extra_offset_m`` off the pad's chord.

    This is the generator the pads-frame A/B measured — the extra
    vertices are single-owner, unvalued, 0.00-2.29 mm off the chord.
    """
    layout = PavementLayout(icao="KFAKE", anchor=(30.12, 31.40))
    pad = [(0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0)]
    layout.shapes.append(_pav(Polygon(pad), ref="pad"))
    hole = [(0.0, 0.0), (20.0, extra_offset_m), (40.0, 0.0),
            (40.0, 30.0), (0.0, 30.0)]
    layout.shapes.append(_pav(
        Polygon([(-40.0, -40.0), (90.0, -40.0), (90.0, 80.0),
                 (-40.0, 80.0)], [hole]),
        ref="cover", alt=101.0))
    return layout


def test_r16_1b_the_hole_adopts_the_pads_chain():
    """One boundary, one spelling: the hole ring ships the pad's own
    chain, not a denser private one, so the two constrained chains
    Triangle sees are identical and no zero-width lens exists.

    Mutation-checked: without the adoption the emitted ring carries one
    vertex the pad's ring does not (a twin-ring pair).
    """
    layout = _dense_hole_scene()
    nodes, ways = _emit_and_parse(layout)
    pad = [nds for _w, nds, tags in ways if tags.get("ref") == "pad"]
    rings = _hole_rings(ways)
    assert pad and rings, [tags for _w, _n, tags in ways]
    for _wid, nds in rings:
        assert set(nds) == set(pad[0]), (
            f"hole ring spells {len(set(nds))} vertices against the "
            f"pad's {len(set(pad[0]))} — one boundary spelled twice")


def test_r16_1b_the_snap_frame_is_the_discriminator():
    """AMENDMENT 2: the test is the private on-edge move's OWN frame.
    A hole vertex 70 mm off the pad's chord is one that ratified move
    would put ON the chord anyway, so adoption picks ONE spelling
    instead of letting the weld splice it into both.

    (Amendment 1 read this case as a keep-both divergence at the 5 mm
    weld tolerance; measured, that tolerance adopted NOTHING at OTHH —
    the whole population lives between the two frames.)
    """
    layout = _dense_hole_scene(extra_offset_m=0.070)
    nodes, ways = _emit_and_parse(layout)
    pad = [nds for _w, nds, tags in ways if tags.get("ref") == "pad"]
    rings = _hole_rings(ways)
    assert pad and rings
    for _wid, nds in rings:
        assert set(nds) == set(pad[0]), (
            f"a {0.070} m offset is inside the snap frame and must "
            f"adopt: ring {sorted(set(nds))} vs pad {sorted(set(pad[0]))}")


def test_r16_1b_beyond_the_snap_frame_keeps_both_spellings():
    """The control the amendment kept: past ``ONEDGE_SNAP_TOL_M`` the
    move itself would not touch the vertex, so the two rings are two
    boundaries — both spellings ship and the emitter reports it."""
    layout = _dense_hole_scene(extra_offset_m=0.200)
    nodes, ways = _emit_and_parse(layout)
    pad = [nds for _w, nds, tags in ways if tags.get("ref") == "pad"]
    rings = _hole_rings(ways)
    assert pad and rings
    assert any(set(nds) != set(pad[0]) for _wid, nds in rings), (
        "a 0.20 m divergence — beyond the snap frame — was adopted")


def test_r16_4b_an_interior_ring_needle_is_repaired():
    """Interior rings join the sliver repair as SOURCES, under the
    emitter's own 2.0 deg / 0.09 m constants — no new 25 deg constant.
    The 1.15 deg tip in this hole is removed exactly as it would be on
    an exterior ring.

    Mutation-checked: with rings left out of the repair the tip ships.
    """
    layout = PavementLayout(icao="KFAKE", anchor=(30.12, 31.40))
    # A VALID hole with a 1.56 deg spur reaching into it (legs 25 m,
    # base 0.8 m apart — both outside the 0.5 m intern bucket).
    hole = [(10.0, 10.0), (60.0, 10.0), (60.0, 40.0), (35.0, 40.0),
            _HOLE_TIP_M, (34.2, 40.0), (10.0, 40.0)]
    layout.shapes.append(_pav(
        Polygon([(-40.0, -40.0), (140.0, -40.0), (140.0, 90.0),
                 (-40.0, 90.0)], [hole]), ref="cover", alt=101.0))
    nodes, ways = _emit_and_parse(layout)
    rings = _hole_rings(ways)
    assert rings, [tags for _w, _n, tags in ways]
    survivors = []
    for _wid, nds in rings:
        survivors += _nids_near(layout, nodes, nds, _HOLE_TIP_M)
    assert not survivors, (
        f"an interior-ring needle tip below "
        f"SLIVER_ANGLE_THRESHOLD_DEG survived: {survivors}")


def test_r16_2b_the_cap_face_reaches_the_mouth_plate(monkeypatch):
    """The cap's face is owned geometry: it reaches the mouth plate's
    near edge (distance 0), shares that edge's two corners, and carries
    the mouth's grade there while its crest keeps the deck grade.

    Mutation-checked: with the cap stopping at the portal station the
    gap reads ``wall_gap_m`` (0.6 m) of ground no shape owns — KCLT's
    3 remaining unowned wall nodes.
    """
    from tests.test_tunnel_dem_cut_portals import (
        TILE_LATITUDE, TILE_LONGITUDE, _install_scene, _shapes_with_ref)
    layout = _install_scene(monkeypatch, carved=True)
    bridges._emit_tunnel_portals(
        layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
    caps = _shapes_with_ref(layout, "tunnel_cap")
    mouths = _shapes_with_ref(layout, "tunnel_mouth")
    assert caps and mouths, [(s.ref, s.role) for s in layout.shapes]
    welded = 0
    for cap in caps:
        near = min(mouths, key=lambda m: cap.polygon.distance(m.polygon))
        if cap.polygon.distance(near.polygon) > 1e-6:
            continue
        welded += 1
        shared = [v for v in _ring_open(cap.polygon)
                  if near.polygon.exterior.distance(Point(v)) <= 1e-6]
        assert len(shared) >= 2, _ring_open(cap.polygon)
        assert cap.node_altitudes, "the cap lost its per-vertex profile"
        assert min(cap.node_altitudes) == pytest.approx(
            float(near.altitude), abs=0.02), (
            f"the cap's shared edge carries {min(cap.node_altitudes)}, "
            f"the mouth plate carries {near.altitude}")
        assert max(cap.node_altitudes) > min(cap.node_altitudes), (
            "the cap face must span the drop, not sit flat")
    assert welded, (
        "no cap reaches its mouth plate — every one still stands a "
        "wall_gap strip away from the pavement it faces")


# ── AMENDMENT 3 (task #10) ──────────────────────────────────────────
# THE FINAL DECIMATION RUNS IN THE FRAME THAT HOLDS EVERY CHAIN.
# Slice C scanned ``pending`` alone, so a vertex spelled by both a pad's
# exterior chain and the hole ring bounding the same boundary was removed
# ONE-SIDEDLY — the measured generator of the twin-ring class (OTHH patch
# frame: 21 pairs / 47 differing vertices, every one within _DEC_PERP_M
# of the partner chord, with the R16-1b loop reporting the two chains as
# ONE spelling upstream).

def _redundant_vertex_scene(offset_m=0.005):
    """A pad whose ring carries ONE 3D-redundant mid-edge vertex
    (``offset_m`` off the chord of its neighbours, flat altitude, chord
    well under the 60 m cap), and a cover whose HOLE spells that same
    ring IDENTICALLY — the configuration the emitter reaches with
    ``same_spelling`` at the R16-1b loop."""
    pad = [(0.0, 0.0), (20.0, offset_m), (40.0, 0.0),
           (40.0, 30.0), (0.0, 30.0)]
    layout = PavementLayout(icao="KFAKE", anchor=(30.12, 31.40))
    layout.shapes.append(_pav(Polygon(pad), ref="pad"))
    layout.shapes.append(_pav(
        Polygon([(-40.0, -40.0), (90.0, -40.0), (90.0, 80.0),
                 (-40.0, 80.0)], [list(pad)]), ref="cover"))
    return layout


def test_r16_1_decimation_removes_from_every_chain_or_none():
    """One boundary, one spelling — through the FINAL decimation too.

    The redundant vertex is 5 mm off the chord (inside ``_DEC_PERP_M``),
    so slice C removes it; the hole ring spelling the same boundary must
    lose it in the same sweep.

    Mutation-checked: with ``_interior_rings`` left out of the
    occurrence map the pad ring emits 4 vertices and the hole ring 5 —
    a twin-ring pair whose differing vertex sits 5.000 mm off the
    partner chord.
    """
    nodes, ways = _emit_and_parse(_redundant_vertex_scene())
    pad = [nds for _w, nds, tags in ways if tags.get("ref") == "pad"]
    rings = _hole_rings(ways)
    assert pad and rings, [tags for _w, _n, tags in ways]
    for _wid, nds in rings:
        assert set(nds) == set(pad[0]), (
            f"the hole ring spells {len(set(nds))} vertices against the "
            f"pad's {len(set(pad[0]))} — the decimation removed from one "
            f"chain and not the other")


def test_r16_1_decimation_control_a_vertex_outside_the_tolerance_stays():
    """The control that keeps the twin honest: at 25 mm the vertex is
    NOT decimation-eligible, so BOTH chains keep it and there is still
    exactly one spelling.  (A 'fix' that simply stopped decimating, or
    one that deleted ring vertices wholesale, fails here.)"""
    nodes, ways = _emit_and_parse(_redundant_vertex_scene(offset_m=0.025))
    pad = [nds for _w, nds, tags in ways if tags.get("ref") == "pad"]
    rings = _hole_rings(ways)
    assert pad and rings
    assert len(set(pad[0])) == 5, (
        f"a 25 mm vertex is outside _DEC_PERP_M and must survive: "
        f"{sorted(set(pad[0]))}")
    for _wid, nds in rings:
        assert set(nds) == set(pad[0]), (
            f"ring {sorted(set(nds))} vs pad {sorted(set(pad[0]))}")


def test_r16_1_a_ring_never_loses_its_own_unvalued_vertex():
    """Ring-PRIVATE protection (amendment 3): a hole-ring vertex no
    exterior chain claims is interned UNVALUED, and the decimation's
    altitude clause keeps it — rings are removal partners, never
    victims.  Here the hole is a plain 5-vertex ring of its own, with a
    mid-edge vertex that is geometrically redundant; nothing values it,
    so it ships."""
    hole = [(10.0, 10.0), (30.0, 10.005), (50.0, 10.0),
            (50.0, 40.0), (10.0, 40.0)]
    layout = PavementLayout(icao="KFAKE", anchor=(30.12, 31.40))
    layout.shapes.append(_pav(
        Polygon([(-40.0, -40.0), (90.0, -40.0), (90.0, 80.0),
                 (-40.0, 80.0)], [hole]), ref="cover"))
    nodes, ways = _emit_and_parse(layout)
    rings = _hole_rings(ways)
    assert rings, [tags for _w, _n, tags in ways]
    for _wid, nds in rings:
        assert len(set(nds)) == 5, (
            f"the ring lost an unvalued vertex of its own: "
            f"{sorted(set(nds))}")
