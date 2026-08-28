"""§W1 — A WALL FOLLOWS ITS CLAIM AS IT FOLLOWS ITS RAMP.

Spec ``docs/specs/claimed-corridor-wall-survival-spec.md`` §W1.

MEASURED (OTHH, app 1.0.264).  ``_wall_claimed_corridors`` mints the
walls — "§2.3 claimed-corridor walls: 15 bodies walled (20 pieces)" — and
the covered-vs-graze discriminator in :func:`_finalize_tunnel_emission`
then deletes them: ``[tunnel-remove] covered-stretch drop: ref=tunnel_wall
way=2291 @25.2559488,51.6086658 coverage=0.743 area=319.4m2`` at the
owner's own site, plus ways 2330/2341/2342 on the same portal at
0.948/0.964/0.985.

WHY.  Ruling 4 judges wall/roof pieces against the POST-CUT pavement
union so a wall is never dropped for overlapping pavement its own ramp
removed.  Only SYNTHETIC ramps cut.  A claimed corridor lowers its host
WITHOUT cutting it (the mouth-D claim design, RULINGS 2026-08-25e option
(a)), so a claim-flank wall overlaps host pavement 50-100 % and drops
whole as a "covered stretch".

THE THREE ARMS below are the whole of the law: the wall survives over a
claim; it still drops where the stretch is genuinely ROOFED (the item-12
covered-span mask — the §W1 scope guard); and with the gate OFF the
adjudication is the pre-round one, piece for piece.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch import bridges
from auto_patch.layout import (BuiltShape, PavementLayout, ROLE_APRON,
                               ROLE_RETAINING_WALL, ROLE_TUNNEL_RAMP,
                               TUNNEL_ROAD_REF)

GRADE_Z = 4.0
BORE_Z = -1.1
#: the emitter's own annulus — ``wall_gap_m + retaining_wall_width_m``,
#: the geometry the perimeter band occupies (spec §2 W/G-1).
WALL_GAP_M = 0.6
WALL_WIDTH_M = 1.0
CLEARANCE_M = WALL_GAP_M + WALL_WIDTH_M


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _scene():
    """A claimed corridor through a host apron, walled on its flank.

    The wall band sits ENTIRELY on host pavement — coverage 1.0, the
    OTHH population's worst case — because the claim never cut the host.
    """
    host = BuiltShape(polygon=_rect(0, 0, 100, 40), role=ROLE_APRON,
                      ref=None, altitude=GRADE_Z)
    claim = BuiltShape(polygon=_rect(0, 15, 100, 25),
                       role=ROLE_TUNNEL_RAMP, ref=TUNNEL_ROAD_REF,
                       node_altitudes=[BORE_Z] * 5)
    wall = BuiltShape(polygon=_rect(0, 25.6, 100, 26.4),
                      role=ROLE_RETAINING_WALL, ref="tunnel_wall",
                      altitude=GRADE_Z)
    lay = PavementLayout(icao="KFAKE", anchor=(25.0, 51.0))
    lay.shapes.extend([host, claim, wall])
    # THE PUBLISHED POPULATION, not a re-derivation: the register is what
    # ``_wall_claimed_corridors`` walled (§T6.3).
    setattr(lay, bridges._CLAIMED_BORE_REGISTER, {id(claim)})
    pre_emit = {id(host), id(claim)}
    return lay, host, claim, wall, pre_emit


def _finalize(lay, host, pre_emit):
    return bridges._finalize_tunnel_emission(
        lay, [], 0.0, host.polygon, pre_emit, 1,
        ramp_way_ids={}, ramp_cut_clearance_m=CLEARANCE_M,
        protected_union=None)


def _walls(lay):
    return [s for s in lay.shapes
            if getattr(s, "ref", "") == "tunnel_wall"]


def test_claim_flank_wall_survives_its_host(monkeypatch):
    """§W1: the claim footprint + the wall band's annulus come out of the
    wall/roof adjudication union, so the band the claim just minted is
    not deleted for standing on the pavement the claim lowered."""
    monkeypatch.delenv(bridges._CLAIM_WALL_GATE_ENV, raising=False)
    lay, host, claim, wall, pre_emit = _scene()
    _finalize(lay, host, pre_emit)
    assert _walls(lay), (
        "the claim-flank wall was dropped as a covered stretch — §W1's "
        "subtraction did not reach the adjudication union")
    # ADJUDICATION ONLY: the host keeps every square metre of its ring.
    assert host.polygon.equals(_rect(0, 0, 100, 40))
    assert claim.polygon.equals(_rect(0, 15, 100, 25))


def test_covered_span_stretch_still_drops_its_wall(monkeypatch):
    """The §W1 scope guard: a claim stretch that is ALSO in the item-12
    covered-span mask is a genuinely ROOFED span — no visible structure,
    so its wall still drops.  ``covered_span_clean`` stays 0."""
    monkeypatch.delenv(bridges._CLAIM_WALL_GATE_ENV, raising=False)
    lay, host, claim, wall, pre_emit = _scene()
    # The published mask (``covered_span.mask_of``), not a second one.
    setattr(lay, "_covered_span_mask", _rect(-10, 10, 110, 30))
    _finalize(lay, host, pre_emit)
    assert not _walls(lay), (
        "a wall over a ROOFED claim stretch survived — the covered-span "
        "scope guard is not holding the relief back")


def test_gate_off_is_the_pre_round_adjudication(monkeypatch):
    """OFF is byte-identical to base: the same piece drops, through the
    same named ledger predicate."""
    monkeypatch.setenv(bridges._CLAIM_WALL_GATE_ENV, "0")
    lay, host, claim, wall, pre_emit = _scene()
    _finalize(lay, host, pre_emit)
    assert not _walls(lay)


def test_no_claim_leaves_the_gate_object_untouched(monkeypatch):
    """No claimed corridor ⇒ the judging union is the post-cut object
    ITSELF, so an airport with no claim is byte-identical."""
    monkeypatch.delenv(bridges._CLAIM_WALL_GATE_ENV, raising=False)
    lay, host, claim, wall, pre_emit = _scene()
    setattr(lay, bridges._CLAIMED_BORE_REGISTER, set())
    gate = bridges._claim_wall_adjudication_gate(
        lay, host.polygon, CLEARANCE_M)
    assert gate is host.polygon


def test_relief_is_the_register_not_every_tunnel_road(monkeypatch):
    """The population is the PUBLISHED register — a ``tunnel_road`` shape
    the waller judged to be at-grade (below ``_CLAIM_WALL_MIN_DIG_M``) is
    not bore geometry and buys no relief."""
    monkeypatch.delenv(bridges._CLAIM_WALL_GATE_ENV, raising=False)
    lay, host, claim, wall, pre_emit = _scene()
    setattr(lay, bridges._CLAIMED_BORE_REGISTER, set())
    _finalize(lay, host, pre_emit)
    assert not _walls(lay)
