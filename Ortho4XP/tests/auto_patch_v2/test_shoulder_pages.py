"""§40 (1) READ PAGE BY PAGE (owner RULINGS 2026-11-02a (2), #1686): a
narrow page along a runway edge that a deep taxiway page touches is still
the runway's shoulder; a face on one page reads as before."""
from __future__ import annotations

from types import SimpleNamespace as NS

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.roles import _page_shoulders, _runway_shoulder
from shapely.geometry import box
from shapely.ops import unary_union
from shapely.strtree import STRtree

RULES = load_rules()
RW = NS(id="09/27")
SLAB = box(0, -20, 1000, 20)
EDGES = [(RW, SLAB, SLAB.exterior.buffer(RULES.cells.on_tol_m, cap_style="flat"))]
STRIP = box(0, 20, 1000, 35)          # 15 m deep along 1,000 m: a ribbon
TAXI = box(400, 30, 600, 300)         # a deep taxiway page welded to it


def _split(pages):
    face = unary_union([g for _i, g in pages])
    return face, _page_shoulders(face, pages, STRtree([g for _i, g in pages]),
                                 EDGES, RULES)


def test_a_narrow_page_welded_to_a_deep_one_is_the_shoulder():
    pages = [("dsf:pol0", STRIP), ("dsf:pol1", TAXI)]
    face, (shoulders, rest) = _split(pages)
    assert _runway_shoulder(face, EDGES, RULES) is None   # the union is deep
    assert len(shoulders) == 1 and abs(shoulders[0].area - STRIP.area) < 1.0
    assert abs(sum(p.area for p in rest) - face.difference(STRIP).area) < 1.0


def test_a_face_on_one_page_is_not_split():
    assert _split([("dsf:pol1", TAXI.union(STRIP))])[1] == ([], [])


def test_no_narrow_page_no_split():
    deep = box(0, 20, 1000, 120)
    assert _split([("dsf:pol0", deep), ("dsf:pol1", TAXI)])[1] == ([], [])
