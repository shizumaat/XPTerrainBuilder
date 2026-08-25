"""THE TUNNEL-CORRIDOR EXCLUSION from the unified node book.

Spec: ``docs/specs/tunnel-corridor-node-book-exclusion-spec.md``
(owner-ordered fix, 2026-08-25) at AMENDMENT 4's mechanics on
AMENDMENT 5's region — v2's per-NODE key scope PLUS boundary severance,
keyed on the portal walk's OPEN CUT rather than on R14-1's claim set.  Owner law it rests on: ``docs/RULINGS.md``
2026-08-11 "Roads serve tunnels — the paved area IS the corridor"
(R14-1, the claim these twins reuse) and the 2026-08-07 tunnel-portal
fidelity rulings.

WHAT WENT WRONG.  ``cce9da6f`` put ``service_road`` +
``service_junction`` into ``_CHORD_LIMIT_ROLES``, so the road family
shares ONE node key space with ``groundside_pavement`` in the
finalize-stage Lipschitz clamp — and at a weld the road's value wins
(authority precedence).  At OTHH's site-1 bore the descending tunnel
FLOOR is a ``groundside_pavement`` ring: it gained 17 shared nodes across
six road rings, took ``tunnel_road`` bench values (+2.28/+2.96 against a
−1.1 m floor), and 9 of the bore's 10 ``authority_retreat_wall`` faces
stopped being emitted.

THE REGION IS THE OPEN CUT, NOT THE CLAIM (Amendment 5, and finding 4
is why).  ``tunnel_open_cut_claim_polys`` names the ROAD SURFACES R14-1
re-profiled; the bore's descending FLOOR is a groundside ring beside
them, 0-2 of its 33 nodes in-claim.  Keyed on the claim, the two halves
below restored exactly the two stations the claim covered and left the
other seven at broken values — mechanics proven, region refuted.  The
node book now reads ``tunnel_open_cut_polys``: the portal walk's own
level and approach zones, published by
``bridges.publish_tunnel_open_cut_regions`` from the same records the
"N AIRSIDE shape(s) lie inside a tunnel open cut" report consumes.

THE RULE HAS TWO HALVES, and the ledger says why each is needed:

  1. PER-NODE KEY SCOPE — an in-cut vertex takes a RING-PRIVATE book
     key, minting no shared key and importing none.  Every ring stays in
     the clamp (v1 removed rings and stripped a boundary-spanning ring's
     lot half of lawful limiting: 1.03 m off, walls 5/10).
  2. BOUNDARY SEVERANCE — a within-ring chord pair STRADDLING the claim
     boundary is withheld from the clamp's chord law.  This is the one
     proven leak of half 1 on its own (v2): the road's value won the
     ring's OUT-OF-CLAIM welds and the ring's own chord law carried it
     back across the boundary onto the bore floor (bore recaptured,
     walls 2/10).

The other two measured refutations, so neither is retried: v3 demoted the
road's PRECEDENCE at cut-touching rings — the bore held, but the weld
stayed a shared key, so the claimants AGREED and no retreat face was
minted (finding 2: a face and a shared key are mutually exclusive);
option A took cut-touching ROAD rings out of the role set — the bench
carriers are the bore ring's partners OUTSIDE the claim, 14 welds to 3,
so no membership rule over roles can name them (finding 3).

The twins Amendment 4 §4 names:

(a) the in-cut NODES leave the shared key space while both rings stay
    in the clamp; OFF reproduces the capture;
(a2) THE TWO REGIONS DIFFER on the measured class — a bore ring outside
    the road claim but inside the cut is protected, and publishing the
    claim alone protects nothing;
(b) a road ring OUTSIDE any claim keeps the limiter AND its precedence
    (the ``cce9da6f`` purpose, unregressed);
(c) THE BOUNDARY CARRIER IS DEAD — a boundary-spanning ring with a road
    seed on its lot half keeps its bore half at portal depth while the
    lot half stays clamped;
(d) claimants disagree at boundary welds and the retreat faces emit;
(e) flag off → the pre-round ``cce9da6f`` pass, exactly.
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


def _layout(shapes, cut_polys=None, claim_polys=None):
    """A minimal layout carrying the PUBLISHED regions.

    ``tunnel_open_cut_polys`` is exactly what
    ``bridges.publish_tunnel_open_cut_regions`` writes — the portal
    walk's own level and approach zones, the region the node book reads
    under Amendment 5.  ``tunnel_open_cut_claim_polys`` is the sibling
    publisher's CLAIM SET (the re-profiled road surfaces), carried here
    only so a twin can assert the node book does NOT read it.  Nothing
    re-derives a cut zone; a second geometric notion of "inside the cut"
    is what the spec forbids.
    """
    lay = types.SimpleNamespace(shapes=list(shapes), anchor=(0.0, 0.0))
    if cut_polys:
        lay.tunnel_open_cut_polys = list(cut_polys)
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
    the claim set is the floor's own polygon and the road's two shared
    vertices sit ON its boundary.

    The road runs 100 m, so the 3.4 m step across the weld is 3.4 % —
    inside even the LOT's 5 %, which is the cap that would govern the
    shared weld.  That keeps the CLAMP out of the twin: what the
    altitudes show afterwards is what the BOOK decided, not what a chord
    law then rearranged.
    """
    floor = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT, FLOOR_Z)
    road = _shape(_rect(40, 0, 140, 10), ROLE_SERVICE_JUNCTION, BENCH_Z)
    lay = _layout([floor, road],
                  cut_polys=[floor.polygon] if claimed else None)
    return lay, floor, road


# ═════════════════════════════════════════════════════════════════════
# (a) half 1 — the in-cut nodes leave the shared key space
# ═════════════════════════════════════════════════════════════════════

class TestInCutNodesMintNoSharedKey:
    """Spec AMENDMENT 4 §1 — the in-cut NODES leave the shared key
    space; the RINGS do not leave the clamp."""

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

    def test_on_no_value_crosses_the_cut_in_either_direction(
            self, monkeypatch):
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 5, (
            "the bore floor moved — nothing may import across the cut")
        assert _alts(road) == [BENCH_Z] * 5, (
            "the road moved — the floor may not export across the cut "
            "either")

    def test_on_the_in_cut_nodes_mint_no_shared_key(self, monkeypatch):
        """The whole of half 1, as a number.  Both rings' in-cut
        vertices ride RING-PRIVATE keys, so the two welds do NOT collapse
        into one book entry: 4 + 4 vertices key as 8, not the 6 the
        shared book makes of them — and the road↔lot weld census reads
        zero."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["nodes"] == 8, (
            f"the two welds collapsed into the shared book "
            f"({stats['nodes']} keys, expected 8)")
        assert stats["shared_road_lot_nodes"] == 0
        # …and both rings are STILL IN the clamp (v1's retired rule
        # removed them, and that is what broke the lot half)
        assert stats["rings"] == {ROLE_GROUNDSIDE_PAVEMENT: 1,
                                  ROLE_SERVICE_JUNCTION: 1}

    def test_the_census_counts_nodes_the_rings_and_the_severed(
            self, monkeypatch):
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        # 4 floor vertices (the claim IS the floor's own ring) + the 2
        # road vertices welded onto that boundary
        assert stats["tunnel_corridor_private_nodes"] == 6
        assert stats["tunnel_corridor_rings_touched"] == {
            ROLE_GROUNDSIDE_PAVEMENT: 1, ROLE_SERVICE_JUNCTION: 1}
        # the ROAD carries both sides of the boundary, so its chord law
        # is severed; the floor is wholly in-cut and has nothing to
        # sever, which is why this reads 1 and not 2
        assert stats["tunnel_corridor_severed_rings"] == 1

    def test_no_claim_means_no_exclusion(self, monkeypatch):
        """No second notion of "inside the cut": with nothing published
        by R14-1 the pass is exactly the pre-round pass."""
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene(claimed=False)
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["tunnel_corridor_private_nodes"] == 0
        assert stats["tunnel_corridor_severed_rings"] == 0
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
                       cut_polys=[bore.polygon]), bore, road, lot

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
        assert stats["tunnel_corridor_private_nodes"] == 4, (
            "only the bore's own four vertices are in the claim")
        assert stats["tunnel_corridor_rings_touched"] == {
            ROLE_GROUNDSIDE_PAVEMENT: 1}
        assert stats["tunnel_corridor_severed_rings"] == 0, (
            "a ring 500 m from the claim had its chord law severed")
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
# (c) half 2 — the within-ring boundary carrier is dead
# ═════════════════════════════════════════════════════════════════════

class TestTheBoundaryCarrierIsDead:
    """Spec AMENDMENT 4 §2, and the twin that distinguishes this design
    from v2 — the ONE mechanism v2's measurement left open.

    OTHH ring ``-12221`` carries the bore floor AND lot area outside the
    cut.  v1 removed the ring and left the lot half unlimited; v2 kept it
    whole, and then the road's value won the OUT-OF-CLAIM weld and the
    ring's own chord law carried it across the boundary onto the floor.
    Severance withholds exactly those straddling pairs: each side keeps
    the ring's law among its own vertices, and no chord prices a
    below-grade node against an at-grade one.
    """

    def _scene(self, claim=True):
        span = BuiltShape(
            polygon=_rect(0, 0, 80, 10), role=ROLE_GROUNDSIDE_PAVEMENT,
            node_altitudes=[FLOOR_Z, 10.0, 10.0, FLOOR_Z, FLOOR_Z])
        road = _shape(_rect(80, 0, 100, 10), ROLE_SERVICE_JUNCTION, 12.0)
        # the cut covers the ring's x≈0 end only — the -12221 class
        lay = _layout([span, road],
                      cut_polys=[_rect(-5, -5, 5, 15)] if claim else None)
        return lay, span, road

    def test_the_bore_half_holds_portal_depth(self, monkeypatch):
        monkeypatch.setenv(FLAG, "1")
        lay, span, road = self._scene()
        gs._grade_limit_groundside_chords(lay)
        after = _alts(span)
        assert after[0] == FLOOR_Z and after[3] == FLOOR_Z, (
            f"the in-cut vertices moved to {after[0]}/{after[3]} — the "
            f"within-ring carrier is still open, which is exactly v2's "
            f"measured failure")

    def test_the_lot_half_is_still_clamped_among_itself(self, monkeypatch):
        """Severance withholds the STRADDLING pairs, not the ring: the
        out-of-cut vertices keep the ring's law among themselves and
        still take the road's seed at their weld."""
        monkeypatch.setenv(FLAG, "1")
        lay, span, road = self._scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["tunnel_corridor_private_nodes"] == 2
        assert stats["tunnel_corridor_severed_rings"] == 1
        assert stats["shared_road_lot_nodes"] == 2, (
            "the OUT-OF-CLAIM weld left the shared book — severance "
            "withholds pairs, never keys")
        after = _alts(span)
        cap = cfg.GROUNDSIDE_MAX_GRADE
        # the surviving pair law, on the out-of-cut side only
        worst = abs(after[1] - after[2]) / max(1e-9, _dist(span, 1, 2))
        assert worst <= cap + 5e-3, (
            "the out-of-cut half is over its own cap — each side must "
            "keep the ring's law among its own vertices")

    def test_off_the_carrier_drags_the_bore_half_up(self, monkeypatch):
        """The control, one variable: with the flag off the same ring's
        chord law prices its in-cut end against the road-seeded lot end,
        and the bore half leaves portal depth."""
        monkeypatch.setenv(FLAG, "0")
        lay, span, road = self._scene()
        gs._grade_limit_groundside_chords(lay)
        after = _alts(span)
        assert after[0] > FLOOR_Z + 0.5, (
            f"the OFF arm did not reproduce the carrier (in-cut end "
            f"{after[0]}) — this twin cannot tell severance from an "
            f"inert scene")

    def test_no_claim_leaves_the_ring_whole(self, monkeypatch):
        """Nothing published ⇒ nothing severed: the same ring is priced
        end to end, as every ring outside a tunnel still is."""
        monkeypatch.setenv(FLAG, "1")
        lay, span, road = self._scene(claim=False)
        gs._grade_limit_groundside_chords(lay)
        assert lay._chord_limit_stats["tunnel_corridor_severed_rings"] == 0
        assert _alts(span)[0] > FLOOR_Z + 0.5


# ═════════════════════════════════════════════════════════════════════
# (d) the retreat faces come back (spec §3, finding 2)
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
            lay.tunnel_open_cut_polys = [floor.polygon]
        return lay, floor, road

    def test_on_the_claimants_DISAGREE_and_the_faces_emit(self, monkeypatch):
        """Finding 2, satisfied: the in-cut weld is ring-private, so
        the bore's below-grade value and the road's bench both survive at
        the shared coordinate — and the loser retreats behind a face."""
        from auto_patch import adjacent_ground as AG
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = self._bore_layout()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 7, (
            "the below-grade values did NOT survive — the exclusion is "
            "not doing its job")
        assert _alts(road)[0] == BENCH_Z, (
            "the road read the groundside value back at the weld — the "
            "key is still shared there")
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

    @staticmethod
    def _walls(lay):
        return [s for s in lay.shapes
                if (getattr(s, "ref", "") or "") == "authority_retreat_wall"]


# ═════════════════════════════════════════════════════════════════════
# (e) the kill switch
# ═════════════════════════════════════════════════════════════════════

class TestTheFlagOffIsThePreRoundBehaviour:
    """Spec AMENDMENT 4 §3 — OFF is ``cce9da6f`` in full (neither v1's
    per-ring exclusion nor option A's role exit, both retired), bit for
    bit, for attribution arms."""

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
            "tunnel_corridor_private_nodes"] == 0)

    def test_off_keeps_the_whole_book_shared(self, monkeypatch):
        """OFF means neither half runs: the weld is one key again and
        both rings are priced end to end."""
        monkeypatch.setenv(FLAG, "0")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        assert stats["rings"] == {ROLE_GROUNDSIDE_PAVEMENT: 1,
                                  ROLE_SERVICE_JUNCTION: 1}
        assert stats["shared_road_lot_nodes"] == 2
        assert stats["nodes"] == 6, (
            "the book did not unify the weld — OFF must be cce9da6f in "
            "full")
        assert stats["tunnel_corridor_severed_rings"] == 0

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


# ═════════════════════════════════════════════════════════════════════
# the kernel's own contract — severance is a KERNEL capability
# ═════════════════════════════════════════════════════════════════════

class TestTheKernelSeversOnlyStraddlingPairs:
    """``_chord_band``/``_chord_cut_and_fill`` gained ``sides``; with it
    absent the arithmetic must be bit for bit what it was, and with it
    present only the STRADDLING pairs may go."""

    def _ring(self):
        # four vertices in a line, 10 m apart, the first two "in claim"
        return [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]

    def test_without_sides_the_band_is_unchanged(self):
        coords = self._ring()
        vals = [0.0, 0.0, 0.0, 5.0]
        lo_a, hi_a = gs._chord_band(coords, vals, list(range(4)), 0, 0.05)
        lo_b, hi_b = gs._chord_band(coords, vals, list(range(4)), 0, 0.05,
                                    None, None)
        assert (lo_a, hi_a) == (lo_b, hi_b)

    def test_a_straddling_pair_generates_no_band(self):
        coords = self._ring()
        vals = [0.0, 0.0, 0.0, 5.0]
        sides = [True, True, False, False]
        # vertex 0 sees only vertex 1 (same side): the far 5.0 cannot
        # price it any more
        _lo, hi = gs._chord_band(coords, vals, list(range(4)), 0, 0.05,
                                 None, sides)
        assert hi == pytest.approx(0.0 + 0.05 * 10.0)
        # …and without severance that same vertex is priced by all three
        _lo2, hi2 = gs._chord_band(coords, vals, list(range(4)), 0, 0.05)
        assert hi2 == pytest.approx(0.0 + 0.05 * 10.0)
        # the CUT is what differs: vertex 3 is over cap against 0/1/2
        vals_sev = list(vals)
        gs._chord_cut_and_fill(coords, vals_sev, list(range(4)),
                               list(range(4)), 0.05, sides=sides)
        vals_whole = list(vals)
        gs._chord_cut_and_fill(coords, vals_whole, list(range(4)),
                               list(range(4)), 0.05)
        assert vals_sev[3] > vals_whole[3], (
            "severance did not spare the far side from the near side's "
            "law")
        assert vals_sev[0] == pytest.approx(0.0, abs=1e-9), (
            "the in-cut side moved — a severed pair may not price it")


# ═════════════════════════════════════════════════════════════════════
# (a2) THE TWO REGIONS ARE NOT THE SAME REGION
# ═════════════════════════════════════════════════════════════════════

class TestTheCutIsNotTheClaim:
    """Spec AMENDMENT 5 §1-2, and finding 4 as a twin.

    THE MEASURED CLASS, at unit scale: OTHH ring ``-12180``/``-12221`` —
    a ``groundside_pavement`` bore floor lying INSIDE the portal walk's
    open cut and OUTSIDE R14-1's claim set, whose welded road partners
    are outside the claim too (14 welds at zero claim coverage against
    3 claimed).  Every claim-keyed round reached two of its nine
    stations; the cut reaches all of them.  If these two regions ever
    collapse into one read, this twin fails.
    """

    def _scene(self):
        """The bore floor sits in the cut; the CLAIM names only the road
        strip beyond it, exactly as R14-1 publishes claimed road
        surfaces."""
        floor = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT,
                       FLOOR_Z)
        road = _shape(_rect(40, 0, 140, 10), ROLE_SERVICE_JUNCTION,
                      BENCH_Z)
        cut = _rect(-5, -5, 45, 15)        # the walk's own footprint
        claim = _rect(40, 0, 140, 10)      # the re-profiled road surface
        return floor, road, cut, claim

    def test_the_cut_protects_the_bore_the_claim_does_not(self,
                                                          monkeypatch):
        monkeypatch.setenv(FLAG, "1")
        floor, road, cut, claim = self._scene()
        on_cut = _layout([floor, road], cut_polys=[cut], claim_polys=[claim])
        gs._grade_limit_groundside_chords(on_cut)
        assert _alts(floor) == [FLOOR_Z] * 5, (
            "the bore floor moved even though it is INSIDE the cut")
        stats = on_cut._chord_limit_stats
        assert stats["tunnel_corridor_rings_touched"].get(
            ROLE_GROUNDSIDE_PAVEMENT) == 1, (
            "the cut did not name the bore ring — Amendment 5's whole "
            "premise")

    def test_the_claim_alone_protects_nothing_here(self, monkeypatch):
        """The control, one variable: publish ONLY the claim (what four
        rounds read) and the same scene reproduces the capture."""
        monkeypatch.setenv(FLAG, "1")
        floor, road, _cut, claim = self._scene()
        claim_only = _layout([floor, road], claim_polys=[claim])
        gs._grade_limit_groundside_chords(claim_only)
        assert claim_only._chord_limit_stats[
            "tunnel_corridor_private_nodes"] == 0, (
            "the node book read the CLAIM — under Amendment 5 it must "
            "read the open cut and nothing else")
        assert max(_alts(floor)) > FLOOR_Z + 0.5, (
            "the capture did not reproduce on the claim-only layout")

    def test_the_cut_is_published_by_the_portal_walk_not_re_derived(self):
        """ONE AUTHORITY: the publisher flattens the walk's OWN region
        records — level zone and approach zone — skips the empty ones,
        and ACCUMULATES across tunnel systems.  It derives nothing."""
        from auto_patch import bridges
        lay = types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))
        level, approach = _rect(0, 0, 10, 10), _rect(10, 0, 30, 10)
        assert bridges.publish_tunnel_open_cut_regions(
            lay, [(level, approach, -1.1)]) == 2
        assert lay.tunnel_open_cut_polys == [level, approach]
        # a portal whose walk could not buffer publishes its level only
        second = _rect(50, 50, 60, 60)
        assert bridges.publish_tunnel_open_cut_regions(
            lay, [(second, None, 2.0)]) == 1
        assert lay.tunnel_open_cut_polys == [level, approach, second]
        # nothing to publish ⇒ no attribute ⇒ no exclusion downstream
        empty = types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))
        assert bridges.publish_tunnel_open_cut_regions(empty, []) == 0
        assert not hasattr(empty, "tunnel_open_cut_polys")

    def test_the_claim_publisher_still_serves_its_own_consumers(self):
        """Spec AMENDMENT 5 §2: only the node-book predicate re-keys.
        The claim set is still published, separately, for the stand-down
        and the R14-1 report."""
        from auto_patch import bridges
        lay = types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))
        a = _rect(0, 0, 10, 10)
        assert bridges.publish_tunnel_open_cut_claim_set(lay, [a]) == 1
        assert lay.tunnel_open_cut_claim_polys == [a]
        assert not hasattr(lay, "tunnel_open_cut_polys"), (
            "the claim publisher wrote the CUT attribute — the two "
            "regions must stay two")
