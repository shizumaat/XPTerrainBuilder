"""WALLS FOLLOW THEIR RAMP, PRODUCTIVELY — the wall rewire.

Spec ``docs/specs/linear-transport-redesign-spec.md`` §5-SUPPLEMENT item
2 (spec author 2026-08-31), correcting this lane's owned deviation:

    Census #27/#28 said REWIRE and the lane retired instead: the
    claim-waller's population (17/39 walls, 20/48 feet at the OTHH
    control) must be REPLACED, not deleted — every merged ramp corridor
    side gets exactly one wall+foot derived from the ramp's own geometry
    through the existing wall-band machinery.

THE MEASUREMENT THAT ORDERED IT.  On the OTHH control, 17 of 39
``tunnel_wall`` and 20 of 48 ``tunnel_wall_foot`` pieces stood within
2 m of a claim surface and MORE than 2 m from any synthetic ramp — the
claim waller's own output, with no other producer.  Retiring it took
walls 39 → 12 and feet 48 → 12, leaving mouths unwalled.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch import bridges
from auto_patch.layout import (BuiltShape, PavementLayout,
                               ROLE_RETAINING_WALL, ROLE_TUNNEL_RAMP)

APT_ELEV = 4.0


def _layout():
    return PavementLayout("OTHH", anchor=(25.0, 51.0))


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _ramp(x0, y0, x1, y1, z=-1.0, ref="tunnel_ramp"):
    poly = _rect(x0, y0, x1, y1)
    return BuiltShape(polygon=poly, role=ROLE_TUNNEL_RAMP, ref=ref,
                      node_altitudes=[z] * len(poly.exterior.coords))


def _dem_at(x, y):
    return APT_ELEV


def _wall_pieces(lay):
    return [s for s in lay.shapes if s.role == ROLE_RETAINING_WALL]


def _run(lay, pre_emit=None):
    return bridges._wall_tunnel_ramp_corridors(
        lay, [], set(pre_emit or ()), 0.6, 1.0, _dem_at, APT_ELEV)


class TestABelowGradeRampGetsItsWall:

    def test_a_dug_ramp_is_walled(self):
        lay = _layout()
        lay.shapes.append(_ramp(0, 0, 8, 60, z=-1.0))
        assert _run(lay) == 1
        band = _wall_pieces(lay)
        assert band, "a dug bore corridor must be walled"
        refs = {s.ref for s in band}
        assert "tunnel_wall" in refs and "tunnel_wall_foot" in refs, (
            "the §T5 FOOT owns the annulus — walling without it "
            "reopens R16-2b")

    def test_a_tunnel_mouth_piece_counts_as_bore_geometry(self):
        """The population is the portal walk's own road surfaces, by
        role and ref — mouth pieces carry ROLE_TUNNEL_RAMP too."""
        lay = _layout()
        lay.shapes.append(_ramp(0, 0, 8, 60, z=-1.0, ref="tunnel_mouth"))
        assert _run(lay) == 1

    def test_an_at_grade_ramp_is_not_walled(self):
        """A surface that was never DUG is an at-grade stretch that
        happens to be tunnel-roled — the discriminator carried over from
        the retired claim waller, unchanged."""
        lay = _layout()
        lay.shapes.append(_ramp(0, 0, 8, 60, z=APT_ELEV - 0.01))
        assert _run(lay) == 0
        assert _wall_pieces(lay) == []

    def test_the_dig_is_measured_against_the_ground_not_zero(self):
        """LEMD's 561-617 m field is what makes an absolute predicate
        vacuous (§T8.1).  At a 600 m field a ramp at 598 m IS dug."""
        lay = _layout()
        lay.shapes.append(_ramp(0, 0, 8, 60, z=598.0))
        n = bridges._wall_tunnel_ramp_corridors(
            lay, [], set(), 0.6, 1.0, lambda x, y: 600.0, 600.0)
        assert n == 1


class TestOneWallPerSideNotTwo:

    def test_a_ramp_the_cluster_band_already_walled_is_skipped(self):
        """Ownership is READ from the register ``emit_wall_band``
        publishes as it appends — never re-derived by asking "which ramp
        is this wall near?".  That re-derivation is what put 7 wall
        pieces at one OTHH mouth (RULINGS 2026-08-30j)."""
        lay = _layout()
        ramp = _ramp(0, 0, 8, 60, z=-1.0)
        lay.shapes.append(ramp)
        existing = BuiltShape(polygon=_rect(-2, 0, -1, 60),
                              role=ROLE_RETAINING_WALL, ref="tunnel_wall",
                              altitude=APT_ELEV)
        lay.shapes.append(existing)
        setattr(lay, bridges._WALL_BAND_OWNER_REGISTER,
                {id(existing): (frozenset({id(ramp)}), 1.6)})
        assert _run(lay) == 0, (
            "the cluster band already owns this ramp — walling it again "
            "is the duplicate-wall defect")

    def test_an_unowned_ramp_beside_an_owned_one_is_still_walled(self):
        lay = _layout()
        owned = _ramp(0, 0, 8, 60, z=-1.0)
        unowned = _ramp(200, 0, 208, 60, z=-1.0)
        lay.shapes.extend([owned, unowned])
        w = BuiltShape(polygon=_rect(-2, 0, -1, 60),
                       role=ROLE_RETAINING_WALL, ref="tunnel_wall",
                       altitude=APT_ELEV)
        lay.shapes.append(w)
        setattr(lay, bridges._WALL_BAND_OWNER_REGISTER,
                {id(w): (frozenset({id(owned)}), 1.6)})
        assert _run(lay) == 1


class TestScope:

    def test_pre_existing_pavement_is_never_walled(self):
        """Only what THIS build emitted below grade is bore geometry."""
        lay = _layout()
        ramp = _ramp(0, 0, 8, 60, z=-1.0)
        lay.shapes.append(ramp)
        assert _run(lay, pre_emit={id(ramp)}) == 0

    def test_nothing_to_wall_is_a_no_op(self):
        lay = _layout()
        assert _run(lay) == 0
        assert lay.shapes == []

    def test_the_ends_are_WRAPPED_not_cut_open(self):
        """``arm_ends=[]`` is what "ends wrapped" means: a mouth's ends
        are the bore, unlike the cluster band whose far ends are cut
        OPEN because the road continues at grade there."""
        import inspect
        src = inspect.getsource(bridges._wall_tunnel_ramp_corridors)
        assert "emit_wall_band(layout, exclusion_zones, _parts, _sources, []" \
            in src.replace("\n", " ").replace("  ", " ") or \
            "_sources, []," in src

    def test_it_uses_the_one_waller(self):
        """ONE WALLER: a second wall emitter is the slightly-different
        duplicate this repo has already paid for (RULINGS 7e90032)."""
        import inspect
        src = inspect.getsource(bridges._wall_tunnel_ramp_corridors)
        assert "emit_wall_band(" in src
        assert "Polygon(" not in src, "it must not build its own band"

    def test_it_is_wired_into_the_portal_emit(self):
        import inspect
        src = inspect.getsource(bridges._emit_tunnel_portals)
        assert "_wall_tunnel_ramp_corridors(" in src

    def test_the_retired_claim_waller_is_still_gone(self):
        assert not hasattr(bridges, "_wall_claimed_corridors")
        assert not hasattr(bridges, "_claim_wall_adjudication_gate")
