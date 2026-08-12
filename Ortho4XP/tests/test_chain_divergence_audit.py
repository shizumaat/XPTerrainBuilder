"""Tests for the interior-edge-crossing detector added to
``tools/chain_divergence_audit.py`` (part-36 queue item 6).

The detector reports pairs of way edges from DIFFERENT ways whose
interiors transversally cross at a single point sitting strictly inside
both edges (farther than the 1 mm endpoint tolerance from every
endpoint).  Endpoint touches, shared-vertex joins and parallel slivers
must NOT be counted — those belong to the T-vertex, coincident-node and
near-parallel classes.

Synthetic fixture (longitude, latitude), built inline and written to a
temporary ``.osm`` so it exercises the exact ``_load`` / ``analyze``
path the lab uses on real patch output:

    node 1: (10.0000, 50.0000)      node 2: (10.0010, 50.0010)
    node 3: (10.0000, 50.0010)      node 4: (10.0010, 50.0000)
    node 5: (10.0020, 50.0000)

    way 100 taxiway: 1 -> 2         # one diagonal of the square
    way 200 runway : 3 -> 4         # the other diagonal -> a true X
    way 300 apron  : 2 -> 5         # shares node 2 (endpoint touch);
                                    # also runs parallel to way 200

The taxiway and runway diagonals cross at the centre (10.0005, 50.0005):
exactly ONE interior crossing.  The apron edge only touches the taxiway
at their shared endpoint and is parallel to the runway diagonal, so it
adds no crossing.
"""

from __future__ import annotations

import importlib.util
import os

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")


def _load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "chain_divergence_audit",
        os.path.join(TOOLS_DIR, "chain_divergence_audit.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_NODES = [
    (1, 10.0000, 50.0000),
    (2, 10.0010, 50.0010),
    (3, 10.0000, 50.0010),
    (4, 10.0010, 50.0000),
    (5, 10.0020, 50.0000),
]
_WAYS = [
    (100, "taxiway", [1, 2]),
    (200, "runway", [3, 4]),
    (300, "apron", [2, 5]),
]


def _write_osm(path):
    lines = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    for nid, lon, lat in _NODES:
        lines.append(f"  <node id='{nid}' lat='{lat:.7f}' lon='{lon:.7f}'/>")
    for wid, role, refs in _WAYS:
        lines.append(f"  <way id='{wid}'>")
        for r in refs:
            lines.append(f"    <nd ref='{r}'/>")
        lines.append(f"    <tag k='o4_feature' v='{role}'/>")
        lines.append("  </way>")
    lines.append("</osm>")
    with open(path, "w") as handle:
        handle.write("\n".join(lines))


def test_interior_edge_crossing_detects_single_transversal(tmp_path, capsys):
    module = _load_audit_module()
    osm_path = os.path.join(str(tmp_path), "synthetic_crossing.osm")
    _write_osm(osm_path)

    total_tv, near_parallel, crossings, _self_crossings = module.analyze(
        osm_path)

    # exactly one interior crossing: the taxiway/runway diagonals.
    assert crossings == 1, f"expected 1 crossing, got {crossings}"
    # the shared-endpoint apron edge is NOT a crossing.
    out = capsys.readouterr().out
    assert "runway~taxiway" in out    # role pair is sorted alphabetically


def test_endpoint_touch_and_parallel_are_not_crossings(tmp_path):
    """Two ways sharing an endpoint, and two parallel ways, yield zero
    crossings on their own."""
    module = _load_audit_module()
    osm_path = os.path.join(str(tmp_path), "no_crossing.osm")
    # only the touch + parallel ways, no transversal diagonal pair.
    lines = ["<osm version='0.6'>"]
    for nid, lon, lat in [(2, 10.0010, 50.0010), (4, 10.0010, 50.0000),
                          (5, 10.0020, 50.0000), (3, 10.0000, 50.0010)]:
        lines.append(f"  <node id='{nid}' lat='{lat:.7f}' lon='{lon:.7f}'/>")
    # way 200 (runway 3->4) and way 300 (apron 2->5) are parallel
    # diagonals; they neither cross nor share a vertex.
    for wid, role, refs in [(200, "runway", [3, 4]), (300, "apron", [2, 5])]:
        lines.append(f"  <way id='{wid}'>")
        for r in refs:
            lines.append(f"    <nd ref='{r}'/>")
        lines.append(f"    <tag k='o4_feature' v='{role}'/>")
        lines.append("  </way>")
    lines.append("</osm>")
    with open(osm_path, "w") as handle:
        handle.write("\n".join(lines))

    _tv, _np, crossings, _self_crossings = module.analyze(osm_path)
    assert crossings == 0, f"parallel/touch pair miscounted: {crossings}"


# ── round-16 geometry-consistency classes (5, 6, 7, 8) ──────────────
#
# ONE implementation answers the CLI, the acceptance runs and these
# twins: ``geometry_consistency()``.  A second counter beside it is the
# census-wrapper defect the tool ruling exists to prevent.

def _write_osm_rich(path, nodes, ways):
    """``nodes`` are ``(id, lon, lat, alt|None)``; ``ways`` are
    ``(id, o4_feature, ref|None, [node id...])``."""
    lines = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    for nid, lon, lat, alt in nodes:
        if alt is None:
            lines.append(
                f"  <node id='{nid}' lat='{lat:.11f}' lon='{lon:.11f}'/>")
            continue
        lines.append(f"  <node id='{nid}' lat='{lat:.11f}' lon='{lon:.11f}'>")
        lines.append(f"    <tag k='alt_abs' v='{alt}' />")
        lines.append("  </node>")
    for wid, feature, ref, refs in ways:
        lines.append(f"  <way id='{wid}'>")
        for r in refs:
            lines.append(f"    <nd ref='{r}'/>")
        lines.append(f"    <tag k='o4_feature' v='{feature}'/>")
        if ref is not None:
            lines.append(f"    <tag k='ref' v='{ref}'/>")
        lines.append("  </way>")
    lines.append("</osm>")
    with open(path, "w") as handle:
        handle.write("\n".join(lines))


def test_twin_ring_pair_is_one_boundary_spelled_twice(tmp_path):
    """Two rings on ONE boundary, one of them carrying an extra vertex
    that sits exactly on the other's chord: one twin-ring pair, one
    differing vertex, counted on the chord."""
    module = _load_audit_module()
    path = os.path.join(str(tmp_path), "twin.osm")
    # a 100 m square (deg offsets are approximate: the class is
    # distance-binned, not coordinate-binned)
    d = 0.0009
    nodes = [(1, 10.0, 50.0, 3.0), (2, 10.0 + d, 50.0, 3.0),
             (3, 10.0 + d, 50.0 + d, 3.0), (4, 10.0, 50.0 + d, 3.0),
             # the extra vertex: the midpoint of edge 1-2, ON the chord
             (5, 10.0 + d / 2.0, 50.0, 3.0)]
    ways = [(100, "apron", None, [1, 2, 3, 4, 1]),
            (200, "shape_interior_ring", None, [1, 5, 2, 3, 4, 1])]
    _write_osm_rich(path, nodes, ways)
    gc = module.geometry_consistency(path)
    assert len(gc["twin_ring_pairs"]) == 1, gc["twin_ring_pairs"]
    assert gc["twin_ring_missing"] == 1
    assert gc["twin_ring_on_chord"] == 1


def test_two_different_boundaries_are_not_a_twin_pair(tmp_path):
    """The control: two rings sharing an EDGE (three nodes) but bounding
    different ground are not one boundary spelled twice."""
    module = _load_audit_module()
    path = os.path.join(str(tmp_path), "neighbours.osm")
    d = 0.0009
    nodes = [(1, 10.0, 50.0, 3.0), (2, 10.0 + d, 50.0, 3.0),
             (3, 10.0 + d, 50.0 + d, 3.0), (4, 10.0, 50.0 + d, 3.0),
             (5, 10.0 + 2 * d, 50.0, 3.0), (6, 10.0 + 2 * d, 50.0 + d, 3.0),
             (7, 10.0 + d, 50.0 + d / 2.0, 3.0)]
    ways = [(100, "apron", None, [1, 2, 7, 3, 4, 1]),
            (200, "apron", None, [2, 5, 6, 3, 7, 2])]
    _write_osm_rich(path, nodes, ways)
    gc = module.geometry_consistency(path)
    assert gc["twin_ring_pairs"] == [], gc["twin_ring_pairs"]


def test_sub_micron_cluster_and_needle_and_unowned_wall(tmp_path):
    """One near-coincident node pair (5e-10 deg apart — inside the
    1e-9 deg default, and NOT an identical coordinate), one 0.1 deg
    needle tip, and one wall node 8 m above a ramp across a gap no
    shape owns."""
    module = _load_audit_module()
    path = os.path.join(str(tmp_path), "classes.osm")
    d = 0.0009
    # metres per degree at lat 50: ~111320 lat, ~71600 lon
    gap_deg = 2.0 / 111320.0            # a 2 m gap: inside the wall reach
    nodes = [
        (1, 10.0, 50.0, -8.0), (2, 10.0 + d, 50.0, -8.0),
        (3, 10.0 + d, 50.0 + d, -8.0), (4, 10.0, 50.0 + d, -8.0),
        # the wall, one gap north of the ramp's top edge
        (10, 10.0, 50.0 + d + gap_deg, 0.5),
        (11, 10.0 + d, 50.0 + d + gap_deg, 0.5),
        (12, 10.0 + d, 50.0 + d + 2 * gap_deg, 0.5),
        (13, 10.0, 50.0 + d + 2 * gap_deg, 0.5),
        # the sub-micron twin of node 10
        (20, 10.0 + 5e-10, 50.0 + d + gap_deg, 0.5),
        # a needle tip: two legs 0.1 deg apart off one apron corner
        (30, 10.0 + 2 * d, 50.0, 3.0),
        (31, 10.0 + 4 * d, 50.0 + 0.000001, 3.0),
        (32, 10.0 + 2 * d, 50.0 + 0.00002, 3.0),
    ]
    ways = [
        (100, "tunnel_ramp", "tunnel_ramp", [1, 2, 3, 4, 1]),
        (200, "retaining_wall", "tunnel_wall", [10, 11, 12, 13, 10]),
        (300, "apron", None, [30, 31, 32, 30]),
    ]
    _write_osm_rich(path, nodes, ways)
    gc = module.geometry_consistency(path)
    assert gc["submicron_clusters"] == 1, gc["submicron_sites"]
    assert gc["submicron_sites"][0][4] is False      # near, not identical
    assert len(gc["wall_above_ramp"]) >= 2, gc["wall_above_ramp"]
    assert gc["wall_unowned"] == len(gc["wall_above_ramp"]), (
        "a wall standing over a gap is UNOWNED")
    assert any(n["role"] == "apron" and n["angle_deg"] < 25.0
               for n in gc["needles"]), gc["needles"]


def test_a_welded_wall_face_reads_owned(tmp_path):
    """The R16-2b acceptance shape: the wall's inner edge IS the ramp's
    boundary (same node ids), so nothing is unowned even though the
    crest still stands metres above the ramp."""
    module = _load_audit_module()
    path = os.path.join(str(tmp_path), "welded.osm")
    d = 0.0009
    out_deg = 1.6 / 111320.0
    nodes = [
        (1, 10.0, 50.0, -8.0), (2, 10.0 + d, 50.0, -8.0),
        (3, 10.0 + d, 50.0 + d, -8.0), (4, 10.0, 50.0 + d, -8.0),
        (12, 10.0 + d, 50.0 + d + out_deg, 0.5),
        (13, 10.0, 50.0 + d + out_deg, 0.5),
    ]
    # the wall reuses nodes 3 and 4 — the ramp's own top edge
    ways = [
        (100, "tunnel_ramp", "tunnel_ramp", [1, 2, 3, 4, 1]),
        (200, "retaining_wall", "tunnel_wall", [4, 3, 12, 13, 4]),
    ]
    _write_osm_rich(path, nodes, ways)
    gc = module.geometry_consistency(path)
    assert gc["wall_unowned"] == 0, gc["wall_above_ramp"]
