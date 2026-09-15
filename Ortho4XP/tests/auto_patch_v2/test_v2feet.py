"""§34 (13) (3) (a) AN OBJECT'S FOOT NEVER HOLDS AIRSIDE PAVEMENT
(Fable 2026-09-15; RULINGS 2026-09-15ad) — lane ``v2lemdstruct2`` r4.

A foot row is stated over the TRIANGLE the foot stands in, and a triangle
on the adjacent ground reaches the pavement's own kerb columns (one node,
one value, 09-01g).  At LEMD ``pav157``'s far edge that put 14 binding
rows, ``sum |dual| 42,656`` — the heaviest family on the vertex — from two
2.23 m bodies of ONE placement onto a taxiway junction's crossfall.  The
row now governs its BARE-GROUND columns and treats the pavement's as
given.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_patch_v2.constraints import foot_rows as FR   # noqa: E402
from auto_patch_v2.law import Law                       # noqa: E402
from auto_patch_v2.law.tables import is_value_role, role_side  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_the_yielding_population_is_every_airside_VALUE_role(law):
    """The scope is the ruling's own — every airside value role, the
    RUNWAY FAMILY INCLUDED.  Narrowing it to the taxi family and the
    apron was measured and rejected: the runway still moved (394 → 196
    vertices, 5.086 → 3.277 m, never 0) and the owner's raw pair read
    2.585 % against the 1.985 % cap instead of 1.160 %."""
    yields = {r for r in law.tables.precedence.roles
              if is_value_role(law, r) and role_side(law, r) == "airside"}
    for r in ("runway", "runway_crossing", "junction", "apron",
              "primary_parallel", "cross_connector"):
        assert r in yields, r
    # the graded strip is AIRSIDE but owns no level, so a foot row over
    # it stays two-sided — otherwise every bare-ground foot row in the
    # tree would become one-way and §11b would state nothing
    assert "graded_strip" not in yields
    assert "retaining_wall" not in yields
    # and nothing groundside is in it
    for r in ("service_road", "tunnel_ramp", "parking_lot"):
        assert r not in yields, r


def test_a_foot_row_clear_of_pavement_is_unchanged(law):
    """The ordinary case §11b states: a body on bare ground, no pavement
    column in any of its triangles, keeps two-sided rows."""
    rows = _rows(law, airside=())
    assert rows, "the fixture must fire rows"
    assert all(r.follows is None for r in rows)


def test_a_foot_row_touching_pavement_follows_its_ground_columns(law):
    """The row keeps every term — the pavement is still IN the average —
    but governs only the bare-ground columns."""
    rows = _rows(law, airside=(1,))
    assert rows
    assert all(r.follows == (0, 2) for r in rows), [r.follows for r in rows]


def test_a_triangle_wholly_on_pavement_stays_two_sided(law):
    """ALL OR NOTHING PER BODY (owner RULINGS 2026-09-11x (1)): a triangle
    with nothing left to follow keeps its two-sided row rather than
    vanishing — dropping it would fire some of a body's feet and not
    others, which §11b forbids."""
    rows = _rows(law, airside=(0, 1, 2))
    assert rows
    assert all(r.follows is None for r in rows)


def test_the_row_is_still_TWO_one_sided_rows_never_an_equality(law):
    """The §33 (5) lesson holds here too: ``solve/rows._law_sides`` reads
    an ``lo == hi`` Linear as the law's own equality and prices it at the
    law weight, so a foot row is always a PAIR of one-sided rows."""
    rows = _rows(law, airside=(1,))
    assert len(rows) % 2 == 0
    assert all(r.lo is None and r.hi is not None for r in rows)
    assert {round(r.hi, 6) for r in rows} == {round(7.5, 6), round(-7.5, 6)}


class _V:
    def __init__(self, faces):
        self.incident_faces = tuple(faces)


class _F:
    def __init__(self, role):
        self.role = role


class _PM:
    """The two things ``foot_rows`` reads off the planar map."""

    def __init__(self, airside):
        self.faces = {0: _F("junction"), 1: _F("graded_strip")}
        self.vertices = {v: _V((0,) if v in airside else (1,))
                         for v in (0, 1, 2)}


def _rows(law, airside):
    """``foot_rows`` over ONE synthetic target whose triangle is
    ``(0, 1, 2)``; ``airside`` names which of them carry pavement."""
    target = FR.FootTarget(gid="fixture#b0",
                           terms=((0, 1 / 3), (1, 1 / 3), (2, 1 / 3)),
                           z=7.5, dem_z=7.4, role="graded_strip")
    real = FR.foot_targets
    FR.foot_targets = lambda *_a, **_k: ([target], [], {"rows": 1})
    try:
        return FR.foot_rows(_PM(airside), law, None)
    finally:
        FR.foot_targets = real
