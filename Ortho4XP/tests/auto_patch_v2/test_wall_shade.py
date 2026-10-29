"""Twin of ``airport/wall_shade`` (issue #1633): a wall that RETAINS ITS OWN
HEIGHT is two levels, never one flat pad, so its footprint leaves every pad
outline (KATL 27R end: ``muro_27R.obj``, 19.99 m, 2,558 m2, was minted
``building30`` at its foot and held the truck route on its ring in a
trench).  The fixture is ``test_wall_class_thick``'s wall."""
from __future__ import annotations

from pathlib import Path

from shapely.geometry import Point

from auto_patch_v2.airport.wall_shade import wall_shade
from auto_patch_v2.geom import pad_shade_extra
from auto_patch_v2.geom.base_slab import pad_shades
from tests.auto_patch_v2.test_wall_class_thick import CFG, FRAME, _airport

SRC = Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2"


def _mid(ap):
    """A point inside the fixture wall's footprint (frame metres)."""
    return Point(FRAME.entry()(-84.42 + 0.0005, 33.64 + 1.5 / 111_320.0))


def test_a_retaining_wall_leaves_every_pad_outline():
    ap = _airport(3.46, 10.65, 10.6)
    got = wall_shade(ap, CFG)
    assert got is not None and got.buffer(0.01).contains(_mid(ap))
    shade = pad_shades(None, FRAME.entry(), None,
                       pad_shade_extra(_with_shade(ap, got)))
    assert shade is not None and shade.buffer(0.01).contains(_mid(ap))


def _with_shade(ap, got):
    ap.wall_shade = got
    ap.sunken_ramps = None
    return ap


def test_a_wall_that_retains_nothing_is_no_shade():
    # thin and wall-class, but the ground does not step across it
    ap = _airport(0.8, 10.65, 0.0)
    assert wall_shade(ap, CFG) is None
    assert wall_shade(_airport(3.46, 10.65, 10.6), None) is None


def test_the_shade_extra_unions_the_sunken_ramps_and_the_walls():
    ap = _with_shade(_airport(3.46, 10.65, 10.6), None)
    ap.sunken_ramps = Point(500.0, 500.0).buffer(3.0)
    ap.wall_shade = wall_shade(ap, CFG)
    both = pad_shade_extra(ap)
    assert both.contains(Point(500.0, 500.0)) and both.buffer(0.01).contains(_mid(ap))
    ap.wall_shade = None
    assert pad_shade_extra(ap) is ap.sunken_ramps


def test_every_pad_reader_takes_the_one_path():
    """The mint, its census and the apron shelf all subtract
    ``geom.pad_shade_extra``: a reader that kept the bare sunken-ramp read
    would mint (or census) the wall's pad the others drop."""
    for rel in ("classify/evidence.py", "constraints/cluster_pad.py",
                "planar/apron_shelf.py"):
        text = (SRC / rel).read_text(encoding="utf-8")
        assert "pad_shade_extra(airport)" in text, rel
        assert 'getattr(airport, "sunken_ramps", None),' not in text, rel
