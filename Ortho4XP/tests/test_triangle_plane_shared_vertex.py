"""TRIANGLE-PLANE SHARED-VERTEX SURGERY (debug lane A 2026-08-05).

Owner directive: "prefer a ring-private vertex as the free lever, shared
only as last resort and reported."

THE DEFECT.  ``_project_triangle_planes`` flattens an over-cap triangle by
moving ONE free vertex — chosen purely by smallest move.  But a triangle's
vertices are CANONICAL SOLVER VARIABLES: the same node is often a ring
vertex of neighbouring shapes too, so the cheapest lever is frequently one
that also re-shapes a neighbour's surface.  The plane fix then leaks out
of the triangle it was computed for, and nothing says it happened.

THE LAW.  Rank candidates in two tiers — ring-private first, least move
inside each tier — and when only a shared vertex can lawfully fix the
plane, COUNT it on the layout and say so.

Hermetic: synthetic layout, no X-Plane install, no airport build.
"""
import pytest
from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.layout import (
    BuiltShape, ROLE_JUNCTION, ROLE_BOUNDARY)
from auto_patch.elevation_per_surface.route_profile.solve import (
    _project_triangle_planes)


class _Layout:
    def __init__(self, shapes, cps):
        self.shapes = shapes
        self.canonical_points = cps


def _tri(a, b, c, role=ROLE_JUNCTION):
    return BuiltShape(polygon=Polygon([a, b, c]), role=role)


def _build(extra_shapes=()):
    """One over-cap triangle plus whatever else shares its vertices.

    Triangle A(0,0)=0, B(30,0)=0.6, C(0,30)=0 — a pure 2 % gradient down
    the x leg, over the 1.5 % junction cap.  EVERY vertex can lawfully
    fix it, and their moves differ:

      * B is the CHEAPEST lever (0.60 -> 0.45, a 0.15 m move);
      * A (or C) needs 0.30 m.

    So a least-move-only chooser picks B.  The neighbour below shares B
    and C, leaving A ring-private — which makes "prefer private" and
    "prefer cheapest" pick DIFFERENT vertices.  That separation is the
    whole point of the fixture.
    """
    cps = CanonicalPointRegistry()
    ring = [(0.0, 0.0), (30.0, 0.0), (0.0, 30.0)]
    shapes = [_tri(*ring)] + list(extra_shapes)
    layout = _Layout(shapes, cps)
    # node list in ring order, then any extra vertices
    bucket_to_idx = {}
    nodes = []
    for s in shapes:
        rr = list(s.polygon.exterior.coords)
        if rr and rr[0] == rr[-1]:
            rr = rr[:-1]
        for (x, y) in rr:
            k = cps.get_or_add(float(x), float(y))
            if k not in bucket_to_idx:
                bucket_to_idx[k] = len(nodes)
                nodes.append(k)
    n = len(nodes)
    elev = [0.0] * n
    elev[bucket_to_idx[cps.get_or_add(30.0, 0.0)]] = 0.6
    return layout, bucket_to_idx, elev, n


def _idx(layout, bucket_to_idx, x, y):
    return bucket_to_idx[layout.canonical_points.get_or_add(x, y)]


def test_the_plane_is_flattened_at_all():
    """Baseline: the pass still does its job (a twin that only checked
    WHICH vertex moved would pass for a no-op)."""
    layout, b2i, elev, n = _build()
    before = list(elev)
    n_fixed, anchored, broken = _project_triangle_planes(
        layout, b2i, elev, immovable=set(), joint={}, n=n)
    assert n_fixed == 1
    assert not broken
    assert elev != before, "the over-cap plane was not touched"


def test_a_ring_private_lever_is_preferred_over_a_cheaper_shared_one():
    """THE LAW.  The neighbour shares (30,0) and (0,30), leaving (0,0)
    ring-private.  (30,0) is the CHEAPEST lawful lever (0.15 m) and
    (0,0) costs 0.30 m, so a least-move-only chooser takes the shared
    one and drags the neighbour with it.  Ring-private must win
    anyway."""
    # ROLE_BOUNDARY carries no grade cap, so the neighbour is invisible
    # to the plane law itself and can only influence the fix through the
    # VERTICES it shares — which is exactly the effect under test.
    neighbour = _tri((30.0, 0.0), (0.0, 30.0), (40.0, 40.0),
                     role=ROLE_BOUNDARY)
    layout, b2i, elev, n = _build([neighbour])
    i_private = _idx(layout, b2i, 0.0, 0.0)
    shared = [_idx(layout, b2i, 30.0, 0.0), _idx(layout, b2i, 0.0, 30.0)]
    before = list(elev)

    n_fixed, _anchored, broken = _project_triangle_planes(
        layout, b2i, elev, immovable=set(), joint={}, n=n)

    assert n_fixed == 1 and not broken
    moved = [i for i in range(n) if abs(elev[i] - before[i]) > 1e-12]
    assert moved == [i_private], (
        f"expected the ring-private vertex {i_private} to be the lever; "
        f"moved {moved} (shared vertices are {shared})")
    assert layout._triangle_plane_shared_surgery == 0


def test_a_shared_vertex_is_the_last_resort_and_is_reported():
    """When the ring-private vertex is IMMOVABLE, the fix still has to
    happen — but the shared move is counted, not silent.  Reporting is
    the whole difference between a known trade and an invisible one."""
    # ROLE_BOUNDARY carries no grade cap, so the neighbour is invisible
    # to the plane law itself and can only influence the fix through the
    # VERTICES it shares — which is exactly the effect under test.
    neighbour = _tri((30.0, 0.0), (0.0, 30.0), (40.0, 40.0),
                     role=ROLE_BOUNDARY)
    layout, b2i, elev, n = _build([neighbour])
    i_private = _idx(layout, b2i, 0.0, 0.0)
    before = list(elev)

    n_fixed, _anchored, broken = _project_triangle_planes(
        layout, b2i, elev, immovable={i_private}, joint={}, n=n)

    assert n_fixed == 1 and not broken
    moved = [i for i in range(n) if abs(elev[i] - before[i]) > 1e-12]
    assert moved and i_private not in moved
    assert layout._triangle_plane_shared_surgery == 1, (
        "a shared-vertex plane fix must be COUNTED — the owner's "
        "'shared only as last resort AND REPORTED'")


def test_an_all_private_triangle_reports_no_shared_surgery():
    """The falsifier: with no neighbour at all, every vertex is private
    and the counter must stay 0.  Without this the counter could be
    'always 1' and the previous twin would still pass."""
    layout, b2i, elev, n = _build()
    _project_triangle_planes(layout, b2i, elev,
                            immovable=set(), joint={}, n=n)
    assert layout._triangle_plane_shared_surgery == 0


def test_ownership_is_read_without_interning():
    """The ownership scan must use the registry's READ-ONLY ``get``: an
    instrument that interns changes which LATER vertices snap together
    and moves the emitted surface (round 6: SPJC +1 node, 86 altitudes).
    Asserted by count: the scan may not grow the registry."""
    # ROLE_BOUNDARY carries no grade cap, so the neighbour is invisible
    # to the plane law itself and can only influence the fix through the
    # VERTICES it shares — which is exactly the effect under test.
    neighbour = _tri((30.0, 0.0), (0.0, 30.0), (40.0, 40.0),
                     role=ROLE_BOUNDARY)
    layout, b2i, elev, n = _build([neighbour])
    cps = layout.canonical_points
    before = cps.size
    _project_triangle_planes(layout, b2i, elev,
                            immovable=set(), joint={}, n=n)
    after = cps.size
    assert after == before, (
        "the ownership scan interned new canonical points — it must use "
        "CanonicalPointRegistry.get, never get_or_add")


def test_a_triangle_with_no_free_vertex_is_still_broken_not_shared():
    """Every vertex immovable ⇒ broken, and NOT counted as shared
    surgery (nothing moved)."""
    layout, b2i, elev, n = _build()
    all_idx = {_idx(layout, b2i, *p)
               for p in ((0.0, 0.0), (30.0, 0.0), (0.0, 30.0))}
    n_fixed, _a, broken = _project_triangle_planes(
        layout, b2i, elev, immovable=all_idx, joint={}, n=n)
    assert n_fixed == 0
    assert broken == all_idx
    assert layout._triangle_plane_shared_surgery == 0
