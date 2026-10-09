"""Spec §62 THE PAD SEAT WHERE PAVEMENT TOUCHES IT — the twins (owner RULINGS
2026-10-09d (1), 08c (4), 09c (2a), 09f; ``constraints/pad_seat.py``,
``constraints/pavement_cap.py``).

The shape they stand for: a pad with NO airside frontage standing between a
service road (low, its level fixed by its own law) and a car park (3 m
higher), each a metre off its rim.  Until §62 the pad's de-facto seat was the
29ac fallback cap's two-sided weld of a rim vertex to whichever pavement
vertex stood within a metre, and its level row followed a ROLE's whole
population with the other role as a reported junior.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v2frontage import (HALF_W, RUN_LEN, _built, _face, _rect,  # noqa: E402
                             _solve, _verts)

from auto_patch_v2.classify.roles import Cell  # noqa: E402
from auto_patch_v2.constraints import pavement_cap  # noqa: E402
from auto_patch_v2.constraints.pad_frontage_gs import (  # noqa: E402
    GEN_GS, groundside_frontage, groundside_frontage_level, held_terrace_pairs)
from auto_patch_v2.constraints.pad_seat import (SEAT_RULING,  # noqa: E402
                                                landside_seats, seat_of_face)
from auto_patch_v2.constraints.pads import (GEN_LEVEL,  # noqa: E402
                                            pad_frontage_level,
                                            pad_fronts_airside)
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.solve.design import (hard_rulings,  # noqa: E402
                                        one_way_rulings, pad_level_rulings)

#: the road's ground, and the lot's 3 m above it
Z_ROAD, Z_LOT = 700.0, 703.0


class _Dem:
    """Flat at the road's level south of the pad's far edge, 3 m higher
    under the lot north of it."""

    provenance = {"synthetic": "landside_pad"}

    def __init__(self, lot: float = Z_LOT):
        self.lot = lot

    def z(self, x: float, y: float) -> float:
        return self.lot if y > 460.5 else Z_ROAD

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _cells(road_role="service_road", lot_role="parking_lot", lot=True,
           road=True, short_road=False):
    """A runway, and far from it a PAD (400..460 north) with a ROAD along
    its south edge and a LOT along its north edge, each 1 m off the rim and
    sharing no vertex with it."""
    out = [Cell(0, "runway", "09/27",
                _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                (), 3, "D", "airside", "runway", {}),
           Cell(1, "building", "padL", _rect(-60.0, 400.0, 60.0, 460.0), (),
                None, None, "groundside", "pad", {})]
    if road:
        x1 = -40.0 if short_road else 160.0
        out.append(Cell(2, road_role, "roadL", _rect(-160.0, 389.0, x1, 399.0),
                        (), None, None, "groundside", road_role, {}))
    if lot:
        out.append(Cell(3, lot_role, "lotL", _rect(-60.0, 461.0, 60.0, 541.0),
                        (), None, None, "groundside", lot_role, {}))
    return out


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _head(row):
    return row.source.ruling.split(" (")[0].strip()


# ── the register ─────────────────────────────────────────────────────────

def test_the_seat_head_is_hard_one_way_and_a_level_ruling(law):
    """A seat is not a preference: the head is in ``hard_rulings``; the pad
    follows (``one_way_rulings``) and carries no DEM datum of its own
    (``pad_level_rulings``)."""
    assert SEAT_RULING in hard_rulings(law)
    assert SEAT_RULING in one_way_rulings(law)
    assert SEAT_RULING in pad_level_rulings(law)


# ── R-C rule 1: ONE leader, the senior touching face ─────────────────────

def test_a_landside_pad_between_a_road_and_a_lot_has_the_road_as_its_one_leader(law):
    """The pad fronts nothing airside; its ONE leader is the ROAD (senior by
    ``precedence.toml``) though the lot's contact is as long, and its level
    rows are the seat's alone — no junior row against the lot."""
    pm, airport = _built(law, _cells(), _Dem())
    pad = _face(pm, "padL")
    assert pad.id not in pad_fronts_airside(pm, law)
    seats = landside_seats(pm, law, airport)
    assert len(seats) == 1
    seat = next(iter(seats.values()))
    assert (seat.ref, seat.role) == ("roadL", "service_road"), seat
    assert seat.contact_m > 100.0, seat.contact_m
    assert seat_of_face(pm, law, airport)[pad.id] is seat
    rows = [r for r in pad_frontage_level(pm, law, airport)
            if r.source.generator == GEN_LEVEL]
    assert rows and {_head(r) for r in rows} == {SEAT_RULING}, rows
    road, lot, rim = _verts(pm, "roadL"), _verts(pm, "lotL"), _verts(pm, "padL")
    for r in rows:
        feet = {v for v, _c in r.terms}
        assert feet & road and not feet & lot, "the leaders are the road's alone"
        assert set(r.follows) <= rim and r.follows, "the pad follows"


def test_seniority_is_the_road_family_then_the_longest_contact(law):
    """A lot leads only where no road touches; between two faces of one
    tier the LONGEST contact leads (§28 (1)'s largest shared edge)."""
    pm, airport = _built(law, _cells(road=False), _Dem())
    (seat,) = landside_seats(pm, law, airport).values()
    assert seat.ref == "lotL"
    # two roads: the short one touches 20 m of rim, the north one 120 m
    cells = _cells(short_road=True, lot_role="service_junction")
    pm2, airport2 = _built(law, cells, _Dem())
    (seat2,) = landside_seats(pm2, law, airport2).values()
    assert seat2.ref == "lotL", seat2


def test_a_pad_that_fronts_airside_or_nothing_has_no_seat(law):
    """§20 seats an airside-fronting pad and a pad touching no pavement
    keeps its DEM datum (09p (3)): neither is here."""
    pm, airport = _built(law, _cells(lot=False, road=False), _Dem())
    assert landside_seats(pm, law, airport) == {}
    from test_v2frontage import _cells as _airside_cells
    pm2, airport2 = _built(law, _airside_cells())
    assert landside_seats(pm2, law, airport2) == {}


# ── R-F: the fallback cap never pairs a pad's own vertex ─────────────────

def test_the_fallback_cap_mints_no_pair_on_a_pads_own_vertex(law):
    """The pad|road and pad|lot pairs across the 1 m stand-off are the
    SEAT relation's, never a two-sided hard weld at the road cap."""
    pm, _airport = _built(law, _cells(), _Dem())
    rim = _verts(pm, "padL")
    other = _verts(pm, "roadL") | _verts(pm, "lotL")
    rows = pavement_cap.pavement_road_cap([], pm, law)
    assert rows, "the rings' own edges are still capped"
    assert not [r for r in rows if (r.a in rim) != (r.b in rim)
                and ({r.a, r.b} & other)]


# ── the solve: the pad stands at its leader's level and does not drift ───

def test_the_solved_pad_stands_at_the_roads_level_not_the_lots(law):
    """The pad's plane takes the ROAD's level (the road stands on its own
    ground at 700); the lot 3 m above does not pull it."""
    pm, z, _rep = _solve(law, _cells(), _Dem())
    rim = sorted(_verts(pm, "padL"))
    road = sorted(_verts(pm, "roadL"))
    pad_lvl, road_lvl = float(np.mean(z[rim])), float(np.mean(z[road]))
    assert abs(pad_lvl - road_lvl) <= 0.05, (pad_lvl, road_lvl)
    assert float(np.ptp(z[rim])) <= 0.61, "one plane under its 1 % ceiling"


# ── R-C rule 2: every OTHER touching face follows the seated pad (§28) ───

def test_the_lot_follows_the_seated_pad_and_the_leader_road_does_not(law):
    """§28's leaders are the pads with a SEAT.  The lot (2 m above, inside
    the §28 (6) bound) is a follower of the landside pad; the road — the
    pad's own leader — is not, so the pair is stated once each way round."""
    pm, airport = _built(law, _cells(), _Dem(Z_ROAD + 2.0))
    rel = groundside_frontage(pm, law, airport)
    pad, lot, road = _face(pm, "padL"), _face(pm, "lotL"), _face(pm, "roadL")
    assert lot.id in rel and rel[lot.id][0][0] == pad.id, rel
    assert road.id not in rel, "the leader face never follows its own pad"
    rows = groundside_frontage_level(pm, law, airport)
    lot_vs, rim = _verts(pm, "lotL"), _verts(pm, "padL")
    assert rows and all(r.source.generator == GEN_GS for r in rows)
    for r in rows:
        assert set(r.follows) <= lot_vs
        assert {v for v, _c in r.terms} - set(r.follows) <= rim


def test_the_solved_lot_meets_the_seated_pad_and_grades_away(law):
    """The joint at the pad's rim goes to the pad's level (the road's), and
    the lot climbs to its own ground under its own cap."""
    pm, z, _rep = _solve(law, _cells(), _Dem(Z_ROAD + 2.0))
    rim = sorted(_verts(pm, "padL"))
    pm_b, airport = _built(law, _cells(), _Dem(Z_ROAD + 2.0))
    front = sorted(groundside_frontage(pm_b, law, airport)[_face(pm_b, "lotL").id][0][3])
    pad_lvl = float(np.mean(z[rim]))
    assert abs(pad_lvl - Z_ROAD) <= 0.05, pad_lvl
    assert float(np.max(np.abs(z[front] - pad_lvl))) <= 0.30, z[front]
    far = sorted(_verts(pm, "lotL") - set(front))
    assert float(np.max(z[far])) > pad_lvl + 1.0, "the lot grades away"


def test_a_lot_past_the_terrace_bound_is_held_not_welded(law):
    """§62 (2) rule 3 / RULINGS 2026-10-09f: the §28 (6) split-level terrace
    STANDS for a landside-only pad too — a follower whose DEM step against
    the pad's area-weighted DEM exceeds ``frontage_step_max_m`` keeps its
    own level; the threshold is the one §28 already reads."""
    pm, airport = _built(law, _cells(), _Dem(Z_ROAD + 3.0))
    rel = groundside_frontage(pm, law, airport)
    pad, lot = _face(pm, "padL"), _face(pm, "lotL")
    assert lot.id not in rel
    assert (lot.id, pad.id) in held_terrace_pairs(pm, law, airport)
    assert groundside_frontage_level(pm, law, airport) == []


# ── rule 4: the seat is published ────────────────────────────────────────

def test_the_seat_is_published_with_its_leader_followers_and_held_pairs(law):
    """One ``platforms[]`` record per seated landside-only pad — never a
    key the platform census reads (``datum``, ``rim_relief_max_m``,
    ``refused``)."""
    from auto_patch_v2.constraints.pad_seat import seat_records
    pm, z, _rep = _solve(law, _cells(), _Dem(Z_ROAD + 2.0))
    pm_b, airport = _built(law, _cells(), _Dem(Z_ROAD + 2.0))
    (rec,) = seat_records(pm_b, law, airport, z)
    assert rec["ref"] == "padL" and rec["seat"] == "landside"
    assert rec["leader"] == "service_road:roadL"
    assert rec["followers"] == ["parking_lot:lotL"] and rec["held_pairs"] == []
    assert abs(rec["seat_level"] - rec["leader_level"]) <= 0.05, rec
    assert not {"datum", "rim_relief_max_m", "refused"} & set(rec)
    pm_h, airport_h = _built(law, _cells(), _Dem(Z_ROAD + 3.0))
    (held,) = seat_records(pm_h, law, airport_h, z)
    assert held["followers"] == [] and held["held_pairs"] == ["parking_lot:lotL"]


# ── R-B: no road law fixes a road vertex inside a seated pad's frontage ──

def test_no_ramp_row_or_join_pin_stands_on_a_frontage_vertex(law):
    """A road vertex §28 makes follow a pad keeps the §28 row and loses its
    §37 (6) target, its hard ceiling and its §37 (9) join pin (recorded so
    the core ribbon yields); the first road vertex OUTSIDE the frontage
    keeps all three."""
    from test_v2frontage import _cells as _airside_cells
    from auto_patch_v2.constraints import road_ramp as RR
    from auto_patch_v2.constraints.pad_frontage_gs import frontage_vertices
    from auto_patch_v2.model.constraints import (Band, ConstraintSet, Linear,
                                                 Pin, Source)
    pm, airport = _built(law, _airside_cells("service_road"))
    rows = groundside_frontage_level(pm, law, airport)
    front = frontage_vertices(pm, law, airport)
    road = _verts(pm, "lotA")
    assert front and front < road
    inside, outside = min(front), min(road - front)

    def ramp(v):
        tag = (f"vertex:{v}", "lotA")
        return [Linear(((v, 1.0),), 705.0, 705.0, Source(RR.GEN, RR.RULING, tag)),
                Band(v, None, 705.5, Source(RR.GEN, RR.RULING_CEILING, tag)),
                Pin(v, 698.0, Source(RR.GEN, RR.JOIN_RULING, tag))]
    cs = ConstraintSet.from_rows([*rows, *ramp(inside), *ramp(outside)])
    out, rep = RR.frontage_release(pm, law, cs)
    assert (rep["targets"], rep["ceilings"]) == (1, 1)
    assert [(r["v"], r["pinned_m"], r["stage"]) for r in rep["joins"]] == [
        (inside, 698.0, "2f")]

    def on(v):
        return sorted(type(r).__name__ for r in out.rows()
                      if r.source.generator == RR.GEN
                      and r.source.inputs[0] == f"vertex:{v}")
    assert on(inside) == [] and on(outside) == ["Band", "Linear", "Pin"]
    assert len([r for r in out.rows() if r.source.generator == GEN_GS]) == len(rows)
    # the rewrite carries the release and its join records
    out2, rep2 = RR.reach_seed_rewrite(pm, law, cs, {})
    assert on(inside) == [] and rep2["frontage"]["targets"] == 1
    assert [r["v"] for r in rep2["welded_join"]] == [inside]
