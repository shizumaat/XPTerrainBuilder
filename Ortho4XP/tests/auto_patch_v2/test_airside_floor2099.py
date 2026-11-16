"""#2099 R3 Part A twins (spec ``docs/specs/2099-R3.md`` §1, §7 T1 / T2):
a structure's floor never stands on an airside vertex (A1,
``constraints/airside_floor``), and a hard deck's depth is read from the
solids standing under it (A2, ``planar/deck_bridge._bottom_y``)."""
from __future__ import annotations

import importlib
import sys
import tempfile
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.constraints.airside_floor import lead, off_airside  # noqa: E402
from auto_patch_v2.model.constraints import (  # noqa: E402
    Band,
    Diff,
    Flat,
    Linear,
    Offset,
    Pin,
    Source,
)

SRC = Source("structures", "tunnel.mouth_depth_m (2026-09-03b)", ())


def test_the_rows_lose_every_airside_vertex_but_a_seat_term():
    """T1 (rows): a Flat sheds the airside vertex and keeps the rest; a
    Diff / Offset / Band / Pin naming it goes; a seat row LEADING on it goes,
    a seat row whose airside vertex is the seat stays."""
    air = {9}
    rows = [Flat((1, 2, 9), SRC), Flat((3, 9), SRC), Diff(1, 9, 0.1, 5.0, SRC),
            Offset(9, 2, 0.0, SRC), Band(9, 1.0, None, SRC), Pin(9, 3.0, SRC),
            Linear(((9, 1.0), (4, -1.0)), None, -7.5, SRC),
            Linear(((1, 1.0), (9, -1.0)), None, -7.5, SRC), Pin(2, 3.0, SRC)]
    out, n = off_airside(rows, air)
    assert out == [Flat((1, 2), SRC), Linear(((1, 1.0), (9, -1.0)), None, -7.5, SRC),
                   Pin(2, 3.0, SRC)]
    assert n == {"flat": 2, "diff": 1, "offset": 1, "band": 1, "pin": 1, "linear": 1}
    assert lead((9, 4, 5), air) == 4 and lead((9,), air) is None
    assert off_airside(rows, set())[0] == rows


@pytest.fixture(scope="module")
def trench():
    """The #2072 deck trench (``test_deck_trench2072``) with its ladder off:
    the floor hangs from the deck's seats by rows the solve reads."""
    import test_deck_trench2072 as T
    import test_m4b as M4B
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.model.airport import OsmWay
    from auto_patch_v2.model.structures import DeckBridge
    d = T._deck()
    db = DeckBridge(d.object_id, d.resource, d.members, d.ring, d.seats_a, d.seats_b,
                    d.top_a, d.top_b, d.bottom_y, d.deck_z, family="taxi")
    tmp = Path(tempfile.mkdtemp()) / "objects"
    tmp.mkdir()
    road = OsmWay(-1, "big_roads", ((0.0, -400.0), (0.0, 400.0)), False,
                  {"highway": "primary", "lanes": "2"})
    airport = M4B._airport({"dir": tmp}, T.LAW, [], (road,))
    pb = importlib.import_module("auto_patch_v2.planar.build")
    real = pb.deck_bridges
    pb.deck_bridges = lambda *a, **k: ((db,), [])
    try:
        pm, _st = pb.build(airport, Classification(tuple(T._cells()), (), {}, ()), T.LAW)
    finally:
        pb.deck_bridges = real
    return types.SimpleNamespace(pm=pm, airport=airport, law=T.LAW)


def _named(r) -> set[int]:
    return set(getattr(r, "group", ()) or ()) | {getattr(r, k) for k in ("v", "a", "b")
                                                 if isinstance(getattr(r, k, None), int)}


def test_a_datum_vertex_airside_carries_leaves_the_floor_and_the_floor_keeps_its_seat(
        trench, monkeypatch):
    """T1: declare one vertex of the trench's datum group airside (as a
    taxiway corner on the cap line is): no structures row names it but as a
    seat term; the datum Flat holds the rest; every seat row leads on a
    vertex of the floor's own."""
    import auto_patch_v2.constraints.structures as CS
    from auto_patch_v2.model.platform import stage_air_vertices
    pm, law, airport = trench.pm, trench.law, trench.airport
    base = CS.structures(pm, law, airport)
    seat_heads = ("tunnel.mouth_depth_m", "bridge.deck_datum")
    seats = [r for r in base if isinstance(r, Linear)]
    group = max((r.group for r in base if isinstance(r, Flat)), key=len)
    assert len(group) > 2
    fake = set(stage_air_vertices(pm, law)) | {group[0]}
    monkeypatch.setattr(CS, "stage_air_vertices", lambda _pm, _law: fake)
    rows = CS.structures(pm, law, airport)
    for r in rows:
        if isinstance(r, Linear):
            assert r.terms[0][0] not in fake, r
        else:
            assert not _named(r) & fake, r
    assert any(isinstance(r, Flat) and set(r.group) == set(group) - {group[0]} for r in rows)
    assert len([r for r in rows if isinstance(r, Linear)]) == len(seats)
    assert seat_heads


def test_a_wall_footing_outside_the_deck_is_no_part_of_its_depth():
    """T2: a frame whose box stands on -0.04 under the deck and whose wing
    wall's footing drops 9.4 m outside the ring: the bottom is the box's."""
    from auto_patch_v2.planar.deck_bridge import _bottom_y
    from shapely.geometry import box
    comps = {"box.obj": [types.SimpleNamespace(min_y=-0.04, cx=0.0, cz=0.0)],
             "wing.obj": [types.SimpleNamespace(min_y=-9.4, cx=0.0, cz=0.0)]}
    cache = types.SimpleNamespace(genuine=lambda path: comps[path])
    frame = [types.SimpleNamespace(id="b", resolved="box.obj", xy=(0.0, 0.0), heading_deg=0.0),
             types.SimpleNamespace(id="w", resolved="wing.obj", xy=(0.0, -30.0),
                                   heading_deg=0.0)]
    under = box(-10.0, -10.0, 10.0, 10.0).buffer(-0.6)
    assert _bottom_y(cache, frame, (), 6.5, under) == (-0.04, False)
    assert _bottom_y(cache, frame, (), 6.5) == (-9.4, False)
    assert _bottom_y(cache, frame[1:], (), 6.5, under) == (6.5, False)
