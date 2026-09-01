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
R16-2b SUPERSEDED by RULINGS 2026-09-01c.  It required a tunnel wall's
       inner boundary to BE the ramp's outer boundary, so no unowned
       strip was left for the mesh to drape.  The owner has ruled the
       gap itself to be the steep face: ramp, then 0.5 m owned by
       NOTHING, then a band whose two edges carry one corridor-top
       value.  The twins below assert THAT model (and the §T5 foot that
       stood in the gap is retired with it).
R16-3  RETIRED.  "ONE FLOOR PER CONNECTED CLAIMED PLATE" was a law of
       R14-1's tunnel-road CLAIM CLASS (which plates a claim levels
       together).  The class retires under RULINGS 2026-08-31b
       (``docs/specs/linear-transport-redesign-spec.md`` §5.1, census
       #23), and R16-3 with it — mapped road pavement over a cut is now
       core road ground above a covered stretch, or severed by the cut.
       Its three twins are deleted; nothing replaces them here.

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


# ── portal fixtures shared by R16-2a / R16-2b / §T5 ─────────────────
#
# R16-3 ("ONE FLOOR PER CONNECTED CLAIMED PLATE") lived here.  It was a
# law OF R14-1's claim class — which plates a claim levels together —
# and it retired with that class (RULINGS 2026-08-31b, redesign spec
# §5.1, census #23).  Its three twins are deleted; the portal-row helper
# below is kept because the surviving R16-2a/R16-2b/§T5 twins use it.

_CLAIM_ANCHOR = (35.215, -80.944)
_AMBIENT_M = 219.8


def _portal_row(way_id, station, outward, mouth_grade, carriage_w=10.0):
    """One ``portal_data`` row with NO deck reference, so the mouth
    grade IS the floor (``_mouth_grade_with_clearance`` passes it
    through) and the twin can name both floors exactly."""
    return ("n" + way_id, way_id, [station, outward], "service",
            _AMBIENT_M, _AMBIENT_M, False, carriage_w, False,
            mouth_grade, [], None, None)


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
    """The §T5 FOOT population — EMPTY since it retired (2026-09-01c).
    Kept as a probe: it reads the shipped ref literal, so a foot
    re-appearing under any emitter fails the twins that call it."""
    return [s for s in layout.shapes if s.ref == "tunnel_wall_foot"]


def _ring_open(polygon):
    ring = list(polygon.exterior.coords)
    return ring[:-1] if ring and ring[0] == ring[-1] else ring


def test_the_corridor_wall_stands_off_the_floor_and_shares_no_node():
    """RULINGS 2026-09-01c: the wall band stands ``wall_gap_m`` off the
    corridor floor and shares NOT ONE vertex with it.

    This SUPERSEDES R16-2b's original frame for this emitter (which
    required the band's inner edge to BE the floor boundary, so that no
    ground was unowned).  The owner has ruled the gap itself to be the
    steep face: the mesher triangulates floor-edge to wall-inner-edge,
    and nothing may weld across it.  Measured before, at OTHH: this
    emitter contributed 32 shared ramp/wall node ids.

    Mutation-checked: start the band at ``_half`` again and the shared
    count returns.
    """
    layout, floor, walls = _corridor_scene()
    assert _corridor_feet(layout) == [], (
        "a wall FOOT was emitted — the §T5 foot retired (2026-09-01c)")
    for wall in walls:
        assert wall.polygon.distance(floor.polygon) >= _WALL_GAP_M - 0.01, (
            f"the wall stands only "
            f"{wall.polygon.distance(floor.polygon):.3f} m off the "
            f"floor — the gap the mesher triangulates is gone")
        on_edge = [v for v in _ring_open(wall.polygon)
                   if floor.polygon.exterior.distance(Point(v)) <= 1e-9]
        assert not on_edge, (
            f"the wall is welded to the corridor floor at {on_edge}")


def test_the_corridor_wall_carries_one_crest_value_per_station():
    """BOTH EDGES, ONE VALUE (RULINGS 2026-09-01c).  No band vertex
    carries a floor value any more: at each station the inner and the
    outer vertex read the SAME crest sample, so the wall top cannot
    twist and the band cannot lean.

    The ring is ``[inner@a, inner@b, outer@b, outer@a]``, so the station
    pairs are (0, 3) and (1, 2).
    """
    _layout, floor, walls = _corridor_scene(floor_a=210.0, floor_b=212.0)
    assert walls
    for wall in walls:
        ring = _ring_open(wall.polygon)
        alts = list(wall.node_altitudes)[:len(ring)]
        assert len(alts) == 4, alts
        assert alts[0] == pytest.approx(alts[3], abs=1e-9), alts
        assert alts[1] == pytest.approx(alts[2], abs=1e-9), alts
        for value in alts:
            assert value == pytest.approx(_AMBIENT_M, abs=0.11), (
                f"a band vertex took {value} — the floor's value leaked "
                f"into the band (210.0/212.0 are the floor's)")


# ── THE WALL BAND, at the PERIMETER emitter (RULINGS 2026-09-01c) ─────
# Driven through ``bridges.emit_wall_band`` directly — the same function
# ``_emit_portal_cluster`` calls with a cluster's ramp union.  THE MODEL:
# ramp = corridor floor; a ``wall_gap_m`` gap owned by NOTHING; then one
# band whose inner AND outer edges carry the corridor-top value.

_T5_RAMP = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 12.0), (0.0, 12.0)])


def _band_scene(ramp_alt=210.0):
    """One ramp body, walled by the perimeter band with ends WRAPPED."""
    layout = PavementLayout(icao="ZZZZ", anchor=_CLAIM_ANCHOR)
    ramp = BuiltShape(polygon=_T5_RAMP, role=bridges.ROLE_TUNNEL_RAMP,
                      ref="tunnel_ramp",
                      node_altitudes=[ramp_alt] * 5)
    layout.shapes.append(ramp)
    zones: list = []
    bridges.emit_wall_band(layout, zones, [_T5_RAMP], [ramp], [],
                           _WALL_GAP_M, _WALL_W_M,
                           lambda x, y: _AMBIENT_M, _AMBIENT_M)
    faces = [s for s in layout.shapes if s.ref == "tunnel_wall"]
    return layout, ramp, faces


def test_the_band_emits_one_ref_and_no_foot():
    """THE FOOT IS GONE — no ref, no shape, no flag.  A band piece is a
    ``tunnel_wall`` and nothing else."""
    layout, _ramp, faces = _band_scene()
    assert faces, "the perimeter band emitted nothing"
    refs = {s.ref for s in layout.shapes
            if s.role == bridges.ROLE_RETAINING_WALL}
    assert refs == {"tunnel_wall"}, refs
    assert not hasattr(bridges, "TUNNEL_WALL_FOOT_REF")
    assert not hasattr(bridges, "ramp_wall_foot_enabled")
    assert not hasattr(bridges, "reclip_wall_feet_against_faces")


def test_the_band_stands_off_the_ramp_and_shares_no_node():
    """RULINGS 2026-08-28c item 1, kept by 2026-09-01c: "there must be a
    small gap".  The band stands ``wall_gap`` off the road surface and
    shares NOT ONE vertex with it — measured before on OTHH: 84 node ids
    shared over 22 pairs at 0.0000 m."""
    _layout, ramp, faces = _band_scene()
    ring = ramp.polygon.exterior
    for face in faces:
        assert face.polygon.distance(ramp.polygon) >= _WALL_GAP_M - 0.01, (
            f"the band stands {face.polygon.distance(ramp.polygon):.3f} m "
            f"off the ramp")
        shared = [v for v in _ring_open(face.polygon)
                  if ring.distance(Point(v)) <= 1e-9]
        assert not shared, (
            f"the band is welded to the ramp at {shared} — the defect "
            f"the owner read in the sim as a broken ramp")


def test_the_gap_is_unowned_by_design():
    """THE MESHER'S TRIANGULATION IS THE FACE (RULINGS 2026-09-01c).
    R16-2b required the ``wall_gap`` annulus to be owned; the owner has
    superseded that.  This twin asserts the RULED state — the annulus is
    covered by NOTHING — so a future shape that quietly re-fills it
    fails here rather than shipping unnoticed."""
    _layout, ramp, faces = _band_scene()
    covered = unary_union([ramp.polygon] + [f.polygon for f in faces])
    annulus = ramp.polygon.buffer(_WALL_GAP_M).difference(ramp.polygon)
    unowned = annulus.difference(covered).area
    assert unowned > 0.9 * annulus.area, (
        f"only {unowned:.2f} of {annulus.area:.2f} m² of the gap is "
        f"unowned — something is bridging the gap the mesher must "
        f"triangulate")


def test_the_band_carries_one_value_per_station_across_its_width():
    """BOTH EDGES, ONE VALUE (RULINGS 2026-09-01c) — the same frame the
    acceptance instrument's ``wall_top_flat`` reads.

    The band is ``_WALL_W_M`` across and its stations stand metres
    apart, so two of its own vertices closer than that in PLAN are
    ACROSS the band, not along its run.  Every such pair must carry ONE
    value: the crest is sampled once per station and both vertices read
    it.  (The crest still DESCENDS along the run under the transition
    law — §F1 — which is why this is a cross-band frame and not a
    flat-band one.)
    """
    _layout, _ramp, faces = _band_scene(ramp_alt=210.0)
    assert faces
    span = _WALL_W_M + 0.5
    pairs = 0
    worst = 0.0
    for face in faces:
        ring = _ring_open(face.polygon)
        alts = list(face.node_altitudes)[:len(ring)]
        for i in range(len(ring)):
            for j in range(i + 1, len(ring)):
                if math.hypot(ring[i][0] - ring[j][0],
                              ring[i][1] - ring[j][1]) > span:
                    continue
                pairs += 1
                worst = max(worst, abs(float(alts[i]) - float(alts[j])))
    assert pairs, "no cross-band pair — the frame read nothing"
    assert worst <= 0.11, (
        f"worst cross-band delta {worst:.2f} m over {pairs} pair(s) — "
        f"the band is leaning, not standing on one crest value")


def test_no_band_vertex_carries_the_ramps_floor_value():
    """NO FLOOR VALUE IN ANY WALL BAND (RULINGS 2026-09-01c).  The band
    no longer touches the road, so the old R16-2b inner-edge overwrite
    (and §T5's flat foot shelf) are gone: the band's own crest profile
    is its ONLY altitude source.

    Mutation-checked: restore the ramp-value overwrite and the band's
    inner edge reads 210.0 at every station instead of at the portal
    alone.
    """
    _layout, _ramp, faces = _band_scene(ramp_alt=210.0)
    at_floor = 0
    total = 0
    for face in faces:
        for v in (face.node_altitudes or ()):
            if v is None:
                continue
            total += 1
            if abs(float(v) - 210.0) <= 0.05:
                at_floor += 1
    assert total
    # The transition law legitimately brings the crest DOWN to meet the
    # road at the portal, so a handful of stations read the floor value;
    # an inner EDGE carrying it would be half the vertices.
    assert at_floor <= 0.25 * total, (
        f"{at_floor} of {total} band vertices sit at the ramp's floor "
        f"value — the inner edge is carrying the road again")


def test_the_band_never_overlaps_itself():
    """``test_no_self_overlap`` has ZERO tolerance and no per-airport
    exceptions."""
    _layout, _ramp, faces = _band_scene()
    for i in range(len(faces)):
        for j in range(i + 1, len(faces)):
            assert faces[i].polygon.intersection(
                faces[j].polygon).area == pytest.approx(0.0, abs=1e-9)


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
