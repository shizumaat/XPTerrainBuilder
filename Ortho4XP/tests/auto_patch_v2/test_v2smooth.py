"""THE DESIGN SURFACE's twins (owner RULINGS 2026-09-08t; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §4; lane ``v2smooth``).

Pavement is a DESIGNED surface: minimum curvature, unbounded cut and fill,
flush and tangent at every contact, the DEM a datum only, every law a
target.  These are the seven readings §4 names, plus the structural one:
there is no relaxation path left to take.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import (Base, DEFAULT_METHOD, METHODS, assemble,
                                        bend_roles, pavement_roles)
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot

RUN_LEN = 1200.0            # ±600 m about the origin
VALLEY_DEPTH = 25.0         # the V-valley's depth at mid-runway


class _ValleyDem:
    """A V-shaped valley across the runway's middle: flat at 700 m at both
    ends, cut to 675 m at x = 0.  The DEM a runway may NOT follow."""

    provenance = {"synthetic": "V valley across the runway"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - VALLEY_DEPTH * max(0.0, 1.0 - abs(x) / 400.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _RidgeDem:
    """A ridge running across the apron: +8 m over a 120 m half-width."""

    provenance = {"synthetic": "ridge across the apron"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 8.0 * max(0.0, 1.0 - abs(y - 200.0) / 120.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law, dem, cells, *, thresholds=(700.0, 700.0)):
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", r((-RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                      thresholds[0], "fixture"),
            RunwayEnd("27", r((RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                      thresholds[1], "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, thresholds[0], (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key), r


def _solve(law, airport, cells):
    cl = Classification(tuple(cells), (), {}, ())
    pm, _st = build(airport, cl, law)
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    return pm, cs, sol, rep


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def valley(law):
    """A runway over the V-valley, a parallel taxiway leaving it, and the
    graded strip the zone law puts around them."""
    airport, r = _airport(law, _ValleyDem(), ())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400.0, 60.0, 400.0, 83.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 60.0), (), None, "D",
             "airside", "taxi", {}),
    )
    return (*_solve(law, airport, cells), airport)


# ── §4 (1) the runway sits on its CHORD, not on the DEM ─────────────────

def test_runway_follows_the_grounds_trend_through_its_pins(valley, law):
    """§21 (RULINGS 2026-09-10x, superseding 08d (1)'s "rides its chord"):
    the runway's target is the DEM's long-wave trend through its threshold
    pins, and the built ridge reaches it.  The V-valley is 25 m deep and
    wider than the fit window, so the trend dips into it (the runway no
    longer bridges a valley wider than its own vertical curves), but the
    profile is SMOOTH: its second difference along the axis stays far
    under the DEM's own V."""
    pm, _cs, sol, _rep = valley[:4]
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    z = np.asarray(sol.z, float)
    runway = [v for v, vx in pm.vertices.items()
              if any(pm.faces[f].role == "runway" for f in vx.incident_faces)]
    assert runway
    mid = [v for v in runway if pm.vertices[v].dem_z is not None
           and pm.vertices[v].dem_z < 690.0]
    assert mid, "the fixture's valley must reach the runway"
    targeted = [v for v in runway if v in pm.preferred_z]
    assert targeted, "the chord channel carries the trend target"
    # the V is sharper than the K law admits, so the family's hard rows
    # hold the ridge ABOVE the trend target here; what §21 guarantees is
    # that the ridge bent TOWARD the ground as far as the laws allow
    # (it no longer rides the flat 700 m chord) while still filling
    fill = [z[v] - pm.vertices[v].dem_z for v in mid]
    assert min(fill) > 0.0, "the V is narrower than the vertical curves: still filled"
    assert min(z[v] for v in mid) < 700.0 - 1.0, \
        "the ridge bends toward the ground's trend, off the straight chord"
    assert min(z[v] for v in targeted) >= min(pm.preferred_z[v] for v in targeted) - 0.5, \
        "the ridge never goes below its trend target"
    # smoothness: along the axis, the profile's second difference is a
    # small fraction of the DEM's (the V has a kink; the trend has none)
    axis = sorted(((pm.vertices[v].xy[0], v) for v in runway
                   if abs(pm.vertices[v].xy[1]) < 1.0), key=lambda t: t[0])
    if len(axis) >= 5:
        xs = np.array([a for a, _ in axis]); zs = np.array([z[v] for _, v in axis])
        ds = np.array([pm.vertices[v].dem_z or 0.0 for _, v in axis])
        d2 = lambda y: np.abs(np.diff(y, 2) / np.maximum(np.diff(xs)[1:] ** 2, 1.0))
        assert d2(zs).max() < 0.5 * max(d2(ds).max(), 1e-9), \
            "the runway's curvature stays well under the valley's kink"


# ── §4 (2) the taxiway leaving it is TANGENT at the contact ─────────────

def test_the_taxiway_rolls_off_the_runway_without_a_kink(valley, law):
    """§4 (2): TANGENCY at the contact.  A shared vertex carries ONE value,
    so flushness is structural; the reading is that the surface's CURVATURE
    at the contact vertices is no worse than along the sheet — the second
    difference across the contact is at most the along-sheet one."""
    pm, _cs, sol, _rep = valley[:4]
    from auto_patch_v2.solve.design import _cotangent_laplacian, _face_triangles
    z = np.asarray(sol.z, float)
    roles = set(bend_roles(law))
    tris = [t for fid, f in pm.faces.items() if f.role in roles
            for t in _face_triangles(pm, fid)]
    L, area = _cotangent_laplacian(pm, tris, len(pm.vertices))
    curv = np.zeros(len(pm.vertices))
    keep = area > 0.0
    curv[keep] = np.abs((L @ z)[keep]) / area[keep]
    stub = next(f for f, fc in pm.faces.items() if fc.ref == "stubB")
    runway = {f for f, fc in pm.faces.items() if fc.role == "runway"}
    contact = [v for v in pm.ring_vertices(pm.faces[stub].ring)
               if runway & set(pm.vertices[v].incident_faces) and keep[v]]
    assert contact, "the stub must touch the runway"
    sheet = curv[keep]
    assert max(curv[v] for v in contact) <= float(np.percentile(sheet, 95)) + 1e-9, \
        "the contact bends no more than the sheet around it"


# ── §4 (3) an apron over a ridge is a MINIMUM-CURVATURE sheet ───────────

@pytest.fixture(scope="module")
def ridge(law):
    airport, r = _airport(law, _RidgeDem(), ())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400.0, 60.0, 400.0, 83.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 60.0), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(r, -300.0, 83.0, 300.0, 320.0), (), None, "D",
             "airside", "apron", {}),
    )
    return (*_solve(law, airport, cells), airport)


def _bending_energy(pm, law, values, roles=None) -> float:
    """The THIN-PLATE energy the objective minimises, read on the same
    operator the solve uses: ``Σ (L z)² / area`` over the pavement
    triangulation (``solve/design._cotangent_laplacian``)."""
    from auto_patch_v2.solve.design import _cotangent_laplacian, _face_triangles
    roles = set(roles or bend_roles(law))
    tris = [t for fid, f in pm.faces.items() if f.role in roles
            for t in _face_triangles(pm, fid)]
    n = len(pm.vertices)
    L, area = _cotangent_laplacian(pm, tris, n)
    z = np.array([values[v] if values[v] is not None else 0.0 for v in range(n)], float)
    r = L @ z
    keep = area > 0.0
    return float(np.sum(r[keep] ** 2 / area[keep]))


def test_the_apron_over_a_ridge_bends_less_than_the_dem(ridge, law):
    pm, _cs, sol, _rep = ridge[:4]
    z = np.asarray(sol.z, float)
    solved = {v: float(z[v]) for v in pm.vertices}
    dem = {v: pm.vertices[v].dem_z for v in pm.vertices}
    e_z = _bending_energy(pm, law, solved, ("apron",))
    e_dem = _bending_energy(pm, law, dem, ("apron",))
    assert e_dem > 0.0, "the fixture's ridge must bend the DEM"
    assert e_z < e_dem, (f"the design surface bends less than the terrain "
                         f"({e_z:.6f} vs {e_dem:.6f})")


# ── §4 (4) RE-SCOPED by RULINGS 2026-09-09b (3): the graded strip is a LAW
#    surface off the pavement edge and its outer ring is NOT the DEM — the
#    mesh engine blends from the patch boundary outward.  What §4 asked of
#    this twin (the strip blends INSIDE its zone) is now read as: the strip
#    runs DOWN from the pavement it serves and is continuous with it.

def test_the_zone_is_a_law_surface_and_its_outer_ring_is_not_the_dem(ridge, law):
    pm, cs, sol, rep = ridge[:4]
    z = np.asarray(sol.z, float)
    strip = [v for v, vx in pm.vertices.items()
             if any(pm.faces[f].role == "graded_strip" for f in vx.incident_faces)
             and not any(pm.faces[f].role in set(pavement_roles(law))
                         for f in vx.incident_faces)]
    assert strip, "the fixture must carry a graded strip"
    # no vertex is FIXED at its DEM sample any more (09-09b (3))
    from auto_patch_v2.solve.design import DesignReport
    base = assemble(pm, cs, law, DesignReport())
    assert not base.red.dem_fixed, "no vertex is the terrain now"
    assert all(base.red.col[v] >= 0 for v in strip), \
        "every strip vertex is an unknown the law shapes"


def test_no_vertex_at_all_carries_a_dem_fit(ridge, law):
    """RE-SCOPED (RULINGS 2026-09-09b (3)): the ``dem_zone`` term is
    DELETED — not "no PAVEMENT vertex takes a DEM fit" but no vertex at
    all.  The DEM's only entries left are the threshold pins, the tile-seam
    preference and a detached body's own terrain plane."""
    pm, cs, _sol, _rep = ridge[:4]
    from auto_patch_v2.solve.design import DesignReport
    base = assemble(pm, cs, law, DesignReport())
    assert not any(own and own[0] == "dem_zone" for own in base.rows.owner)
    assert not hasattr(law.tables.emit.design, "dem_zone")


# ── §4 (7) a law target is MET where the geometry allows ────────────────

def test_the_law_targets_are_met_where_the_geometry_allows(valley, law):
    _pm, _cs, _sol, rep = valley[:4]
    # the runway's own families (its profile, its crown, its transverse) sit
    # on flat ground here: nothing forces them off their target
    for fam in ("runway_profile", "transverse"):
        rec = rep.families.get(fam)
        if rec is None:
            continue
        assert rec["max_m"] < 0.5, f"{fam} missed by {rec['max_m']} m on flat ground"


def test_the_report_names_every_family_it_read(valley):
    _pm, cs, _sol, rep = valley[:4]
    gens = {r.source.generator for r in cs.rows()}
    read = set(rep.families)
    # every generator that minted an inequality or an equality is reported
    assert read <= gens
    assert read, "the design report names the families it read"


# ── §4 (8) ONE solve; no relaxation path exists ─────────────────────────

def test_there_is_no_relaxation_path_left():
    import importlib
    for gone in ("auto_patch_v2.solve.relax", "auto_patch_v2.solve.tiers",
                 "auto_patch_v2.solve.stage1", "auto_patch_v2.solve.variance",
                 "auto_patch_v2.solve.iis", "auto_patch_v2.solve.assemble",
                 "auto_patch_v2.solve.highs", "auto_patch_v2.constraints.yielding",
                 "auto_patch_v2.law.yield_schema"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(gone)


def test_the_law_tables_carry_no_relaxation_or_yield_block(law):
    emit = law.tables.emit
    assert not hasattr(emit, "relaxation")
    assert not hasattr(emit, "yielding")
    d = emit.design
    # the BENDING WEIGHT IS PER CLASS (RULINGS 2026-09-08v)
    for term in ("bend_runway", "bend_taxi", "bend_apron", "bend_strip",
                 "bend_road", "chord", "law", "taxi_profile", "road",
                 "detached_mean"):
        assert d.weight(term) > 0.0
    for cls in ("runway", "taxi", "apron", "road", "strip"):
        assert d.bend(cls) > 0.0
    # THE RUNWAY FAMILY'S LAWS ARE CONSTRAINTS, not targets
    assert d.hard_rulings and d.hard_weight > d.law and d.hard_tol_m > 0.0


def test_the_solve_is_one_call_and_never_infeasible(valley):
    _pm, _cs, sol, rep = valley[:4]
    assert sol.status is not Status.ERROR
    assert rep.rounds >= 1
    assert rep.converged, "the active set settled"
    assert DEFAULT_METHOD in METHODS


# ── the shape of the model ──────────────────────────────────────────────

def test_the_bending_complex_is_the_sheet_not_only_the_pavement(law):
    """The graded strip bends too (08t answer 3: the blend happens INSIDE
    the zone), the structures never do (they carry their own law)."""
    bend = set(bend_roles(law))
    assert "graded_strip" in bend
    assert "apron" in bend and "runway" in bend
    assert "tunnel_ramp" not in bend and "retaining_wall" not in bend
    pav = set(pavement_roles(law))
    assert "graded_strip" not in pav and "apron" in pav


def test_a_rigid_group_is_one_unknown(valley, law):
    """A ``Flat`` group is merged, not equality-constrained: one column for
    the whole pad (the reduction, §1 'subject to')."""
    pm, cs, _sol, rep = valley[:4]
    from auto_patch_v2.solve.design import DesignReport
    base = assemble(pm, cs, law, DesignReport())
    for f in cs.flats:
        cols = {int(base.red.col[v]) for v in f.group}
        assert len(cols) == 1, "a rigid group is ONE unknown (or wholly fixed)"


def test_pins_are_eliminated_not_penalised(valley, law):
    pm, cs, sol, _rep = valley[:4]
    z = np.asarray(sol.z, float)
    for p in cs.pins:
        assert abs(z[p.v] - p.z) < 1e-6, "a pin is an equality, exactly held"
    assert isinstance(cs, ConstraintSet)


def test_assemble_is_deterministic(valley, law):
    pm, cs, _sol, _rep = valley[:4]
    from auto_patch_v2.solve.design import DesignReport
    a = assemble(pm, cs, law, DesignReport())
    b = assemble(pm, cs, law, DesignReport())
    assert isinstance(a, Base) and isinstance(b, Base)
    assert a.rows.n == b.rows.n and a.red.n_cols == b.red.n_cols
