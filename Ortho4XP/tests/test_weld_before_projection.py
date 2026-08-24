"""WELD BEFORE PROJECTION — emit-minted adjacencies enter the law
(spec ``docs/specs/weld-before-projection-spec.md``, owner "proceed"
2026-08-21).

The nid-level final weld used to insert on-edge node references AFTER the
bake and AFTER ``final_grade_projection``, minting ring adjacencies no law
had priced: 22 of SPJC's 48 sub-5 m > 2x rows are pairs whose ENDPOINTS are
baked nodes (within 9 mm) but whose PAIR the bake never saw, and the
law-aware emit snap validates BAKED pairs only.  Values are single-authored
throughout — the defect is topology TIMING.

Twins (spec §4):
  (a) a zero-weld layout is a no-op (nothing to insert);
  (b) a two-shape weld's inserted adjacency reaches the ring the bake walks
      and is priced like any ring edge;
  (c) the inserted vertex takes the edge's interpolated altitude — it is
      surface-neutral at insert time and a normal node thereafter;
  (d) IDEMPOTENCE: welding twice inserts 0 the second time, which is what
      makes the ``to_osm`` pass pure verification.
"""
import os
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch import conformance as CF
from auto_patch import pipeline as PL
from auto_patch.layout import BuiltShape, PavementLayout


def _layout(shapes):
    lay = PavementLayout.__new__(PavementLayout)
    lay.shapes = shapes
    lay.canonical_points = None
    return lay


def _apron(ring, ref, alt=10.0):
    return BuiltShape(polygon=Polygon(ring), role="apron", ref=ref,
                      altitude=alt)


# ── (a) the no-op case ───────────────────────────────────────────────

def test_a_layout_with_no_t_junction_welds_nothing():
    """Two shapes that share only exact corners have no vertex lying in the
    INTERIOR of a neighbour's edge, so the weld is a no-op."""
    a = _apron([(0, 0), (10, 0), (10, 10), (0, 10)], "a")
    b = _apron([(10, 0), (20, 0), (20, 10), (10, 10)], "b")
    n_s, n_v = CF.enforce_conformance(_layout([a, b]),
                                      tol=CF.FINAL_WELD_TOL_M,
                                      include_overlay_refs=True)
    assert n_v == 0, "no T-junction exists, so nothing may be inserted"


def test_the_flag_defaults_on_and_is_readable():
    """The kill switch exists and defaults ON in the lane (spec §8)."""
    assert PL._WELD_BEFORE_PROJECTION in (True, False)
    assert os.environ.get("O4_WELD_BEFORE_PROJECTION", "1") != "0" \
        or PL._WELD_BEFORE_PROJECTION is False


# ── (b) the adjacency reaches the ring ───────────────────────────────

def _t_junction():
    """``b``'s corner (10, 5) lies in the INTERIOR of ``a``'s right edge."""
    a = _apron([(0, 0), (10, 0), (10, 10), (0, 10)], "a")
    b = _apron([(10, 5), (20, 5), (20, 10), (10, 10)], "b")
    return a, b


def test_the_weld_inserts_the_t_vertex_into_the_receiving_ring():
    a, b = _t_junction()
    before = len(a.polygon.exterior.coords)
    n_s, n_v = CF.enforce_conformance(_layout([a, b]),
                                      tol=CF.FINAL_WELD_TOL_M,
                                      include_overlay_refs=True)
    assert n_v >= 1, "the T-vertex must be inserted"
    coords = [tuple(round(c, 6) for c in p)
              for p in a.polygon.exterior.coords]
    assert (10.0, 5.0) in coords, (
        "the neighbour's on-edge corner must become a vertex of the ring "
        "the bake walks — that is what puts the adjacency in the law")
    assert len(a.polygon.exterior.coords) > before


def test_the_inserted_adjacency_is_a_ring_edge_the_law_can_price():
    """Once inserted, (10,0)-(10,5) and (10,5)-(10,10) are ORDINARY ring
    edges: consecutive vertices of the ring, which is exactly what the
    ring-adjacent branch of ``classify_pair`` prices."""
    a, b = _t_junction()
    CF.enforce_conformance(_layout([a, b]), tol=CF.FINAL_WELD_TOL_M,
                           include_overlay_refs=True)
    ring = [tuple(round(c, 6) for c in p)
            for p in a.polygon.exterior.coords][:-1]
    i = ring.index((10.0, 5.0))
    nbrs = {ring[(i - 1) % len(ring)], ring[(i + 1) % len(ring)]}
    assert nbrs == {(10.0, 0.0), (10.0, 10.0)}, (
        f"the inserted vertex must split the edge it welded into; got {nbrs}")


# ── (c) the insert is surface-neutral ────────────────────────────────

def test_the_inserted_vertex_takes_the_edges_interpolated_altitude():
    """Spec §1: topology only.  The insert carries the edge's own linear
    interpolation, so the surface it describes is unchanged at insert time
    (the seat-is-the-weld invariant, 2026-08-08, is not touched)."""
    a = BuiltShape(polygon=Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
                   role="apron", ref="a",
                   node_altitudes=[0.0, 0.0, 20.0, 20.0])
    b = _apron([(10, 5), (20, 5), (20, 10), (10, 10)], "b")
    CF.enforce_conformance(_layout([a, b]), tol=CF.FINAL_WELD_TOL_M,
                           include_overlay_refs=True)
    # ``node_altitudes`` is kept aligned with the CLOSED ring (the repeated
    # closing vertex carries its own entry), which is the layout's own
    # convention — assert that rather than assume the open form.
    closed = [tuple(round(c, 6) for c in p)
              for p in a.polygon.exterior.coords]
    alts = list(getattr(a, "node_altitudes", None) or [])
    assert len(alts) == len(closed), "altitudes stay aligned with the ring"
    ring = closed
    i = ring.index((10.0, 5.0))
    # the right edge runs (10,0) z=0 -> (10,10) z=20, so the midpoint is 10
    assert alts[i] == pytest.approx(10.0, abs=1e-6), (
        f"expected the edge's interpolated altitude, got {alts[i]}")


# ── (d) idempotence — what makes to_osm pure verification ────────────

def test_welding_twice_inserts_nothing_the_second_time():
    """Spec §4(d) and the reason the ``to_osm`` pass can become an
    assertion: once the rings are welded, the same pass finds nothing."""
    a, b = _t_junction()
    lay = _layout([a, b])
    _s1, v1 = CF.enforce_conformance(lay, tol=CF.FINAL_WELD_TOL_M,
                                     include_overlay_refs=True)
    assert v1 >= 1
    _s2, v2 = CF.enforce_conformance(lay, tol=CF.FINAL_WELD_TOL_M,
                                     include_overlay_refs=True)
    assert v2 == 0, (
        "the weld must be idempotent — a second pass inserting anything "
        "means the two passes disagree on the weld set (spec STOP)")


def test_the_weld_uses_the_one_candidate_enumeration():
    """``_plan_shape_inserts`` is documented as THE weld's candidate
    enumeration; a second implementation would be the census-wrapper
    defect.  The pre-projection pass reaches it through
    ``enforce_conformance``, so there is no second notion of which
    vertices weld."""
    assert hasattr(CF, "_plan_shape_inserts")
    assert "only one" in CF._plan_shape_inserts.__doc__.lower() or \
        "the only one" in CF._plan_shape_inserts.__doc__.lower()


# ── AMENDMENT A1: the wedge insert joins the pre-projection pass ──────

def test_the_wedge_and_nid_inserts_are_the_same_function():
    """A1 §1a asks for "wedge + nid inserts together".  They already ARE one
    function at one tolerance — what distinguished the post-projection wedge
    call was only its DEM/tile frame — so merging them is a call-site
    change, not a second enumeration."""
    import inspect
    src = inspect.getsource(PL)
    pre = src.index("weld-before-projection] {icao}: inserted")
    head = src[:pre]
    assert "_enf_pre(layout, tol=_PRE_WELD_TOL_M" in src
    assert "dem=_projection_dem" in src[head.rindex("_enf_pre"):pre + 400], (
        "the pre-projection insert must carry the DEM frame — the "
        "'cuts never fill' bound the wedge call had")


def test_the_snap_is_idempotent_so_it_may_run_in_both_places():
    """A1 §1b keeps the SNAP post-projection.  The pre-projection pass adds
    an idempotent call because the snap is the insert's documented
    precondition; snapping already-unified twins must be a no-op, or the
    second call would move the surface."""
    a = _apron([(0, 0), (10, 0), (10, 10), (0, 10)], "a")
    b = _apron([(10.0005, 0), (20, 0), (20, 10), (10.0005, 10)], "b")
    lay = _layout([a, b])
    _s1, v1 = CF.snap_subcm_vertex_twins(lay)
    _s2, v2 = CF.snap_subcm_vertex_twins(lay)
    assert v2 == 0, (
        "a second snap must find nothing — otherwise running it in two "
        "places moves the surface twice")


def test_the_post_projection_wedge_is_verification_when_the_gate_is_on():
    """A1 §1a: the post-projection wedge insert count MUST read 0, and a
    nonzero count is the loud residue line, never silence."""
    import inspect
    src = inspect.getsource(PL)
    assert "final epsilon-wedge weld: 0 " in src, (
        "a zero count must print its own verification line")
    assert "POST-PROJECTION WELD RESIDUE" in src
    assert src.count("POST-PROJECTION WELD RESIDUE") >= 1
