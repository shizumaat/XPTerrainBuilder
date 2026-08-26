"""THE PORTAL CORRIDOR CLAIM + the per-piece named refusals.

Spec: ``docs/specs/portal-corridor-claim-spec.md`` (Fable, 2026-08-25),
implementing owner ruling ``docs/RULINGS.md`` 2026-08-25e — "A PORTAL
APPROACH ON UNCLAIMED PAVEMENT CLAIMS AND LOWERS IT", option (a) of the
mouth-D disposition.

THE EVIDENCE.  OTHH mouth D is ADMITTED and EMITTED
("[tunnel-cover-bore] admitted on cover (pavement=0.993)") and then
every piece of it is removed by three aggregate-logging passes — the
covered-stretch drop, the graze-clip and R14-1's stand-down.  4 of 8
OTHH portal clusters lose every ramp that way, and because no remover
NAMED what it deleted, the acceptance instrument could only report the
mouth as 806.1 m away: absence was all there was to see.

TWO CHANGES, and §1 comes first because it is required either way:

§1 THE INSTRUMENT (ungated, mandatory).  Every post-emit tunnel-piece
   remover logs ONE LINE PER PIECE — predicate, ref, way, centroid,
   coverage.  Aggregate summaries may stay; the per-piece lines are the
   law.  A silent aggregate is the defect that made mouth D
   unattributable for three weeks.
§2 THE CLAIM (gated ``O4_PORTAL_CORRIDOR_CLAIM``, default ON).  Where a
   mapped mouth's approach lands on pavement R14-1 may not claim, the
   ramp claims the CORRIDOR FOOTPRINT — the ramp-width strip — and
   lowers it to the bore profile.  The footprint only, never the host
   whole: a 673,901 m² apron crossed by an 8 m ramp cedes the 8 m strip
   and keeps its role, its law and the rest of its area.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Polygon

from auto_patch import bridges
from auto_patch.layout import (BuiltShape, PavementLayout, ROLE_APRON,
                               ROLE_GROUNDSIDE_PAVEMENT, ROLE_TUNNEL_RAMP)

CLAIM_FLAG = "O4_PORTAL_CORRIDOR_CLAIM"


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    lay = PavementLayout(icao="KFAKE", anchor=(25.0, 51.0))
    lay.shapes.extend(shapes)
    return lay


def _portal(walk, width=8.0, grade=0.0):
    """A ``portal_data`` row shaped as ``_tunnel_open_cut_regions`` reads
    it: index 2 is the walk, 7 the carriageway width, 9 the mouth
    grade."""
    row = [None] * 12
    row[2] = list(walk)
    row[7] = float(width)
    row[9] = float(grade)
    row[11] = None
    return row


# ═════════════════════════════════════════════════════════════════════
# §1 the instrument — one line PER PIECE
# ═════════════════════════════════════════════════════════════════════

class TestEveryRemovedPieceIsNamed:
    """Spec §1.2 — the line carries the piece's identity, and the
    summary count equals the line count."""

    def test_the_line_names_the_piece_and_where_it_was(self, capsys):
        lay = _layout([])
        piece = BuiltShape(polygon=_rect(0, 0, 10, 4),
                           role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp")
        bridges.log_tunnel_piece_removal(
            lay, piece, "covered-stretch drop", coverage=0.993, index=7)
        out = capsys.readouterr().out
        assert "[tunnel-remove] covered-stretch drop:" in out
        assert "ref=tunnel_ramp" in out and "way=7" in out
        assert "coverage=0.993" in out
        # THE CENTROID IS THE JOIN KEY — a removed piece has no emitted
        # id, so where it was is all that survives.
        assert "@25." in out and ",51." in out

    def test_the_instrument_never_takes_a_build_down(self, capsys):
        """An instrument that can raise is a remover with a new failure
        mode.  A shape with no geometry still gets a line."""
        lay = _layout([])
        broken = BuiltShape(polygon=None, role="", ref="")
        bridges.log_tunnel_piece_removal(lay, broken, "graze-clip")
        assert "[tunnel-remove] graze-clip:" in capsys.readouterr().out

    def test_it_is_UNGATED(self):
        """§1 is law, not behaviour: no env flag may silence it.  The
        gate that exists belongs to §2 alone."""
        import inspect
        src = inspect.getsource(bridges.log_tunnel_piece_removal)
        assert "environ" not in src and "getenv" not in src

    def test_every_removal_counter_has_a_named_line(self):
        """The structural half: each place a post-emit pass DROPS a
        tunnel piece must call the instrument.  Counting the call sites
        against the drop sites is what stops a fifth silent remover
        being added later."""
        import inspect
        src = inspect.getsource(bridges)
        body = src.split("def _finalize_tunnel_emission", 1)[1]
        body = body.split("def _record_tunnel_mouth_walling", 1)[0]
        drops = body.count("_n_clip += 1") + body.count("_n_wclip += 1")
        named = body.count("log_tunnel_piece_removal(")
        assert named >= drops, (
            f"{drops} drop site(s) but only {named} named line(s) — a "
            f"silent remover is the mouth-D defect")


# ═════════════════════════════════════════════════════════════════════
# §2 (a) the corridor strip is claimed and lowered
# ═════════════════════════════════════════════════════════════════════

class TestTheCorridorFootprintIsClaimed:
    """Twin (a): a mouth whose approach crosses a pavement ring."""

    def _scene(self, role=ROLE_APRON):
        # a big host ring, and a walk crossing it end to end
        host = BuiltShape(polygon=_rect(-50, -50, 50, 50), role=role,
                          ref="apron", node_altitudes=[10.0] * 5)
        lay = _layout([host])
        pre = {id(s) for s in lay.shapes}
        portal = _portal([(0.0, -200.0), (0.0, 200.0)], width=8.0,
                         grade=2.0)
        return lay, host, pre, [portal]

    def test_on_the_strip_is_cut_out_and_lowered(self, monkeypatch,
                                                 capsys):
        monkeypatch.setenv(CLAIM_FLAG, "1")
        lay, host, pre, portals = self._scene()
        n = bridges._claim_portal_corridor_footprint(
            lay, portals, [], 0.6, pre)
        assert n >= 1, "no corridor strip was claimed"
        strips = [s for s in lay.shapes
                  if getattr(s, "ref", "") == bridges.TUNNEL_ROAD_REF]
        assert strips, "the claimed strip was not minted"
        strip = strips[0]
        assert strip.role == ROLE_TUNNEL_RAMP
        assert min(strip.node_altitudes) < 10.0, (
            "the claim did not LOWER the strip to the bore profile")
        # …and only where the profile is BELOW the host: the approach
        # climbs back to ambient, so the far end keeps its own value.
        # The claim can only dig (R14-1's law, inherited).
        assert max(strip.node_altitudes) == pytest.approx(10.0)
        # …and it is NAMED (§1's positive twin)
        out = capsys.readouterr().out
        assert "[tunnel-claim] corridor footprint:" in out
        assert "host_role=apron" in out

    def test_the_host_keeps_its_role_law_and_remaining_area(
            self, monkeypatch):
        """Twin (c): FOOTPRINT-SCOPED.  The host is CUT, never claimed —
        a 100x100 m ring crossed by an ~9 m strip keeps ~91 % of itself,
        its role and its ref."""
        monkeypatch.setenv(CLAIM_FLAG, "1")
        lay, host, pre, portals = self._scene()
        before = host.polygon.area
        bridges._claim_portal_corridor_footprint(lay, portals, [], 0.6, pre)
        kept = [s for s in lay.shapes if s.role == ROLE_APRON]
        assert host.role == ROLE_APRON and host.ref == "apron"
        total = sum(s.polygon.area for s in kept)
        assert total < before, "nothing was cut out of the host"
        assert total > 0.80 * before, (
            f"the claim took {100 * (1 - total / before):.0f} % of the "
            f"host — §2 is the corridor FOOTPRINT, never the shape whole")
        # the crossing splits the host in two: BOTH sides survive
        assert len(kept) == 2, (
            "the corridor severed the host and a side was dropped")

    def test_off_nothing_is_claimed(self, monkeypatch):
        """(b)/§2.5: the gate is real — OFF is today's behaviour, and
        today's behaviour is that the host keeps the corridor and the
        ramp above it is removed (with §1's named line, which is
        ungated)."""
        monkeypatch.setenv(CLAIM_FLAG, "0")
        lay, host, pre, portals = self._scene()
        before = host.polygon.area
        assert bridges._claim_portal_corridor_footprint(
            lay, portals, [], 0.6, pre) == 0
        assert host.polygon.area == before
        assert not [s for s in lay.shapes
                    if getattr(s, "ref", "") == bridges.TUNNEL_ROAD_REF]

    def test_a_host_that_would_not_survive_is_left_alone(self,
                                                         monkeypatch):
        """§2.2's hard edge: "never the host shape whole".  A ring
        narrower than the corridor would be consumed, so it is NOT
        claimed — R14-1's airside finding keeps speaking for it."""
        monkeypatch.setenv(CLAIM_FLAG, "1")
        narrow = BuiltShape(polygon=_rect(-3, -20, 3, 20),
                            role=ROLE_APRON, ref="apron",
                            node_altitudes=[10.0] * 5)
        lay = _layout([narrow])
        pre = {id(s) for s in lay.shapes}
        portal = _portal([(0.0, -200.0), (0.0, 200.0)], width=8.0,
                         grade=2.0)
        assert bridges._claim_portal_corridor_footprint(
            lay, [portal], [], 0.6, pre) == 0
        assert narrow.polygon.area == pytest.approx(6 * 40)

    def test_a_corridor_already_below_the_pavement_claims_nothing(
            self, monkeypatch):
        """THE CLAIM CAN ONLY DIG (R14-1's own law, inherited).  Where
        the profile is already above the host's surface there is nothing
        to lower, so no strip is cut."""
        monkeypatch.setenv(CLAIM_FLAG, "1")
        low = BuiltShape(polygon=_rect(-50, -50, 50, 50), role=ROLE_APRON,
                         ref="apron", node_altitudes=[-40.0] * 5)
        lay = _layout([low])
        pre = {id(s) for s in lay.shapes}
        portal = _portal([(0.0, -200.0), (0.0, 200.0)], width=8.0,
                         grade=2.0)
        assert bridges._claim_portal_corridor_footprint(
            lay, [portal], [], 0.6, pre) == 0
        assert low.polygon.area == pytest.approx(100 * 100)

    def test_a_tunnel_piece_is_never_a_host(self, monkeypatch):
        """The claim is FOR the emitted pieces; it may not eat them.
        Only pre-existing pavement is a host."""
        monkeypatch.setenv(CLAIM_FLAG, "1")
        host = BuiltShape(polygon=_rect(-50, -50, 50, 50), role=ROLE_APRON,
                          ref="apron", node_altitudes=[10.0] * 5)
        lay = _layout([host])
        pre = {id(s) for s in lay.shapes}
        ramp = BuiltShape(polygon=_rect(-4, -60, 4, 60),
                          role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                          node_altitudes=[2.0] * 5)
        lay.shapes.append(ramp)          # emitted AFTER the snapshot
        portal = _portal([(0.0, -200.0), (0.0, 200.0)], width=8.0,
                         grade=2.0)
        bridges._claim_portal_corridor_footprint(lay, [portal], [], 0.6, pre)
        assert ramp.polygon.area == pytest.approx(8 * 120), (
            "the corridor claim cut the very ramp it exists to protect")

    def test_a_landside_host_is_claimed_too(self, monkeypatch):
        """The ruling says "airside OR LANDSIDE pavement" — the class is
        "pavement the walk can neither cut nor claim", not a role."""
        monkeypatch.setenv(CLAIM_FLAG, "1")
        lay, host, pre, portals = self._scene(
            role=ROLE_GROUNDSIDE_PAVEMENT)
        assert bridges._claim_portal_corridor_footprint(
            lay, portals, [], 0.6, pre) >= 1


# ═════════════════════════════════════════════════════════════════════
# (d) R14-1's own machinery is unregressed
# ═════════════════════════════════════════════════════════════════════

class TestOneClaimAuthority:
    """Twin (d) — the corridor claim EXTENDS R14-1; it does not fork it.
    The region, the profile and the ref all come from the same place."""

    def test_the_region_is_the_portal_walks_own(self):
        import inspect
        src = inspect.getsource(bridges._claim_portal_corridor_footprint)
        assert "_tunnel_open_cut_regions(" in src, (
            "the corridor claim derived its own zone — one region "
            "authority (spec §2.1)")
        assert "TUNNEL_APPROACH_GRADE" in src, (
            "the profile must be R14-1's, not a second grade constant")
        assert "TUNNEL_ROAD_REF" in src

    def test_the_stand_down_still_fires_for_synthetic_over_claimed(self):
        """R14-1's existing stand-down is untouched: a synthetic rect
        over ALREADY-claimed pavement still goes — now with its named
        line."""
        lay = _layout([])
        claimed = _rect(0, 0, 40, 10)
        rect = BuiltShape(polygon=_rect(5, 1, 35, 9),
                          role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                          node_altitudes=[1.0] * 5)
        lay.shapes.append(rect)
        n = bridges._stand_down_synthetic_over_claimed(lay, claimed, set())
        assert n == 1
        assert rect not in lay.shapes


# ═════════════════════════════════════════════════════════════════════
# THE PHANTOM CLAIM (mouth D's real blocker, measured 2026-08-25)
# ═════════════════════════════════════════════════════════════════════

class TestTheStandDownJudgesTheCorridorNotTheShape:
    """THE MOUTH-D MECHANISM, and the fix RULINGS 2026-08-25e requires
    ("mouth D must emit").

    MEASURED, from the §1 instrument's first run: mouth D's four ramp
    pieces (919.5, 934.5, 934.5, 817.6 m²) were deleted at share=1.000
    by ONE claimant — 19,461.6 m², 1,525 m of perimeter, centroid 147 to
    258 m away.  A long service lot covers the open cut at one end and
    blankets a DIFFERENT mouth's approach at the other, where it sits at
    grade and carries no tunnel surface at all.  The claim was not
    mis-anchored and it had not outlived its road: it was JUDGED WHOLE.

    ``_claim_road_pavement`` re-profiles a claimed road IN PLACE and
    hands its consumers the shape's own polygon.  For the node book —
    "is this ring the bore's own geometry" — that is the right list and
    it is untouched (main's merged v1 rule reads exactly it).  For the
    stand-down — "does claimed road carry the corridor HERE" — it is
    not: the question is about the ground under the piece, so the answer
    is the claim ∩ THE CUT, the same region the claim was judged against
    in the first place.
    """

    def _scene(self):
        """A claimable road lot 500 m long: its west end lies in the
        cut, its east end is a plain lot — and a synthetic ramp sits on
        the east end, 300 m from anything the bore touches."""
        lot = BuiltShape(
            polygon=_rect(-20, -6, 480, 6),
            role=ROLE_GROUNDSIDE_PAVEMENT, ref="",
            node_altitudes=[10.0] * 5)
        lay = _layout([lot])
        pre = {id(s) for s in lay.shapes}
        far_ramp = BuiltShape(polygon=_rect(400, -4, 460, 4),
                              role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                              node_altitudes=[9.0] * 5)
        near_ramp = BuiltShape(polygon=_rect(-15, -4, 20, 4),
                               role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                               node_altitudes=[2.0] * 5)
        lay.shapes.extend([far_ramp, near_ramp])
        portal = _portal([(0.0, 0.0), (60.0, 0.0)], width=8.0, grade=2.0)
        return lay, lot, far_ramp, near_ramp, [portal]

    def test_the_claim_returns_its_corridor_footprint(self, monkeypatch):
        """The claim hands on BOTH: the whole shapes (the node book's
        list, unchanged) and their corridor footprints."""
        monkeypatch.setenv(CLAIM_FLAG, "1")
        lay, lot, _far, _near, portals = self._scene()
        n, whole, corridor = bridges._claim_road_pavement(
            lay, portals, [], 0.6)
        assert n >= 1, "the lot was not claimed at all"
        assert whole and corridor
        assert whole[0].area == pytest.approx(500 * 12)
        # corridor members are ``(polygon, depth)``: the footprint AND
        # the depth the claim gave it (Amendment 1 needs both)
        _cpoly, _cdepth = corridor[0]
        assert _cdepth is not None
        assert _cpoly.area < 0.5 * whole[0].area, (
            "the corridor footprint is the whole shape again — the "
            "mouth-D phantom is back")

    def test_a_ramp_far_from_the_cut_survives(self, monkeypatch):
        """Mouth D's case in one assertion: a ramp over the claimed
        shape but NOT over the corridor is not redundant to anything, so
        it stays."""
        monkeypatch.setenv(CLAIM_FLAG, "1")
        lay, lot, far, near, portals = self._scene()
        _n, whole, corridor = bridges._claim_road_pavement(
            lay, portals, [], 0.6)
        pre = {id(s) for s in lay.shapes if s is lot}
        bridges._stand_down_synthetic_over_claimed(lay, corridor, pre)
        assert far in lay.shapes, (
            "the far ramp was stood down by a claim 300 m away — that "
            "is the mouth-D deletion")
        # (the NEAR ramp's fate is Amendment 1's question, not this
        # one's: this lot was graded out at the 5 % cap and never
        # levelled, so it does not carry bore depth — see
        # TestTheStandDownNeedsABoreDepthClaimant below.)

    def test_the_whole_shape_list_reproduces_the_phantom(self,
                                                         monkeypatch):
        """The control, one variable: judged against the WHOLE claimed
        shape — today's behaviour, and the flag's OFF path — the far
        ramp dies."""
        monkeypatch.setenv(CLAIM_FLAG, "1")
        lay, lot, far, near, portals = self._scene()
        _n, whole, _corridor = bridges._claim_road_pavement(
            lay, portals, [], 0.6)
        pre = {id(s) for s in lay.shapes if s is lot}
        bridges._stand_down_synthetic_over_claimed(lay, whole, pre)
        assert far not in lay.shapes

    def test_the_node_books_list_is_UNTOUCHED(self):
        """The merged v1 rule reads ``tunnel_open_cut_claim_polys`` and
        must keep reading whole claimed shapes — the fix changes which
        list the STAND-DOWN consumes, nothing else."""
        import inspect
        src = inspect.getsource(bridges._emit_tunnel_portals)
        assert "publish_tunnel_open_cut_claim_set(layout, _claimed)" in src, (
            "the publisher stopped receiving the whole-shape claim set — "
            "that would change the merged node-book rule")


# ═════════════════════════════════════════════════════════════════════
# AMENDMENT 1 — an AT-GRADE claimant never stands down a below-grade
# piece (the mouth-D fork, ruled)
# ═════════════════════════════════════════════════════════════════════

class TestTheStandDownNeedsABoreDepthClaimant:
    """Spec ``portal-corridor-claim-spec.md`` AMENDMENT 1.

    MEASURED (lane/tunnelmerge, OTHH): with the phantom whole-shape
    claim fixed to corridor footprints, mouth D's claimant is legitimate
    at share ~0.62 — and R14-1's own line reads "claimed 12 road
    surface(s) (0 LEVELLED AT BORE DEPTH, the rest graded out at the 5 %
    cap)".  No claimed surface carried the corridor anywhere on the
    field, so the pass was deleting the ONLY below-grade geometry the
    mouth had.  The pass exists to stop DUPLICATE corridor geometry; a
    claimant standing above the piece is not a duplicate of it, it is
    the ground the bore is cut into.
    """

    def _scene(self, lot_x0, ramp_z):
        """A claimable lot from ``lot_x0`` to +480 m and a synthetic ramp
        at the mouth.  With the lot's west edge AT the mouth its claimed
        vertices take the bore floor; set back 20 m they take the 5 %
        approach grade instead — the two cases the amendment separates,
        one scene, one variable.
        """
        lot = BuiltShape(
            polygon=_rect(lot_x0, -6, 480, 6),
            role=ROLE_GROUNDSIDE_PAVEMENT, ref="",
            node_altitudes=[10.0] * 5)
        lay = _layout([lot])
        ramp = BuiltShape(polygon=_rect(2, -4, 30, 4),
                          role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                          node_altitudes=[ramp_z] * 5)
        lay.shapes.append(ramp)
        portal = _portal([(0.0, 0.0), (60.0, 0.0)], width=8.0, grade=2.0)
        _n, _whole, corridor = bridges._claim_road_pavement(
            lay, [portal], [], 0.6)
        pre = {id(s) for s in lay.shapes if s is lot}
        return lay, lot, ramp, corridor, pre

    def test_an_at_grade_claimant_keeps_the_piece_and_NAMES_the_keep(
            self, capsys):
        """Mouth D's case: the claimant was graded out, not levelled, so
        it stands ABOVE the ramp — and the ramp is the only bore
        geometry there."""
        lay, lot, ramp, corridor, pre = self._scene(lot_x0=-20,
                                                    ramp_z=-1.1)
        n = bridges._stand_down_synthetic_over_claimed(lay, corridor, pre)
        assert n == 0
        assert ramp in lay.shapes, (
            "an at-grade claimant deleted the only below-grade geometry "
            "at the mouth — the measured mouth-D deletion")
        out = capsys.readouterr().out
        assert "[tunnel-keep] R14-1 stand-down REFUSED" in out
        assert "AT GRADE" in out, "the keep verdict was not named"

    def test_a_bore_depth_claimant_still_stands_the_piece_down(self,
                                                               capsys):
        """The other half, unregressed: where the claimed road really
        does carry the corridor, the synthetic rectangle beside it is
        still duplicate geometry and still goes — with its verdict."""
        lay, lot, ramp, corridor, pre = self._scene(lot_x0=0, ramp_z=2.0)
        n = bridges._stand_down_synthetic_over_claimed(lay, corridor, pre)
        assert n == 1, "the stand-down's own purpose did not survive"
        assert ramp not in lay.shapes
        out = capsys.readouterr().out
        assert "[tunnel-remove] R14-1 stand-down over claimed road" in out
        assert "carries bore depth" in out

    def test_an_unknown_depth_behaves_exactly_as_before(self):
        """A caller passing the WHOLE-SHAPE list (no depths) is every
        pre-Amendment caller: the pass must behave as it always did, so
        this amendment can only ever SAVE a piece it can prove is
        alone."""
        lay, lot, ramp, corridor, pre = self._scene(lot_x0=-20,
                                                    ramp_z=-1.1)
        whole = [_poly for _poly, _d in corridor]
        n = bridges._stand_down_synthetic_over_claimed(lay, whole, pre)
        assert n == 1 and ramp not in lay.shapes

    def test_the_tolerance_is_the_emits_own_scale(self):
        """Not a tuning knob: a claimant within the vertex-merge
        tolerance of the piece IS the piece's surface."""
        from auto_patch.layout import SHARED_VERTEX_TOL_M
        assert bridges._STAND_DOWN_BORE_DEPTH_TOL_M == pytest.approx(
            float(SHARED_VERTEX_TOL_M))
