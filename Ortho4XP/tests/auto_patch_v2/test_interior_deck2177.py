"""Issue #2177 (owner RULINGS 2026-11-19f): everything inside a building
moves with the building — a flagged floor inside a building of its frame
is no deck — and a deck footprint's touching pieces are read per
shared-vertex group (``airport/deck_touch``), the same partition.

RJTT's ``T3INTER.obj`` (stacked interior floors flagged ``ATTR_hard_deck``)
stalled the placement plan in the viaduct footprints; the twins are a
building with a floor inside it, and two overlapping floors of one deck
footprint."""
from __future__ import annotations

import random

import pytest
from auto_patch_v2.airport import bridge_family as BF
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.basin_witness import read_objects
from auto_patch_v2.law import Law
from test_deck_contains_many import _full_query_partition
from test_m4b import _box_obj
from test_v2basinfix import _FlatDem
from test_wells551 import _airport

HX, HZ = 30.0, 20.0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("interior2177_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text(
        "I\n1000 Version\n", encoding="utf-8", newline="")
    deck = "ATTR_hard_deck"
    return {
        "dir": d,
        # the building: four walls 0..12 m, a ground floor and a roof
        "shell": _box_obj(d / "shell.obj", hx=HX, hz=HZ, depth=0.0, top=12.0,
                          lid=True),
        # its interior: a walkable floor 4 m up, inside the walls
        "floor": _box_obj(d / "floor.obj", hx=HX - 2, hz=HZ - 2, depth=-4.0,
                          walls=(), attr=deck),
        # the same floor standing beside the building, in the same frame
        "beside": _box_obj(d / "beside.obj", hx=HX - 2, hz=HZ - 2, depth=-4.0,
                           walls=(), attr=deck, cx=4.0 * HX),
        # a bridge's lower deck at 2 m roofed by its upper deck whose own
        # structure stands from 6 m: roofed, but no floor under it
        "upper": _box_obj(d / "upper.obj", hx=HX, hz=HZ, depth=-6.0, top=9.0,
                          lid=True),
        "lower": _box_obj(d / "lower.obj", hx=HX - 2, hz=HZ - 2, depth=-2.0,
                          walls=(), attr=deck),
    }


def _kinds(objs, law, names):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(_airport(objs, law, names, _FlatDem()), law, cache)
    return {o.path.rsplit("/", 1)[-1][:-4]: o for o in objects}


def test_a_floor_inside_its_building_is_no_deck(objs, law):
    got = _kinds(objs, law, ["shell", "floor"])
    assert got["floor"].deck_kind == ""
    assert got["floor"].hard_deck is None and got["floor"].deck_top_z is None
    assert "inside objects/shell.obj" in got["floor"].deck_evidence[0]


def test_alone_or_beside_the_building_the_floor_is_a_deck(objs, law):
    assert _kinds(objs, law, ["floor"])["floor"].deck_kind == "flag"
    assert _kinds(objs, law, ["shell", "beside"])["beside"].deck_kind == "flag"


def test_a_deck_roofed_with_no_floor_under_it_stays_a_deck(objs, law):
    got = _kinds(objs, law, ["upper", "lower"])
    assert got["lower"].deck_kind == "flag"


def _floor(la: float, lo: float, n: int, d: float, k: int) -> list:
    """An ``n`` x ``n`` grid of welded squares (two triangles each)."""
    def q(i: int, j: int) -> tuple:
        return (la + i * d, lo + j * d * 1.25 + k * 1e-9)
    out = []
    for i in range(n):
        for j in range(n):
            out += [(q(i, j), q(i + 1, j), q(i, j + 1)),
                    (q(i + 1, j), q(i + 1, j + 1), q(i, j + 1))]
    return out


def test_two_overlapping_floors_read_as_the_full_query():
    """Two stacked floors of one footprint (unwelded, offset in plan), a
    floor drawn twice, wall faces seen edge-on, a far floor and a point:
    the per-group reading is the per-triangle partition."""
    rnd = random.Random(7)
    la, lo, d = 39.31, -94.69, 2e-5
    tris = _floor(la, lo, 12, d, 0)
    tris += _floor(la + 3 * d, lo + 4 * d, 12, d, 1)          # second storey
    tris += _floor(la + 3 * d, lo + 4 * d, 12, d, 1)          # drawn twice
    tris += _floor(la + 40 * d, lo, 4, d, 0)                  # a far piece
    for _ in range(40):                                       # wall faces
        a = (la + rnd.uniform(-5, 30) * d, lo + rnd.uniform(-5, 30) * d)
        b = (a[0] + rnd.uniform(-2, 2) * d, a[1] + rnd.uniform(-2, 2) * d)
        tris.append((a, b, a))
    tris.append(((la - 30 * d, lo),) * 3)                     # a point
    las = [q[0] for t in tris for q in t]
    los = [q[1] for t in tris for q in t]
    p = BF.DeckPrint(key="t.obj", unit=0, member=0, under_y=0.0,
                     box=(min(las), min(los), max(las), max(los)),
                     tris=tuple(tris))
    p.index()
    for gap in (BF.CONTACT_M, 0.05, 3.0):
        want = _full_query_partition(p, gap)
        got: dict = {}
        for i, k in enumerate(BF._touch_components(p, gap)):
            got.setdefault(k, []).append(i)
        assert sorted(got.values(), key=lambda g: g[0]) == want
        assert 1 < len(want) < len(tris)
