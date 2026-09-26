"""§41 — A FACE INSIDE A PAVEMENT FACE IS A HOLE OF IT; ZONES ARE CLIPPED
OUT OF PAVEMENT (owner RULINGS 2026-09-13co item 2; attribution RULINGS
2026-09-13cs item 2; lane ``v2zonehole``).

Three twins, one per limb of the ruling:

1. ``planar.overlay.absorb_enclosed_pavement`` — a pavement face ≥ 95 % of
   whose own area lies inside another, larger pavement face's EXTERIOR
   RING is absorbed into it: one face, one role, one ref, no boundary for
   a step to stand on.  The frame is the host's RING and not its solid,
   because the arrangement is a partition — the enclosed face sits in the
   host's HOLE, so their hole-aware intersection is 0 m² by construction
   (measured on the owner's 1.0.329 HECA patch: 22 enclosed faces, every
   one at solid fraction 0.000).  An enclosed face that shares NO boundary
   with the host is an ISLAND, not a notch, and is refused.
2. ``check_grade.zone_on_pavement`` — an adjacent-ground zone strip
   standing on a pavement face's SOLID is a defect, CRITICAL over 0.5 m².
   Registered in ``LAW_FAMILIES`` (``tests/test_harness.py`` refuses an
   unregistered family).
3. ``tools/role_overlap_read.py`` — the containment census, and the
   ``KeyError: 'anchor'`` repair (v2's ``SIDECAR_KEYS`` publishes no
   anchor: the frame is then the census's own mean-of-nodes frame, named
   in the report, never a crash).
"""
from __future__ import annotations

import os
import sys

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "tools"))

from auto_patch_v2.planar.overlay import (ENCLOSED_MIN_FRAC, Region,
                                          absorb_enclosed_pavement)

ROLES = ("runway", "primary_parallel", "cross_connector", "apron")


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _region(role, ref):
    return Region(role, ref, Polygon(_rect(0, 0, 1, 1)), None, None,
                  "airside", "cell")


def _host_with_notch():
    """A 100x100 parallel with a 20x20 notch cut out of its middle, and the
    cross-connector that fills the notch — the HECA pav73 / pav77 shape."""
    host = Polygon(_rect(0, 0, 100, 100), [_rect(40, 40, 60, 60)[::-1]])
    notch = Polygon(_rect(40, 40, 60, 60))
    return host, notch


# ── 1. the enclosed pavement face ────────────────────────────────────

def test_a_cross_connector_inside_a_parallel_is_the_parallel():
    host, notch = _host_with_notch()
    par = _region("primary_parallel", "pav73")
    xc = _region("cross_connector", "pav77")
    faces = [(host, par), (notch, xc)]
    out, absorbed, detached = absorb_enclosed_pavement(faces, ROLES)
    assert (absorbed, detached) == (1, 0)
    assert len(out) == 1
    poly, region = out[0]
    # the notch is gone: one solid body, the host's law
    assert region is par
    assert poly.area == pytest.approx(100.0 * 100.0)
    assert not poly.interiors


def test_the_frame_is_the_host_ring_not_its_solid():
    """The hole-aware intersection of host and notch is 0 m² — the reading
    a solid-frame test gives, and the reason it finds nothing."""
    host, notch = _host_with_notch()
    assert host.intersection(notch).area == pytest.approx(0.0)
    assert notch.intersection(Polygon(host.exterior)).area == \
        pytest.approx(notch.area)


def test_an_island_that_touches_nothing_is_refused():
    """An enclosed face sharing no boundary with the host is an island in
    the middle of a loop (HECA ``apron:pav5``, 12.97 m off its host), not a
    notch: absorbing it would make one face out of two disjoint pieces."""
    host = Polygon(_rect(0, 0, 100, 100), [_rect(30, 30, 70, 70)[::-1]])
    island = Polygon(_rect(40, 40, 60, 60))
    out, absorbed, detached = absorb_enclosed_pavement(
        [(host, _region("cross_connector", "pav67")),
         (island, _region("apron", "pav5"))], ROLES)
    assert (absorbed, detached) == (0, 1)
    assert len(out) == 2


def test_a_notch_reached_through_a_narrow_mouth_is_a_separate_body():
    """RULINGS 2026-09-08k: a neck narrower than the mouth separates two
    bodies, and a step between bodies is LAWFUL.  Measured (CYXY): the one
    contained face there, ``apron:pav21#204``, is reached through a 9.31 m
    mouth, and absorbing it moved the control's ``airside_no_step`` 39 ->
    54 rows (10 over 0.5 m -> 26) with the v1 oracle unmoved at 39."""
    host = Polygon(_rect(0, 0, 100, 100),
                   [((40, 40), (40, 60), (45, 60), (45, 40))[::-1]])
    notch = Polygon(_rect(40, 40, 45, 60))               # a 20 m contact
    par = _region("primary_parallel", "pav1")
    faces = [(host, par), (notch, _region("apron", "pav2"))]
    assert absorb_enclosed_pavement(faces, ROLES, mouth_m=12.0)[1] == 1
    assert absorb_enclosed_pavement(faces, ROLES, mouth_m=60.0)[1] == 0
    # the default is the ungated read, so a caller must pass the law's own
    # number (``emit.terrace.narrow_mouth_max_m``); the arrangement does
    assert absorb_enclosed_pavement(faces, ROLES)[1] == 1


def test_a_neighbour_that_is_not_enclosed_is_left_alone():
    """Two faces side by side share a boundary and neither is inside the
    other's ring — the ordinary case, untouched."""
    a = Polygon(_rect(0, 0, 100, 100))
    b = Polygon(_rect(100, 0, 120, 20))
    out, absorbed, detached = absorb_enclosed_pavement(
        [(a, _region("primary_parallel", "pav1")),
         (b, _region("cross_connector", "pav2"))], ROLES)
    assert (absorbed, detached) == (0, 0)
    assert len(out) == 2


def test_the_floor_is_the_fraction_of_the_enclosed_face_s_own_area():
    """A face only PARTLY inside the host's ring is not its hole."""
    host = Polygon(_rect(0, 0, 100, 100), [_rect(90, 40, 100, 60)[::-1]])
    half_out = Polygon(_rect(90, 40, 110, 60))       # 50 % inside the ring
    out, absorbed, _d = absorb_enclosed_pavement(
        [(host, _region("primary_parallel", "pav1")),
         (half_out, _region("cross_connector", "pav2"))], ROLES)
    assert absorbed == 0 and len(out) == 2
    # at a floor it does clear, the same pair absorbs
    out, absorbed, _d = absorb_enclosed_pavement(
        [(host, _region("primary_parallel", "pav1")),
         (half_out, _region("cross_connector", "pav2"))], ROLES, min_frac=0.4)
    assert absorbed == 1 and len(out) == 1


def test_a_non_pavement_face_is_never_absorbed_and_never_a_host():
    """Only ``emit.terrace.shape_roles`` pavement takes part: an
    adjacent-ground strip in the notch stays its own face."""
    host, notch = _host_with_notch()
    out, absorbed, detached = absorb_enclosed_pavement(
        [(host, _region("primary_parallel", "pav73")),
         (notch, _region("graded_strip", "adjacent_ground:taxi:F:zone2#7"))],
        ROLES)
    assert (absorbed, detached) == (0, 0) and len(out) == 2


def test_nested_notches_fold_into_the_outermost_body():
    """Smallest first, so a chain folds all the way out."""
    host = Polygon(_rect(0, 0, 100, 100), [_rect(20, 20, 80, 80)[::-1]])
    mid = Polygon(_rect(20, 20, 80, 80), [_rect(40, 40, 60, 60)[::-1]])
    inner = Polygon(_rect(40, 40, 60, 60))
    out, absorbed, detached = absorb_enclosed_pavement(
        [(host, _region("primary_parallel", "pav1")),
         (mid, _region("cross_connector", "pav2")),
         (inner, _region("cross_connector", "pav3"))], ROLES)
    assert (absorbed, detached) == (2, 0)
    assert len(out) == 1 and out[0][0].area == pytest.approx(10000.0)


def test_the_default_floor_is_the_ruling_s_95_percent():
    import role_overlap_read as ROR
    assert ENCLOSED_MIN_FRAC == 0.95
    # ONE floor, two spellings (the engine's and the instrument's)
    assert ROR.CONTAINED_MIN_FRAC == ENCLOSED_MIN_FRAC


# ── 2. the census family ─────────────────────────────────────────────

def test_zone_on_pavement_is_a_registered_law_family():
    import check_grade as CG
    assert CG.ZONE_ON_PAVEMENT_FAMILY == "zone_on_pavement"
    assert "zone_on_pavement" in {k for k, _t, _b in CG.LAW_FAMILIES}
    # the cockpit reader refuses a family with no families.toml entry
    assert CG.cockpit_law(refresh=True)["family_class"][
        "zone_on_pavement"] == "keepout"


def test_zone_on_pavement_prices_the_solid_frame():
    """A strip inside a pavement face's HOLE stands on nothing; a strip
    over its SOLID is the defect."""
    import check_grade as CG
    host, notch = _host_with_notch()
    assert CG._zone_on_pavement_area(notch, [host]) == pytest.approx(0.0)
    over = Polygon(_rect(0, 0, 10, 10))
    assert CG._zone_on_pavement_area(over, [host]) == pytest.approx(100.0)


def test_zone_on_pavement_reads_the_strips_own_hole():
    """NLWF 2026-09-21 (#18): a zone-2 strip is a RING around the runway
    and zone 1; its hole is published under the STRIP's shapeID.  Read
    ring-blind it 'stood on' the whole runway (34,069.6 m², one
    adjudicated FAIL); read in its own solid frame it stands on 0 m²."""
    import check_grade as CG
    ll = lambda la, lo: (lo * 1000.0, la * 1000.0)        # noqa: E731
    runway = CG.Way(wid="-1", role="runway", ref="07/25", aeroway="runway",
                    nids=["r0", "r1", "r2", "r3", "r0"], elevs=[4.9] * 5,
                    tags={"role": "runway", "shapeID": "0", "ref": "07/25"})
    strip = CG.Way(wid="-2", role="graded_strip",
                   ref="adjacent_ground:runway:2:zone2#0", aeroway="apron",
                   nids=["s0", "s1", "s2", "s3", "s0"], elevs=[4.9] * 5,
                   tags={"role": "graded_strip", "shapeID": "7",
                         "ref": "adjacent_ground:runway:2:zone2#0"})
    nodes = {"r0": (0.02, 0.02), "r1": (0.02, 0.08), "r2": (0.04, 0.08),
             "r3": (0.04, 0.02), "s0": (0.0, 0.0), "s1": (0.0, 0.1),
             "s2": (0.06, 0.1), "s3": (0.06, 0.0)}
    ways = [runway, strip]
    ring_blind = CG._check_zone_on_pavement(ways, nodes, ll, None)
    assert len(ring_blind) == 1 and ring_blind[0].de_m == pytest.approx(
        20.0 * 60.0)
    hole = [ll(0.02, 0.02), ll(0.02, 0.08), ll(0.04, 0.08), ll(0.04, 0.02)]
    assert CG._check_zone_on_pavement(ways, nodes, ll, {"7": [hole]}) == []


# ── 3. the containment census / the anchor repair ────────────────────

def test_a_sidecar_without_an_anchor_is_not_a_crash(tmp_path):
    """v2's ``SIDECAR_KEYS`` publishes no ``anchor``: the read falls back
    to the census's OWN mean-of-nodes frame and says so."""
    import json

    import role_overlap_read as ROR
    patch = tmp_path / "X_auto.patch.osm"
    patch.write_text(_two_face_patch())
    (tmp_path / "X_auto.patch.osm.axes.json").write_text(json.dumps(
        {"ruleset": "icao", "face_holes": {}}))
    res = ROR.read(patch, over="graded_strip", on="primary_parallel")
    assert res["anchor"] is None
    assert res["frame"] == "mean-of-nodes"


def test_the_containment_census_reads_the_ring_frame(tmp_path):
    import json

    import role_overlap_read as ROR
    patch = tmp_path / "X_auto.patch.osm"
    patch.write_text(_two_face_patch())
    (tmp_path / "X_auto.patch.osm.axes.json").write_text(json.dumps(
        {"ruleset": "icao",
         "face_holes": {"1": [[[0.0002, 0.0002], [0.0002, 0.0006],
                               [0.0006, 0.0006], [0.0006, 0.0002]]]}}))
    res = ROR.contained(patch, min_frac=0.95)
    assert res["contained"] == 1
    row = res["rows"][0]
    assert row["ref"] == "pav77" and row["in_ref"] == "pav73"
    assert row["ring_frac"] == pytest.approx(1.0, abs=1e-3)
    assert row["solid_frac"] == pytest.approx(0.0, abs=1e-3)
    assert row["touches"] is True


def _two_face_patch() -> str:
    """A 0.001° pavement ring with a hole, and a small face inside it."""
    outer = [(0.0, 0.0), (0.0, 0.001), (0.001, 0.001), (0.001, 0.0)]
    hole = [(0.0002, 0.0002), (0.0002, 0.0006), (0.0006, 0.0006),
            (0.0006, 0.0002)]
    lines = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    nid = -1
    ids = {}
    for tag, ring in (("o", outer), ("h", hole)):
        ids[tag] = []
        for la, lo in ring:
            lines.append(f"<node id='{nid}' lat='{la:.8f}' lon='{lo:.8f}'>"
                         f"<tag k='alt_abs' v='10.0'/></node>")
            ids[tag].append(nid)
            nid -= 1

    def way(wid, ns, role, ref, shape):
        lines.append(f"<way id='{wid}'>")
        for n in ns + [ns[0]]:
            lines.append(f"<nd ref='{n}'/>")
        lines.append(f"<tag k='aeroway' v='taxiway'/>")
        lines.append(f"<tag k='role' v='{role}'/>")
        lines.append(f"<tag k='ref' v='{ref}'/>")
        lines.append(f"<tag k='shapeID' v='{shape}'/>")
        lines.append("</way>")
    way(-1, ids["o"], "primary_parallel", "pav73", "1")
    way(-2, ids["h"], "cross_connector", "pav77", "2")
    lines.append("</osm>")
    return "\n".join(lines) + "\n"


# ── 4. the hole survives the emit (RULINGS 2026-09-13da residual) ───────
#
# The 3 rows / 52.3 m² the family reported on the v2zonehole HECA closing
# arm were minted BETWEEN the arrangement and the sidecar: ``publication``
# read ``face_holes`` off the planar map, then ``merge_sub_spacing`` folded
# 782 sub-spacing vertices out of the emitted rings — the host's hole ring
# and the zone strip's ring that shares it alike — and the sidecar kept the
# stale vertex.  Exterior (emitted) minus hole (stale) is a 0.5 m sliver of
# "solid" along the strip.  The writer now derives the key from the surface
# it writes.

M_LAT = 111_320.0


def _host_hole_strip(law):
    """A 200 m apron with a 100 m hole, and the zone strip that IS the
    hole (the arrangement's partition: the strip ring shares the hole's
    vertices).  One hole vertex ``B`` stands 0.42 m from its neighbour
    ``H2`` and 0.3 m into the hole — a sub-spacing detour the identity
    join folds away.  Returns ``(surface, B's vertex id)``."""
    import math

    from auto_patch_v2.emit.surface import (GradedSurface, SurfaceFace,
                                            SurfaceVertex)
    la0, lo0 = 30.0, 31.0
    m_lon = M_LAT * math.cos(math.radians(la0))

    def ll(x, y):
        return (round(la0 + y / M_LAT, 11), round(lo0 + x / m_lon, 11))

    pts = {0: ll(0, 0), 1: ll(200, 0), 2: ll(200, 200), 3: ll(0, 200),
           4: ll(50, 50), 5: ll(50, 150), 6: ll(150, 150), 7: ll(150, 50),
           8: ll(150 - 0.3, 150 - 0.3)}       # B: 0.42 m from H2 (id 6)
    verts = tuple(SurfaceVertex(i, pts[i], 100.0) for i in sorted(pts))
    hole = (4, 5, 8, 6, 7)
    faces = (SurfaceFace(1, "apron", "pav1", (0, 1, 2, 3), (hole,), "airside"),
             SurfaceFace(2, "graded_strip", "adjacent_ground:taxi:E:zone1#1",
                         tuple(reversed(hole)), (), "airside"))
    return GradedSurface(icao="TEST", ruleset="icao", origin=(la0, lo0),
                         crs="+proj=tmerc", identity_dp=11, vertices=verts,
                         faces=faces, breaklines=(), provenance={}), 8


def _family_rows(patch, holes_ll):
    import check_grade as CG
    nodes, ways = CG._parse_osm(patch)[:2]
    ll_to_m = CG._ll_to_m_factory(nodes, None)
    holes_m = {k: [[ll_to_m(*pt) for pt in r] for r in rings]
               for k, rings in holes_ll.items()}
    return CG._check_zone_on_pavement(ways, nodes, ll_to_m, holes_m)


def test_a_hole_holding_a_zone_strip_survives_the_emit_intact(tmp_path):
    """The twin: host with a hole containing a zone strip → merge → patch.
    The sidecar's hole is the hole the EMITTED rings bound (the merged
    vertex gone, the ring still one hole), and the family reads 0 rows."""
    import json

    from auto_patch_v2.emit import osm_adapter as A
    from auto_patch_v2.law import Law
    law = Law.for_airport("HECA")
    surf0, b_id = _host_hole_strip(law)
    b_ll = [v.ll for v in surf0.vertices if v.id == b_id][0]
    rep = A.WeldReport()
    surf = A.merge_sub_spacing(surf0, law, rep)
    assert rep.merged == 1
    assert all(b_id not in h for f in surf.faces for h in f.holes)
    # the caller's (stale) publication is superseded by the writer's own
    paths = A.write_patch(surf, law, tmp_path,
                          {"face_holes": A.face_holes_ll(surf0)})
    side = json.loads(paths.sidecar.read_text())
    holes = side["face_holes"]
    assert list(holes) == ["1"] and len(holes["1"]) == 1, "one host, one hole"
    ring = [tuple(pt) for pt in holes["1"][0]]
    assert len(ring) == 4 and b_ll not in ring
    # the hole ring IS the emitted strip ring (same vertices, same identity)
    text = paths.patch.read_text()
    assert f"lat='{b_ll[0]:.11f}'" not in text, "the merged vertex is not a node"
    assert _family_rows(paths.patch, holes) == []


def test_the_stale_planar_hole_is_the_defect(tmp_path):
    """The control that reproduces the HECA residual: the PRE-merge hole
    ring read against the POST-merge rings mints the sliver (0.5 × 100 m ×
    0.3 m = 15 m²) as pavement under the strip — one CRITICAL row."""
    from auto_patch_v2.emit import osm_adapter as A
    from auto_patch_v2.law import Law
    law = Law.for_airport("HECA")
    surf0, _b = _host_hole_strip(law)
    surf = A.merge_sub_spacing(surf0, law, A.WeldReport())
    paths = A.write_patch(surf, law, tmp_path, {})
    rows = _family_rows(paths.patch, A.face_holes_ll(surf0))
    assert len(rows) == 1
    assert rows[0].de_m == pytest.approx(15.0, abs=0.5)
    assert rows[0].way_a.ref == "adjacent_ground:taxi:E:zone1#1"


def test_publication_no_longer_derives_face_holes():
    """One derivation site: the writer.  ``publication`` publishes no
    ``face_holes`` of its own for a later pass to make stale."""
    import inspect

    from auto_patch_v2.pipeline import publication as P
    assert not hasattr(P, "face_holes_ll")
    assert '"face_holes"' not in inspect.getsource(P.publication)
