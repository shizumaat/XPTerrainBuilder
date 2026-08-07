"""Node-identity twins for the sliver / node-identity repair (phase A).

Governing law: ``docs/specs/cycle5-node-identity-spec.md`` — *any
boundary shared by two ways is the IDENTICAL vertex chain in both*, and
a canonical solve node has exactly ONE plan coordinate.  Spec:
``docs/specs/sliver-node-identity-repair-spec.md`` phase A.

Every assertion here is made on the EMITTED patch, because that is the
frame the law is measured in.  This is not a stylistic choice: the same
geometric predicate applied to ``layout.shapes`` instead catches 0 of
the 10 divergent wall vertices and 0 of the 375 hole vertices at HECA,
while in the emitted frame it catches 10 of 10 — canonical interning,
the ``buffer(0)`` validity repair, the needle removal and the weld's own
insertions all sit between the two frames.

Three repairs, one twin each plus their negative controls:

A1  an interior ring lying on a pavement ring's edge SHARES its node
    ids (interior rings were structurally absent from the emitter's
    chain-identity weld, in both directions);
A2  a private wall vertex lying on a foreign chain's edge is moved onto
    it and welded (measured at HECA: wall feet 37-125 mm off the edge
    they sit on — invisible to the canonical POINT registry, and far
    outside the 5 mm nid weld's reach);
A3  the emitter never mints a COORDINATE TWIN — two node ids at one
    plan coordinate — which is the dual of the same law.

Every case has a hand-computable answer (the projection of a named
point onto a named segment), so these are calibration twins, not
change-detectors.
"""
import re
import tempfile
from pathlib import Path

from shapely.geometry import Polygon

from auto_patch.layout import (
    BuiltShape,
    ONEDGE_SNAP_TOL_M,
    PavementLayout,
    ROLE_APRON,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_RETAINING_WALL,
)


# ── helpers ─────────────────────────────────────────────────────────

def _emit_and_parse(layout):
    with tempfile.NamedTemporaryFile(
            mode="r", suffix=".osm", delete=False) as f:
        path = f.name
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
    nodes = {int(m.group(1)): (m.group(2), m.group(3))
             for m in node_re.finditer(text)}
    bodies = re.findall(r"<way id='-?\d+'[^>]*>(.*?)</way>",
                        text, flags=re.DOTALL)
    ways = []
    for i, m_open in enumerate(way_open_re.finditer(text)):
        body = bodies[i]
        ways.append((int(m_open.group(1)),
                     [int(x) for x in nd_re.findall(body)],
                     dict(tag_re.findall(body))))
    return nodes, ways


def _pav(polygon, role=ROLE_GROUNDSIDE_PAVEMENT, ref="pav", alt=100.0):
    return BuiltShape(polygon=polygon, role=role, ref=ref, altitude=alt)


def _way(ways, **match):
    for wid, nds, tags in ways:
        if all(tags.get(k) == v for k, v in match.items()):
            return wid, nds, tags
    raise AssertionError(f"no way matching {match}: "
                         f"{[t for _w, _n, t in ways]}")


def _shared(nds_a, nds_b):
    return set(nds_a) & set(nds_b)


def _coincident_coords(nodes):
    seen, dupes = {}, []
    for nid, ll in nodes.items():
        if ll in seen:
            dupes.append((seen[ll], nid, ll))
        seen[ll] = nid
    return dupes


# ── A2: a private wall vertex on a foreign edge welds ───────────────

def _wall_scene(offset_m, x0=30.0, x1=60.0):
    """A 100x50 pavement square, and a wall band whose two top corners
    sit ``offset_m`` above the pavement's y=0 edge at x=30 and x=60.

    The nearest pavement VERTEX is 30 m away, so the canonical point
    registry cannot see these; the projection onto the edge is exactly
    (30, 0) / (60, 0) — the hand-computable answer.
    """
    layout = PavementLayout(icao="KFAKE", anchor=(30.12, 31.40))
    layout.shapes.append(
        _pav(Polygon([(0, 0), (100, 0), (100, 50), (0, 50)])))
    layout.shapes.append(BuiltShape(
        polygon=Polygon([(x0, offset_m), (x1, offset_m),
                         (x1, -3.0), (x0, -3.0)]),
        role=ROLE_RETAINING_WALL, ref="wall",
        node_altitudes=[100.0, 100.0, 97.0, 97.0, 100.0]))
    return layout


def test_a2_private_wall_vertex_on_a_foreign_edge_joins_its_chain():
    _nodes, ways = _emit_and_parse(_wall_scene(0.08))
    _wid_p, pav_nds, _t = _way(ways, ref="pav")
    _wid_w, wall_nds, _t2 = _way(ways, ref="wall")
    shared = _shared(pav_nds, wall_nds)
    assert len(shared) == 2, (
        f"the wall's two on-edge feet should be spelled by the pavement "
        f"chain too; shared={len(shared)} pav={pav_nds} wall={wall_nds}")
    # the pavement ring grew by exactly those two references
    assert len(pav_nds) == 7, pav_nds
    assert len(wall_nds) == 5, wall_nds


def test_a2_beyond_the_reach_is_left_alone():
    """A vertex further off than ``ONEDGE_SNAP_TOL_M`` is real geometry,
    not a divergent spelling of a shared boundary."""
    _nodes, ways = _emit_and_parse(_wall_scene(ONEDGE_SNAP_TOL_M + 0.05))
    _wid_p, pav_nds, _t = _way(ways, ref="pav")
    _wid_w, wall_nds, _t2 = _way(ways, ref="wall")
    assert not _shared(pav_nds, wall_nds)
    assert len(pav_nds) == 5, pav_nds


def test_a2_a_shared_vertex_is_never_dragged():
    """Within ``SHARED_VERTEX_TOL_M`` of a pavement CORNER the canonical
    point registry already welds the wall foot onto it.  That node is
    then shared, so the on-edge move must not touch it — moving it
    would drag the pavement corner with it."""
    _nodes, ways = _emit_and_parse(_wall_scene(0.08, x0=0.2, x1=60.0))
    _wid_p, pav_nds, _t = _way(ways, ref="pav")
    _wid_w, wall_nds, _t2 = _way(ways, ref="wall")
    shared = _shared(pav_nds, wall_nds)
    # the x=0.2 foot welded to the corner; the x=60 foot moved on-edge
    assert len(shared) == 2, (pav_nds, wall_nds)
    assert len(pav_nds) == 6, pav_nds


def test_a2_role_is_not_the_predicate_ownership_is():
    """The law is about chains, not roles: an APRON vertex that is
    private and lies on a foreign edge joins that chain too."""
    layout = _wall_scene(0.08)
    layout.shapes[1].role = ROLE_APRON
    _nodes, ways = _emit_and_parse(layout)
    _wid_p, pav_nds, _t = _way(ways, ref="pav")
    _wid_w, other_nds, _t2 = _way(ways, ref="wall")
    assert len(_shared(pav_nds, other_nds)) == 2, (pav_nds, other_nds)


# ── A1: interior rings ──────────────────────────────────────────────

def _hole_scene(offset_m=0.0185):
    """A pavement strip at y=20..30, and a covering shape with a HOLE
    whose lower edge sits ``offset_m`` ABOVE the strip's y=30 edge.

    HECA's specimen class in miniature: the hole boundary and the
    pavement ring bounding the same hole spelled two ways, 18.5 mm
    apart, with nothing within the point registry's reach (the nearest
    strip VERTEX is 30 m away).
    """
    layout = PavementLayout(icao="KFAKE", anchor=(30.12, 31.40))
    layout.shapes.append(
        _pav(Polygon([(0, 20), (100, 20), (100, 30), (0, 30)]),
             ref="strip"))
    layout.shapes.append(
        _pav(Polygon([(0, 0), (100, 0), (100, 60), (0, 60)],
                     [[(30, 30 + offset_m), (70, 30 + offset_m),
                       (70, 45), (30, 45)]]),
             ref="cover", alt=101.0))
    return layout


def test_a1_interior_ring_shares_the_boundary_node_ids():
    """The emitter's own assertion — *the nids are the already-interned
    exterior vertices, so nothing new is created here* — made true by
    construction for the vertices that lie on the boundary.

    Measured before the repair at HECA: the specimen ring shared ZERO
    nids with either pavement way whose edge it crosses 18.5 mm away.
    """
    _nodes, ways = _emit_and_parse(_hole_scene())
    _wid_s, strip_nds, _t = _way(ways, ref="strip")
    rings = [nds for _w, nds, tags in ways
             if tags.get("o4_feature") == "shape_interior_ring"]
    assert rings, [t for _w, _n, t in ways]
    shared = set()
    for nds in rings:
        shared |= _shared(strip_nds, nds)
    assert len(shared) >= 2, (
        f"interior ring shares {len(shared)} nid(s) with the pavement "
        f"way whose edge it lies on — the boundary is still spelled "
        f"twice; strip={strip_nds} rings={rings}")


def test_a1_free_hole_boundary_is_not_dragged():
    """A hole standing clear of every foreign ring is real geometry and
    must not move (HECA: 110 of 116 private ring vertices are more than
    0.33 m from anything)."""
    _nodes, ways = _emit_and_parse(_hole_scene(offset_m=1.0))
    _wid_s, strip_nds, _t = _way(ways, ref="strip")
    rings = [nds for _w, nds, tags in ways
             if tags.get("o4_feature") == "shape_interior_ring"]
    assert rings
    assert not any(_shared(strip_nds, nds) for nds in rings)
    assert len(strip_nds) == 5, strip_nds


# ── A3: one coordinate, one node id ─────────────────────────────────

def test_a3_emitter_never_mints_a_coordinate_twin():
    """Two ids at one plan coordinate is the dual of the node-identity
    law.  The weld used to mint one whenever the chain it was splicing
    into already passed through the hit node elsewhere."""
    layout = _hole_scene()
    layout.shapes.extend(_wall_scene(0.08).shapes[1:])
    layout.shapes.append(_pav(
        Polygon([(20, -3.0), (20, -8.0), (80, -8.0), (80, -3.0)]),
        role=ROLE_APRON, ref="apron", alt=99.0))
    nodes, _ways = _emit_and_parse(layout)
    dupes = _coincident_coords(nodes)
    assert not dupes, (
        f"{len(dupes)} coincident-coordinate node id(s): {dupes[:5]}")


def test_a3_repeated_reference_beats_a_second_node_id():
    """White-box: when a chain must reference a node it already
    contains, the chain references THAT node — the node table never
    grows a coordinate alias."""
    nodes, ways = _emit_and_parse(_wall_scene(0.004))
    assert not _coincident_coords(nodes)
    _wid, pav_nds, _t = _way(ways, ref="pav")
    assert len(pav_nds) >= 6, pav_nds
