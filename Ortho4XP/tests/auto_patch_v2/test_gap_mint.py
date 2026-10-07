"""Twins of the §53 gap mint (issues #292, #358; owner RULINGS 2026-10-04o
(a), (b)): the mint only APPENDS; a piece is the sheet minus every cell
standing and every pad's set-back; the floor; the apron contact is the §27
length and is published; a piece along a runway / taxi face and no apron
is not minted; every piece is a LATE cell."""
from __future__ import annotations

import copy
import types

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.classify import gap_mint as gm
from auto_patch_v2.classify.roles import Cell, is_late_cell
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap, role_side, rolled_on_roles
from auto_patch_v2.model import planar as mp
from auto_patch_v2.model.airport import Pavement

LAW, RULES = Law.for_airport("HECA"), load_rules()


def _ring(b):
    return tuple(b.exterior.coords)[:-1]


def _cell(i, role, ref, b):
    return Cell(i, role, ref, _ring(b), (), None, None, role_side(LAW, role), role, {})


def _airport(*sheets):
    frame = types.SimpleNamespace(
        transformers=lambda: (None, lambda x, y: (30.0 + y * 1e-5, 31.0 + x * 1e-5)))
    return types.SimpleNamespace(frame=frame, gap_sheets=tuple(
        Pavement(f"dsf:gapsheet{k}", None, _ring(s), (), "Airport/ground/asphalt.obj")
        for k, s in enumerate(sheets)))


def _mint(airport, cells):
    cells = list(cells)
    before = copy.deepcopy(cells)
    out, notes = [], []

    def add(role, ref, poly, kind, cn=None, cl=None, evidence=None):
        out.append((role, ref, poly, kind, dict(evidence or {})))
    stats = gm.mint_gap_pieces(airport, cells, LAW, RULES, add, notes)
    assert cells == before                 # THE MINT ONLY APPENDS (through add)
    return out, stats, notes


def test_a_piece_is_the_sheet_minus_every_cell_standing_and_the_pad_setback():
    apron = _cell(0, "apron", "pav1", box(0, 0, 100, 50))
    road = _cell(1, "service_road", "route3", box(0, 110, 100, 118))
    pad = _cell(2, "building", "building26", box(40, 70, 60, 90))
    out, stats, _ = _mint(_airport(box(-20, -20, 120, 140)), [apron, road, pad])
    assert [ref for _r, ref, *_ in out] == ["gap:0"]
    piece = out[0][2]
    for c in (apron, road, pad):
        assert piece.intersection(Polygon(c.ring)).area == pytest.approx(0.0, abs=1e-6)
    ident = LAW.tables.emit.identity.min_distinct_spacing_m
    # one identity cell beyond the pad set-back — the facade strip's stand-off
    # — from the pad AND from the road; flush on the apron rim only
    assert piece.distance(Polygon(pad.ring)) == pytest.approx(0.95 + ident, abs=0.02)
    assert piece.distance(Polygon(road.ring)) == pytest.approx(0.95 + ident, abs=0.02)
    assert piece.distance(Polygon(apron.ring)) == 0.0
    assert stats["gap_pieces"] == 1 and stats["gap_piece_m2"] == pytest.approx(piece.area)


def test_no_sheet_mints_nothing_and_a_missing_attribute_is_no_sheet():
    apron = _cell(0, "apron", "pav1", box(0, 0, 100, 50))
    assert _mint(_airport(), [apron])[0] == []
    assert _mint(types.SimpleNamespace(), [apron])[0] == []


def test_the_apron_contact_is_the_section_27_length_and_is_published():
    apron = _cell(0, "apron", "pav1", box(0, 0, 100, 50))
    out, stats, _ = _mint(_airport(box(0, 50, 100, 90), box(300, 0, 340, 40)), [apron])
    # weld-tolerant: the 100 m shared run plus the weld spacing up each side
    by = sorted((e["apron_shared_m"], role, e["touches_apron"]) for role, _ref, _p, _k, e in out)
    assert by[0] == (0.0, gm.ROLE, 0.0)
    assert 100.0 <= by[1][0] <= 103.0 and by[1][1:] == (gm.APRON_TOUCH_ROLE, 1.0)
    assert stats["gap_pieces_apron"] == 1
    assert RULES.lot.airside_edge_min_m == 10.0


def test_the_floor_is_the_area_and_a_lane_wide_disc():
    lane = LAW.tables.emit.road_profile.lane_width_m
    small = box(0, 0, 10, 10)                            # under 200 m2
    hair = box(100, 0, 100 + 0.5 * lane, 400)            # 800 m2, half a lane wide
    ok = box(300, 0, 300 + 2 * lane, 100)
    out, stats, _ = _mint(_airport(small, hair, ok), [])
    assert len(out) == 1 and out[0][2].bounds[0] == pytest.approx(300.0)
    assert stats["gap_pieces_under_floor"] == 2


def test_a_piece_along_a_runway_or_taxi_face_and_no_apron_is_not_minted(monkeypatch):
    """Where the taxi face carries NO band (the envelope is empty) a piece
    running along it and touching no apron is listed, not minted; with a
    band the piece is trimmed off it instead (the band twin below)."""
    from auto_patch_v2.classify import ribbon_mint
    monkeypatch.setattr(ribbon_mint, "ribbon_extent", lambda cells, law, pu: Polygon())
    taxi = _cell(0, "junction", "pav9", box(0, 0, 100, 30))
    out, stats, notes = _mint(_airport(box(0, 30, 100, 60)), [taxi])
    assert out == [] and stats["gap_pieces_unminted_airside"] == 1
    assert "NOT minted" in notes[0] and "2,855 m2" in notes[0]
    # ...and with an apron contact as well it IS minted
    apron = _cell(1, "apron", "pav1", box(100, 30, 160, 60))
    out, _s, _n = _mint(_airport(box(0, 30, 100, 60)), [taxi, apron])
    assert len(out) == 1 and out[0][4]["touches_apron"] == 1.0


def test_a_gap_piece_is_a_late_groundside_cell_at_the_road_cap():
    assert mp.is_gap_ref("gap:3") and mp.is_late_ref("gap:3#1")
    assert not mp.is_gap_ref("gapx:3") and not mp.is_osm_ribbon_ref("gap:3")
    assert is_late_cell(_cell(0, gm.ROLE, "gap:0", box(0, 0, 1, 1)))
    # R1 (master 2026-10-04): never a rolled-on role — pass C holds the
    # airside vertex set identical with and without the late cells
    for role in (gm.ROLE, gm.APRON_TOUCH_ROLE):
        assert role not in rolled_on_roles(LAW) and role_side(LAW, role) == "groundside"
        assert role_cap(LAW, role).longitudinal == role_cap(LAW, "service_road").longitudinal


def test_the_sheet_outline_is_simplified_before_the_difference():
    """A saw-tooth edge (the triangulation's teeth) under half the identity
    spacing is not emitted; the run shared with a standing cell is that
    cell's own boundary."""
    ident = LAW.tables.emit.identity.min_distinct_spacing_m
    teeth = [(x, 100.0 + (0.2 * ident if x % 2 else 0.0)) for x in range(0, 101)]
    sheet = Polygon([(0, 50), (100, 50), *reversed(teeth)])
    apron = _cell(0, "apron", "pav1", box(0, 0, 100, 50))
    out, _s, _n = _mint(_airport(sheet), [apron])
    assert len(out) == 1 and len(out[0][2].exterior.coords) <= 8
    assert out[0][2].bounds[1] == pytest.approx(50.0)


def test_a_piece_never_claims_the_runway_or_taxi_familys_band():
    """The adjacent-ground bands are not cells; the mint subtracts their
    un-trimmed envelope (``ribbon_mint.ribbon_extent``) like a standing cell."""
    from auto_patch_v2.classify.ribbon_mint import ribbon_extent
    taxi = Cell(0, "junction", "pav9", _ring(box(0, 0, 200, 30)), (), 4, "E", "airside",
                "junction", {})
    apron = _cell(1, "apron", "pav1", box(0, 300, 200, 400))
    band = ribbon_extent([taxi, apron], LAW, Polygon())
    assert band.area > Polygon(taxi.ring).area            # there IS a band here
    out, stats, _ = _mint(_airport(box(0, 30, 200, 300)), [taxi, apron])
    assert len(out) == 1
    assert out[0][2].intersection(band).area == pytest.approx(0.0, abs=1e-6)
    assert stats["gap_band_trim_m2"] > 0.0


def test_a_piece_shares_its_rim_with_a_mapped_road_ribbon():
    """A ribbon through a piece is solved WITH it (the last stage's
    follower): no stand-off between them."""
    apron = _cell(0, "apron", "pav1", box(0, 0, 100, 50))
    ribbon = _cell(1, "service_road", "small_roads:-7", box(0, 80, 100, 88))
    out, _s, _n = _mint(_airport(box(0, 50, 100, 120)), [apron, ribbon])
    assert len(out) == 2
    assert all(p.distance(Polygon(ribbon.ring)) == 0.0 for _r, _f, p, _k, _e in out)


def test_a_gap_piece_is_never_cover_for_the_structures_or_the_wall_field():
    """spec §53 (18): the classified cover the mapped-tunnel field and the
    kerb corridors' field read (one derivation, handed to the pool
    workers) is the STANDING cells — a late gap piece admits no corridor
    and leaves the standing cells' polygons index-aligned."""
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.planar.structure_approach import cover_polygons, wall_field
    apron, piece = box(0, 0, 50, 50), box(50, 0, 90, 50)
    standing = (_cell(0, "apron", "pav1", apron),)
    full = Classification(
        standing + (_cell(1, gm.ROLE, f"{mp.GAP_PREFIX}:0", piece),), (), {}, ())
    base = Classification(standing, (), {}, ())
    assert [p.wkb for p in cover_polygons(full)] == [p.wkb for p in cover_polygons(base)]
    assert ([p.wkb for p in wall_field(full, LAW).polys]
            == [p.wkb for p in wall_field(base, LAW).polys])
