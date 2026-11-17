"""Twins of the generated-deck writers (spec 2123 §A2, P0):
``airport/deck_obj8.py`` and ``airport/deck_texture.py``."""
from __future__ import annotations

import io

import numpy as np
import pytest
from auto_patch_v2.airport import deck_texture as tex
from auto_patch_v2.airport.deck_obj8 import (
    DECK_MARK,
    DeckFrame,
    DeckLight,
    DeckLine,
    deck_obj8_text,
)
from auto_patch_v2.airport.obj8 import parse_obj8
from PIL import Image
from shapely.geometry import Polygon

THICK = 1.0


def _top(x, z):
    return -0.01 * z


def _deck(tmp_path, **kw):
    ring = Polygon([(-10, -20), (10, -20), (12, 20), (-10, 20)])
    text = deck_obj8_text(ring, _top, thickness_m=THICK, texture="o4_deck_concrete.png", **kw)
    path = tmp_path / "deck.obj"
    path.write_text(text, encoding="ascii", newline="\n")
    return ring, text, parse_obj8(str(path))


def test_frame_round_trip_and_heading():
    f = DeckFrame(17.937, 59.6406, 58.5)
    x, z = f.to_local(*f.to_lonlat(12.0, -30.0))
    assert abs(x - 12.0) < 1e-6 and abs(z + 30.0) < 1e-6
    x, z = DeckFrame(17.0, 59.0, 0.0).to_local(17.0, 59.001)     # heading 0: z south
    assert abs(x) < 1e-6 and -112 < z < -110
    x, z = DeckFrame(17.0, 59.0, 90.0).to_local(17.001, 59.0)    # heading 90: -z east
    assert abs(x) < 1e-6 and z < -50


def test_top_is_the_hard_deck_and_covers_the_ring(tmp_path):
    ring, text, g = _deck(tmp_path)
    assert DECK_MARK in text and "ATTR_hard_deck concrete" in text
    deck, v = g.hard_deck, g.vertices
    assert deck.shape[0] > 0 and not g.hard_plate
    area = sum(abs((v[b][0] - v[a][0]) * (v[c][2] - v[a][2])
                   - (v[c][0] - v[a][0]) * (v[b][2] - v[a][2])) / 2 for a, b, c in deck)
    assert area == pytest.approx(ring.area, rel=1e-6)
    assert {round(v[i][1] - _top(v[i][0], v[i][2]), 6) for t in deck for i in t} == {0.0}
    assert v[:, 1].min() == pytest.approx(_top(0, 20) - THICK, abs=1e-3)


def test_every_face_is_clockwise_from_outside(tmp_path):
    ring, _, g = _deck(tmp_path)
    v = g.vertices
    cx, cz = ring.centroid.x, ring.centroid.y
    for a, b, c in g.solid:
        p0, p1, p2 = v[a], v[b], v[c]
        n = np.cross(p1 - p0, p2 - p0)
        centre = (p0 + p1 + p2) / 3
        if abs(n[1]) > 0.5 * float(np.linalg.norm(n)):                  # top or underside
            on_top = centre[1] > _top(centre[0], centre[2]) - THICK / 2
            outward = np.array([0.0, 1.0 if on_top else -1.0, 0.0])
        else:                                                         # fascia
            outward = np.array([centre[0] - cx, 0.0, centre[2] - cz])
        assert float(np.dot(n, outward)) < 0     # right-hand normal points in: CW from outside


def test_paint_and_lights(tmp_path):
    lines = [DeckLine(((0.0, -15.0), (0.0, 15.0)), 0.15, "yellow")]
    lights = [DeckLight("taxi_g", 0.0, 5.0), DeckLight("taxi_g_rev", 0.0, 5.0)]
    _, text, g = _deck(tmp_path, lines=lines, lights=lights)
    rows = text.splitlines()
    assert rows.index("ATTR_poly_os 2") > rows.index("ATTR_no_hard")
    lit = [r.split()[:2] + [float(t) for t in r.split()[2:]] for r in rows
           if r.startswith("LIGHT_NAMED")]
    assert [r[1] for r in lit] == ["taxi_g", "taxi_g_rev"]
    assert lit[0][3] == pytest.approx(_top(0, 5) + 0.05, abs=1e-3)
    # the paint is not hard: only the top carries the deck flag
    assert g.solid[g.hardness == 2].shape[0] == g.hard_deck.shape[0]


def test_invalid_ring_is_refused():
    with pytest.raises(ValueError):
        deck_obj8_text(Polygon(), _top, thickness_m=1.0, texture="t.png")


def test_texture_is_deterministic_and_painted_by_region():
    a = tex.deck_texture_png()
    assert a == tex.deck_texture_png() and a != tex.deck_texture_png(seed=1)
    img = np.asarray(Image.open(io.BytesIO(a)).convert("RGB")).astype(int)
    assert img.shape == (tex.SIZE, tex.SIZE, 3)

    def at(region):
        u, v = tex.uv_centre(region)
        return img[int((1 - v) * tex.SIZE), int(u * tex.SIZE)]
    yellow, white = at(tex.YELLOW_UV), at(tex.WHITE_UV)
    assert yellow[0] > 200 and yellow[2] < 80 and min(white) > 200
    assert at(tex.FASCIA_UV).mean() < at(tex.CONCRETE_UV).mean()
