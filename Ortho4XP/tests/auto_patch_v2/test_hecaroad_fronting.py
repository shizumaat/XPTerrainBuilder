"""§20 FRONTING ACROSS BARE GROUND — the twins (owner RULINGS 2026-09-27a
(9), Q-11 option A; issue #11 [HECA-6]; ``constraints/pad_fronting``).

The site they stand for: HECA's cargo pad ``building52`` (shapeID 201)
touches the low apron ``dsf:objpav399`` at its north corner and FACES the
higher east apron (``pav37`` / ``dsf:objpav68#0``) across 20–40 m of bare
ground.  §20 saw only the corner, so the pad sat 4 m under the apron it
faces.

The fixture: a 40 m × 200 m pad welded along its 40 m SOUTH edge to apron
A (DEM 700) and facing apron B (DEM 704) 30 m east of its 200 m EAST
edge.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import pad_fronting, pads
from auto_patch_v2.law import Law
from auto_patch_v2.planar.build import build

from test_v2frontage import HALF_W, RUN_LEN, _airport, _rect  # noqa: E402

PAD = _rect(-20.0, 200.0, 20.0, 400.0)


class _Dem:
    provenance = {"synthetic": "east_high"}

    def z(self, x: float, y: float) -> float:
        return 704.0 if x >= 35.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _cells(blocker: bool = False, east_gap: float = 30.0):
    out = [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                (), 3, "D", "airside", "runway", {}),
           Cell(1, "apron", "apronA", _rect(-60.0, 140.0, 60.0, 200.0), (),
                None, None, "airside", "apron", {}),
           Cell(2, "building", "padA", PAD, (), None, None, "airside", "pad", {}),
           Cell(3, "apron", "apronB",
                _rect(20.0 + east_gap, 200.0, 120.0 + east_gap, 400.0), (),
                None, None, "airside", "apron", {})]
    if blocker:
        # a car park filling the gap: the ground is not bare
        out.append(Cell(4, "parking_lot", "lotG",
                        _rect(21.0, 190.0, 19.0 + east_gap, 410.0), (),
                        None, None, "groundside", "parking_lot", {}))
    return out


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _built(law, cells):
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return pm, airport


def _fid(pm, ref):
    return next(f.id for f in pm.faces.values() if f.ref == ref)


def test_the_reach_and_roles_are_law_values(law):
    assert pad_fronting.reach_m(law) == pytest.approx(
        float(law.tables.emit.design.pad_fronting_reach_m))
    assert "apron" in law.tables.emit.design.pad_fronting_roles


def test_a_pad_faces_the_apron_across_bare_ground(law):
    """The pad's east-edge vertices face apron B; apron A (welded) is
    §20's own frontage and never appears here."""
    pm, _a = _built(law, _cells())
    rel = pad_fronting.facing(pm, law)
    pad, b, a = _fid(pm, "padA"), _fid(pm, "apronB"), _fid(pm, "apronA")
    assert pad in rel and b in rel[pad] and a not in rel[pad]
    xs = [pm.vertices[v].xy[0] for v in rel[pad][b]]
    assert min(xs) > 19.0                      # the EAST edge only


def test_a_pavement_face_in_the_gap_blocks_the_relation(law):
    pm, _a = _built(law, _cells(blocker=True))
    assert pad_fronting.facing(pm, law) == {}


def test_an_apron_beyond_the_reach_is_not_faced(law):
    pm, _a = _built(law, _cells(east_gap=pad_fronting.reach_m(law) + 10.0))
    assert pad_fronting.facing(pm, law) == {}


def test_a_touching_apron_at_another_level_is_terraced_and_facing_is_senior(law):
    """The pad is welded to apron A (DEM 700) and faces the higher apron B
    (704) along its longest edge: owner RULINGS 2026-09-28b SUPERSEDES the
    shipped "touching stays senior" — A is split off as a terrace
    (``planar/pad_terrace``), no vertex is shared, and the facing row is
    the pad's SENIOR level row (``test_cargoterrace.py`` for the rule)."""
    pm, airport = _built(law, _cells())
    pad = _fid(pm, "padA")
    g = pad_fronting.analysis(pm, law, airport)["groups"][pad]
    assert g["senior"]
    assert pad not in pads.pad_shared(pm, law)
    rows = pad_fronting.pad_fronting_level(pm, law, airport)
    assert rows and all(r.source.ruling.startswith(pads.LEVEL_RULING + " ")
                        for r in rows)


def test_a_pad_that_only_faces_takes_the_faced_edge_as_senior_one_way(law):
    """No weld: the facing row is the pad's SENIOR level row, one-way with
    the pad's own vertices as the followers — the apron never moves."""
    cells = [c for c in _cells() if c.ref != "apronA"]
    pm, airport = _built(law, cells)
    pad = _fid(pm, "padA")
    rows = pad_fronting.pad_fronting_level(pm, law, airport)
    assert rows and all(r.source.ruling.startswith(pads.LEVEL_RULING + " ")
                        for r in rows)
    b = {v for v in pm.vertices if _fid(pm, "apronB") in pm.vertices[v].incident_faces}
    padv = {v for v in pm.vertices if pad in pm.vertices[v].incident_faces}
    for r in rows:
        assert set(r.follows) & b == set() and set(r.follows) <= padv
