"""``tools/deck_probe.py`` (the deck probe off a ``--solved-out`` pickle):
its pure readers on stubs — the station offsets, the vertices near a deck,
the hard rows over the floor touching them, the order-free fingerprint."""
from __future__ import annotations

import importlib.util
import types
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "deck_probe", Path(__file__).resolve().parents[2] / "tools" / "deck_probe.py")
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)


def test_station_offsets_names_the_worst_station_off_the_anchor_level():
    a = types.SimpleNamespace(object_id="o", end="A", v=0, z_m=10.0, family="taxi", ref="",
                              pinned=True, yielding=False, cut="bank", note="",
                              stations=(0, 1, 2))
    (q,) = P.station_offsets([a], [10.0, 10.03, 9.9])
    assert q["worst_station"] == 2 and abs(q["worst_station_m"] - 0.1) < 1e-9


def test_rows_over_the_floor_near_a_deck_are_listed_worst_first():
    ring = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    near = P.near_vertices({0: (5.0, 5.0), 1: (13.0, 5.0), 2: (40.0, 40.0)}, [ring], {7}, 5.0)
    assert near == {0, 1, 7}
    src = types.SimpleNamespace(generator="g", ruling="r", inputs=())
    rows = [types.SimpleNamespace(vs=(0,), m=0.5, source=src),
            types.SimpleNamespace(vs=(2,), m=3.0, source=src),
            types.SimpleNamespace(vs=(1, 2), m=0.01, source=src),
            types.SimpleNamespace(vs=(7,), m=0.9, source=src)]
    got = P.unsettled_rows(rows, near, None, lambda r: True, lambda r, _z: r.m,
                           lambda r: r.vs)
    assert [q["m"] for q in got] == [0.9, 0.5]


def test_the_fingerprint_ignores_row_order():
    assert P.fingerprint(["b", "a"]) == P.fingerprint(["a", "b"])
    assert P.fingerprint(["a"])[0] == 1
