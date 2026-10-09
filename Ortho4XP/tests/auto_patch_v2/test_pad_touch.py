"""Spec §63 twins (owner RULINGS 2026-10-09j: a groundside cell TOUCHING a
pad in the source geometry is welded to it; a GAPPED one is free).  Rule T
— the touch witness at the one site, ``classify/roles._cut_back_groundside``
— on a pad with four lots drawn round it: one OVERLAPPING it, one 0.3 m off
(a gap the identity grid cannot hold), one 0.8 m off and one 2 m off.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.pad_touch import (EVIDENCE_KEY, is_touching,
                                              touch_records)
from auto_patch_v2.classify.roles import Cell, _cut_back_groundside
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.publication import pad_touch


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _lot(i, ref, ring):
    return Cell(i, "parking_lot", ref, ring, (), None, None, "groundside",
                "parking_lot", {})


def _cells():
    """The pad is 100..200 x 100..200; every coordinate is on the 0.5 m
    identity grid except the stand-offs under test."""
    return [Cell(0, "building", "padA", _rect(100.0, 100.0, 200.0, 200.0), (),
                 None, None, "airside", "pad", {}),
            _lot(1, "over", _rect(150.0, 190.0, 180.0, 260.0)),      # overlaps 10 m
            _lot(2, "hair", _rect(200.3, 110.0, 260.0, 150.0)),      # 0.3 m off
            _lot(3, "gap08", _rect(40.0, 110.0, 99.2, 150.0)),       # 0.8 m off
            _lot(4, "gap2", _rect(110.0, 40.0, 150.0, 98.0)),        # 2 m off
            _lot(5, "far", _rect(110.0, 0.0, 150.0, 30.0))]          # 70 m off


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def cut(law):
    cells, _n = _cut_back_groundside(_cells(), law, load_rules())
    return cells


def _witness(cells, ref):
    got = [c.evidence.get(EVIDENCE_KEY) for c in cells
           if c.ref.split("#")[0] == ref]
    assert got, ref
    return got[0]


def test_an_overlapping_cell_reads_touching(cut, law):
    w = _witness(cut, "over")
    assert w == {"padA": 0.0} and is_touching(law, w["padA"])


def test_a_gap_the_identity_grid_cannot_hold_reads_touching(cut, law):
    """0.3 m off the pad as drawn; on the 0.5 m identity grid the lot's
    edge lands on the pad's or one cell off it — either way no gap that
    can stand in the planar map (RULINGS 2026-09-04u)."""
    w = _witness(cut, "hair")
    assert set(w) == {"padA"} and is_touching(law, w["padA"])


def test_a_real_gap_reads_gapped_with_its_distance(cut, law):
    """0.8 m as drawn reads on the grid as 1.0 m (99.2 -> 99.0): gapped,
    and the gap is the published number."""
    w = _witness(cut, "gap08")
    assert not is_touching(law, w["padA"])
    assert w["padA"] == pytest.approx(0.8, abs=law.tables.emit.identity.min_distinct_spacing_m / 2 + 1e-9)
    assert _witness(cut, "gap2") == {"padA": 2.0}


def test_a_cell_beyond_the_frontage_radius_has_no_relation(cut):
    assert _witness(cut, "far") is None


def test_the_sidecar_names_every_neighbour_of_a_pad_by_class(cut, law):
    recs = pad_touch(cut, law)
    assert recs == touch_records(cut, law)
    (rec,) = recs
    assert rec["pad"] == "padA"
    assert {n.split("#")[0] for n in rec["touching"]} == {"parking_lot:over",
                                                          "parking_lot:hair"}
    assert [g["cell"].split("#")[0] for g in rec["gapped"]] == [
        "parking_lot:gap08", "parking_lot:gap2"]
    assert [g["gap_m"] for g in rec["gapped"]][1] == 2.0


# ── Rule W (spec §63 (4)): touching welds at the rim, a hillside pair is
#    held, a gapped cell is left as drawn ────────────────────────────────

from shapely.geometry import Polygon                                  # noqa: E402

from auto_patch_v2.classify.pad_touch import HELD_KEY, WELD_KEY, weld_partners  # noqa: E402
from auto_patch_v2.classify.roles import Classification               # noqa: E402
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack  # noqa: E402
from auto_patch_v2.model.frame import Frame                           # noqa: E402
from auto_patch_v2.planar.build import build                          # noqa: E402


class _Dem:
    """Flat at 700 m, with the ground NORTH of the pad (y > 200, the
    ``over`` lot's side) ``north`` metres up — the hillside of §28 (6)."""

    provenance = {"synthetic": "pad_touch"}

    def __init__(self, north: float = 0.0):
        self.north = north

    def z(self, x: float, y: float) -> float:
        return 700.0 + (self.north if y > 200.0 else 0.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law, dem):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-800.0, -400.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (800.0, -400.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key)


def _all_cells():
    return [Cell(9, "runway", "09/27", _rect(-800.0, -422.5, 800.0, -377.5), (),
                 3, "D", "airside", "runway", {})] + _cells()


def _poly(c):
    return Polygon(c.ring, c.holes)


def _parts(cells, ref):
    return [c for c in cells if c.ref.split("#")[0] == ref]


def test_a_touching_cell_is_clipped_at_the_footprint_and_named_a_weld_partner(law):
    cells, n_knife = _cut_back_groundside(_all_cells(), law, load_rules(),
                                          _airport(law, _Dem()))
    pad = _poly(next(c for c in cells if c.ref == "padA"))
    (over,) = _parts(cells, "over")
    assert n_knife == 0 and over.evidence[WELD_KEY] == 1.0
    assert _poly(over).distance(pad) == 0.0
    assert _poly(over).intersection(pad).area == pytest.approx(0.0, abs=1e-9)
    assert min(y for _x, y in over.ring) == pytest.approx(200.0)       # the rim, no stand-off
    assert weld_partners(over, law) == ["padA"]
    assert weld_partners(_parts(cells, "hair")[0], law) == ["padA"]


def test_a_gapped_cell_is_left_as_drawn(law):
    """09j: any gap and the pavement is free — no knife, no weld, no
    partner; its ring is the source ring."""
    src = {c.ref: c for c in _cells()}
    cells, _n = _cut_back_groundside(_all_cells(), law, load_rules(),
                                     _airport(law, _Dem()))
    for ref in ("gap08", "gap2", "far"):
        (c,) = _parts(cells, ref)
        assert c.ring == src[ref].ring and weld_partners(c, law) == []
        assert WELD_KEY not in c.evidence and "mixed_pad_cutback" not in c.evidence


def test_a_touching_pair_across_a_hillside_keeps_the_knife(law):
    """§28 (6) / RULINGS 2026-10-09f, the one exception: the ground under
    the overlapping lot stands 4 m above the pad's — a hillside terrace.
    It is HELD: cut back by the set-back as before, never a weld partner;
    the 0.3 m lot on level ground beside the same pad still welds."""
    cells, n_knife = _cut_back_groundside(_all_cells(), law, load_rules(),
                                          _airport(law, _Dem(north=4.0)))
    pad = _poly(next(c for c in cells if c.ref == "padA"))
    (over,) = _parts(cells, "over")
    back = law.tables.structures.building_pad.groundside_cutback_m
    assert n_knife == 1 and over.evidence[HELD_KEY] == ("padA",)
    assert over.evidence["mixed_pad_cutback"] == 1.0 and WELD_KEY not in over.evidence
    assert _poly(over).distance(pad) >= back - 1e-6
    assert weld_partners(over, law) == []
    assert weld_partners(_parts(cells, "hair")[0], law) == ["padA"]
    (rec,) = touch_records(cells, law)
    assert [n.split("#")[0] for n in rec["held"]] == ["parking_lot:over"]
    assert [n.split("#")[0] for n in rec["touching"]] == ["parking_lot:hair"]


def test_without_a_dem_no_pair_is_measured_a_hillside(law):
    """A pair is welded unless it is MEASURED to be a terrace."""
    cells, n_knife = _cut_back_groundside(_all_cells(), law, load_rules())
    assert n_knife == 0 and weld_partners(_parts(cells, "over")[0], law) == ["padA"]


def _shared(pm, a_ref, b_ref):
    def vs(ref):
        out = set()
        for f in pm.faces.values():
            if f.ref.split("#")[0] == ref:
                out |= set(pm.ring_vertices(f.ring))
        return out
    return vs(a_ref) & vs(b_ref)


def test_the_planar_map_shares_the_rim_with_a_welded_cell_and_no_other(law):
    """The pad and each welded lot share EVERY vertex of their run — one
    chain, no sliver and no T-vertex — the overlapping lot by the clip,
    the 0.3 m lot by ``planar/weld``'s project + insert halves with the
    pad frozen; the gapped lots share nothing."""
    airport = _airport(law, _Dem())
    cells, _n = _cut_back_groundside(_all_cells(), law, load_rules(), airport)
    pm, stats = build(airport, Classification(tuple(cells), (), {}, ()), law)
    assert stats.t_vertices == 0
    over = _shared(pm, "padA", "over")
    xs = sorted(pm.vertices[v].xy[0] for v in over)
    assert xs[0] == pytest.approx(150.0) and xs[-1] == pytest.approx(180.0)
    assert all(pm.vertices[v].xy[1] == pytest.approx(200.0) for v in over)
    hair = _shared(pm, "padA", "hair")
    ys = sorted(pm.vertices[v].xy[1] for v in hair)
    assert ys[0] == pytest.approx(110.0) and ys[-1] == pytest.approx(150.0)
    assert all(pm.vertices[v].xy[0] == pytest.approx(200.0) for v in hair)
    # every pad rim vertex on a shared run is a vertex of the lot too
    pad_vs = _shared(pm, "padA", "padA")
    assert {v for v in pad_vs if pm.vertices[v].xy[1] == pytest.approx(200.0)
            and 150.0 - 1e-6 <= pm.vertices[v].xy[0] <= 180.0 + 1e-6} == over
    assert not _shared(pm, "padA", "gap08") and not _shared(pm, "padA", "gap2")
    # the pad kept its footprint: the weld never moved the senior
    pad_f = next(f for f in pm.faces.values() if f.ref == "padA")
    ring = [pm.vertices[v].xy for v in pm.ring_vertices(pad_f.ring)]
    assert Polygon(ring).area == pytest.approx(100.0 * 100.0)


# ── a road along a pad ────────────────────────────────────────────────

def _road_cells():
    """The pad with a service road drawn ALONG its south edge (touching:
    y 92..100 against the pad's y = 100) and running 100 m beyond it."""
    return [Cell(9, "runway", "09/27", _rect(-800.0, -422.5, 800.0, -377.5), (),
                 3, "D", "airside", "runway", {}),
            Cell(0, "building", "padA", _rect(100.0, 100.0, 200.0, 200.0), (),
                 None, None, "airside", "pad", {}),
            Cell(1, "service_road", "roadA", _rect(0.0, 92.0, 300.0, 100.0), (),
                 None, None, "groundside", "service_road", {})]


def test_a_road_along_a_pad_is_level_along_it_and_inside_its_cap_beyond(law):
    """Spec §63 (4) (ii), owner RULINGS 2026-10-09j / 09d (1), on ground
    climbing 4 % along the road: the pad keeps its own seat (its DEM mean
    — the road does not lead it), the road stands at the pad's level along
    the whole shared run, and it leaves the rim at each end inside its own
    longitudinal cap."""
    import numpy as np

    from auto_patch_v2.constraints import generate
    from auto_patch_v2.law.tables import role_cap
    from auto_patch_v2.solve import Status, solve_design

    class _Slope(_Dem):
        def z(self, x: float, y: float) -> float:
            return 700.0 + 0.04 * x
    airport = _airport(law, _Slope())
    cells, _n = _cut_back_groundside(_road_cells(), law, load_rules(), airport)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    z = np.asarray(sol.z, float)
    rim = sorted(_shared(pm, "padA", "roadA"), key=lambda v: pm.vertices[v].xy)
    pad = sorted(_shared(pm, "padA", "padA"))
    dem_mean = float(np.mean([pm.vertices[v].dem_z for v in pad]))
    assert float(np.mean(z[pad])) == pytest.approx(dem_mean, abs=0.05)     # its own seat
    assert float(z[rim].max() - z[rim].min()) <= 0.01 * 100.0 + 1e-6       # the pad's plane
    assert float(abs(z[rim] - dem_mean).max()) <= 0.5                      # level along the pad
    cap = float(role_cap(law, "service_road").longitudinal)
    road_f = next(f for f in pm.faces.values() if f.ref == "roadA")
    ring = list(pm.ring_vertices(road_f.ring))
    left = 0
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if (a in rim) == (b in rim):
            continue                                   # along the rim, or off it
        (ax, ay), (bx, by) = pm.vertices[a].xy, pm.vertices[b].xy
        if ay != by:
            continue                                   # the cross-section, not the run
        left += 1
        assert abs(z[a] - z[b]) / abs(ax - bx) <= cap + 1e-3
    assert left == 2                                   # one edge leaving each end of the run


# ── Rule B′ (spec §63 (6)): no road law names a level on the rim ─────────

def test_no_ramp_row_or_join_pin_stands_on_a_vertex_shared_with_a_pad(law):
    """The road's §37 (6) target and ceiling and its §37 (9) join pin are
    withdrawn on the vertices it shares with the pad — the pad's plane
    names that level — and every other road vertex keeps its rows
    byte-identical: the ramp starts at the first vertex off the rim."""
    import dataclasses as dc

    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from auto_patch_v2.constraints.road_ramp import (JOIN_RULING, RULING,
                                                     RULING_CEILING,
                                                     pad_weld_release,
                                                     road_join_rows,
                                                     road_ramp_rows)
    from auto_patch_v2.model.constraints import ConstraintSet
    airport = _airport(law, _Dem())
    cells, _n = _cut_back_groundside(_road_cells(), law, load_rules(), airport)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    rim = pad_welded_vertices(pm, law)
    road = {v for f in pm.faces.values() if f.ref == "roadA"
            for v in pm.ring_vertices(f.ring)}
    assert rim and rim == _shared(pm, "padA", "roadA")
    xs = sorted(pm.vertices[v].xy[0] for v in rim)
    assert xs[0] == pytest.approx(100.0) and xs[-1] == pytest.approx(200.0)
    off = sorted(road - rim)
    pm = dc.replace(pm, road_ramp_z={v: 700.0 for v in road},
                    road_coverage_join={min(rim): 701.0, off[0]: 702.0})
    rows = road_ramp_rows(pm, law, airport) + road_join_rows(pm, law, airport)
    cs = ConstraintSet.from_rows(rows)
    out, rep = pad_weld_release(pm, law, cs)
    assert rep["rim_vertices"] == len(rim)
    assert rep["targets"] == rep["ceilings"] == len(rim)
    assert [j["v"] for j in rep["joins"]] == [min(rim)] and rep["joins"][0]["stage"] == "2f"

    def tagged(rs, ruling):
        return {int(r.source.inputs[0][7:]) for r in rs if r.source.ruling == ruling}
    assert tagged(out.linears, RULING) == set(off)
    assert tagged(out.bands, RULING_CEILING) == set(off)
    assert tagged(out.pins, JOIN_RULING) == {off[0]}
    keep = lambda rs: [r for r in rs if int(r.source.inputs[0][7:]) not in rim]   # noqa: E731
    assert list(out.linears) == keep(cs.linears) and list(out.bands) == keep(cs.bands)
    # a map with no rim weld is returned untouched
    cells2 = [c for c in _road_cells() if c.ref != "padA"]
    pm2, _ = build(airport, Classification(tuple(cells2), (), {}, ()), law)
    cs2 = ConstraintSet.from_rows(road_ramp_rows(
        dc.replace(pm2, road_ramp_z={0: 700.0}), law, airport))
    assert pad_weld_release(pm2, law, cs2)[0] is cs2
