"""TWO AIRSIDE PAVEMENTS WITHIN WELD SPACING ARE ONE SURFACE (owner RULINGS
2026-10-19an, issue #328; ``constraints/proximity.airside_sliver_pairs``).

The fixture is the HECA site in small: a junction whose corner stands
0.97 m off an apron's edge across a strip of graded ground (no pavement
between them), so no route pair crosses it — the row ties the corner to
the edge's level at the perpendicular foot at the stricter cap.  A pad
(rigid), a groundside face, a gap over the weld spacing and a gap FILLED
by pavement are no pair."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from auto_patch_v2.constraints import proximity
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Diff, Linear


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rows(monkeypatch, law, faces, xy):
    """``faces``: fid -> (role, ring vertex ids, cap)."""
    vw = SimpleNamespace(
        xy=xy, rings={f: list(r) for f, (_ro, r, _c) in faces.items()},
        holes={f: [] for f in faces},
        caps={f: (None if c is None else (c, c)) for f, (_ro, _r, c) in faces.items()})
    pm = SimpleNamespace(faces={f: SimpleNamespace(role=ro, ref=f"ref{f}")
                                for f, (ro, _r, _c) in faces.items()})
    monkeypatch.setattr(proximity, "view", lambda planar, lw: vw)
    return proximity.airside_sliver_pairs(pm, law, None)


# apron 0..100 x 0..50 (vertices 0-3); junction above it, its corner 4 at
# (40, 50.97) — 0.97 m over the apron's top edge 2->3
XY = {0: (0.0, 0.0), 1: (100.0, 0.0), 2: (100.0, 50.0), 3: (0.0, 50.0),
      4: (40.0, 50.97), 5: (60.0, 52.0), 6: (60.0, 80.0), 7: (40.0, 80.0)}


def test_corner_across_the_sliver_is_tied_to_the_edge(monkeypatch, law):
    rows = _rows(monkeypatch, law, {1: ("apron", (0, 1, 2, 3), 0.015),
                                    2: ("junction", (4, 5, 6, 7), 0.02)}, XY)
    (row,) = rows
    assert isinstance(row, Linear) and row.source.generator == proximity.GEN
    terms = dict(row.terms)
    assert terms[4] == 1.0 and terms[2] == pytest.approx(-0.4) and terms[3] == pytest.approx(-0.6)
    assert row.hi == pytest.approx(0.015 * 0.97) and row.lo == -row.hi


@pytest.mark.parametrize("role", ["building", "service_road"])
def test_no_pair_with_a_pad_or_groundside(monkeypatch, law, role):
    assert _rows(monkeypatch, law, {1: ("apron", (0, 1, 2, 3), 0.015),
                                    2: (role, (4, 5, 6, 7), 0.02)}, XY) == []


def test_no_pair_beyond_the_weld_spacing(monkeypatch, law):
    xy = {**XY, 4: (40.0, 51.2)}
    assert _rows(monkeypatch, law, {1: ("apron", (0, 1, 2, 3), 0.015),
                                    2: ("junction", (4, 5, 6, 7), 0.02)}, xy) == []


def test_no_pair_across_pavement(monkeypatch, law):
    # a third apron fills the gap: the two are joined by pavement already
    xy = {**XY, 8: (30.0, 50.0), 9: (70.0, 50.0), 10: (70.0, 51.5), 11: (30.0, 51.5)}
    faces = {1: ("apron", (0, 1, 2, 3), 0.015), 2: ("junction", (4, 5, 6, 7), 0.02),
             3: ("apron", (8, 9, 10, 11), 0.015)}
    rows = _rows(monkeypatch, law, faces, xy)
    assert all(4 not in (dict(r.terms) if isinstance(r, Linear) else (r.a, r.b))
               or 2 not in (dict(r.terms) if isinstance(r, Linear) else (r.a, r.b))
               for r in rows)


def test_foot_at_a_vertex_is_a_diff(monkeypatch, law):
    xy = {**XY, 4: (100.5, 50.5)}                    # off corner 2
    rows = _rows(monkeypatch, law, {1: ("apron", (0, 1, 2, 3), 0.015),
                                    2: ("junction", (4, 5, 6, 7), 0.02)}, xy)
    assert any(isinstance(r, Diff) and {r.a, r.b} == {4, 2} for r in rows)
