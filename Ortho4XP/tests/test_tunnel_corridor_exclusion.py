"""THE TUNNEL-CORRIDOR EXCLUSION from the unified node book.

Spec: ``docs/specs/tunnel-corridor-node-book-exclusion-spec.md``
(owner-ordered fix, 2026-08-25).  Owner law it rests on:
``docs/RULINGS.md`` 2026-08-11 "Roads serve tunnels — the paved area IS
the corridor" (R14-1, the claim these twins reuse) and 2026-08-07's
tunnel-portal fidelity rulings.

WHAT WENT WRONG, and why the fix is SCOPE not REVERT.  ``cce9da6f`` put
``service_road`` + ``service_junction`` into ``_CHORD_LIMIT_ROLES``, so
the road family shares ONE node key space with ``groundside_pavement``
in the finalize-stage Lipschitz clamp — and at a weld the road's value
wins (authority precedence).  At OTHH's site-1 bore the descending
tunnel FLOOR is a ``groundside_pavement`` ring: it gained 17 shared
nodes across six road rings, took ``tunnel_road`` bench values
(+2.28/+2.96 against a −1.1 m floor — a 3.3 m mid-ramp step), and 9 of
the bore's 10 ``authority_retreat_wall`` faces stopped being emitted.
The limiter joined the roles for a reason, so the exemption axis moves
from ROLE (``tunnel_ramp``, which this bore's floor is not) to
AUTHORITY: a ring inside R14-1's OWN open-cut claim belongs to the
portal walk, whatever its role.

AMENDMENT 2 (Fable, 2026-08-25) is the ruled design, and it is what it
is because two narrower rules were BUILT AND MEASURED first — the spec's
do-not-retry ledger:

  * excluding the whole RING gave a perfect bore floor and stripped
    lawful limiting from a boundary-spanning ring's lot half (OTHH ring
    ``-12221`` carries BOTH halves: lot worst 1.03 m off the reference,
    retreat walls 5 of 10);
  * PRIVATE KEYS for in-cut nodes closed the direct weld channel but
    left the TWO-STEP path open — the road's value still won at the SAME
    ring's out-of-cut welds (``cce9da6f``'s design), and the ring's own
    chord law then carried it across the cut boundary without ever
    minting a key inside it (bore recaptured, walls 2 of 10).

So what is withheld is neither the key nor the clamp: it is the ROAD'S
PRECEDENCE.  A ring touching the claim keys, welds and clamps exactly as
before, but no road-role value WINS at any of its weld nodes — on either
half.  Rings touching no claim keep ``cce9da6f``'s full precedence.

The four twins the spec names, at the amended rule:

(a) a claim-touching ring welded to a road — the groundside value
    survives ON THE SHARED KEY, and the same weld on a NON-claim ring
    still goes to the road; OFF reproduces the capture;
(b) a road ring OUTSIDE any claim still takes the limiter's precedence
    (the ``cce9da6f`` purpose, unregressed);
(c) retreat-wall derivation: with the restored ramp the retreat faces
    emit — and with the capture they do not (spec §3);
(d) flag off → the pre-fix result, exactly.
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


def _bore_scene(claimed=True):
    """The site-1 shape of the defect, at unit scale.

    ``floor`` is the bore's descending floor — a ``groundside_pavement``
    ring at −1.1 m.  ``road`` is the at-grade ``service_junction`` beside
    it, sharing the two vertices on their common edge (the weld the node
    book unified).  R14-1 claimed the FLOOR as the tunnel corridor, so
    the claim set is the floor's own polygon.

    The road runs 100 m, so the 3.4 m step across the weld is 3.4 % —
    inside even the LOT's 5 %, which is the cap that governs the shared
    weld under the stricter-cap rule.  That keeps the CLAMP out of the
    twin: what the altitudes show afterwards is what PRECEDENCE decided,
    not what a chord law then rearranged.
    """
    floor = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT, FLOOR_Z)
    road = _shape(_rect(40, 0, 140, 10), ROLE_SERVICE_JUNCTION, BENCH_Z)
    lay = _layout([floor, road],
                  claim_polys=[floor.polygon] if claimed else None)
    return lay, floor, road


# ═════════════════════════════════════════════════════════════════════
# (a) the road-precedence exemption itself
# ═════════════════════════════════════════════════════════════════════

class TestAClaimTouchingRingIsRoadPrecedenceExempt:
    """Spec §2 as AMENDED 2 — the ring keys, welds and clamps exactly as
    before; what it does NOT do is let a road value win at its welds."""

    def test_off_reproduces_the_capture(self, monkeypatch):
        """The pre-fix world, on purpose: the road's bench value wins at
        the weld and drags the bore floor up out of its cut."""
        monkeypatch.setenv(FLAG, "0")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        after = _alts(floor)
        assert max(after) > FLOOR_Z + 0.5, (
            f"the capture did not reproduce: floor {after} — this twin's "
            f"OFF arm must show the defect the fix removes")

    def test_on_the_groundside_value_survives_ON_THE_SHARED_KEY(
            self, monkeypatch):
        """The ruled behaviour, and the whole of it.

        The weld is STILL A SHARED KEY — nothing is withheld from the
        book — but the road's value does not win it, so the bore floor's
        own number stands there and the ROAD's ring reads it back at that
        node (which is what a tunnel approach physically does: the road
        descends to meet the bore).
        """
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 5, (
            "the bore floor moved — no road value may win at its weld")
        weld, far = _alts(road)[0], _alts(road)[1]
        assert weld == FLOOR_Z, (
            f"the shared weld holds {weld}, not the groundside "
            f"{FLOOR_Z} — the road still won")
        assert far == BENCH_Z, "the road's own far end must be untouched"
        stats = lay._chord_limit_stats
        assert stats["shared_road_lot_nodes"] == 2, (
            "the weld left the shared book — Amendment 2 withholds "
            "PRECEDENCE, never the key")
        assert stats["rings"] == {ROLE_GROUNDSIDE_PAVEMENT: 1,
                                  ROLE_SERVICE_JUNCTION: 1}

    def test_the_same_weld_on_a_NON_claim_ring_still_goes_to_the_road(
            self, monkeypatch):
        """The other half of (a), in ONE scene so the two cannot drift
        apart: an identical lot/road weld 500 m from any claim keeps
        ``cce9da6f``'s precedence exactly."""
        monkeypatch.setenv(FLAG, "1")
        near = _shape(_rect(0, 0, 40, 10), ROLE_GROUNDSIDE_PAVEMENT,
                      FLOOR_Z)
        near_road = _shape(_rect(40, 0, 140, 10), ROLE_SERVICE_JUNCTION,
                           BENCH_Z)
        # the far lot is 100 m wide for the same reason the near road is:
        # so the stricter-cap clamp is inert and the twin reads
        # PRECEDENCE, not chord arithmetic
        far = _shape(_rect(1000, 0, 1100, 10), ROLE_GROUNDSIDE_PAVEMENT,
                     FLOOR_Z)
        far_road = _shape(_rect(1100, 0, 1200, 10), ROLE_SERVICE_JUNCTION,
                          BENCH_Z)
        lay = _layout([near, near_road, far, far_road],
                      claim_polys=[near.polygon])
        gs._grade_limit_groundside_chords(lay)
        assert _alts(near)[1] == FLOOR_Z, (
            "the CLAIM-touching lot lost its weld to the road")
        assert _alts(far)[1] == BENCH_Z, (
            "the NON-claim lot kept its own value at the weld — the "
            "exemption leaked past the claim and cce9da6f's purpose "
            "with it")
        stats = lay._chord_limit_stats
        assert stats["tunnel_corridor_exempt_rings"] == {
            ROLE_GROUNDSIDE_PAVEMENT: 1, ROLE_SERVICE_JUNCTION: 1}

    def test_the_census_counts_the_exempt_rings_and_welds(
            self, monkeypatch):
        monkeypatch.setenv(FLAG, "1")
        lay, floor, road = _bore_scene()
        gs._grade_limit_groundside_chords(lay)
        stats = lay._chord_limit_stats
        # the floor (the claim itself) and the road welded to its
        # boundary: both rings touch, so both are exempt
        assert stats["tunnel_corridor_exempt_rings"] == {
            ROLE_GROUNDSIDE_PAVEMENT: 1, ROLE_SERVICE_JUNCTION: 1}
        # the road offers a value at 4 nodes, every one of them on an
        # exempt ring, so every one is demoted
        assert stats["tunnel_corridor_exempt_nodes"] == 4

    def test_a_boundary_spanning_ring_reads_the_GOOD_regime_throughout(
            self, monkeypatch):
        """AMENDMENT 2's motivating case (OTHH ring ``-12221``).

        One ring carries the bore floor AND lot area outside the cut.
        Excluding it whole left the lot half unlimited; private keys left
        the road winning that half's weld and carrying its value back to
        the floor through the ring's own chord law.  Under the exemption
        the WHOLE ring reads the pre-``cce9da6f`` regime: the road wins
        nothing on it, the weld is still shared, and the ring's own law
        limits every vertex.
        """
        def _scene(claim):
            span = BuiltShape(
                polygon=_rect(0, 0, 80, 10), role=ROLE_GROUNDSIDE_PAVEMENT,
                node_altitudes=[FLOOR_Z, 10.0, 10.0, FLOOR_Z, FLOOR_Z])
            road = _shape(_rect(80, 0, 100, 10), ROLE_SERVICE_JUNCTION,
                          12.0)
            return _layout([span, road],
                           claim_polys=[_rect(-5, -5, 5, 15)] if claim
                           else None), span
        monkeypatch.setenv(FLAG, "1")
        lay, span = _scene(True)          # the cut covers the x≈0 end only
        assert gs._grade_limit_groundside_chords(lay) >= 1
        stats = lay._chord_limit_stats
        assert stats["tunnel_corridor_exempt_rings"] == {
            ROLE_GROUNDSIDE_PAVEMENT: 1}
        assert stats["shared_road_lot_nodes"] == 2, (
            "the OUT-OF-CUT weld left the shared book — the exemption "
            "must withhold precedence, not the key")
        after = _alts(span)
        assert after[1] < 10.0, (
            "the ring's out-of-cut half was not limited — that is the "
            "per-RING defect on the do-not-retry ledger")
        assert max(after) < 12.0, (
            "the road's 12.0 reached the ring — the two-step carrier is "
            "still open")
        cap = cfg.GROUNDSIDE_MAX_GRADE
        worst = max(abs(after[i] - after[j]) / max(1e-9, _dist(span, i, j))
                    for i in range(4) for j in range(i + 1, 4))
        assert worst <= cap + 5e-3, (
            "the ring is over its own cap — within-ring limiting must "
            "continue for every vertex, in-cut ones included")
        # …and the control: with no claim the road DOES seed that weld,
        # so the same ring settles higher.  One scene, one variable.
        ctl, ctl_span = _scene(False)
        gs._grade_limit_groundside_chords(ctl)
        assert max(_alts(ctl_span)) > max(after), (
            "the claim made no difference to this ring — the exemption "
            "is inert")

    def test_no_claim_means_no_exemption(self, monkeypatch):
        """No second notion of "inside the cut": with nothing published
        by R14-1 the pass is exactly the pre-fix pass."""
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
        assert stats["tunnel_corridor_exempt_rings"] == {
            ROLE_GROUNDSIDE_PAVEMENT: 1}
        assert stats["tunnel_corridor_exempt_nodes"] == 0, (
            "a road value was demoted 500 m from any claim")
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
# (c) the retreat faces come back (spec §3)
# ═════════════════════════════════════════════════════════════════════

class TestTheRetreatWallsFollowTheRestoredRamp:
    """Spec §3 — ``authority_retreat_wall`` emission is VERIFIED
    downstream of the exclusion.

    The faces are derived from the below-grade geometry retreating from
    a higher-precedence claimant: they exist only while the two
    claimants DISAGREE at the shared node.  The capture erased the
    disagreement (the shared key wrote one value into both rings), which
    is why 9 of OTHH site-1's 10 faces stopped being emitted.  Walls are
    lawful here because this is a CARVE STRUCTURE (owner 2026-08-07:
    "walls are lawful ONLY at tunnel/bridge carve structures").
    """

    def _bore_layout(self, claimed=True):
        lay = PavementLayout(icao="KFAKE", anchor=(25.27, 51.60))
        lay.canonical_points = CanonicalPointRegistry(
            tol_m=SHARED_VERTEX_TOL_M)
        # the at-grade road, welded to the middle of the floor's top edge
        # (a mid-ring contested vertex — a ring CORNER can only retreat
        # along its diagonal, which the emitter refuses)
        # 100 m deep, so the 3.4 m step across the weld is 3.4 % — under
        # the LOT's 5 %, which governs the shared node.  The twin is
        # about the retreat FACE, not about the clamp.
        lay.shapes.append(_shape(_rect(100, 0, 140, 100),
                                 ROLE_SERVICE_JUNCTION, BENCH_Z))
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
            lay.tunnel_open_cut_claim_polys = [floor.polygon]
        return lay, floor

    @staticmethod
    def _walls(lay):
        return [s for s in lay.shapes
                if (getattr(s, "ref", "") or "") == "authority_retreat_wall"]

    def test_on_the_ramp_values_survive_but_the_weld_now_AGREES(
            self, monkeypatch):
        """THE STRUCTURAL FINDING OF AMENDMENT 2, pinned as a twin.

        The exemption does what it says: the bore floor keeps every one
        of its below-grade values, because no road value wins on its
        ring.  But the weld is a SHARED KEY (Amendment 2 §1 keeps it one
        deliberately), so the writeback puts that same value into the
        ROAD's ring too — and a retreat face exists only where the two
        claimants DISAGREE at a shared node.  They now agree, so no face
        is minted here.

        That is the weld-or-gap law working (owner 2026-08-13: "two patch
        surfaces that touch AGREE at shared nodes"), and it is in direct
        tension with the spec's §3 requirement that all ten of GOOD's
        faces come back: GOOD's faces exist precisely BECAUSE its road
        family was outside the book and therefore disagreed.  Recorded
        here, measured at OTHH in the lane report, ruled by Fable — never
        papered over by weakening this assertion.
        """
        from auto_patch import adjacent_ground as AG
        monkeypatch.setenv(FLAG, "1")
        lay, floor = self._bore_layout()
        gs._grade_limit_groundside_chords(lay)
        assert _alts(floor) == [FLOOR_Z] * 7, (
            "the below-grade values did NOT survive — the exemption is "
            "not doing its job")
        road = lay.shapes[0]
        assert _alts(road)[0] == FLOOR_Z and _alts(road)[1] == FLOOR_Z, (
            "the road did not read the groundside value back at the "
            "shared weld")
        assert AG.emit_authority_retreat_walls(lay) == 0
        assert not self._walls(lay), (
            "a face was minted at a weld the two claimants AGREE on — "
            "that would contradict weld-or-gap")

    def test_off_the_faces_vanish_too_but_for_the_opposite_reason(
            self, monkeypatch):
        """The capture's own arm: the claimants also agree — but at the
        ROAD's bench, with the bore floor dragged up to meet it.  Same
        face count, opposite surface; the ramp values are the thing the
        twin distinguishes them by."""
        from auto_patch import adjacent_ground as AG
        monkeypatch.setenv(FLAG, "0")
        lay, floor = self._bore_layout()
        gs._grade_limit_groundside_chords(lay)
        assert max(_alts(floor)) > FLOOR_Z + 0.5
        AG.emit_authority_retreat_walls(lay)
        assert not self._walls(lay)


# ═════════════════════════════════════════════════════════════════════
# (d) the kill switch
# ═════════════════════════════════════════════════════════════════════

class TestTheFlagOffIsTodaysBehaviour:
    """Spec §5 — OFF is the pre-fix pass, bit for bit, for attribution
    arms."""

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

    def test_the_flag_defaults_ON(self, monkeypatch):
        """Default ON (spec §5): the production build carries the fix."""
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
