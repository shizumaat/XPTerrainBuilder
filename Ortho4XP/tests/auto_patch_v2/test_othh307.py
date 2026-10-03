"""Issue #307: the contents seat's host outline, widened by
``footprint_touch_m``, must be VALID.

OTHH's cached ``sw1002`` plan (version 10, Aeroscape OTHH Hamad Intl)
raised a shapely TopologyException in ``contents.attach_contents``: the
host of cluster 30 (6,706 walled bodies, all of them valid, their union
valid) came back from GEOS 3.13.1's ``buffer(0.5)`` as a MultiPolygon
with NESTED SHELLS, and ``grown.intersection(leaf)`` refused it.  Three
of its walled bodies reproduce the invalid buffer; the fixture carries
them verbatim from the plan, plus a 0.5 m leaf the bad outline cannot be
intersected with.  The plan version is not the cause (contents read no
version-12 field; a v10 plan reads lawfully through ``RebakePlan.from_dict``)."""
from __future__ import annotations

import json
import pathlib
import types

import pytest
import shapely
from shapely.ops import unary_union

from auto_patch_v2.airport import contents as C

FIX = pathlib.Path(__file__).parent / "fixtures" / "othh307_nested_shells.json"


@pytest.fixture(scope="module")
def fx():
    return json.loads(FIX.read_text(encoding="utf-8"))


def _parts(fx):
    return [C._poly(p["rings"], p["boxes"], fx["ml"], fx["mo"])
            for p in fx["parts"]]


def test_parts_and_union_are_valid(fx):
    ps = _parts(fx)
    assert all(p is not None and p.is_valid for p in ps)
    assert unary_union(ps).is_valid


def test_grow_is_valid_and_is_the_union_of_grown_parts(fx):
    host = unary_union(_parts(fx))
    raw = host.buffer(fx["touch_m"])
    g = C._grow(host, fx["touch_m"])
    assert g.is_valid
    # the widened outline is the union of the widened parts: the raw
    # buffer dropped a hole, which no make_valid method recovers.
    ref = shapely.union_all([p.buffer(fx["touch_m"]) for p in _parts(fx)])
    assert abs(g.area - ref.area) < 1e-3 * ref.area
    assert g.symmetric_difference(ref).area < 1e-3 * ref.area
    if raw.is_valid:  # a GEOS that no longer mints it: the pass-through
        assert g.equals(raw)
    else:  # the defect as measured: the hole is gone from the raw buffer
        assert sum(len(p.interiors) for p in shapely.get_parts(g)) == 1
        for m in ("linework", "structure"):
            v = shapely.make_valid(raw, method=m)
            assert v.symmetric_difference(ref).area > 1.0


def test_grow_passes_a_valid_buffer_through():
    sq = shapely.box(0, 0, 10, 10)
    assert C._grow(sq, 0.5).equals(sq.buffer(0.5))
    assert C._grow(sq, 0.0) is sq


def test_attach_contents_survives_the_othh_host(fx):
    ml, mo = fx["ml"], fx["mo"]
    shims = [types.SimpleNamespace(rings=p["rings"], part_boxes=p["boxes"],
                                   walled=True) for p in fx["parts"]]
    x0, y0, x1, y1 = fx["leaf_box_m"]
    ring = [(y0 / ml, x0 / mo), (y0 / ml, x1 / mo), (y1 / ml, x1 / mo),
            (y1 / ml, x0 / mo)]
    shims.append(types.SimpleNamespace(rings=[ring], part_boxes=[],
                                       walled=False))
    leaf = len(shims) - 1
    raw = unary_union(_parts(fx)).buffer(fx["touch_m"])
    lp = C._poly([ring], [], ml, mo)
    if not raw.is_valid:  # the defect as measured: the raw outline refuses
        with pytest.raises(shapely.errors.GEOSException):
            raw.intersection(lp)
    counts: dict = {}
    out, singles = C.attach_contents(
        shims, [[0, 1, 2]], [0, 1, 2], [leaf], fx["touch_m"], 0.5, counts,
        is_deck=lambda i: False, base_y=lambda i: 0.0, ml=ml, mo=mo)
    assert singles == []
    assert out == {leaf: 0}
    assert counts["contents_bodies"] == 1
