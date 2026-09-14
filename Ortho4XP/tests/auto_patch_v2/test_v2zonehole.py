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
