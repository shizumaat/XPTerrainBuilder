"""Spec §59 (owner RULINGS 2026-10-08c (6), 08g): a gap piece classed APRON
is a stage-1 ``apron`` cell, ref ``gapapron:<j>`` — the names, and the one
planar consumer that must not see it (the zone claim: "with the runway held
at zero")."""
from __future__ import annotations

from shapely.geometry import box

from auto_patch_v2.classify.roles import Cell, is_late_cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_side
from auto_patch_v2.model import planar as mp
from auto_patch_v2.planar.zones import zone_regions

LAW = Law.for_airport("HECA")


def _ring(b):
    return tuple(b.exterior.coords)[:-1]


def _cell(i, role, ref, b, code_number=None, code_letter=None):
    return Cell(i, role, ref, _ring(b), (), code_number, code_letter,
                role_side(LAW, role), role, {})


def test_a_gap_apron_ref_is_no_gap_piece_and_is_not_late():
    ref = f"{mp.GAP_APRON_PREFIX}:3"
    assert mp.is_gap_apron_ref(ref) and mp.is_gap_apron_ref(ref + "#1")
    assert not mp.is_gap_ref(ref) and not mp.is_late_ref(ref)
    assert not mp.is_gap_apron_ref("gap:3") and not mp.is_gap_apron_ref("pav3")
    assert not mp.is_gap_apron_ref(None)
    assert mp.gap_part_kind(ref) is None and not mp.gap_step_part(ref)
    # a stage-1 cell: never dropped from the ribbon-free / gap-free maps
    assert not is_late_cell(_cell(0, "apron", ref, box(0, 0, 1, 1)))


def _zones(cells):
    return [(z.ref, z.polygon.wkb_hex) for z in zone_regions(tuple(cells), LAW)]


def test_a_gap_apron_cell_is_not_in_the_zone_claim():
    """The zone bands are the STANDING cells' (§59, the runway's planar
    half): a gap-apron cell — minted outside every band's envelope — leaves
    every band byte-identical, however the claim's union would re-node."""
    runway = _cell(0, "runway", "05/23", box(0, 0, 3000, 60), code_number=4)
    taxi = _cell(1, "junction", "pav9", box(1000, 60, 1030, 400), code_letter="E")
    apron = _cell(2, "apron", "pav1", box(900, 400, 1200, 700))
    base = _zones([runway, taxi, apron])
    assert base                                           # there ARE bands here
    far = _cell(3, "apron", "gapapron:0", box(1200, 420, 1260, 480))
    assert _zones([runway, taxi, apron, far]) == base
    # the same polygon as a standing apron IS in the claim (today's rule)
    assert _zones([runway, taxi, apron,
                   _cell(3, "apron", "pav2", box(1035, 100, 1100, 160))]) != base


def test_a_gap_apron_cell_that_reaches_a_band_is_cut_out_of_that_band():
    """Planarity is kept where the stand-off did not hold: the band yields
    the cell's ground, and no other band moves."""
    runway = _cell(0, "runway", "05/23", box(0, 0, 3000, 60), code_number=4)
    taxi = _cell(1, "junction", "pav9", box(1000, 60, 1030, 400), code_letter="E")
    part = box(1035, 100, 1100, 160)
    got = zone_regions((runway, taxi, _cell(2, "apron", "gapapron:0", part)), LAW)
    assert got and all(z.polygon.intersection(part).area < 1e-6 for z in got)
