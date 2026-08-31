"""THE TUNNEL OPEN-CUT EXCLUSION from the unified node book.

Spec: ``docs/specs/tunnel-corridor-node-book-exclusion-spec.md``
(owner-ordered fix, 2026-08-25), RE-KEYED by
``docs/specs/linear-transport-redesign-spec.md`` §5.2 and census row #51
under RULINGS 2026-08-31b.  Owner law it rests on: the 2026-08-30
canonical tunnel mouth and 2026-08-07's tunnel-portal fidelity rulings.

WHAT WENT WRONG, and why the fix is SCOPE not REVERT.  ``cce9da6f`` put
``service_road`` + ``service_junction`` into ``_CHORD_LIMIT_ROLES``, so
the road family shares ONE node key space with ``groundside_pavement``
in the finalize-stage Lipschitz clamp — and at a weld the road's value
wins (authority precedence).  At OTHH's site-1 bore the descending
tunnel FLOOR is a ``groundside_pavement`` ring: it gained 17 shared
nodes across six road rings, took the surrounding at-grade bench values
(+2.28/+2.96 against a −1.1 m floor — a 3.3 m mid-ramp step), and 9 of
the bore's 10 ``authority_retreat_wall`` faces stopped being emitted.
The limiter joined the roles for a reason, so the exemption axis moves
from ROLE (``tunnel_ramp``, which this bore's floor is not) to
AUTHORITY: a ring inside the portal walk's OWN OPEN CUT belongs to the
portal walk, whatever its role.

WHAT THE RE-KEY CHANGED.  The region used to be R14-1's CLAIM SET
(``layout.tunnel_open_cut_claim_polys`` — the road surfaces the claim
re-profiled).  That class is RETIRED; the region is now
``layout.tunnel_open_cut_polys``, the portal walk's own plan-space
extent, published by ``bridges.publish_tunnel_open_cut_regions``.  The
two regions are measured different, so the MEMBERSHIP TEST moved with
the region — see :class:`TestSeamProbe4NodeOnlyMembershipWouldEvaporate`,
which is this file's record of seam probe 4.

WHAT §5-SUPPLEMENT ITEM 3 THEN NARROWED, and this is the current law.
Keyed on GEOMETRY ALONE the clause fired wherever a cut was published
and swept in at-grade ground that carries no bore depth at all: at LEMD
— whose tunnel population, decks and basin are byte-identical between
the Batch-3 arm and merged main — it moved 467 solve-owned airside
nodes, worst 0.23 m.  The ``O4_TUNNEL_CORRIDOR_NODE_BOOK_EXCLUSION=0``
arm then reproduced merged main's LEMD patch BYTE FOR BYTE
(``body_sha 2bc2bd88f961``), naming this clause the sole author.
Membership is now BELOW-GRADE ROLE **and** (node-in-cut OR ≥ 2 m²
in-cut).

AND THE CONSEQUENCE, WHICH THIS FILE MEASURES RATHER THAN ASSUMES: with
R14-1's claim retired, no ring carrying a PAVEMENT role carries bore
depth any more, so ``_OPEN_CUT_BELOW_GRADE_ROLES`` and
``_CHORD_LIMIT_ROLES`` are DISJOINT and the exclusion is inert inside
the pass.  The original defect — a bore FLOOR shipping as
``groundside_pavement`` — cannot arise, because the claim that made a
groundside ring carry a bore profile is gone.  That is a zero to
measure, not a law to keep: see
:class:`TestTheExclusionIsNowInertAndMeasuredSo`.

The twins:

(a) the PREDICATE: a below-grade-roled ring meeting the cut is a member;
    a groundside/road ring meeting the same cut is NOT (the spillover
    item 3 removed);
(b) a road ring OUTSIDE any cut still takes the limiter's precedence
    (the ``cce9da6f`` purpose, unregressed);
(c) the exclusion is INERT in the pass, and the count says so;
(d) flag off → the pre-fix result, exactly;
(e) SEAM PROBE 4 — the membership test itself.
"""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Polygon

from auto_patch import config as cfg
from auto_patch import groundside as gs
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.layout import (BuiltShape, PavementLayout,
                               ROLE_GROUNDSIDE_PAVEMENT,
                               ROLE_SERVICE_JUNCTION, ROLE_TUNNEL_RAMP,
                               SHARED_VERTEX_TOL_M)

FLAG = "O4_TUNNEL_CORRIDOR_NODE_BOOK_EXCLUSION"

#: The bore floor's own solved value — the OTHH site-1 number.
FLOOR_Z = -1.1
#: The surrounding road's at-grade bench — the value that captured it.
BENCH_Z = 2.3


# ═════════════════════════════════════════════════════════════════════
# helpers — synthetic, headless, no DEM, no X-Plane install
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _shape(poly, role, z):
    return BuiltShape(polygon=poly, role=role,
                      node_altitudes=[z] * len(poly.exterior.coords))


def _layout(shapes, cut_polys=None):
    """A minimal layout carrying the PUBLISHED open cut.

    ``tunnel_open_cut_polys`` is exactly what
    ``bridges.publish_tunnel_open_cut_regions`` writes — the portal
    walk's own plan-space extent.  Nothing here re-derives a cut zone; a
    second geometric notion of "inside the cut" is what the spec
    forbids.
    """
    lay = types.SimpleNamespace(shapes=list(shapes), anchor=(0.0, 0.0))
    if cut_polys:
        lay.tunnel_open_cut_polys = list(cut_polys)
    return lay


def _alts(shape):
    return [round(float(a), 2) for a in shape.node_altitudes]


def _bore_scene(cut=True):
    """The site-1 shape of the defect, at unit scale.

    ``floor`` is the bore's descending floor — a ``groundside_pavement``
    ring at −1.1 m.  ``road`` is the at-grade ``service_junction`` beside
    it, sharing the two vertices on their common edge (the weld the node
    book unified).  The portal walk's OPEN CUT covers the floor, so the
    published region is the floor's own footprint.
    """
    floor = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT, FLOOR_Z)
    road = _shape(_rect(40, 0, 60, 10), ROLE_SERVICE_JUNCTION, BENCH_Z)
    lay = _layout([floor, road],
                  cut_polys=[floor.polygon] if cut else None)
    return lay, floor, road


# ═════════════════════════════════════════════════════════════════════
# (a) the exclusion itself
# ═════════════════════════════════════════════════════════════════════

class TestTheMembershipPredicate:
    """§5-SUPPLEMENT item 3 — BELOW-GRADE ROLE **and** geometry."""

    def _cut(self):
        lay = _layout([], cut_polys=[_rect(0, 0, 40, 10)])
        member, bounds = gs._tunnel_open_cut_region(lay)
        assert member is not None
        return member, bounds

    def test_a_below_grade_roled_ring_in_the_cut_is_a_member(self):
        """The exclusion's whole purpose: bore-depth values must not
        travel outward through a shared key."""
        member, bounds = self._cut()
        body = _rect(0, 0, 40, 10)
        ring = list(body.exterior.coords)[:-1]
        for role in gs._OPEN_CUT_BELOW_GRADE_ROLES:
            assert gs._ring_touches_open_cut(
                ring, body, member, bounds, role), role

    def test_a_groundside_ring_in_the_SAME_cut_is_NOT_a_member(self):
        """The spillover item 3 removed.  Geometry alone made this ring
        a member; it carries no bore depth, so sweeping it in moved
        at-grade airside for nothing (467 nodes at LEMD)."""
        member, bounds = self._cut()
        body = _rect(0, 0, 40, 10)
        ring = list(body.exterior.coords)[:-1]
        assert not gs._ring_touches_open_cut(
            ring, body, member, bounds, ROLE_GROUNDSIDE_PAVEMENT)
        assert not gs._ring_touches_open_cut(
            ring, body, member, bounds, ROLE_SERVICE_JUNCTION)

    def test_a_below_grade_ring_OUTSIDE_the_cut_is_not_a_member(self):
        """The role clause admits; it does not replace the geometry."""
        member, bounds = self._cut()
        away = _rect(500, 0, 540, 10)
        ring = list(away.exterior.coords)[:-1]
        assert not gs._ring_touches_open_cut(
            ring, away, member, bounds, ROLE_TUNNEL_RAMP)

    def test_the_role_clause_comes_first(self):
        """A role that is not below grade short-circuits before any
        geometry is touched — the clause order IS the fix."""
        member, bounds = self._cut()
        body = _rect(0, 0, 40, 10)
        ring = list(body.exterior.coords)[:-1]
        assert gs._ring_touches_open_cut(
            ring, body, member, bounds, "") is False

    def test_no_cut_means_no_region_at_all(self):
        """No second notion of "inside the cut": with nothing published
        by the portal walk there is no region to ask about."""
        lay = _layout([], cut_polys=None)
        assert gs._tunnel_open_cut_region(lay) == (None, None)


# ═════════════════════════════════════════════════════════════════════
# (b) the road chord limiter's own purpose, unregressed
# ═════════════════════════════════════════════════════════════════════

class TestARoadOutsideAnyCutKeepsTheLimiter:
    """Spec §4 — "the limiter keeps its full role set everywhere else"."""

    def _scene(self):
        """A road/lot weld 500 m from the bore, and an open cut that
        covers only the bore."""
        bore = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT, FLOOR_Z)
        road = BuiltShape(polygon=_rect(500, 0, 540, 20),
                          role=ROLE_SERVICE_JUNCTION,
                          node_altitudes=[10.0, 14.0, 14.0, 10.0, 10.0])
        lot = _shape(_rect(500, 20, 540, 60), ROLE_GROUNDSIDE_PAVEMENT, 10.0)
        return _layout([bore, road, lot],
                       cut_polys=[bore.polygon]), bore, road, lot

    def test_the_far_road_is_still_clamped(self, monkeypatch):
        """A road ring over its own cap is still pulled inside it — the
        exclusion is scoped to the cut, never to the family."""
        monkeypatch.setenv(FLAG, "1")
        lay, bore, road, lot = self._scene()
        n = gs._grade_limit_groundside_chords(lay)
        assert n >= 1
        after = _alts(road)
        assert after[1] < 14.0, "the over-cap road vertex was not CUT"
        cap = cfg.ROLE_GRADE_LIMITS[ROLE_SERVICE_JUNCTION]
        worst = max(abs(after[i] - after[j])
                    / max(1e-9, _dist(road, i, j))
                    for i in range(4) for j in range(i + 1, 4))
        assert worst <= cap + 5e-3

    def test_the_road_still_wins_the_weld(self, monkeypatch):
        """Authority precedence across roles — the ``cce9da6f`` rule the
        node book exists for — is untouched outside the cut."""
        monkeypatch.setenv(FLAG, "1")
        lay, bore, road, lot = self._scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["shared_road_lot_nodes"] == 2, (
            "the road↔lot weld left the unified book")
        # …and NOTHING is excluded: the scene's bore ring wears a
        # pavement role, which §5-SUPPLEMENT item 3 no longer sweeps in.
        assert stats["tunnel_corridor_excluded_rings"] == 0
        # one value per shared node, both rings
        shared = {}
        for shape in (road, lot):
            ring = list(shape.polygon.exterior.coords)[:-1]
            for (x, y), v in zip(ring, _alts(shape)):
                k = (round(x, 2), round(y, 2))
                if k in shared:
                    assert shared[k] == pytest.approx(v, abs=1e-9)
                shared[k] = v


def _dist(shape, i, j):
    ring = list(shape.polygon.exterior.coords)
    ax, ay = ring[i]
    bx, by = ring[j]
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


# ═════════════════════════════════════════════════════════════════════
# (c) the exclusion is INERT in the pass — measured, not assumed
# ═════════════════════════════════════════════════════════════════════

class TestTheExclusionIsNowInertAndMeasuredSo:
    """The §6 Batch-4 "dormant passes measured zero-fire then deleted"
    path, entered honestly.

    The exclusion protected a ring that carried BORE DEPTH while wearing
    a PAVEMENT role — which only R14-1's claim could produce.  With the
    claim retired the two role sets are disjoint, so the pass can no
    longer fire.  The retreat-wall twin that used to live here rested on
    exactly that scene (a ``groundside_pavement`` bore floor) and is
    removed with it rather than rewritten around a shape the emitter
    cannot make.
    """

    def test_the_two_role_sets_are_disjoint(self):
        assert set(gs._OPEN_CUT_BELOW_GRADE_ROLES).isdisjoint(
            gs._CHORD_LIMIT_ROLES), (
            "a below-grade role entering the chord limiter's own role "
            "set would make this exclusion live again — and would need "
            "its own measurement before it did")

    def test_a_bore_beside_a_road_now_excludes_NOTHING(self, monkeypatch):
        """The original site-1 scene, replayed: the count is zero and
        the limiter simply does its job on both rings."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene(cut=True)
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["tunnel_corridor_excluded_rings"] == 0
        assert stats["tunnel_corridor_excluded_by_role"] == {}

    def test_and_the_pass_is_byte_equal_with_the_flag_OFF(
            self, monkeypatch):
        """Inert means inert: ON and OFF must produce the same values.
        This is the LEMD byte-identity result in the small."""
        monkeypatch.setenv(FLAG, "1")
        lay_on, floor_on, _r = _bore_scene(cut=True)
        gs._grade_limit_groundside_chords(lay_on)
        monkeypatch.setenv(FLAG, "0")
        lay_off, floor_off, _r2 = _bore_scene(cut=True)
        gs._grade_limit_groundside_chords(lay_off)
        assert _alts(floor_on) == _alts(floor_off)


# ═════════════════════════════════════════════════════════════════════
# (d) the kill switch
# ═════════════════════════════════════════════════════════════════════

class TestTheFlagOffIsTodaysBehaviour:
    """Spec §5 — OFF is the pre-fix pass, bit for bit, for attribution
    arms."""

    def test_off_equals_a_layout_with_no_cut_published(self, monkeypatch):
        """The only thing the fix adds to the pass is the cut read; with
        the flag off, a layout CARRYING a cut and one carrying none must
        produce the same altitudes, the same return value and the same
        census."""
        monkeypatch.setenv(FLAG, "0")
        with_cut, floor_a, road_a = _bore_scene(cut=True)
        without, floor_b, road_b = _bore_scene(cut=False)
        n_a = gs._grade_limit_groundside_chords(with_cut)
        n_b = gs._grade_limit_groundside_chords(without)
        assert n_a == n_b
        assert _alts(floor_a) == _alts(floor_b)
        assert _alts(road_a) == _alts(road_b)
        assert (with_cut._chord_limit_stats
                == without._chord_limit_stats)
        assert (with_cut._chord_limit_stats[
            "tunnel_corridor_excluded_rings"] == 0)

    def test_the_flag_defaults_ON(self, monkeypatch):
        """Default ON (spec §5): the production build carries the fix.

        What "the fix" DOES is now the narrowed membership, so the
        default is asserted where it is still observable — the predicate
        answers, and the region is read — rather than through a pass the
        role clause has made inert.  The pass-level default is covered
        by the ON/OFF byte-equality twin above.
        """
        monkeypatch.delenv(FLAG, raising=False)
        lay = _layout([], cut_polys=[_rect(0, 0, 40, 10)])
        member, bounds = gs._tunnel_open_cut_region(lay)
        assert member is not None, (
            "the flag defaults OFF — the production build would not "
            "read the published cut at all")
        body = _rect(0, 0, 40, 10)
        ring = list(body.exterior.coords)[:-1]
        assert gs._ring_touches_open_cut(
            ring, body, member, bounds, ROLE_TUNNEL_RAMP)

    def test_the_flag_off_publishes_no_region(self, monkeypatch):
        monkeypatch.setenv(FLAG, "0")
        lay = _layout([], cut_polys=[_rect(0, 0, 40, 10)])
        assert gs._tunnel_open_cut_region(lay) == (None, None)


# ═════════════════════════════════════════════════════════════════════
# (e) SEAM PROBE 4 — the membership test moved with the region
# ═════════════════════════════════════════════════════════════════════

class TestSeamProbe4NodeOnlyMembershipWouldEvaporate:
    """THE RECORD OF SEAM PROBE 4 (census #51, redesign spec §5.2).

    Census row #51 named the failure mode by name: re-key the exclusion
    from R14-1's claim set to ``tunnel_open_cut_polys`` and *"otherwise
    the exclusion evaporates and bench values travel across the cut
    boundary again"*.  The old region WAS the claimed shapes' own
    polygons, so "any node inside" picked out exactly the claimed rings.
    The cut is a different region and node membership does not translate.

    MEASURED (lane/tunnelfix, OTHH): **the cut covers ZERO of the bore
    ring's 34 nodes where the claim covered 2** — a straight node-only
    re-key would have excluded nothing at all.

    The geometry class in one sentence: a NARROW corridor crossing a
    BROAD ring leaves every one of that ring's perimeter nodes outside
    the cut while the cut runs right through its body.  So membership is
    the claim's own membership expressed against the cut — a node inside,
    OR at least ``_OPEN_CUT_MIN_OVERLAP_M2`` (2.0 m², R14-1's own
    "cover the alignment, do not graze it" floor) of the ring's area
    inside.
    """

    #: An 8 m corridor — the OTHH carriageway width class — crossing the
    #: whole scene in y.
    CUT = staticmethod(lambda: _rect(40, -10, 48, 60))

    #: the geometry clause is what these twins measure, so they hand the
    #: predicate a BELOW-GRADE role and vary only the geometry; the role
    #: clause has its own class above.
    ROLE = ROLE_TUNNEL_RAMP

    def _member(self, cut_poly):
        lay = _layout([], cut_polys=[cut_poly])
        member, bounds = gs._tunnel_open_cut_region(lay)
        assert member is not None and bounds is not None
        return member, bounds

    @staticmethod
    def _nodes_inside(ring, member):
        """Node-only membership, computed HERE rather than asked of the
        module — so the twin proves what the retired rule would have
        done, not what the live rule does."""
        prepared, _body = member
        from shapely.geometry import Point
        return sum(1 for (x, y) in ring if prepared.covers(Point(x, y)))

    def test_the_crossed_lot_has_no_node_in_the_cut(self):
        """The measurement, reproduced: 0 of the ring's nodes are inside
        — node-only membership would NOT exclude this ring."""
        lot = _rect(0, 0, 100, 50)
        ring = list(lot.exterior.coords)[:-1]
        member, _bounds = self._member(self.CUT())
        assert self._nodes_inside(ring, member) == 0, (
            "the fixture no longer encodes the measured class — the "
            "point of the twin is that EVERY perimeter node is outside")

    def test_the_area_clause_excludes_the_crossed_lot_anyway(self):
        """…and the live rule DOES exclude it: 8 m × 50 m of the lot's
        body is the cut's ground."""
        lot = _rect(0, 0, 100, 50)
        ring = list(lot.exterior.coords)[:-1]
        member, bounds = self._member(self.CUT())
        assert gs._ring_touches_open_cut(ring, lot, member, bounds, self.ROLE), (
            "the crossed lot is not a member — the exclusion evaporated, "
            "which is the failure census #51 names")

    def test_a_ring_merely_GRAZING_the_cut_is_not_excluded(self):
        """The other side of the floor.  A 0.2 m-deep sliver crossing the
        same 8 m corridor overlaps 1.6 m² — under the 2.0 m² bar — and
        its nodes are outside too, so it stays in the node book.  Without
        this clause the exclusion would swallow every ring the cut so
        much as brushes."""
        graze = _rect(0, 0.0, 100, 0.2)
        ring = list(graze.exterior.coords)[:-1]
        member, bounds = self._member(self.CUT())
        overlap = graze.intersection(self.CUT()).area
        assert overlap == pytest.approx(1.6, abs=1e-6)
        assert overlap < gs._OPEN_CUT_MIN_OVERLAP_M2
        assert self._nodes_inside(ring, member) == 0
        assert not gs._ring_touches_open_cut(ring, graze, member, bounds, self.ROLE)

    def test_the_floor_is_r14_1s_own_claim_floor(self):
        """The bar is CARRIED OVER, not invented here: R14-1 required a
        shape to COVER the alignment (2.0 m²), not graze it."""
        assert gs._OPEN_CUT_MIN_OVERLAP_M2 == pytest.approx(2.0)

    def test_a_ring_with_a_node_inside_is_still_a_member(self):
        """The weld case is unchanged — ``covers``, so a shared vertex
        sitting exactly ON the cut boundary counts."""
        welded = _rect(48, 0, 148, 50)          # touches the cut's edge
        ring = list(welded.exterior.coords)[:-1]
        member, bounds = self._member(self.CUT())
        assert self._nodes_inside(ring, member) == 2
        assert welded.intersection(self.CUT()).area == pytest.approx(
            0.0, abs=1e-9), "this twin must prove the NODE clause alone"
        assert gs._ring_touches_open_cut(ring, welded, member, bounds, self.ROLE)

    def test_a_ring_clear_of_the_cut_is_never_a_member(self):
        far = _rect(500, 500, 600, 600)
        ring = list(far.exterior.coords)[:-1]
        member, bounds = self._member(self.CUT())
        assert not gs._ring_touches_open_cut(ring, far, member, bounds)

    def test_the_region_reads_the_cut_and_never_the_retired_claim_set(
            self):
        """ONE AUTHORITY (spec §2): the exclusion reads
        ``tunnel_open_cut_polys``.  A layout carrying only the retired
        ``tunnel_open_cut_claim_polys`` attribute publishes NOTHING —
        the claim half is gone, not silently still consulted."""
        lay = types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))
        lay.tunnel_open_cut_claim_polys = [_rect(0, 0, 10, 10)]
        assert gs._tunnel_open_cut_region(lay) == (None, None)
        from auto_patch import bridges
        assert not hasattr(bridges, "publish_tunnel_open_cut_claim_set")
