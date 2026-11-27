"""A ROAD MEETING AIRSIDE WELDS TO IT (owner RULINGS 2026-11-27a, #2281;
``constraints/road_weld.road_airside_weld``).

The fixture is the EKVG site in small: a service road whose end vertex
stands 0.6 m off a junction's edge across a strip of graded ground, so no
row ties them -- the weld ties the road vertex to the edge's level at the
perpendicular foot, ONE-WAY (the road follows).  A road vertex past the
weld spacing, one on a tunnel structure face, one already on the
pavement, and a gap FILLED by pavement take no weld."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from auto_patch_v2.constraints import proximity, road_weld
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import is_structure_role
from auto_patch_v2.model.constraints import Linear


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# junction 0..100 x 0..50 (vertices 0-3); road above it, its end vertex 4
# at (40, 50.6) -- 0.6 m over the junction's top edge 2->3
XY = {0: (0.0, 0.0), 1: (100.0, 0.0), 2: (100.0, 50.0), 3: (0.0, 50.0),
      4: (40.0, 50.6), 5: (46.0, 50.6), 6: (46.0, 80.0), 7: (40.0, 80.0)}


def _rows(monkeypatch, law, faces, xy):
    """``faces``: fid -> (role, ring vertex ids, cap)."""
    vw = SimpleNamespace(
        xy=xy, rings={f: list(r) for f, (_ro, r, _c) in faces.items()},
        holes={f: [] for f in faces},
        caps={f: (None if c is None else (c, c)) for f, (_ro, _r, c) in faces.items()})
    inc: dict[int, list[int]] = {}
    for f, (_ro, r, _c) in faces.items():
        for v in r:
            inc.setdefault(v, []).append(f)
    pm = SimpleNamespace(faces={f: SimpleNamespace(role=ro, ref=f"ref{f}")
                                for f, (ro, _r, _c) in faces.items()},
                         vertices={v: SimpleNamespace(incident_faces=inc.get(v, []))
                                   for v in xy})
    monkeypatch.setattr(proximity, "view", lambda planar, lw: vw)
    return road_weld.road_airside_weld(pm, law, None)


def _base():
    return {1: ("junction", (0, 1, 2, 3), 0.015), 2: ("service_road", (4, 5, 6, 7), 0.08)}


def test_road_end_across_the_strip_welds_to_the_edge(monkeypatch, law):
    rows = _rows(monkeypatch, law, _base(), XY)
    (row,) = [r for r in rows if 4 in dict(r.terms)]
    assert isinstance(row, Linear) and row.source.generator == road_weld.GEN
    assert row.follows == (4,)
    terms = dict(row.terms)
    assert terms[4] == 1.0
    assert terms[2] == pytest.approx(-0.4) and terms[3] == pytest.approx(-0.6)
    min_d = float(law.tables.emit.identity.min_distinct_spacing_m)
    assert row.hi == pytest.approx(0.015 * max(0.6, min_d)) and row.lo == -row.hi


def test_the_weld_is_one_way(law):
    heads = [str(h) for h in law.tables.emit.design.one_way_rulings]
    assert road_weld.RULING.split(" (")[0] in heads


def test_no_weld_beyond_the_weld_spacing(monkeypatch, law):
    xy = {**XY, 4: (40.0, 51.2), 5: (46.0, 51.2)}
    assert _rows(monkeypatch, law, _base(), xy) == []


def test_no_weld_into_a_tunnel(monkeypatch, law):
    struct = next(r for r in law.tables.precedence.roles if is_structure_role(law, r))
    faces = {**_base(), 3: (struct, (4, 5, 8), None)}
    xy = {**XY, 8: (43.0, 50.8)}
    rows = _rows(monkeypatch, law, faces, xy)
    assert all(4 not in dict(r.terms) and 5 not in dict(r.terms) for r in rows)


def test_no_weld_across_pavement(monkeypatch, law):
    xy = {**XY, 8: (30.0, 50.0), 9: (70.0, 50.0), 10: (70.0, 50.4), 11: (30.0, 50.4)}
    faces = {**_base(), 3: ("apron", (8, 9, 10, 11), 0.015)}
    rows = _rows(monkeypatch, law, faces, xy)
    assert not any(set(dict(r.terms)) >= {4, 2} for r in rows if isinstance(r, Linear))


def test_no_weld_for_a_vertex_on_the_pavement(monkeypatch, law):
    faces = {1: ("junction", (0, 1, 2, 4, 3), 0.015), 2: ("service_road", (4, 5, 6, 7), 0.08)}
    xy = {**XY, 4: (40.0, 50.0)}
    rows = _rows(monkeypatch, law, faces, xy)
    assert all(r.follows != (4,) for r in rows)
