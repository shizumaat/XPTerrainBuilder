"""Twins of the §52 facade mint (issue #334, RULINGS 2026-10-04d (3)):
the strip is edge x reach outside the footprint, hosted by the pad under
the facade, trimmed by what stands; the lot is a ``parking_lot`` and never
a pad source; both are LATE cells."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport import facade
from auto_patch_v2.classify import facade_mint as fm
from auto_patch_v2.classify.roles import Cell, is_late_cell, is_osm_ribbon
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model import planar as mp
from auto_patch_v2.model.airport import Building, FacadeEdge, FacadeRead

SQ = ((0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0))


def _cell(i, role, ref, ring):
    return Cell(i, role, ref, tuple(ring), (), None, None,
                "airside" if role in ("building", "apron") else "groundside", role, {})


def _mint(buildings, cells):
    law, rules = Law.for_airport("SPJC"), load_rules()
    out = []

    def add(role, ref, poly, kind, cn=None, cl=None, evidence=None):
        out.append((role, ref, poly, dict(evidence or {})))
    stats = fm.mint_facade_cells(types.SimpleNamespace(buildings=buildings),
                                 list(cells), law, rules, add)
    return out, stats


def _fac(edges, undecided=0):
    return Building("dsf:fac1", SQ, (), "dsf:fac:building", None, None, None,
                    FacadeRead("lib/x/Cargo.fac", facade.ROOFED, tuple(edges), undecided))


def test_sweep_goes_away_from_the_footprint_whatever_the_winding():
    fp = Polygon(SQ)
    for a, b in (((0.0, 0.0), (40.0, 0.0)), ((40.0, 0.0), (0.0, 0.0))):
        s = fm.strip_sweep(a, b, 13.2, fp)
        assert s.bounds[1] == pytest.approx(-13.2) and s.difference(fp).area == pytest.approx(40 * 13.2)


def test_strip_is_hosted_trimmed_and_thresholded():
    south = FacadeEdge((0.0, 0.0), (40.0, 0.0), 13.2, "Loading_doors", "lib/vehicles/t.obj", True)
    stairs = FacadeEdge((40.0, 0.0), (40.0, 20.0), 2.9, "Entrance", "stairs.obj", False)
    pad = _cell(0, "building", "building7", SQ)
    apron = _cell(1, "apron", "pav1", ((30.0, -30.0), (60.0, -30.0), (60.0, -5.0), (30.0, -5.0)))
    out, stats = _mint([_fac([south, stairs], undecided=2)], [pad, apron])
    assert [(r, ref) for r, ref, _p, _e in out] == [("groundside_pavement", "facstrip:building7:0")]
    strip = out[0][2]
    # outside the pad and the apron (airside wins), inside the sweep
    assert strip.intersection(Polygon(SQ)).area == pytest.approx(0.0, abs=1e-6)
    assert strip.intersection(Polygon(apron.ring)).area == pytest.approx(0.0, abs=1e-6)
    assert strip.bounds[1] == pytest.approx(-13.2, abs=0.02)
    assert 300.0 < strip.area < 40 * 13.2
    assert out[0][3]["host"] == "building7" and out[0][3]["reach_m"] == pytest.approx(13.2)
    assert stats["facade_strips"] == 1 and stats["facade_edges_undecided"] == 2
    assert mp.facade_strip_host(out[0][1]) == "building7"
    # no pad under the facade: no strip, counted
    out, stats = _mint([_fac([south])], [apron])
    assert out == [] and stats["facade_strip_no_host"] == 1


def test_lot_is_a_parking_lot_and_never_a_pad_source():
    assert fm.LOT_SOURCE == facade.LOT_SOURCE
    rules = load_rules()
    assert not fm.LOT_SOURCE.startswith(tuple(rules.buildings.sources))
    assert "dsf:fac:building".startswith(tuple(rules.buildings.sources))
    lot = Building("dsf:faclot0", SQ, (), fm.LOT_SOURCE, None, None, None,
                   FacadeRead("lib/x/Fenced_Parking.fac", facade.LOT))
    pad = _cell(0, "building", "building9", ((35.0, 5.0), (60.0, 5.0), (60.0, 15.0), (35.0, 15.0)))
    out, stats = _mint([lot], [pad])
    ((role, ref, poly, _e),) = out
    assert (role, ref) == ("parking_lot", "faclot:0")
    # the pad wins and keeps its set-back
    assert poly.distance(Polygon(pad.ring)) > 0.5 and poly.area < 800.0
    assert stats["facade_lots"] == 1


def test_facade_cells_are_late_and_not_road_ribbons():
    for ref in ("facstrip:building7:0", "faclot:0", "facstrip:building7:0#1"):
        c = _cell(0, "groundside_pavement", ref, SQ)
        assert is_late_cell(c) and not is_osm_ribbon(c)
        assert mp.is_late_ref(ref) and mp.is_facade_ref(ref) and not mp.is_osm_ribbon_ref(ref)
    assert mp.is_facade_strip_ref("facstrip:b:1") and not mp.is_facade_strip_ref("faclot:0")
    assert mp.is_late_ref("small_roads:-3") and not mp.is_late_ref("pav12")
    assert mp.facade_strip_host("faclot:0") is None


# ── the strip's level: a projection onto the host pad's FINAL plane ──────

def _fake_map():
    xy = {0: (0, 0), 1: (40, 0), 2: (40, 20), 3: (0, 20),            # pad b7
          4: (0, -0.7), 5: (40, -0.7), 6: (40, -13.2), 7: (0, -13.2),  # its strip
          8: (100, 0), 9: (120, 0), 10: (120, 20),                    # pad b9
          11: (0, -13.2), 12: (40, -30.0)}
    V = {k: types.SimpleNamespace(xy=(float(x), float(y))) for k, (x, y) in xy.items()}
    F = [("building", "building7", (0, 1, 2, 3)),
         ("groundside_pavement", "facstrip:building7:0", (4, 5, 6, 7)),
         ("building", "building9#collar", (8, 9, 10)),
         ("service_road", "small_roads:-1", (6, 7, 12)),               # a road at the strip
         ("groundside_pavement", "facstrip:building404:1", (11, 6, 12))]
    faces = {i: types.SimpleNamespace(id=i, role=r, ref=ref, ring=ring, holes=())
             for i, (r, ref, ring) in enumerate(F)}
    return types.SimpleNamespace(faces=faces, vertices=V,
                                 ring_vertices=lambda ring: tuple(ring))


def test_projection_puts_every_strip_vertex_on_the_host_pad_and_moves_no_pad():
    from auto_patch_v2.solve.project_strip import project_facade_strips
    law, pm = Law.for_airport("SPJC"), _fake_map()
    z = [25.88] * 4 + [32.5, 33.0, 31.0, 33.2] + [40.0] * 3 + [9.0, 50.0]
    out, rep = project_facade_strips(pm, law, z)
    assert out[4:8] == pytest.approx((25.88,) * 4, abs=1e-9)
    assert out[:4] == tuple(z[:4]) and out[8:11] == tuple(z[8:11])   # pads read, never written
    assert out[11:] == tuple(z[11:])                                  # hostless strip untouched
    assert rep["vertices"] == 4 and rep["no_host"] == 1
    assert rep["shared"] == 2                    # the road's two vertices went with the strip
    (s,) = rep["strips"]
    assert s["pad_ref"] == "building7" and s["level"] == pytest.approx(25.88)
    assert s["moved_max_m"] == pytest.approx(7.32)
    # an UNHELD pad's plane (1 % ceiling) is evaluated at the strip vertex
    z2 = [30.0, 30.2, 30.2, 30.0] + z[4:]
    out2, _ = project_facade_strips(pm, law, z2)
    assert out2[4] == pytest.approx(30.0, abs=1e-6) and out2[5] == pytest.approx(30.2, abs=1e-6)
    # no strip: z comes back as it went in
    pm.faces = {i: f for i, f in pm.faces.items() if not mp.is_facade_strip_ref(f.ref)}
    assert project_facade_strips(pm, law, z) == (tuple(z), {
        "strips": [], "vertices": 0, "no_host": 0, "shared": 0, "moved_max_m": 0.0})


def test_both_exits_of_the_design_solve_project_the_strips():
    """``staged_solve = false`` returns through the same projection (the
    single solve leaves a strip on its own terrain otherwise)."""
    import inspect
    from auto_patch_v2.solve import design
    src = inspect.getsource(design.solve_design)
    assert src.count("return _with_facade_strips(") == 2
    assert "return published(" not in src and "return sol, rep2" not in src
    pm, law = _fake_map(), Law.for_airport("SPJC")
    z = tuple([25.88] * 4 + [32.5, 33.0, 31.0, 33.2] + [40.0] * 3 + [9.0, 50.0])
    sol = types.SimpleNamespace(z=z)
    rep = types.SimpleNamespace(facade_strip={})
    import dataclasses
    S = dataclasses.make_dataclass("S", ["z"])
    out, rep = design._with_facade_strips(pm, law, S(z), rep)
    assert out.z[4:8] == pytest.approx((25.88,) * 4) and rep.facade_strip["vertices"] == 4
    empty, _ = design._with_facade_strips(pm, law, S(()), rep)
    assert empty.z == ()
