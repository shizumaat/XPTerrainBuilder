"""THE TUNNEL-CORRIDOR EXCLUSION from the unified node book.

Spec: ``docs/specs/tunnel-corridor-node-book-exclusion-spec.md``
(owner-ordered fix, 2026-08-25) at AMENDMENT 3 / OPTION A.  Owner law it
rests on: ``docs/RULINGS.md`` 2026-08-11 "Roads serve tunnels — the paved
area IS the corridor" (R14-1, the claim these twins reuse) and the
2026-08-07 tunnel-portal fidelity rulings.

WHAT WENT WRONG, and why the fix is SCOPE not REVERT.  ``cce9da6f`` put
``service_road`` + ``service_junction`` into ``_CHORD_LIMIT_ROLES``, so
the road family shares ONE node key space with ``groundside_pavement``
in the finalize-stage Lipschitz clamp — and at a weld the road's value
wins (authority precedence).  At OTHH's site-1 bore the descending
tunnel FLOOR is a ``groundside_pavement`` ring: it gained 17 shared
nodes across six road rings, took ``tunnel_road`` bench values
(+2.28/+2.96 against a −1.1 m floor — a 3.3 m mid-ramp step), and 9 of
the bore's 10 ``authority_retreat_wall`` faces stopped being emitted.

THE RULE, and the three measured refutations behind it (the spec's
do-not-retry ledger — none of them is to be tried again):

  * v1, EXCLUDE THE CLAIM-TOUCHING RING whatever its role: perfect bore
    floor, but a boundary-spanning GROUNDSIDE ring lost lawful limiting
    on its out-of-cut half (OTHH ``-12221``: lot worst 1.03 m off the
    reference, retreat walls 5 of 10);
  * v2, PRIVATE KEYS for in-cut nodes: closed the direct weld channel and
    left the TWO-STEP path open — the road still won the SAME ring's
    out-of-cut welds and the ring's own chord law carried that value back
    across the boundary (bore recaptured, walls 2 of 10);
  * v3, DEMOTE THE ROAD'S PRECEDENCE at a claim-touching ring's welds:
    the bore floor held, and then the weld — still a SHARED KEY — wrote
    that value into the road's ring, so the claimants AGREED and no
    retreat face was minted (walls 2 of 10).

v3 is the STRUCTURAL FINDING (spec "finding 2"): a retreat face and a
shared key are MUTUALLY EXCLUSIVE, because a face exists only where
claimants DISAGREE at a node.  So at a tunnel site the ROAD FAMILY MUST
LEAVE THE SHARED KEY SPACE — which is option A: a ROAD-role ring
touching the open-cut claim leaves ``_CHORD_LIMIT_ROLES`` for the pass
(no key minted, none consumed, no clamp), ``groundside_pavement`` rings
stay in the pass EVERYWHERE, and a road ring touching no claim keeps
``cce9da6f`` in full.

The four twins the spec names (Amendment 3 §4):

(a) a claim-touching ROAD ring is unclamped and unkeyed, while its
    GROUNDSIDE partner stays in the pass and is limited by its own law;
(b) a road ring OUTSIDE any claim still takes the limiter and its
    precedence (the ``cce9da6f`` purpose, unregressed);
(c) retreat-wall derivation: with the road out of the book the claimants
    disagree at the bore and the faces EMIT (spec §3 / finding 2);
(d) flag off → the pre-round ``cce9da6f`` pass, exactly.
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


def _layout(shapes, claim_polys=None):
    """A minimal layout carrying R14-1's PUBLISHED claim set.

    ``tunnel_open_cut_claim_polys`` is exactly what
    ``bridges.publish_tunnel_open_cut_claim_set`` writes — the claimed
    road surfaces themselves.  Nothing here re-derives a cut zone; a
    second geometric notion of "inside the cut" is what the spec
    forbids.
    """
    lay = types.SimpleNamespace(shapes=list(shapes), anchor=(0.0, 0.0))
    if claim_polys:
        lay.tunnel_open_cut_claim_polys = list(claim_polys)
    return lay


def _alts(shape):
    return [round(float(a), 2) for a in shape.node_altitudes]


def _dist(shape, i, j):
    ring = list(shape.polygon.exterior.coords)
    ax, ay = ring[i]
    bx, by = ring[j]
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _bore_scene(claimed=True):
    """The site-1 shape of the defect, at unit scale.

    ``floor`` is the bore's descending floor — a ``groundside_pavement``
    ring at −1.1 m.  ``road`` is the at-grade ``service_junction`` beside
    it, sharing the two vertices on their common edge (the weld the node
    book unified).  R14-1 claimed the FLOOR as the tunnel corridor, so
    the claim set is the floor's own polygon and the road TOUCHES it at
    those two shared vertices.

    The road runs 100 m, so the 3.4 m step across the weld is 3.4 % —
    inside even the LOT's 5 %, which is the cap that would govern the
    shared weld.  That keeps the CLAMP out of the twin: what the
    altitudes show afterwards is what the BOOK decided, not what a chord
    law then rearranged.
    """
    floor = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT, FLOOR_Z)
    road = _shape(_rect(40, 0, 140, 10), ROLE_SERVICE_JUNCTION, BENCH_Z)
    lay = _layout([floor, road],
                  claim_polys=[floor.polygon] if claimed else None)
    return lay, floor, road


# ═════════════════════════════════════════════════════════════════════
# (a) the claim-scoped ROLE exclusion itself
# ═════════════════════════════════════════════════════════════════════

class TestAClaimTouchingRoadRingLeavesTheRoleSet:
    """Spec AMENDMENT 3 §1 — the ROAD ring leaves the pass at a tunnel
    site; the GROUNDSIDE ring never does."""

    def test_off_reproduces_the_capture(self, monkeypatch):
        """The pre-round world, on purpose: the road's bench value wins
        at the weld and drags the bore floor up out of its cut."""
        monkeypatch.setenv(FLAG, "0")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        after = _alts(floor)
        assert max(after) > FLOOR_Z + 0.5, (
            f"the capture did not reproduce: floor {after} — this twin's "
            f"OFF arm must show the defect the fix removes")

    def test_on_the_bore_floor_keeps_its_own_values(self, monkeypatch):
        """The ruled behaviour: no road key reaches the bore floor, so
        its below-grade field stands."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 5, (
            "the bore floor moved — a road value reached it")

    def test_on_the_road_neither_keys_nor_is_clamped(self, monkeypatch):
        """Both halves of "leaves the role set", read off the census and
        off the road's own altitudes.

        THE DISAGREEMENT IS THE POINT (finding 2): the road keeps its
        bench and the floor keeps its cut, so the two claimants differ at
        the shared vertex — which is what a retreat face is made of, and
        what v3's shared key destroyed.
        """
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(road) == [BENCH_Z] * 5, (
            "the excluded road was still clamped by this pass")
        stats = lay._chord_limit_stats
        assert stats["rings"] == {ROLE_GROUNDSIDE_PAVEMENT: 1}, (
            "the road ring is still collected — it must leave the pass, "
            "and the GROUNDSIDE ring must stay (v1's retired rule "
            "removed that one too)")
        assert stats["shared_road_lot_nodes"] == 0, (
            "a road↔lot key survived at the claim — the road did not "
            "leave the shared key space")
        assert stats["tunnel_corridor_exempt_rings"] == {
            ROLE_SERVICE_JUNCTION: 1}
        assert stats["tunnel_corridor_exempt_nodes"] == 4

    def test_the_excluded_road_is_not_even_CUT(self, monkeypatch):
        """"Not clamped by the pass" is a real exemption, not a no-op on
        a flat ring: an over-cap road inside the claim keeps its own
        steep field (the portal walk owns it), and the OFF arm shows the
        same ring being cut."""
        def _scene():
            road = BuiltShape(
                polygon=_rect(0, 0, 20, 10), role=ROLE_SERVICE_JUNCTION,
                node_altitudes=[0.0, 6.0, 6.0, 0.0, 0.0])
            return _layout([road], claim_polys=[_rect(-5, -5, 5, 15)]), road
        monkeypatch.setenv(FLAG, "1")
        lay, road = _scene()
        assert gs._grade_limit_groundside_chords(lay) == 0
        assert _alts(road) == [0.0, 6.0, 6.0, 0.0, 0.0]
        monkeypatch.setenv(FLAG, "0")
        ctl, ctl_road = _scene()
        assert gs._grade_limit_groundside_chords(ctl) == 1
        assert max(_alts(ctl_road)) < 6.0, (
            "the OFF arm did not clamp this ring — the twin cannot tell "
            "an exemption from an inert scene")

    def test_the_claim_may_be_the_ROADS_own_surface(self, monkeypatch):
        """R14-1 claims ROAD PAVEMENT as the corridor, so the commonest
        claim polygon IS a road ring's own footprint.  Same rule, same
        predicate: that ring covers its own vertices, so it leaves."""
        monkeypatch.setenv(FLAG, "1")
        floor = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT,
                       FLOOR_Z)
        road = _shape(_rect(40, 0, 140, 10), ROLE_SERVICE_JUNCTION,
                      BENCH_Z)
        lay = _layout([floor, road], claim_polys=[road.polygon])
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 5
        assert lay._chord_limit_stats["tunnel_corridor_exempt_rings"] == {
            ROLE_SERVICE_JUNCTION: 1}

    def test_a_boundary_spanning_GROUNDSIDE_ring_is_limited_throughout(
            self, monkeypatch):
        """v1's MEASURED DEFECT, pinned so it cannot come back (OTHH ring
        ``-12221``).

        One groundside ring carries the bore floor AND lot area outside
        the cut.  v1 excluded it whole and left the lot half unlimited.
        Option A never removes a groundside ring: this one stays in the
        pass and its own law limits every vertex, in-cut ones included —
        while the claim-touching ROAD beside it contributes nothing.
        """
        monkeypatch.setenv(FLAG, "1")
        span = BuiltShape(
            polygon=_rect(0, 0, 80, 10), role=ROLE_GROUNDSIDE_PAVEMENT,
            node_altitudes=[FLOOR_Z, 10.0, 10.0, FLOOR_Z, FLOOR_Z])
        road = _shape(_rect(80, 0, 100, 10), ROLE_SERVICE_JUNCTION, 12.0)
        # the cut covers the x≈0 end AND the road (R14-1's corridor)
        lay = _layout([span, road],
                      claim_polys=[_rect(-5, -5, 5, 15), road.polygon])
        assert gs._grade_limit_groundside_chords(lay) >= 1
        stats = lay._chord_limit_stats
        assert stats["rings"] == {ROLE_GROUNDSIDE_PAVEMENT: 1}, (
            "the spanning groundside ring left the pass — that is v1's "
            "retired rule and its lot-half defect")
        after = _alts(span)
        assert after[1] < 10.0, (
            "the ring's out-of-cut half was not limited")
        assert max(after) < 12.0, (
            "the road's 12.0 reached the ring — the road is out of the "
            "book, so no path may carry it here")
        cap = cfg.GROUNDSIDE_MAX_GRADE
        worst = max(abs(after[i] - after[j]) / max(1e-9, _dist(span, i, j))
                    for i in range(4) for j in range(i + 1, 4))
        assert worst <= cap + 5e-3, (
            "the ring is over its own cap — within-ring limiting must "
            "continue for every vertex, in-cut ones included")

    def test_no_claim_means_no_exclusion(self, monkeypatch):
        """No second notion of "inside the cut": with nothing published
        by R14-1 the pass is exactly the pre-round pass."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene(claimed=False)
        gs._grade_limit_groundside_chords(lay)
        assert lay._chord_limit_stats["tunnel_corridor_exempt_rings"] == {}
        assert max(_alts(floor)) > FLOOR_Z + 0.5


# ═════════════════════════════════════════════════════════════════════
# (b) the road chord limiter's own purpose, unregressed
# ═════════════════════════════════════════════════════════════════════

class TestARoadOutsideAnyClaimKeepsTheLimiter:
    """Spec §4 — "the limiter keeps its full role set everywhere else"."""

    def _scene(self):
        """A road/lot weld 500 m from the bore, and a claim that covers
        only the bore."""
        bore = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT, FLOOR_Z)
        road = BuiltShape(polygon=_rect(500, 0, 540, 20),
                          role=ROLE_SERVICE_JUNCTION,
                          node_altitudes=[10.0, 14.0, 14.0, 10.0, 10.0])
        lot = _shape(_rect(500, 20, 540, 60), ROLE_GROUNDSIDE_PAVEMENT, 10.0)
        return _layout([bore, road, lot],
                       claim_polys=[bore.polygon]), bore, road, lot

    def test_the_far_road_is_still_clamped(self, monkeypatch):
        """A road ring over its own cap is still pulled inside it — the
        exclusion is scoped to the claim, never to the family."""
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
        node book exists for — is untouched outside the claim."""
        monkeypatch.setenv(FLAG, "1")
        lay, bore, road, lot = self._scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["shared_road_lot_nodes"] == 2, (
            "the road↔lot weld left the unified book")
        assert stats["tunnel_corridor_exempt_rings"] == {}, (
            "a ring was excluded 500 m from any claim — and the BORE is "
            "groundside, which is never excluded at all")
        assert stats["tunnel_corridor_exempt_nodes"] == 0
        assert stats["rings"] == {ROLE_GROUNDSIDE_PAVEMENT: 2,
                                  ROLE_SERVICE_JUNCTION: 1}
        # one value per shared node, both rings
        shared = {}
        for shape in (road, lot):
            ring = list(shape.polygon.exterior.coords)[:-1]
            for (x, y), v in zip(ring, _alts(shape)):
                k = (round(x, 2), round(y, 2))
                if k in shared:
                    assert shared[k] == pytest.approx(v, abs=1e-9)
                shared[k] = v


# ═════════════════════════════════════════════════════════════════════
# (c) the retreat faces come back (spec §3, finding 2)
# ═════════════════════════════════════════════════════════════════════

class TestTheRetreatWallsFollowTheRestoredRamp:
    """Spec §3 — ``authority_retreat_wall`` emission is VERIFIED
    downstream of the exclusion.

    The faces are derived from the below-grade geometry retreating from a
    higher-precedence claimant: they exist only while the two claimants
    DISAGREE at the shared node.  The capture erased the disagreement by
    writing one value into both rings, which is why 9 of OTHH site-1's 10
    faces stopped being emitted — and it is why v3, which kept the shared
    key, could not bring them back.  Walls are lawful here because this
    is a CARVE STRUCTURE (owner 2026-08-07: "walls are lawful ONLY at
    tunnel/bridge carve structures").
    """

    def _bore_layout(self, claimed=True):
        lay = PavementLayout(icao="KFAKE", anchor=(25.27, 51.60))
        lay.canonical_points = CanonicalPointRegistry(
            tol_m=SHARED_VERTEX_TOL_M)
        # the at-grade road, welded to the middle of the floor's top edge
        # (a mid-ring contested vertex — a ring CORNER can only retreat
        # along its diagonal, which the emitter refuses)
        road = _shape(_rect(100, 0, 140, 100), ROLE_SERVICE_JUNCTION,
                      BENCH_Z)
        lay.shapes.append(road)
        floor = BuiltShape(
            polygon=Polygon([(0, 0), (0, -200), (400, -200), (400, 0),
                             (140, 0), (100, 0)]),
            role=ROLE_GROUNDSIDE_PAVEMENT, ref="bore_floor",
            node_altitudes=[FLOOR_Z] * 7)
        lay.shapes.append(floor)
        # THE CARVE STRUCTURE — the portal the wall is lawful at.
        lay.shapes.append(_shape(_rect(110, 2, 130, 12),
                                 ROLE_TUNNEL_RAMP, BENCH_Z - 6.0))
        if claimed:
            # R14-1's claim: the road pavement IS the corridor
            lay.tunnel_open_cut_claim_polys = [road.polygon]
        return lay, floor, road

    @staticmethod
    def _walls(lay):
        return [s for s in lay.shapes
                if (getattr(s, "ref", "") or "") == "authority_retreat_wall"]

    def test_on_the_claimants_DISAGREE_and_the_faces_emit(self, monkeypatch):
        """Finding 2, satisfied: the road left the book, so the bore's
        below-grade values and the road's bench both survive at the
        shared vertices — and the loser retreats behind a face."""
        from auto_patch import adjacent_ground as AG
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = self._bore_layout()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 7, (
            "the below-grade values did NOT survive — the exclusion is "
            "not doing its job")
        assert _alts(road) == [BENCH_Z] * 5, (
            "the road was clamped or keyed at a claim it touches")
        assert AG.emit_authority_retreat_walls(lay) >= 1
        assert self._walls(lay), (
            "no retreat face at a bore whose claimants disagree — this "
            "is exactly what v1/v2/v3 could not deliver")

    def test_off_the_capture_erases_the_disagreement(self, monkeypatch):
        """The capture's own arm: the claimants AGREE — at the ROAD's
        bench, with the bore floor dragged up to meet it — so no face is
        minted.  Same emitter, opposite surface."""
        from auto_patch import adjacent_ground as AG
        monkeypatch.setenv(FLAG, "0")
        lay, floor, road = self._bore_layout()
        gs._grade_limit_groundside_chords(lay)
        assert max(_alts(floor)) > FLOOR_Z + 0.5
        AG.emit_authority_retreat_walls(lay)
        assert not self._walls(lay)


# ═════════════════════════════════════════════════════════════════════
# (d) the kill switch
# ═════════════════════════════════════════════════════════════════════

class TestTheFlagOffIsThePreRoundBehaviour:
    """Spec AMENDMENT 3 §3 — OFF is ``cce9da6f`` in full (NOT v1's
    per-ring exclusion, which this change retires), bit for bit, for
    attribution arms."""

    def test_off_equals_a_layout_with_no_claim_published(self, monkeypatch):
        """The only thing the fix adds to the pass is the claim read; with
        the flag off, a layout CARRYING a claim and one carrying none must
        produce the same altitudes, the same return value and the same
        census."""
        monkeypatch.setenv(FLAG, "0")
        with_claim, floor_a, road_a = _bore_scene(claimed=True)
        without, floor_b, road_b = _bore_scene(claimed=False)
        n_a = gs._grade_limit_groundside_chords(with_claim)
        n_b = gs._grade_limit_groundside_chords(without)
        assert n_a == n_b
        assert _alts(floor_a) == _alts(floor_b)
        assert _alts(road_a) == _alts(road_b)
        assert (with_claim._chord_limit_stats
                == without._chord_limit_stats)
        assert (with_claim._chord_limit_stats[
            "tunnel_corridor_exempt_rings"] == {})

    def test_off_keeps_the_ROAD_in_the_book_at_the_claim(self, monkeypatch):
        """OFF no longer means v1: the claim-touching road is back in the
        role set, keying and clamping as ``cce9da6f`` wrote it."""
        monkeypatch.setenv(FLAG, "0")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["rings"] == {ROLE_GROUNDSIDE_PAVEMENT: 1,
                                  ROLE_SERVICE_JUNCTION: 1}
        assert stats["shared_road_lot_nodes"] == 2

    def test_the_flag_defaults_ON(self, monkeypatch):
        """Default ON (spec §3): the production build carries the fix."""
        monkeypatch.delenv(FLAG, raising=False)
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 5

    def test_the_claim_set_is_published_by_r14_1_not_re_derived(self):
        """ONE AUTHORITY (spec §2): the publisher hands the claim list
        through verbatim — the same polygons
        ``_stand_down_synthetic_over_claimed`` consumes."""
        from auto_patch import bridges
        lay = types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))
        a, b = _rect(0, 0, 10, 10), _rect(20, 20, 30, 30)
        assert bridges.publish_tunnel_open_cut_claim_set(
            lay, [a, None, b]) == 2
        assert lay.tunnel_open_cut_claim_polys == [a, b]
        # a second system's claim ACCUMULATES, never replaces
        c = _rect(40, 40, 50, 50)
        assert bridges.publish_tunnel_open_cut_claim_set(lay, [c]) == 1
        assert lay.tunnel_open_cut_claim_polys == [a, b, c]
        # nothing claimed ⇒ nothing published ⇒ nothing excluded
        empty = types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))
        assert bridges.publish_tunnel_open_cut_claim_set(empty, []) == 0
        assert not hasattr(empty, "tunnel_open_cut_claim_polys")
