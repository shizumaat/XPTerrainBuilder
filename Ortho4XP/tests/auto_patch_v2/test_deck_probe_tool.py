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


def test_the_width_read_gives_each_deck_its_letters_tsa_and_sides():
    """``--widths`` (``tools/deck_width_bars``, RULINGS 2026-11-21c): a deck
    across taxiway K (E) reads its width and each side of the centreline;
    a deck no taxi route crosses reads ``route None``."""
    import sys

    from auto_patch_v2.law import Law
    from auto_patch_v2.model.structures import GENERATED_WITNESS, DeckBridge
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from deck_width_bars import width_rows

    def deck(oid, x0, x1):
        ring = ((x0, -15.0), (x1, -15.0), (x1, 15.0), (x0, 15.0))
        return DeckBridge(oid, "x.obj", (), ring, ring[:2], ring[2:], 0.0, 0.0, -6.0, 100.0,
                          witness=GENERATED_WITNESS)
    nodes = {1: types.SimpleNamespace(xy=(0.0, -100.0)), 2: types.SimpleNamespace(xy=(0.0, 100.0))}
    ap = types.SimpleNamespace(
        taxi_nodes=nodes, taxi_edges=[types.SimpleNamespace(a=1, b=2, name="K", is_runway=False,
                                                            width_class="E")],
        frame=types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (y, x))))
    pm = types.SimpleNamespace(decks=(deck("o4gen_a", -30.0, 35.2), deck("o4gen_b", 50.0, 90.0)))
    a, b = width_rows(pm, ap, Law.load())
    assert (a["route"], a["letters"], a["tsa_m"], a["width_m"]) == ("K", ["E"], 65.2, 65.2)
    assert {a["left_m"], a["right_m"]} == {30.0, 35.2}
    assert b["route"] is None
