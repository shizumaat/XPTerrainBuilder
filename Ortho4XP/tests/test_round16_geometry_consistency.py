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

from shapely.geometry import Polygon

from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    ROLE_GROUNDSIDE_PAVEMENT,
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
