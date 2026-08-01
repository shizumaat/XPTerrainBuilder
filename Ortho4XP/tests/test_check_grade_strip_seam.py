"""Unit tests: the cross-shape graded-strip SEAM tear check.

``tools/check_grade.py::_check_strip_seam_tears`` is the cross-shape twin of
the within-shape ``_check_adjacent_ground_edges`` sentinel.  A ``graded_strip``
drapes raw terrain and carries no lawful within-shape grade cap, so the ONE
DEM-free-provable defect BETWEEN two strips is a large vertical STEP across a
short gap — the clip / weld seam the in-sim renderer draws as a sharp cliff
(root-caused at SPJC, 2026-07-18).

Properties, one test each:

* a metre-plus step across a sub-radius gap between two DIFFERENT strips is
  flagged;
* an exactly-shared canonical node (distance ~0) is NOT a tear;
* a sub-``STRIP_SEAM_TEAR_MIN_STEP_M`` step is NOT flagged (lawful terrace);
* nodes farther apart than ``STRIP_SEAM_TEAR_RADIUS_M`` are NOT flagged;
* a big step WITHIN one strip is NOT counted by the cross-shape check;
* two ways that share a ``shapeID`` are one strip and are NOT paired.

The synthetic OSM node ``lat``/``lon`` are treated directly as local meters via
an identity projection, so gap distances are exact.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "tools"), os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade  # noqa: E402


def _identity_meters(lat: float, lon: float) -> Tuple[float, float]:
    """Unit-test frame: a node's stored ``lat``/``lon`` ARE local meters
    ``(y, x)``, so planar gaps between synthetic nodes are exact."""
    return (lon, lat)


# A synthetic node: id, x-meter, y-meter, absolute altitude.
Node = Tuple[str, float, float, float]


def _write_osm(tmp_path: Path,
               ways_spec: List[Dict],
               filename: str = "seam.osm") -> Path:
    """Emit a minimal X-Plane patch OSM file to ``tmp_path``.

    ``ways_spec`` is a list of ``{"wid", "role", "shapeID", "nodes"}`` dicts
    where ``nodes`` is a list of :data:`Node` tuples.  A single node id may be
    reused across ways to model a shared canonical node.  Each node carries an
    ``alt_abs`` child tag (the per-node elevation form the parser reads); the
    node's ``lat``/``lon`` are the ``(y, x)`` meter coordinates."""
    node_lines: List[str] = []
    emitted_nids: Dict[str, Node] = {}
    for spec in ways_spec:
        for (nid, x_m, y_m, alt) in spec["nodes"]:
            if nid in emitted_nids:
                continue
            emitted_nids[nid] = (nid, x_m, y_m, alt)
    for (nid, x_m, y_m, alt) in emitted_nids.values():
        node_lines.append(
            f"  <node id='{nid}' action='modify' visible='true' "
            f"lat='{y_m}' lon='{x_m}'>\n"
            f"    <tag k='alt_abs' v='{alt}' />\n"
            f"  </node>")
    way_lines: List[str] = []
    for spec in ways_spec:
        nds = "".join(
            f"    <nd ref='{nid}' />\n" for (nid, _, _, _) in spec["nodes"])
        way_lines.append(
            f"  <way id='{spec['wid']}' action='modify' visible='true'>\n"
            f"{nds}"
            f"    <tag k='role' v='{spec['role']}' />\n"
            f"    <tag k='shapeID' v='{spec['shapeID']}' />\n"
            f"  </way>")
    text = (
        "<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
        + "\n".join(node_lines) + "\n"
        + "\n".join(way_lines) + "\n</osm>\n")
    out = tmp_path / filename
    out.write_text(text)
    return out


def _run(tmp_path: Path, ways_spec: List[Dict]):
    """Parse a synthetic OSM file and run the cross-shape seam-tear check
    in the identity meter frame; returns the list of violations."""
    path = _write_osm(tmp_path, ways_spec)
    nodes, ways = check_grade._parse_osm(path)
    vertices, _edges = check_grade._build_vertex_edge_tables(
        nodes, ways, _identity_meters)
    return check_grade._check_strip_seam_tears(vertices, ways)


# Far-flung padding nodes keep each way a legal >=3-node ring without
# minting extra cross-way pairs (they sit >100 m from the other strip).
def _pad_a() -> List[Node]:
    return [("-90", 0.0, 200.0, 10.0), ("-91", 0.0, 400.0, 10.0)]


def _pad_b() -> List[Node]:
    return [("-92", 200.0, 0.0, 10.0), ("-93", 400.0, 0.0, 10.0)]


def test_metre_step_across_short_gap_is_flagged(tmp_path):
    # Strip A node at (0,0)=10.0 m; strip B node 1.5 m away at (1.5,0)=12.0 m.
    # Δalt 2.0 m over 1.5 m ⇒ a seam tear (~133 %).
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 10.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 12.0)] + _pad_b()},
    ]
    violations = _run(tmp_path, ways_spec)
    assert len(violations) == 1, [
        (v.de_m, v.distance_m) for v in violations]
    v = violations[0]
    assert abs(v.de_m - 2.0) < 1e-6
    assert abs(v.distance_m - 1.5) < 1e-6


def test_exactly_shared_node_is_not_a_tear(tmp_path):
    # Both strips reference the SAME canonical node id (-1) at (0,0) with
    # ONE agreed value: the altitude delta is zero, so the step floor
    # excludes the pair (an interned consensus node is not a tear).
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 10.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-1", 0.0, 0.0, 10.0)] + _pad_b()},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_sub_metre_step_is_not_flagged(tmp_path):
    # 0.5 m step at 1.5 m spacing: below STRIP_SEAM_TEAR_MIN_STEP_M (1.0 m),
    # a lawful terrace between adjacent strips.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 10.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.5)] + _pad_b()},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_nodes_beyond_radius_are_not_flagged(tmp_path):
    # 2.0 m step but 8 m apart: beyond STRIP_SEAM_TEAR_RADIUS_M (6.0 m) the
    # two nodes are not a seam, so no tear.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 10.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 8.0, 0.0, 12.0)] + _pad_b()},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_same_way_step_is_not_counted(tmp_path):
    # A big step WITHIN one strip (nodes 1.5 m apart, Δalt 2.0 m) is the
    # within-shape check's business; the cross-shape check skips same-way
    # pairs and reports nothing.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 10.0),
                   ("-2", 1.5, 0.0, 12.0),
                   ("-90", 0.0, 200.0, 10.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_same_shape_id_across_two_ways_is_not_paired(tmp_path):
    # Two ways carrying the SAME shapeID model ONE strip emitted as several
    # ways; a step between them is not a cross-shape seam.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "7",
         "nodes": [("-1", 0.0, 0.0, 10.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "7",
         "nodes": [("-2", 1.5, 0.0, 12.0)] + _pad_b()},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_steep_drape_below_grade_floor_is_not_flagged(tmp_path):
    # 1.5 m over 5 m = 30 %: lawful hillside drape between neighbour
    # strips on steep relief (the CYXY class), under the 50 % grade
    # floor — must NOT be flagged despite exceeding the 1 m step floor.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 10.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 5.0, 0.0, 11.5)] + _pad_b()},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_wall_spanned_step_is_not_flagged(tmp_path):
    # The no-stacked-nodes unit renders a strip-vs-strip level change
    # as a retreated edge + retaining_wall face: the wall way
    # references BOTH endpoints (top row on the upper strip's chain,
    # bottom row on the retreated lower strip).  The face fills the
    # gap, so the pair is deliberate geometry — NOT a tear.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 0.6, 0.0, 10.0)] + _pad_b()},
        {"wid": "-30", "role": "retaining_wall", "shapeID": "3",
         "nodes": [("-1", 0.0, 0.0, 12.0), ("-2", 0.6, 0.0, 10.0),
                   ("-3", 0.6, 5.0, 10.0), ("-4", 0.0, 5.0, 12.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_unrelated_wall_does_not_exempt_a_tear(tmp_path):
    # A retaining_wall touching only ONE endpoint does not span the
    # pair — the tear is still bare and must be flagged.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 0.6, 0.0, 10.0)] + _pad_b()},
        {"wid": "-30", "role": "retaining_wall", "shapeID": "3",
         "nodes": [("-1", 0.0, 0.0, 12.0), ("-5", 0.0, 5.0, 12.0),
                   ("-6", -0.6, 5.0, 10.0), ("-7", -0.6, 0.0, 10.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert len(violations) == 1


def test_wall_straddling_pair_is_not_flagged(tmp_path):
    # The sanctioned face need not REFERENCE either node: here the wall
    # runs strictly between them (top row x=0.6, bottom row x=0.9) and
    # its elevation range covers the step, so the level change is drawn
    # as wall geometry, not as a bare cliff.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.0)] + _pad_b()},
        {"wid": "-30", "role": "retaining_wall", "shapeID": "3",
         "nodes": [("-31", 0.6, -5.0, 12.0), ("-32", 0.6, 5.0, 12.0),
                   ("-33", 0.9, 5.0, 10.0), ("-34", 0.9, -5.0, 10.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_wall_bottom_vertex_straddle_is_not_flagged(tmp_path):
    # The HECA class (2026-08-01): the pair is a high-side pavement weld
    # vertex against the WALL'S OWN bottom-row node — shared with the low
    # strip, so only ONE endpoint is a wall coordinate and _wall_spans
    # cannot fire.  The wall's top row still crosses the pair interior.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.0)] + _pad_b()},
        {"wid": "-30", "role": "retaining_wall", "shapeID": "3",
         "nodes": [("-31", 0.6, -5.0, 12.0), ("-32", 0.6, 5.0, 12.0),
                   ("-33", 1.5, 5.0, 10.0), ("-2", 1.5, 0.0, 10.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_bare_cliff_pair_still_flagged(tmp_path):
    # Control for the straddle tests: the SAME pair geometry with no wall
    # anywhere near is an unsanctioned cliff and stays flagged.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.0)] + _pad_b()},
    ]
    violations = _run(tmp_path, ways_spec)
    assert len(violations) == 1
    assert abs(violations[0].de_m - 2.0) < 1e-6


def test_low_wall_not_bracketing_does_not_exempt(tmp_path):
    # A wall DOES cross the pair interior, but its 10.0-10.5 m face
    # cannot account for a 10.0 -> 20.5 m step even with the step-floor
    # slack: 10 m of the level change is still bare mesh.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 20.5)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.0)] + _pad_b()},
        {"wid": "-30", "role": "retaining_wall", "shapeID": "3",
         "nodes": [("-31", 0.6, -5.0, 10.5), ("-32", 0.6, 5.0, 10.5),
                   ("-33", 0.9, 5.0, 10.0), ("-34", 0.9, -5.0, 10.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert len(violations) == 1


# ── The straddle exemption's OPEN-GROUND clause (2026-08-01) ──────
# The exemption is for the graded→DEM terrace in OPEN ground.  A pair
# whose connecting segment never leaves the graded domain is an INTERIOR
# tear of the graded corridor (zones 1-2) or of a filled pocket, and no
# crossing wall face may dissolve it.  The two straddle tests above are
# the positive controls: their strips are degenerate chains, so raw
# terrain does lie between the nodes and the exemption still fires.


def _straddling_wall() -> Dict:
    """The wall of ``test_wall_straddling_pair_is_not_flagged``: its top
    row (x=0.6) and bottom row (x=0.9) cross the pair's interior and its
    10-12 m elevation range brackets the step."""
    return {"wid": "-30", "role": "retaining_wall", "shapeID": "3",
            "nodes": [("-31", 0.6, -5.0, 12.0), ("-32", 0.6, 5.0, 12.0),
                      ("-33", 0.9, 5.0, 10.0), ("-34", 0.9, -5.0, 10.0)]}


def test_zone_1_2_pair_with_crossing_wall_stays_flagged(tmp_path):
    # The SAME pair and the SAME crossing wall as
    # test_wall_straddling_pair_is_not_flagged, but the graded corridor's
    # own fabric (a third graded_strip, 24x24 m, its corners >16 m away
    # so it mints no pairs of its own) covers the ground BETWEEN the two
    # nodes.  Nothing there falls to DEM, so this is a zone-1/2 interior
    # tear: a real defect, and the wall face must not dissolve it.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.0)] + _pad_b()},
        _straddling_wall(),
        {"wid": "-40", "role": "graded_strip", "shapeID": "4",
         "nodes": [("-41", -12.0, -12.0, 11.0), ("-42", 12.0, -12.0, 11.0),
                   ("-43", 12.0, 12.0, 11.0), ("-44", -12.0, 12.0, 11.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert len(violations) == 1, [
        (v.de_m, v.distance_m) for v in violations]
    assert abs(violations[0].de_m - 2.0) < 1e-6


def test_pocket_interior_pair_with_crossing_wall_stays_flagged(tmp_path):
    # The pocket class: the pair sits inside a pavement-enclosed pocket
    # whose fill/drainage grading the owner's enclosure ruling KEEPS, so
    # the ground between the two nodes is graded, not DEM.  Same pair,
    # same crossing wall; the exemption must refuse to fire.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.0)] + _pad_b()},
        _straddling_wall(),
        {"wid": "-50", "role": "apron", "shapeID": "5",
         "nodes": [("-51", -12.0, -12.0, 11.0), ("-52", 12.0, -12.0, 11.0),
                   ("-53", 12.0, 12.0, 11.0), ("-54", -12.0, 12.0, 11.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert len(violations) == 1
    assert abs(violations[0].de_m - 2.0) < 1e-6


def test_hairline_graded_gap_is_not_open_ground(tmp_path):
    # Two abutting pavement plates leave a 4 mm slit at x=0.748-0.752 —
    # a polygon-boundary artifact, not open ground.  The interior sample
    # that lands in it is within STRIP_SEAM_OPEN_GROUND_MIN_M of graded
    # ground, so the pair is still interior and stays flagged.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.0)] + _pad_b()},
        _straddling_wall(),
        {"wid": "-60", "role": "apron", "shapeID": "6",
         "nodes": [("-61", -12.0, -12.0, 11.0), ("-62", 0.748, -12.0, 11.0),
                   ("-63", 0.748, 12.0, 11.0), ("-64", -12.0, 12.0, 11.0)]},
        {"wid": "-70", "role": "apron", "shapeID": "7",
         "nodes": [("-71", 0.752, -12.0, 11.0), ("-72", 12.0, -12.0, 11.0),
                   ("-73", 12.0, 12.0, 11.0), ("-74", 0.752, 12.0, 11.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert len(violations) == 1


def test_wall_ring_closing_face_straddle_is_not_flagged(tmp_path):
    # The wall ring's CLOSING face — last node back to first, its end cap
    # — is a real emitted face, but the vertex table drops a closed ring's
    # repeated last node, so walking consecutive vertices alone misses it.
    # Here ONLY the closing face (x=0.75, y=-3..3) crosses the pair; every
    # consecutive segment is >=3 m away.  The pair is open ground (both
    # strips are degenerate chains), so the exemption must fire.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 12.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 1.5, 0.0, 10.0)] + _pad_b()},
        {"wid": "-30", "role": "retaining_wall", "shapeID": "3",
         "nodes": [("-31", 0.75, 3.0, 12.0), ("-32", 60.0, 3.0, 12.0),
                   ("-33", 60.0, -3.0, 10.0), ("-34", 0.75, -3.0, 10.0)]},
    ]
    violations = _run(tmp_path, ways_spec)
    assert violations == []


def test_stacked_wall_same_coordinate_is_flagged(tmp_path):
    # Two strips holding DIFFERENT values at the same coordinate emit as
    # stacked separate nodes — a bare vertical terrain wall.  The grade
    # denominator clamps at the minimum distance, so the pair is flagged.
    ways_spec = [
        {"wid": "-10", "role": "graded_strip", "shapeID": "1",
         "nodes": [("-1", 0.0, 0.0, 10.0)] + _pad_a()},
        {"wid": "-20", "role": "graded_strip", "shapeID": "2",
         "nodes": [("-2", 0.0, 0.0, 13.8)] + _pad_b()},
    ]
    violations = _run(tmp_path, ways_spec)
    assert len(violations) == 1
    assert violations[0].de_m > 3.0
