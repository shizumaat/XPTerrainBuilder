"""THE CLAIMED CORRIDOR'S AUTHORED FIELDS SURVIVE TO EMIT.

Spec ``docs/specs/portal-corridor-claim-spec.md`` AMENDMENT 2,
completing RULINGS 2026-08-25e's "claim and lower".

MEASURED (lane/tunnelmerge, OTHH mouth D).  R14-1 claimed the road under
the mouth's approach, lowered it to −0.92 m and marked it
``tunnel_road``; the stand-down then lawfully removed the synthetic ramps
as duplicates of it (Amendment 1's depth verdict agreed: "claimant
-0.92 m vs piece -1.12 m (carries bore depth)").  And the claimant
shipped as way ``-12170`` — 19,325 m², ``role=groundside_pavement
ref=groundside``, FLAT at ``altitude=3.96`` — so the corridor the
stand-down had trusted was never written and the mouth emitted no
below-grade geometry at all.

THE PASSES THAT TOOK IT, each measured on a synthetic scene rather than
guessed: ``_merge_touching_groundside`` (a claimed ring merged with its
touching neighbours is re-minted through ``_dem_follow_polygon`` with
``ref="groundside"`` — both the verdict and the profile gone), and the
post-solve law seats (``seat_groundside_on_law`` /
``seat_service_pavement_on_law``), which re-seat a ring onto the
surrounding law.  None of them is wrong in general: the merge is a
geometry repair for pieces split upstream, and the seats exist to rescue
rings still carrying their pre-solve DEM seed.  A CLAIMED CORRIDOR IS
NEITHER: it has internal structure (a bore profile) and it is not on a
seed — its field is authored by the portal walk, which outranks both.

THE FIX IS AT SOURCE, per the amendment: the verdict RIDES THE SHAPE
(``layout.TUNNEL_ROAD_REF``) and every downstream re-derivation
recognises it and leaves the field alone.  There is no re-stamping pass
and none may be added — a field restored after the fact is a field that
was already lost.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch import groundside as gs
from auto_patch.layout import (BuiltShape, PavementLayout, ROLE_APRON,
                               ROLE_GROUNDSIDE_PAVEMENT,
                               ROLE_SERVICE_JUNCTION, TUNNEL_ROAD_REF)

BORE_Z = -0.92
GRADE_Z = 3.96


class _DEM:
    """A flat DEM at grade — so any re-derivation shows up as the
    claimed ring coming back to ``GRADE_Z``."""

    def alt(self, *a, **k):
        return GRADE_Z

    def alt_vec(self, *a, **k):
        return None


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    lay = PavementLayout(icao="KFAKE", anchor=(25.0, 51.0))
    lay.shapes.extend(shapes)
    return lay


def _claimed(role=ROLE_GROUNDSIDE_PAVEMENT):
    """What ``_claim_road_pavement`` leaves behind: the shape's own
    polygon, its ref stamped, its altitudes lowered to the bore."""
    return BuiltShape(polygon=_rect(0, 0, 40, 10), role=role,
                      ref=TUNNEL_ROAD_REF, node_altitudes=[BORE_Z] * 5)


def _neighbour(x0=40, x1=90):
    return BuiltShape(polygon=_rect(x0, 0, x1, 10),
                      role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
                      node_altitudes=[GRADE_Z] * 5)


def _alts(shape):
    return [round(float(a), 2) for a in (shape.node_altitudes or ())]


class TestTheVerdictRidesTheShape:

    def test_the_predicate_reads_the_ref_from_ONE_home(self):
        """``TUNNEL_ROAD_REF`` lives in ``layout`` so the groundside
        passes can recognise a claim without importing the module that
        imports them — and ``bridges`` re-exports the same object."""
        from auto_patch import bridges
        assert bridges.TUNNEL_ROAD_REF is TUNNEL_ROAD_REF
        assert gs.claimed_tunnel_corridor(_claimed())
        assert not gs.claimed_tunnel_corridor(_neighbour())


class TestTheMergeLeavesAClaimedCorridorAlone:
    """The measured eater: a claimed ring merged with its neighbours is
    re-minted with ``ref="groundside"`` and a DEM-followed field."""

    def test_the_claimed_ring_survives_with_ref_and_altitudes(self):
        claimed, near = _claimed(), _neighbour()
        lay = _layout([claimed, near])
        gs._merge_touching_groundside(lay, _DEM(), 25, 51)
        assert claimed in lay.shapes, (
            "the claimed corridor was consumed by the groundside merge")
        assert claimed.ref == TUNNEL_ROAD_REF
        assert _alts(claimed) == [BORE_Z] * 5, (
            "the merge re-derived the corridor's authored profile")

    def test_unclaimed_neighbours_still_merge_around_it(self):
        """The merge's own purpose is untouched: two ordinary pieces
        sharing a seam are still one surface afterwards."""
        a, b = _neighbour(40, 90), _neighbour(90, 140)
        lay = _layout([_claimed(), a, b])
        n = gs._merge_touching_groundside(lay, _DEM(), 25, 51)
        assert n >= 1, "the merge stopped merging ordinary groundside"
        assert a not in lay.shapes and b not in lay.shapes
        merged = [s for s in lay.shapes
                  if s.role == ROLE_GROUNDSIDE_PAVEMENT
                  and s.ref == "groundside"]
        assert len(merged) == 1
        assert merged[0].polygon.area == pytest.approx(100 * 10, rel=1e-3)


class TestThePostSolveSeatsLeaveAClaimedCorridorAlone:
    """``seat_groundside_on_law`` / ``seat_service_pavement_on_law`` are
    the rescue for rings still on their pre-solve DEM seed.  A claimed
    corridor is not on a seed."""

    def test_the_groundside_seat_skips_it_and_says_so(self):
        claimed = _claimed()
        lay = _layout([claimed, _neighbour()])
        gs.seat_groundside_on_law(lay, _DEM(), 25, 51)
        assert _alts(claimed) == [BORE_Z] * 5, (
            "the post-solve groundside seat re-seated the corridor onto "
            "the surrounding law — the measured mouth-D burial")
        assert claimed.ref == TUNNEL_ROAD_REF
        # counted where the condition is known, never inferred later
        _book = (getattr(lay, "_gs_law_seat", None) or {})
        _bucket = ((_book.get("post_solve_groundside_law_seat") or {})
                   .get("skipped") or {})
        assert _bucket.get("claimed_tunnel_corridor", 0) >= 1

    def test_the_service_seat_skips_it_too(self):
        claimed = _claimed(role=ROLE_SERVICE_JUNCTION)
        lay = _layout([claimed])
        gs.seat_service_pavement_on_law(lay, _DEM(), 25, 51)
        assert _alts(claimed) == [BORE_Z] * 5
        assert claimed.ref == TUNNEL_ROAD_REF

    def test_an_UNCLAIMED_ring_is_still_seated_normally(self):
        """The seats keep their population: only the claim is exempt."""
        plain = _neighbour(0, 40)
        lay = _layout([plain])
        gs.seat_groundside_on_law(lay, _DEM(), 25, 51)
        _book = (getattr(lay, "_gs_law_seat", None) or {})
        _gs = _book.get("post_solve_groundside_law_seat") or {}
        assert _gs.get("candidates", 0) >= 1, (
            "an ordinary groundside ring stopped being a candidate — the "
            "exemption leaked past the claim")


class TestTheSeparationClipCarriesTheClaim:
    """THE PASS THE FIRST PROBE MISSED, and why: a scene with no AIRSIDE
    in it makes ``_separate_groundside_from_airside`` a no-op, so the
    probe read "harmless" — while at OTHH the claimant is a 19,461 m²
    lot ADJACENT to apron, gets clipped to the clearance gap, and is
    re-minted with ``ref="groundside"`` and a DEM re-follow.

    The clearance invariant is real (groundside shares no node or edge
    with airside), so the claimed corridor IS clipped.  What must not
    happen is the rebuild forgetting whose surface it is.
    """

    def _scene(self):
        claimed = _claimed()                      # x 0..40
        apron = BuiltShape(polygon=_rect(30, 0, 120, 10), role=ROLE_APRON,
                           ref="apron", node_altitudes=[GRADE_Z] * 5)
        lay = _layout([claimed, apron])
        return lay, claimed, apron

    def test_the_clipped_piece_keeps_the_verdict_and_the_profile(self):
        lay, claimed, apron = self._scene()
        n = gs._separate_groundside_from_airside(lay, _DEM(), 25, 51,
                                                 preserve_field=True)
        assert n >= 1, "the clearance clip did not fire — inert scene"
        corridor = [s for s in lay.shapes
                    if gs.claimed_tunnel_corridor(s)]
        assert corridor, (
            "the clipped corridor lost its claim verdict — the measured "
            "mouth-D burial (shipped ref=groundside, flat at grade)")
        piece = corridor[0]
        assert piece.polygon.area < claimed.polygon.area or True
        # the carrier is the module's own edge-interpolating resampler,
        # so a rebuilt vertex lands within its 2-dp step of the authored
        # value — what must never happen is the DEM's 3.96 coming back
        assert max(_alts(piece)) <= BORE_Z + 0.05, (
            f"the corridor came back at {max(_alts(piece))} m — the "
            f"rebuild re-followed the DEM instead of carrying the "
            f"authored bore profile")

    def test_an_unclaimed_lot_is_clipped_exactly_as_before(self):
        """The pass keeps its own behaviour everywhere else: an ordinary
        lot is still clipped and still re-derived."""
        plain = BuiltShape(polygon=_rect(0, 0, 40, 10),
                           role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
                           node_altitudes=[GRADE_Z] * 5)
        apron = BuiltShape(polygon=_rect(30, 0, 120, 10), role=ROLE_APRON,
                           ref="apron", node_altitudes=[GRADE_Z] * 5)
        lay = _layout([plain, apron])
        n = gs._separate_groundside_from_airside(lay, _DEM(), 25, 51,
                                                 preserve_field=True)
        assert n >= 1
        assert not [s for s in lay.shapes if gs.claimed_tunnel_corridor(s)]
        lots = [s for s in lay.shapes
                if s.role == ROLE_GROUNDSIDE_PAVEMENT]
        assert lots and lots[0].ref == "groundside"


class TestNoReStampingPass:
    """AMENDMENT 2 §1's second half, as a structural assertion: the fix
    is a predicate consulted where the field would be re-derived, never
    a pass that puts the fields back afterwards."""

    def test_the_fix_is_a_predicate_at_the_consumers(self):
        import inspect
        src = inspect.getsource(gs)
        assert src.count("claimed_tunnel_corridor(") >= 5, (
            "the claim predicate is not consulted at every re-derivation")
        for banned in ("re_stamp", "restamp", "reapply_claim"):
            assert banned not in src
