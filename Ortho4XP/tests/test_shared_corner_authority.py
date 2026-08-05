"""Twins for the SHARED-CORNER AUTHORITY law
(``auto_patch.emit_snap.shared_corner_authority_nodes``).

THE DEFECT — SPJC node 10625 (``spjc16/``).  A FREE node (``hard_cat``
None) at the corner of apron 551 + junction 444 + junction 568.  Between
two arms its value in SOLVE SPACE — the input to
``final_grade_projection`` — moved **+0.078 m** (22.101 -> 22.179), while
its EMITTED value moved **+0.310 m** (22.490 -> 22.800): a **4.0x**
amplification at that ONE node, its 12 m neighbours emitting +0.04..+0.11.
It minted a **50.67 %** grade row, rank 1 in the whole airport against a
both-off worst of 13.0 %, and 10 of that arm's 28 new census rows trace to
it alone (+16 -> +7 with the single vertex neutralised).

THE MECHANISM.  ``_fair_ring_edges`` builds its triples PER RING.  A node
on three rings is the CENTRE of up to three different triples, with
different flanks and a length-scaled lever, all mutating one shared slot in
sequence — while any owner that reads the same vertex as a CORNER treats it
as a real grade break and refuses to move it.  One population, three
authorities.

THE LAW.  A vertex owned by 2+ rings that ANY owner sees as a corner keeps
the value the GLOBAL projection converged to.  It joins the pass's ANCHOR
set, never ``skip_nodes`` — readable as a flank, not writable — which is
the same discipline a weld-shared vertex follows.

Hermetic: shapely polygons + the real canonical registry, no build.
"""
import math

import pytest
from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.emit_snap import (SHARED_CORNER_MAX_BEND_DEG,
                                  shared_corner_authority_nodes)
from auto_patch.layout import (BuiltShape, ROLE_APRON, ROLE_BUILDING,
                               ROLE_JUNCTION)


class _FakeLayout:
    def __init__(self, shapes):
        self.shapes = shapes
        self.canonical_points = CanonicalPointRegistry()


def _shape(ring, role, ref=""):
    return BuiltShape(polygon=Polygon(ring), role=role, ref=ref)


def _register(layout):
    """Intern every ring vertex; hand back ``bucket_to_idx`` and a
    ``(x, y) -> node index`` lookup for the assertions."""
    cps = layout.canonical_points
    b2i, at, idx = {}, {}, 0
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            k = cps.get_or_add(float(x), float(y))
            if k not in b2i:
                b2i[k] = idx
                idx += 1
            at[(round(x, 6), round(y, 6))] = b2i[k]
    return b2i, at


def _spjc_corner_layout():
    """SPJC node 10625 in miniature: ONE vertex where three shapes meet.

    The shared vertex is ``(50, 50)``.  It is a straight-through point on
    the apron's south edge — the owner that would happily fair it — and a
    right-angle CORNER on both junctions, which is what makes fairing it an
    authority it does not have.
    """
    apron = _shape([(0.0, 50.0), (50.0, 50.0), (100.0, 50.0),
                    (100.0, 0.0), (0.0, 0.0)], ROLE_APRON, "apron551")
    j444 = _shape([(0.0, 50.0), (50.0, 50.0), (50.0, 100.0),
                   (0.0, 100.0)], ROLE_JUNCTION, "junction444")
    j568 = _shape([(50.0, 50.0), (100.0, 50.0), (100.0, 100.0),
                   (50.0, 100.0)], ROLE_JUNCTION, "junction568")
    return _FakeLayout([apron, j444, j568])


def test_the_free_triple_shape_corner_is_claimed_by_the_law():
    layout = _spjc_corner_layout()
    b2i, at = _register(layout)
    got = shared_corner_authority_nodes(layout, b2i)
    assert at[(50.0, 50.0)] in got, (
        "a vertex on three rings that two of them read as a corner is not "
        "any single ring's variable")


def test_a_shared_vertex_every_owner_reads_as_straight_is_left_alone():
    """The falsifier.  Where no owner sees a break there is no
    disagreement, so a ring-local pass may still fair the node — a law
    that claimed every shared vertex would silence the whole pass."""
    a = _shape([(0.0, 0.0), (50.0, 0.0), (100.0, 0.0), (100.0, -40.0),
                (0.0, -40.0)], ROLE_APRON, "a")
    b = _shape([(0.0, 0.0), (50.0, 0.0), (100.0, 0.0), (100.0, 40.0),
                (0.0, 40.0)], ROLE_APRON, "b")
    layout = _FakeLayout([a, b])
    b2i, at = _register(layout)
    got = shared_corner_authority_nodes(layout, b2i)
    assert at[(50.0, 0.0)] not in got
    # the two ring END vertices ARE corners on both rings, so they are
    # claimed — which is correct and is not what this twin is about.
    assert at[(0.0, 0.0)] in got and at[(100.0, 0.0)] in got


def test_a_corner_owned_by_one_ring_only_is_that_rings_own_variable():
    """Single ownership means no second authority: an isolated pad's own
    corners stay fully available to its ring-local passes."""
    pad = _shape([(200.0, 200.0), (220.0, 200.0), (220.0, 220.0),
                  (200.0, 220.0)], ROLE_BUILDING, "padLonely")
    layout = _FakeLayout([pad])
    b2i, at = _register(layout)
    assert shared_corner_authority_nodes(layout, b2i) == set()
    assert at[(200.0, 200.0)] not in shared_corner_authority_nodes(layout, b2i)


def test_one_owner_seeing_a_corner_is_enough():
    """ANY owner, not EVERY owner.  The apron reads ``(50, 50)`` as a
    straight run and would fair it; junction444 reads it as a 90-degree
    break.  One dissent decides."""
    layout = _spjc_corner_layout()
    b2i, at = _register(layout)
    claimed = shared_corner_authority_nodes(layout, b2i)
    # remove the two junctions: with only the apron left, the vertex is
    # single-owned AND straight, and nothing is claimed there.
    apron_only = _FakeLayout([layout.shapes[0]])
    b2i2, at2 = _register(apron_only)
    assert at2[(50.0, 50.0)] not in shared_corner_authority_nodes(
        apron_only, b2i2)
    assert at[(50.0, 50.0)] in claimed


def test_the_bend_threshold_is_the_fairing_passs_own():
    """One number, one meaning.  A second threshold here would be a second
    instrument over one population."""
    assert SHARED_CORNER_MAX_BEND_DEG == pytest.approx(25.0)
    # a bend just inside the threshold is NOT a corner
    eps = math.radians(SHARED_CORNER_MAX_BEND_DEG - 2.0)
    dx, dy = 50.0 * math.cos(eps), 50.0 * math.sin(eps)
    a = _shape([(0.0, 0.0), (50.0, 0.0), (50.0 + dx, dy), (50.0, -40.0),
                (0.0, -40.0)], ROLE_APRON, "a")
    b = _shape([(0.0, 0.0), (50.0, 0.0), (50.0 + dx, dy), (50.0 + dx, 60.0),
                (0.0, 60.0)], ROLE_APRON, "b")
    layout = _FakeLayout([a, b])
    b2i, at = _register(layout)
    assert at[(50.0, 0.0)] not in shared_corner_authority_nodes(layout, b2i)
    # and just outside it IS
    big = math.radians(SHARED_CORNER_MAX_BEND_DEG + 20.0)
    dx2, dy2 = 50.0 * math.cos(big), 50.0 * math.sin(big)
    a2 = _shape([(0.0, 0.0), (50.0, 0.0), (50.0 + dx2, dy2), (50.0, -40.0),
                 (0.0, -40.0)], ROLE_APRON, "a2")
    b2 = _shape([(0.0, 0.0), (50.0, 0.0), (50.0 + dx2, dy2),
                 (50.0 + dx2, 90.0), (0.0, 90.0)], ROLE_APRON, "b2")
    layout2 = _FakeLayout([a2, b2])
    b2i_2, at_2 = _register(layout2)
    assert at_2[(50.0, 0.0)] in shared_corner_authority_nodes(layout2, b2i_2)


def test_ownership_counts_every_role_including_buildings():
    """A junction that shares a vertex with a BUILDING ring is exactly the
    cross-authority case.  Restricting ownership to the roles a given pass
    happens to skip would make the answer pass-specific."""
    j = _shape([(0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0)],
               ROLE_JUNCTION, "j1")
    pad = _shape([(40.0, 20.0), (80.0, 20.0), (80.0, 60.0), (40.0, 60.0)],
                 ROLE_BUILDING, "pad1")
    layout = _FakeLayout([j, pad])
    b2i, at = _register(layout)
    assert at[(40.0, 20.0)] in shared_corner_authority_nodes(layout, b2i)


def test_the_query_never_interns_a_new_canonical_point():
    """``canonical_points.get``, never ``get_or_add``: interning a point
    changes which LATER points intern together and would move the emitted
    surface.  This is a measurement."""
    layout = _spjc_corner_layout()
    b2i, _at = _register(layout)
    before = layout.canonical_points.size
    shared_corner_authority_nodes(layout, b2i)
    assert layout.canonical_points.size == before


def test_a_node_outside_the_solve_index_map_is_simply_absent():
    """The set is returned in the CALLER's index space; a ring vertex the
    solve never registered contributes nothing and never raises."""
    layout = _spjc_corner_layout()
    b2i, at = _register(layout)
    victim = at[(50.0, 50.0)]
    trimmed = {k: v for k, v in b2i.items() if v != victim}
    assert victim not in shared_corner_authority_nodes(layout, trimmed)


def test_an_empty_layout_and_a_missing_registry_are_both_empty_sets():
    assert shared_corner_authority_nodes(_FakeLayout([]), {}) == set()

    class _NoRegistry:
        shapes = []
    assert shared_corner_authority_nodes(_NoRegistry(), {"k": 0}) == set()


def test_the_scan_is_cached_per_geometry_state():
    """``final_grade_projection`` runs twice; the ownership relation is a
    pure function of the ring geometry plus the registry, so the second
    call must not re-scan."""
    layout = _spjc_corner_layout()
    b2i, _at = _register(layout)
    first = shared_corner_authority_nodes(layout, b2i)
    assert getattr(layout, "_shared_corner_authority_cache", None) is not None
    # poison the shapes: a cached answer is returned unchanged
    stamp = layout._shared_corner_authority_cache[0]
    layout._shared_corner_authority_cache = (stamp, frozenset({-99}))
    assert shared_corner_authority_nodes(layout, b2i) == {-99}


def test_the_cache_invalidates_when_the_geometry_changes():
    """The LATE projection sees appended shapes — a stale answer there
    would silently anchor the wrong nodes."""
    layout = _spjc_corner_layout()
    b2i, _at = _register(layout)
    shared_corner_authority_nodes(layout, b2i)
    stamp = layout._shared_corner_authority_cache[0]
    layout._shared_corner_authority_cache = (stamp, frozenset({-99}))
    layout.shapes = list(layout.shapes) + [
        _shape([(300.0, 300.0), (320.0, 300.0), (320.0, 320.0),
                (300.0, 320.0)], ROLE_APRON, "late")]
    assert shared_corner_authority_nodes(layout, b2i) != {-99}
