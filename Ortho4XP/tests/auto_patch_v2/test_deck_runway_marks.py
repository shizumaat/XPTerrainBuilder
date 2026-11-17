"""Twins of the runway markings on a generated deck that carries a runway
(``airport/deck_runway_marks``; owner 2026-11-17: the deck surface matches
the pavement it carries, runway markings included where they cross it).
Headless: ``tmp_path``, a synthetic atlas and a synthetic runway."""
from __future__ import annotations

import io

import numpy as np
import pytest
from auto_patch_v2.airport import deck_objects as objs
from auto_patch_v2.airport import deck_runway_marks as rm
from auto_patch_v2.airport.apt_dat import AptRunway
from auto_patch_v2.airport.deck_skin import PageArt
from auto_patch_v2.law.tables import load_default
from PIL import Image
from shapely.geometry import Point, Polygon
from test_deck_bridge_2132 import _check_obj8  # noqa: E402  (sibling twin)
from test_generated_2123 import _pub  # noqa: E402

G = load_default().tables.structures.deck_gen
FT = rm.FT
W, H = 2048, 1024


def _cells(marks, cell):
    return [m for m in marks if m.cell == cell]


def test_a_precision_runway_carries_the_faa_layout():
    marks = rm.runway_marks(45.0, 2786.0, (150.0, 151.0), (3, 3))
    assert len(_cells(marks, "threshold")) == 2 * 12       # 150 ft wide: 12 bars an end
    assert len(_cells(marks, "aiming")) == 4
    assert len(_cells(marks, "tdz")) == 2 * 2 * (3 + 2 + 2 + 1 + 1)
    aim = sorted(_cells(marks, "aiming"), key=lambda m: m.s0)
    assert aim[0].s0 == pytest.approx(150.0 + 1020 * FT)
    assert aim[-1].s1 == pytest.approx(2786.0 - 151.0 - 1020 * FT)
    assert min(abs(m.t0) for m in aim) == pytest.approx(36 * FT * 45.0 / (150 * FT))
    edges = [m for m in marks if m.cell == "stripe" and m.s1 - m.s0 > 1000.0]
    assert sorted(round(m.t1, 3) for m in edges) == [round(-22.5 + 3 * FT, 3), 22.5]
    dashes = [m for m in marks if m.cell == "stripe" and m.s1 - m.s0 < 100.0]
    assert dashes and all(m.t1 - m.t0 == pytest.approx(36 * FT / 12) for m in dashes)


def test_a_visual_end_carries_centreline_only_and_unmarked_carries_nothing():
    marks = rm.runway_marks(30.0, 1500.0, (0.0, 0.0), (1, 1))
    assert {m.cell for m in marks} == {"stripe"}
    assert all(m.t1 - m.t0 == pytest.approx(FT) for m in marks)
    assert rm.runway_marks(30.0, 1500.0, (0.0, 0.0), (0, 0)) == []


def test_decals_are_the_marks_on_the_deck_clipped_with_the_cells_uv():
    marks = rm.runway_marks(45.0, 2000.0, (0.0, 0.0), (3, 3))
    R = Polygon([(-30, -340), (30, -340), (30, -400), (-30, -400)])  # s 340..400
    decals = rm.deck_decals(marks, (0.0, 0.0), (0.0, -2000.0), R, 0.01)
    assert decals
    for d in decals:
        for tri in d.tris:
            for x, z, u, _v in tri:
                assert R.buffer(1e-6).contains(Point(x, z))
                assert any(x0 / W <= u <= x1 / W for x0, _y0, x1, _y1 in rm.CELLS.values())
    # the aiming point (s 310.9-356.6) is cut at the deck's end, s = 340
    x0, _y0, x1, y1 = rm.CELLS["aiming"]
    aim = [c for d in decals for t in d.tris for c in t if x0 / W <= c[2] <= x1 / W]
    assert aim and min(-c[1] for c in aim) == pytest.approx(340.05, abs=0.01)
    assert min(c[3] for c in aim) > 1.0 - (y1 - 1.5) / H + 0.1   # the part past s 340 only
    assert not rm.deck_decals(marks, (0.0, 0.0), (0.0, -2000.0),
                              Polygon([(100, 0), (120, 0), (120, -20), (100, -20)]), 0.0)


def test_read_atlas_recasts_the_red_mask_as_tinted_alpha(tmp_path):
    a = np.zeros((H, W, 4), dtype=np.uint8)
    a[..., 0] = (np.arange(W, dtype=np.uint32)[None, :] % 256).astype(np.uint8)
    Image.fromarray(a, "RGBA").save(tmp_path / "RWY_markings_9.png")
    pol = tmp_path / "rwy.pol"
    pol.write_text("A\n850\nDRAPED_POLYGON\nRUNWAY_MARKINGS 0.8 0.8 0.8 1 RWY_markings_9.png\n")
    atlas = rm.read_atlas(str(pol))
    assert atlas.name == "o4_RWY_markings_9_cccccc.png"
    px = np.asarray(Image.open(io.BytesIO(atlas.png)))
    assert (px[..., 3] == a[..., 0]).all() and (px[..., :3] == 204).all()
    Image.fromarray(a[:512], "RGBA").save(tmp_path / "RWY_markings_9.png")
    assert rm.read_atlas(str(pol)) is None                  # not the known layout
    assert rm.read_atlas(None) is None


def test_a_deck_over_a_runway_writes_a_marks_overlay():
    rec = _pub()["decks"][0]                                # lat 59.003-59.007
    runway = AptRunway(45.0, 1, (("05", 59.0, 17.005, 0.0, 0.0),
                                 ("23", 59.018, 17.005, 0.0, 0.0)), markings=(3, 3))
    art = objs.install_art(G, "", None)._replace(
        slab=lambda page: PageArt("/x/a_ALB.dds", "", (18.0, 36.0)),
        marks=lambda page: rm._MarkAtlas("o4_marks.png", b"png") if "runway" in page else None)
    out, stats = objs.deck_objects(rec, (), art, G, surface_code=1, runway=runway)
    (text,) = [t for p, t in out if p.endswith("deck_t_marks.obj")]
    assert "TEXTURE o4_marks.png" in text and "TRIS 0 " in text and "ATTR_no_hard" in text
    assert stats["runway_marks"] > 0
    assert art.files == {f"{objs.GENERATED_DIR}/o4_marks.png": b"png"}
    _check_obj8(text)
    out, stats = objs.deck_objects(rec, (), art, G, surface_code=1, runway=None)
    assert not any(p.endswith("_marks.obj") for p, _ in out)
