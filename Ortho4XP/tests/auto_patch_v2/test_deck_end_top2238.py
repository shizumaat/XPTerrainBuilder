"""#2238 / #2241: a pack deck's top at an end line is its DRIVEN slab there
(``planar/deck_end_top``), never its highest hard-deck vertex (a parapet,
the slab's high corner)."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.planar.deck_end_top import EDGE_M, _station_tops, line_tops, slab_faces


def driven_top(faces, seats, edge_m, fallback):
    return line_tops(faces, seats, edge_m, fallback)[0]


def _box(x0, x1, z0, z1, y):
    """Two triangles of a level rectangle at height y (OBJ8 x / z plan)."""
    v = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
    return v, [(0, 1, 2), (0, 2, 3)]


def _deck(parts):
    verts, tris = [], []
    for v, t in parts:
        k = len(verts)
        verts += v
        tris += [(a + k, b + k, c + k) for a, b, c in t]
    g = types.SimpleNamespace(vertices=np.array(verts, float), hard_deck=np.array(tris, int))
    cache = types.SimpleNamespace(geometry=lambda _p: g)
    d = types.SimpleNamespace(resolved="deck.obj", xy=(0.0, 0.0), heading_deg=0.0)
    return cache, [d]


def _end_line(x0, x1, z):
    """Stations along an end line at OBJ8 z (frame y = -z at heading 0)."""
    return [(float(x), -float(z)) for x in np.arange(x0, x1 + 1e-9, 5.0)]


def test_a_roof_with_parapets_reads_its_slab_not_the_parapet_top():
    # a tunnel roof: the slab at y 5.0, its underside at 4.4, parapets along
    # the sides standing to y 6.54 -- all one ATTR_hard_deck block
    cache, decks = _deck([_box(0, 80, -8, 8, 5.0), _box(0, 80, -8, 8, 4.4),
                          _box(0, 80, -8, -7, 6.54), _box(0, 80, 7, 8, 6.54)])
    faces = slab_faces(cache, decks, 0.7)
    seats = _end_line(0, 80, 8.0)[:1] + _end_line(0, 80, 0.0)
    # every vertex near the line reaches the parapet (the old reading)
    assert max(float(v[1]) for v in cache.geometry("").vertices) == 6.54
    assert driven_top(faces, _end_line(0, 80, 0.0), EDGE_M, 6.54) == 5.0
    # a corner station standing on the parapet is outvoted
    assert driven_top(faces, seats, EDGE_M, 6.54) == 5.0


def test_a_slab_falling_along_its_end_line_reads_its_middle():
    # one slab falling 1.0 m along its 70 m end lines
    v = [(0, 7.0, -9), (70, 8.0, -9), (70, 8.0, 9), (0, 7.0, 9)]
    cache, decks = _deck([(v, [(0, 1, 2), (0, 2, 3)])])
    faces = slab_faces(cache, decks, 0.7)
    tops = _station_tops(faces, _end_line(0, 70, -9.0), EDGE_M)
    assert np.allclose(tops, 7.0 + np.arange(0, 70.1, 5.0) / 70.0)
    assert abs(driven_top(faces, _end_line(0, 70, -9.0), EDGE_M, 8.0) - 7.5) < 1e-9


def test_a_line_over_no_slab_keeps_the_callers_reading():
    cache, decks = _deck([_box(0, 10, -2, 2, 0.0)])
    faces = slab_faces(cache, decks, 0.7)
    assert driven_top(faces, [(50.0, 50.0)], EDGE_M, 1.25) == 1.25


def test_a_falling_slab_reads_a_top_per_station_and_their_mean():
    v = [(0, 7.0, -9), (70, 8.0, -9), (70, 8.0, 9), (0, 7.0, 9)]
    # kerbs standing on the slab at the line's two ends
    cache, decks = _deck([(v, [(0, 1, 2), (0, 2, 3)]), _box(0, 6, -9, 9, 8.6),
                          _box(64, 70, -9, 9, 9.6)])
    faces = slab_faces(cache, decks, 0.7)
    seats = _end_line(0, 70, -8.5)
    top, tops = line_tops(faces, seats, EDGE_M, 9.0)
    # every station its own slab, never the kerb standing 1.6 m over it
    assert np.allclose(tops, 7.0 + np.arange(0, 70.1, 5.0) / 70.0)
    assert abs(top - float(np.mean(tops))) < 1e-12


def test_station_rows_hold_each_seat_at_its_own_top():
    from auto_patch_v2.constraints.edge_deck import _station_rows
    ends = [(((1, 0.5), (2, 0.5)), 7.5), (((3, 0.5), (4, 0.5)), 7.5)]
    vt = {1: 7.0, 2: 8.0, 3: 7.0, 4: 8.0}
    rows = _station_rows("d", ends, 0.04, [160.0, None], vt)
    by_v = {r.v: r for r in rows if hasattr(r, "v")}
    # a held end line: its mean at the anchor, each seat off it by its top
    assert abs(by_v[1].lo - (159.5 - 0.04)) < 1e-9 and abs(by_v[2].hi - (160.5 + 0.04)) < 1e-9
