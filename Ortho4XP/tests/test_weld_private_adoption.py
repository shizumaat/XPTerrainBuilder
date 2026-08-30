"""Twins for the weld-before-projection §1 closure (session 2026-08-29):
the two emit-frame passes that used to mint airside vertices AFTER
``final_grade_projection`` — caught by
``test_solver_and_validator_same_nodes`` at CYXY — now have pre-projection
layout-frame twins, and these tests pin their behaviour synthetically.

  * PRIVATE ON-EDGE ADOPTION (``enforce_conformance(private_snap_tol=…)``,
    ``conformance._private_snap_hits``): the emit-time "private on-edge
    node move" takes a node owned by exactly ONE chain within
    ``(weld tol, ONEDGE_SNAP_TOL_M)`` of a foreign edge interior, moves it
    onto the edge and splices it — post-projection, so the receiving way
    gained an ungraded vertex.  The pre-projection pass adopts the donor's
    CANONICAL point into the receiving ring instead, and the emit move and
    splice then stand down by their own two-owner tests.
  * QUANTIZED-RING REPAIR (``conformance.repair_emit_quantized_rings``):
    a ring valid at full precision can self-intersect in the emitted
    frame (canonical coords at 11 dp lat/lon); the emit-time buffer(0)
    repair interned its self-touch vertices fresh, post-projection.  The
    pre-projection twin repairs the same frame so the law graph prices
    the ring that actually ships.

No airport build, no X-Plane install.
"""
from __future__ import annotations

from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.conformance import (
    FINAL_WELD_TOL_M,
    enforce_conformance,
    repair_emit_quantized_rings,
)
from auto_patch.layout import (
    BuiltShape,
    ONEDGE_SNAP_TOL_M,
    PavementLayout,
    ROLE_JUNCTION,
    SHARED_VERTEX_TOL_M,
)


def _make_layout(*shapes: BuiltShape) -> PavementLayout:
    layout = PavementLayout(icao="TEST", anchor=(0.0, 0.0),
                            shapes=list(shapes))
    registry = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    for s in shapes:
        for (x, y) in list(s.polygon.exterior.coords):
            registry.get_or_add(float(x), float(y))
    layout.canonical_points = registry
    return layout


def _receiver_square() -> BuiltShape:
    ring = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_JUNCTION,
                      node_altitudes=[10.0, 10.0, 10.0, 10.0])


def _offedge_donor(perp: float) -> BuiltShape:
    """Donor triangle whose apex sits ``perp`` metres BELOW the
    receiver's bottom edge interior at x=10 — off the edge, so the
    strict T-junction weld can never insert it."""
    ring = [(5.0, -10.0), (15.0, -10.0), (10.0, -float(perp))]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_JUNCTION,
                      node_altitudes=[9.0, 9.0, 9.5])


def _ring_xy(shape) -> list:
    return list(shape.polygon.exterior.coords)


def test_private_offedge_donor_adopted():
    """A PRIVATE donor vertex inside the emit move's snap frame is
    adopted into the receiving ring at its canonical point."""
    recv = _receiver_square()
    donor = _offedge_donor(0.05)          # (weld tol, snap tol)
    layout = _make_layout(recv, donor)
    n_shapes, n_inserts = enforce_conformance(
        layout, tol=FINAL_WELD_TOL_M,
        private_snap_tol=ONEDGE_SNAP_TOL_M)
    assert n_inserts >= 1
    assert any(abs(x - 10.0) < 1e-6 and abs(y + 0.05) < 1e-6
               for (x, y) in _ring_xy(recv)), (
        "receiver ring did not adopt the donor's canonical point — the "
        "emit-time move/splice would mint it post-projection instead")


def test_shared_vertex_not_adopted():
    """A donor vertex carried by TWO shapes is not private — adoption
    must stand down exactly as the emit move does (len(owners) != 1)."""
    recv = _receiver_square()
    donor = _offedge_donor(0.05)
    twin = BuiltShape(
        polygon=Polygon([(10.0, -0.05), (12.0, -3.0), (8.0, -3.0)]),
        role=ROLE_JUNCTION, node_altitudes=[9.5, 9.0, 9.0])
    layout = _make_layout(recv, donor, twin)
    enforce_conformance(layout, tol=FINAL_WELD_TOL_M,
                        private_snap_tol=ONEDGE_SNAP_TOL_M)
    assert not any(abs(x - 10.0) < 1e-6 and abs(y + 0.05) < 1e-6
                   for (x, y) in _ring_xy(recv)), (
        "a SHARED vertex was adopted — the emit move would never touch "
        "it, so adoption minted an insert the emit frame disagrees with")


def test_no_adoption_without_snap_tol():
    """``private_snap_tol=None`` (every pre-existing caller) stays
    byte-identical: an off-edge donor is out of the strict weld's reach."""
    recv = _receiver_square()
    donor = _offedge_donor(0.05)
    layout = _make_layout(recv, donor)
    before = _ring_xy(recv)
    enforce_conformance(layout, tol=FINAL_WELD_TOL_M)
    assert _ring_xy(recv) == before


def test_quantized_ring_repair():
    """A ring valid at full precision but self-intersecting at 11 dp
    lat/lon (two base vertices 0.1 µm apart quantize to ONE point,
    degenerating the spike between them) is repaired pre-projection —
    the spike drops and the quantized image of the repaired ring is
    valid, so the emit-time repair finds nothing to do."""
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0),
            (6.0, 10.0), (5.0, 20.0), (6.0 - 1e-7, 10.0),
            (0.0, 10.0)]
    spike = BuiltShape(polygon=Polygon(ring), role=ROLE_JUNCTION,
                       node_altitudes=[1.0] * 7)
    assert spike.polygon.is_valid          # full precision: lawful input
    layout = _make_layout(spike)
    # Precondition: the EMITTED frame really is invalid.
    q = [tuple(round(v, 11) for v in layout.m_to_ll(x, y))
         for (x, y) in ring]
    assert not Polygon([(lo, la) for la, lo in q]).is_valid
    repaired = repair_emit_quantized_rings(layout)
    assert repaired == 1
    new_ring = list(spike.polygon.exterior.coords)[:-1]
    assert not any(abs(y - 20.0) < 1e-6 for (_x, y) in new_ring), (
        "the degenerate spike survived the repair")
    q2 = [tuple(round(v, 11) for v in layout.m_to_ll(x, y))
          for (x, y) in new_ring]
    assert Polygon([(lo, la) for la, lo in q2]).is_valid
    # node_altitudes carried, aligned to the new ring (+ closing repeat).
    assert spike.node_altitudes is not None
    assert len(spike.node_altitudes) == len(new_ring) + 1
    # Idempotent: a second call finds nothing.
    assert repair_emit_quantized_rings(layout) == 0
