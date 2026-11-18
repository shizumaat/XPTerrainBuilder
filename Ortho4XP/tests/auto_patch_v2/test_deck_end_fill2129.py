"""#2129 (spec ``docs/specs/2129-deck-ends-spec.md``): the ground grades up
to the ELEVATED end of a unit's deck — a landing of kind ``end`` at the
end's top beyond its edge, banked 1:3 on every side and run out at road
grade (straight for a stub, along the carried route for a route end).
Hermetic: a synthetic deck print in a local metre frame (x east, y north;
1e-5 degree = 1 m), the unit a held block south of it."""
from __future__ import annotations

import types

import numpy as np
import pytest
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from auto_patch_v2.airport import bridge_family as BF
from auto_patch_v2.airport import deck_end_witness as W
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar import landing as LD

DATUM = 100.0


def _ll(x: float, y: float) -> tuple[float, float]:
    return (40.0 + y * 1e-5, -3.0 + x * 1e-5)


def _quad(x0, y0, x1, y1, ya, yb):
    """Two triangles of a quad from (x0, y0) to (x1, y1), authored y ``ya``
    along y0 and ``yb`` along y1."""
    a, b, c, d = _ll(x0, y0), _ll(x1, y0), _ll(x1, y1), _ll(x0, y1)
    return [((a, b, c), (ya, ya, yb)), ((a, c, d), (ya, yb, yb))]


def _deck(faces) -> BF.DeckPrint:
    tris = tuple(t for t, _y in faces)
    las = [q[0] for t in tris for q in t]
    los = [q[1] for t in tris for q in t]
    p = BF.DeckPrint(key="deck.obj", unit=0, member=0, under_y=0.0,
                     box=(min(las), min(los), max(las), max(los)), tris=tris,
                     ys=tuple(y for _t, y in faces))
    p.index()
    return p


def _print(top: float = 6.0, wall: bool = False, more=()) -> BF.DeckPrint:
    """A deck 10 m wide: a ramp 0 -> ``top`` over 60 m north of the pad
    (y 0..60), then a level stub at ``top`` to y 90 — its north edge the
    elevated END.  ``wall``: a wall under that edge down to the pad."""
    faces = _quad(0, 0, 10, 60, 0.0, top) + _quad(0, 60, 10, 90, top, top) + list(more)
    if wall:
        a, b = _ll(0, 90), _ll(10, 90)
        a2, b2 = _ll(0, 89.99), _ll(10, 89.99)
        faces += [((a, b, b2), (top, top, 0.0)), ((a, b2, a2), (top, 0.0, 0.0))]
    return _deck(faces)


class _Dem:
    """Rising 1 m per 30 m northward from the pad (``base`` at y 0)."""

    def __init__(self, base: float = DATUM, wet=None) -> None:
        self.base, self.wet = base, wet

    def z(self, x, y):
        return self.base + float(y) / 30.0

    def z_many(self, xs, ys):
        return self.base + np.asarray(ys, float) / 30.0

    def water_geometry(self, _box):
        return self.wet


def _way(wid, pts, **tags):
    return types.SimpleNamespace(id=wid, points=tuple(pts), tags={"highway": "service", **tags},
                                 kind="", closed=False)


def _run(monkeypatch, p, ways=(), dem=None, airside=()):
    from auto_patch_v2.planar.overlay import Region
    deck = types.SimpleNamespace(resource=p.key, parts=(), origin=None, heading_deg=0.0,
                                 deck_kind="flag")
    part = types.SimpleNamespace(units=[types.SimpleNamespace(members=[deck],
                                                              anchor=(40.0, -3.0))])
    frame = types.SimpleNamespace(
        entry=lambda: (lambda lo, la: ((lo + 3.0) * 1e5, (la - 40.0) * 1e5)),
        transformers=lambda: (None, _ll))
    airport = types.SimpleNamespace(partition=part, frame=frame, dem=dem or _Dem(),
                                    osm_ways=tuple(ways), osm_ways_mapped=None,
                                    pavements=tuple(airside), runways=(), taxi_nodes={},
                                    ground_routes=())
    monkeypatch.setattr(LD, "_prints", lambda _part: [p])
    monkeypatch.setattr(BF, "viaduct_units", lambda *_a, **_k: {p.key: ("u", 3, None, p)})
    pad = Region("building", "u", box(-200, -200, 200, -1), None, None, "airside", "cell")
    counts: dict = {}
    reg = Registries()
    reg.held["u"] = {"unit": "u", "k": 0, "blocks": 1, "datum_pred": DATUM}
    got = LD.landing_regions([pad], {}, [box(-900, -900, -800, -890)], airport, Law.load(),
                             0.0, 15.0, counts, reg=reg)
    return got, counts, reg


def _ends(reg):
    return reg.held["u"].get("deck_ends", [])


def _no_end_landing(reg) -> bool:
    return not any(v.get("kind") == "end" for v in reg.landings.values())


def test_a_level_stub_over_its_pad_grades_its_end_up(monkeypatch):
    """A stub 6 m over its pad: one ``end`` landing at y 6, its collar
    round it (the deck's side too), a straight run-out at road grade."""
    got, _c, reg = _run(monkeypatch, _print())
    end, = [r for r in _ends(reg) if r["state"] == "graded"]
    assert end["path"] == "stub"
    ref = end["landing"]
    rec = reg.landings[ref]
    assert rec["kind"] == "end" and rec["y"] == pytest.approx(6.0, abs=0.01)
    assert rec["end"] is end
    plat = unary_union([r.polygon for r in got if str(r.ref) == ref])
    collar = unary_union([r.polygon for r in got if str(r.ref) == ref + "#collar"])
    # the platform stands beyond the edge (y 90), one step out
    assert plat.bounds[1] < 90.0 < plat.bounds[3] and plat.bounds[3] >= 94.9
    # the collar banks every side, the deck's (south) side included
    cb = collar.bounds
    assert cb[0] < plat.bounds[0] and cb[2] > plat.bounds[2] and cb[1] < plat.bounds[1]
    run, = [v for v in reg.landing_runouts.values() if v["landing"] == ref]
    assert run["dir"] == pytest.approx((0.0, 1.0), abs=1e-6) and "path" not in run
    assert run["g"] == pytest.approx(0.05)


def test_a_route_end_runs_out_along_its_carried_way(monkeypatch):
    """A way on the deck (``layer`` 1) crossing the end: a ROUTE end whose
    run-out follows the way's bend; the strip is keyed by path distance."""
    way = _way(7, [(5, 30), (5, 90), (5, 110), (35, 150), (80, 170)], layer="1")
    _g, _c, reg = _run(monkeypatch, _print(), ways=[way])
    end, = [r for r in _ends(reg) if r["state"] == "graded"]
    assert end["path"] == "route" and end["carried"] == [7]
    run, = [v for v in reg.landing_runouts.values() if v["landing"] == end["landing"]]
    path = LineString(run["path"])
    assert path.hausdorff_distance(LineString(way.points).intersection(
        path.buffer(1.0))) < 1.5
    from auto_patch_v2.constraints.ramp_runout import _station
    s, t = _station(run, *run["path"][-1])
    assert s == pytest.approx(path.length, abs=0.5) and abs(t) < 0.5


def test_a_way_with_no_layer_or_bridge_is_not_carried(monkeypatch):
    """A way at grade under the deck is not carried — and, lying in the
    stub's run, it keeps its ground (Q2 (a)): the end is listed."""
    _g, _c, reg = _run(monkeypatch, _print(), ways=[_way(8, [(5, 30), (5, 150)])])
    end, = _ends(reg)
    assert end["path"] == "stub" and end["carried"] == []
    assert end["state"] == "listed" and end["why"].startswith("end_run_held")
    assert _no_end_landing(reg)


def test_a_wall_under_the_end_is_its_own_abutment(monkeypatch):
    _g, _c, reg = _run(monkeypatch, _print(wall=True))
    assert [r["why"] for r in _ends(reg)] == ["end_on_own_abutment"]
    assert _no_end_landing(reg)


def test_an_end_meeting_another_plate_of_its_frame_is_a_joint(monkeypatch):
    """A second plate of the deck at its level just past the edge: a JOINT
    (nothing minted there; the plate's own far tip is an end of its own)."""
    _g, _c, reg = _run(monkeypatch, _print(more=_quad(0, 91, 10, 120, 6.0, 6.0)))
    joints = [r["stations"][0][0] for r in _ends(reg) if r["why"] == "end_is_joint"]
    assert sorted(round(la, 5) for la in joints) == [40.0009, 40.00091]
    assert all(r["stations"][0][0] > 40.0011 for r in _ends(reg) if r.get("landing"))


def test_an_end_within_the_band_is_the_old_landing(monkeypatch):
    """A deck standing within ``BAND_M`` of its lowest y: no end is read,
    the 10-03e landing alone."""
    _g, counts, reg = _run(monkeypatch, _print(top=0.3))
    assert _ends(reg) == [] and counts.get("end_at_landing_band", 0) >= 1
    assert {v["kind"] for v in reg.landings.values()} == {"deck"}


def test_an_end_over_airside_or_water_is_listed(monkeypatch):
    apron = types.SimpleNamespace(outer=((-50, 95), (60, 95), (60, 300), (-50, 300)), holes=())
    _g, _c, reg = _run(monkeypatch, _print(), airside=[apron])
    end, = _ends(reg)
    assert end["state"] == "listed" and end["why"].startswith("end_on_airside")
    assert _no_end_landing(reg)
    _g, _c, reg = _run(monkeypatch, _print(), dem=_Dem(wet=box(-50, 93, 60, 300)))
    end, = _ends(reg)
    assert end["state"] == "listed" and end["why"].startswith("end_on_water")
    assert _no_end_landing(reg)


def test_a_unit_with_no_elevated_end_leaves_the_registries_alone(monkeypatch):
    """A deck at its pad's level throughout: the landings are exactly the
    10-03e ones, nothing kept for ends, no end run-out."""
    _g, counts, reg = _run(monkeypatch, _print(top=0.0))
    assert _ends(reg) == [] and "deck_ends" not in reg.held["u"]
    assert {v["kind"] for v in reg.landings.values()} == {"deck"}
    assert "end_runouts" not in counts


def test_the_carried_stretch_inside_the_deck_is_a_graded_end_bridge():
    """R8: the carried way is cut at the end edge; its stretch inside S is
    a bridge marked ``END_TAG`` (no ribbon), the rest stays as mapped."""
    from auto_patch_v2.airport.deck_carry import END_TAG
    from auto_patch_v2.airport.deck_stack import _rewrite_ways
    S = Polygon([(0, 0), (10, 0), (10, 90), (0, 90)])
    from auto_patch_v2.model.airport import OsmWay
    way = OsmWay(7, "small_roads", ((5.0, 30.0), (5.0, 150.0)), False,
                 {"highway": "service", "layer": "1"})
    out = _rewrite_ways([way], (), Law.load(), {7: [("deck.obj", S)]})
    on = [w for w in out if w.tags.get(END_TAG)]
    off = [w for w in out if not w.tags.get(END_TAG)]
    assert len(on) == 1 and on[0].tags["bridge"] == "yes"
    assert max(q[1] for q in on[0].points) == pytest.approx(90.0, abs=1e-6)
    assert off and all(min(q[1] for q in w.points) >= 90.0 - 1e-6 for w in off)


def test_the_witness_finds_a_tip_and_not_a_side():
    """R3's geometry: a 10 x 90 m strip has two end edges (its short
    sides), a strip narrower than a lane or wider than a road none."""
    got = W.end_edges(Polygon([(0, 0), (10, 0), (10, 90), (0, 90)]), 0.04, 24.0, 3.5)
    assert sorted(round(L, 3) for *_x, L in got) == [10.0, 10.0]
    assert sorted(tuple(round(c, 6) + 0.0 for c in o) for _a, _b, o, _L in got) == \
        [(0.0, -1.0), (0.0, 1.0)]
    assert not W.end_edges(box(0, 0, 2, 90), 0.04, 24.0, 3.5)
    assert not W.end_edges(box(0, 0, 30, 90), 0.04, 24.0, 3.5)
