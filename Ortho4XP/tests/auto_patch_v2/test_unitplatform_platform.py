"""THE UNIT PAD WITHOUT A COLLAR — the twins (spec §56 (3), owner RULINGS
2026-10-07b (4) / 07c (6), issue #452; flat-pad spec §1-§4; the bank rows
of unit-platform spec §1 (3) as they stand for a LANDING, #290).

A unit pad (>= ``[placement] cluster_pad_min_m2``) that FRONTS AIRSIDE is
ONE face under its own ref: no erosion, no ``#collar`` annulus, no refusal
by shape.  HELD, it is flat at its datum column — every own vertex equal to
it, every welded contact held to it — and the object stage reads its ring
as it is.  The 1:3 bank machinery remains for the two banks left inside a
footprint: a block's ``#strip`` (``test_pad_blocks``) and a ramp landing's
``#collar``, twinned here on a landing-shaped pair of cells.

The fixture: an apron (-100..100, 100..200) on ground FALLING 4 % across x,
a 120 x 100 m pad welded to its north edge, the runway far south.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate, platform
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import COLLAR_SUFFIX, is_bank_ref
from auto_patch_v2.model.platform import HELD, datum_vertices
from auto_patch_v2.planar import platform as pplat
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.overlay import Region

from test_v2frontage import HALF_W, RUN_LEN, _airport, _rect  # noqa: E402

APRON = _rect(-100.0, 100.0, 100.0, 200.0)
PAD = _rect(-60.0, 200.0, 60.0, 300.0)
#: the landing-shaped pair: a flat face 5 m inside ``PAD`` and its bank
LANDING = "padU/landing0"
INNER = _rect(-55.0, 205.0, 55.0, 295.0)


class _Dem:
    provenance = {"synthetic": "falling 4 % across x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 0.04 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _base_cells():
    return [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                 (), 3, "D", "airside", "runway", {}),
            Cell(1, "apron", "apronA", APRON, (), None, None, "airside", "apron", {})]


def _cells(pad=PAD):
    return _base_cells() + [
        Cell(2, "building", "padU", pad, (), None, None, "airside", "pad", {})]


def _bank_cells(inset: float = 5.0):
    """A flat face and the bank ``inset`` wide around it, as
    ``planar/landing`` mints a ramp landing (``<unit>/landing<k>`` +
    ``#collar``): the bank's outer rim is welded to the apron, its north
    rim is on the coverage edge."""
    inner = (INNER if inset == 5.0 else
             _rect(-60.0 + inset, 200.0 + inset, 60.0 - inset, 300.0 - inset))
    return _base_cells() + [
        Cell(2, "building", LANDING, inner, (), None, None, "airside", "pad", {}),
        Cell(3, "building", LANDING + COLLAR_SUFFIX, PAD, (inner,), None, None,
             "airside", "pad", {})]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def bank_law(law):
    # the bank pair's flat face is no held block: the 29s contact-led plane
    from tests.auto_patch_v2._plate import contact_led_law
    return contact_led_law(law)


@pytest.fixture(scope="module")
def built(law):
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    return pm, airport, dict(HELD), list(pplat.PLATFORMS)


@pytest.fixture(scope="module")
def banked(bank_law):
    airport = _airport(bank_law, _Dem())
    pm, _st = build(airport, Classification(tuple(_bank_cells()), (), {}, ()), bank_law)
    return pm, airport


def _faces(pm, ref):
    return [f.id for f in pm.faces.values() if f.ref == ref]


def _vs(pm, fids):
    return {v for v, vx in pm.vertices.items() if set(vx.incident_faces) & set(fids)}


def _air_regions():
    return [Region("apron", "a", Polygon(APRON), None, None, "airside", "cell")]


# ── the mint: one face, no collar, no refusal by shape ──────────────────────

def test_a_unit_pad_is_one_face_with_no_collar(built):
    """Spec §56 (3): the pad keeps its ref and its WHOLE polygon — one
    face, welded to the apron — and no bank face is minted for it."""
    pm, _a, held, plats = built
    pad = _faces(pm, "padU")
    assert len(pad) == 1
    assert not [f.ref for f in pm.faces.values() if is_bank_ref(f.ref)]
    assert [(p.ref, p.refused, p.pad_m2) for p in plats] == [("padU", "", 12000.0)]
    assert held["padU"]["verdict"] == "one_block" and not held["padU"].get("conforming")
    assert _vs(pm, pad) & _vs(pm, _faces(pm, "apronA"))          # welded
    ring = Polygon([pm.vertices[v].xy for v in pm.ring_vertices(pm.faces[pad[0]].ring)])
    assert abs(ring.area - 12000.0) < 1.0


def test_no_pad_is_refused_for_its_shape(law):
    """The erosion refusals went with the collar: a 9 m-deep unit pad the
    collar would have ``eroded_away`` is a unit pad; a pad under the unit
    bar or fronting no airside is left alone, as before."""
    thin = Region("building", "thin", Polygon(_rect(-60.0, 200.0, 60.0, 208.0)),
                  None, None, "airside", "cell")
    far = _dc.replace(thin, ref="far", polygon=Polygon(_rect(-60.0, 600.0, 60.0, 700.0)))
    got, counts = pplat.platform_split(_air_regions(), [thin, far], law, 0.5)
    assert [r.ref for r in got] == ["thin", "far"] and counts["platforms"] == 0
    assert not HELD.get("far") and HELD["thin"]["conforming"]
    big = _dc.replace(thin, ref="big", polygon=Polygon(_rect(-100.0, 200.0, 100.0, 245.0)))
    narrow = _dc.replace(thin, ref="narrow",
                         polygon=Polygon(_rect(-400.0, 200.0, 400.0, 209.0)))
    got, counts = pplat.platform_split(_air_regions(), [big, narrow], law, 0.5)
    assert [(r.ref, r.polygon.equals(q.polygon)) for r, q in zip(got, [big, narrow])] == [
        ("big", True), ("narrow", True)]
    assert [(p.ref, p.refused) for p in pplat.PLATFORMS] == [("big", ""), ("narrow", "")]
    assert counts["platforms"] == 2 and counts["platforms_refused"] == 0


def test_a_draped_facade_footprint_is_no_unit_platform(law):
    """Issue #223 (owner read 2026-10-02, SPJC ``building14`` = ``dsf:fac170``
    floating): a pad whose polygon is a DRAPED FACADE's footprint (a
    ``dsf:fac:*`` building covering >= ``DRAPED_FACADE_COVER`` of it) is
    REFUSED ``draped_facade`` — the one refusal left — and is a HELD
    conforming pad (flat-pad spec v2 §4), so the sim's one-floor facade
    sits on a flat footprint.  An OSM building's pad and a pad a facade
    merely touches are unit pads."""
    from types import SimpleNamespace as NS
    pad = Region("building", "fac", Polygon(PAD), None, None, "airside", "cell")
    osm = _dc.replace(pad, ref="osm", polygon=Polygon(_rect(-60.0, 320.0, 60.0, 420.0)))
    air2 = _air_regions() + [Region("apron", "b", Polygon(_rect(-100.0, 300.0, 100.0, 320.0)),
                                    None, None, "airside", "cell")]
    fac = NS(source="dsf:fac:building", outer=tuple(PAD), holes=())
    touch = NS(source="dsf:fac:building",
               outer=tuple(_rect(50.0, 400.0, 80.0, 440.0)), holes=())   # grazes ``osm``
    airport = NS(buildings=(fac, touch))
    got, counts = pplat.platform_split(air2, [pad, osm], law, 0.5, airport=airport)
    assert sorted(r.ref for r in got) == ["fac", "osm"]
    assert [(p.ref, p.refused) for p in pplat.PLATFORMS] == [
        ("fac", pplat.REFUSED_DRAPED_FACADE), ("osm", "")]
    assert counts["platforms"] == 1 and counts["platforms_refused"] == 1
    assert HELD["fac"]["conforming"]
    # the one derivation both the mint and this twin read
    assert pplat.draped_facade_pads([pad, osm], airport) == {id(pad)}
    assert pplat.draped_facade_pads([pad, osm], None) == set()


def test_a_junction_frontage_is_a_frontage_at_both_sites(law):
    """Issue #223 deviation 4: the mint and the flat-pad block planner read
    ONE frontage accessor (``law.tables.frontage_roles`` = every airside
    rolled-on role).  A pad fronting only a taxi-family JUNCTION cell (SPJC
    ``building14`` on pav40's junction) is a platform AND a planned block —
    never a platform the planner leaves unheld (the 29s contact-led tilt)."""
    from auto_patch_v2.law.tables import frontage_roles, rolled_on_roles
    from auto_patch_v2.planar.pad_blocks import plan_blocks
    assert frontage_roles(law) == rolled_on_roles(law)
    assert {"junction", "apron", "stub", "runway"} <= frontage_roles(law)
    air = [Region("junction", "j", Polygon(APRON), 3, "C", "airside", "cell")]
    pad = Region("building", "u", Polygon(PAD), None, None, "airside", "cell")
    airport = _airport(law, _Dem())
    plan = plan_blocks("u", Polygon(PAD), air, law, _Dem(), airport, 2.0)
    assert plan is not None and plan.contacts > 0


def test_a_second_region_of_a_unit_ref_keeps_the_ref(law):
    """ONE REF, ONE PAD: a sliver the 23a cut left under the same ref is the
    pad's (HECA ``building4``'s rim slivers) — there is no collar to give
    it to."""
    main = Region("building", "u", Polygon(PAD), None, None, "airside", "cell")
    sliver = _dc.replace(main, polygon=Polygon(_rect(60.0, 200.0, 61.0, 201.0)))
    got, _c = pplat.platform_split(_air_regions(), [main, sliver], law, 0.5)
    assert [r.ref for r in got] == ["u", "u"]


def test_a_unit_pad_is_one_face_when_a_foreign_ring_edge_crosses_it(law):
    """ONE PAD, ONE FACE (owner RULINGS 2026-09-29n (4), issue #94).  The
    ``_mixed_rim_cells`` shape: an apron whose hole covers only the pad's
    western half, touching its own shell along x = 20 — a ring edge that
    runs THROUGH the pad.  The pad's faces are merged back along it."""
    pad = _rect(-60.0, 180.0, 60.0, 240.0)
    cells = [_cells(pad)[0],
             Cell(1, "apron", "apronA", _rect(-260.0, 140.0, 20.0, 260.0),
                  (_rect(-60.0, 180.0, 20.0, 240.0),), None, None, "airside",
                  "apron", {}),
             Cell(2, "building", "padU", pad, (), None, None, "airside", "pad", {})]
    pm, _st = build(_airport(law, _Dem()), Classification(tuple(cells), (), {}, ()), law)
    assert [p.ref for p in pplat.PLATFORMS] == ["padU"] and not pplat.PLATFORMS[0].refused
    plat = _faces(pm, "padU")
    assert len(plat) == 1, [len(pm.faces[q].ring) for q in plat]
    pf = pm.faces[plat[0]]
    P = Polygon([pm.vertices[v].xy for v in pm.ring_vertices(pf.ring)])
    assert not pf.holes and abs(P.area - 7200.0) < 1.0


def test_merge_platform_faces_keeps_every_boundary_vertex(law):
    """The merge is exact: an edge walked by both faces cancels, every
    other vertex is kept coordinate for coordinate (a collinear node the
    collar still walks stays on the platform ring); pieces that share no
    edge stay separate faces."""
    a = Polygon([(0, 0), (10, 0), (10, 5), (10, 10), (0, 10)])
    b = Polygon([(10, 0), (20, 0), (20, 10), (10, 10), (10, 5)])
    far = Polygon([(40, 0), (50, 0), (50, 10), (40, 10)])
    out = pplat._merge_group([a, b])
    assert out is not None and len(out) == 1
    assert set(out[0].exterior.coords) == {(0, 0), (10, 0), (20, 0), (20, 10),
                                           (10, 10), (0, 10)}
    assert abs(out[0].area - 200.0) < 1e-9
    two = pplat._merge_group([a, far])
    assert two is not None and len(two) == 2


# ── the rows: flat at the datum, the frontage held ────────────────────────

def test_the_held_pad_is_flat_at_its_datum_and_leads_its_frontage(built, law):
    """Spec §56 (3) / flat-pad spec §1: the contacts are the pad face's own
    airside vertices; the datum column is an OWN vertex; every other own
    vertex takes a hard two-way row to it; every contact a hold row."""
    pm, airport, held, _p = built
    HELD.clear()
    HELD.update(held)
    (ref, flat, weld), = platform.platform_contacts(pm, law)
    air = _vs(pm, _faces(pm, "apronA"))
    assert ref == "padU" and set(weld) == _vs(pm, _faces(pm, "padU")) & air
    assert flat and not set(flat) & air
    dv = datum_vertices(pm, law)["padU"]
    assert dv in flat
    assert platform.flat_held_refs(pm, law) == {"padU"}
    plane = platform.platform_plane_rows(pm, law, airport)
    assert len(plane) == 2 * (len(flat) - 1)
    assert all(platform.PLANE_RULING in r.source.ruling
               and {v for v, _c in r.terms} - {dv} <= set(flat) for r in plane)
    hold = platform.frontage_hold_rows(pm, law, airport)
    assert {v for r in hold for v, _c in r.terms} == set(weld) | {dv}
    assert all(platform.HOLD_RULING in r.source.ruling for r in hold)


def test_a_vertex_a_structure_carries_is_not_the_host_pads_flat_vertex(law, monkeypatch):
    """A structure cut into its host pad (a wall-corridor / door / tunnel
    ramp's top) keeps its own level at the vertices it shares with the pad:
    they are neither held contacts nor flat vertices, and never the datum
    column.  MEASURED on the OTHH closing build (lane pads59): with the 25
    ramp-top vertices of ``building6`` in the flat set the terminal settled
    at the ramps' 2.61 m — 1.35 m under its frontage median 3.962, the apron
    following, hard_conflict 0 -> 210; out of it, 3.962 and 66 (pad tier).
    The fixture stands a face in for the structure by its ROLE."""
    cells = _cells() + [Cell(3, "parking_lot", "lotN", _rect(-60.0, 300.0, 60.0, 340.0),
                             (), None, None, "groundside", "lot", {})]
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    lot = _vs(pm, _faces(pm, "lotN")) & _vs(pm, _faces(pm, "padU"))
    assert lot
    (_r, flat0, _w), = platform.platform_contacts(pm, law)
    assert lot <= set(flat0)                     # a lot is no structure
    monkeypatch.setattr("auto_patch_v2.law.tables.is_structure_role",
                        lambda _law, role: role == "parking_lot")
    (_r, flat, weld), = platform.platform_contacts(pm, law)
    assert not lot & set(flat) and not lot & set(weld)
    assert set(flat) == set(flat0) - lot


def test_the_solved_pad_is_flat_and_its_record_carries_no_collar_key(built, law):
    """On a solve: one flat plane at the datum, every weld on it, nothing
    released, nothing warned — and the record names no collar."""
    from auto_patch_v2.solve import solve_design
    pm, airport, held, _p = built
    HELD.clear()
    HELD.update(held)
    cs, _c, _w = generate(pm, law, airport)
    z = np.asarray(solve_design(pm, cs, law)[0].z, float)
    rec, = platform.platform_records(pm, law, z)
    assert rec["ref"] == "padU" and rec["pad_m2"] == 12000.0
    assert rec["plane_residual_max_m"] <= 0.01 and rec["tilt_pct"] <= 0.01
    assert rec["hold_verdict"] == "held" and rec["released"] == 0
    assert rec["held_within_tol"] == rec["held_contacts"] > 0
    assert rec["warned"] is False and rec["warning"] is None
    assert not {"collar_m", "collar_minted_m", "collar_needed_m", "collar_why",
                "rim_relief_max_m", "rim_relief_p50_m", "over_collar_max"} & set(rec)
    pad_v = sorted(_vs(pm, _faces(pm, "padU")))
    assert float(np.ptp(z[pad_v])) <= 0.02              # the WHOLE rim on the plane


# ── the object stage ─────────────────────────────────────────────────────

def _doc(pm, z):
    return {"vertices": [[v, vx.key[0], vx.key[1], z[v]] for v, vx in pm.vertices.items()],
            "faces": [{"ref": f.ref, "role": f.role, "ring": list(pm.ring_vertices(f.ring))}
                      for f in pm.faces.values() if f.role == "building"],
            "breaklines": []}


def test_the_object_stage_reads_the_pad_face_as_it_is(built):
    """§56 (3): ``pads_rims_from_graded_doc`` publishes the pad face's own
    ring at its own heights — one ring per ref."""
    from auto_patch_v2.airport.placement_read import pads_rims_from_graded_doc
    pm, _a, _h, _p = built
    pads, _rims = pads_rims_from_graded_doc(_doc(pm, {v: 100.0 for v in pm.vertices}))
    assert [(p.ref, len(p.ring)) for p in pads] == [
        ("padU", len(pm.ring_vertices(pm.faces[_faces(pm, "padU")[0]].ring)))]
    assert set(pads[0].z) == {100.0}


# ── the bank rows, as a landing keeps them ───────────────────────────────

def test_the_bank_never_joins_the_plate(banked, bank_law):
    """§3 P1 / P9: the flat face's plane group holds its own vertices only;
    the bank's face rides it and adds none."""
    from auto_patch_v2.constraints.cluster_pad import plane_groups
    pm, airport = banked
    plat, col = _faces(pm, LANDING), _faces(pm, LANDING + COLLAR_SUFFIX)
    grp = [g for g in plane_groups(pm, bank_law, airport) if set(g[3]) & set(plat)]
    assert len(grp) == 1
    _fid, _ref, vs, fids = grp[0]
    assert set(col) <= set(fids) and set(vs) == _vs(pm, plat)


def test_the_bank_rows_are_a_one_way_bank_and_the_flat_face_one_plane(banked, bank_law):
    """§3 P3: every airside rim vertex leads a 1:3 row to the flat face (it
    follows); the bank's OWN rim row is the 1:3 bank, one-way with the flat
    side leading (RULINGS 2026-10-02v (5)); the flat face is one HARD plane."""
    pm, airport = banked
    rows = platform.platform_collar_rows(pm, bank_law, airport)
    bs = float(bank_law.tables.emit.design.bank_slope)
    inner = _vs(pm, _faces(pm, LANDING))
    air = _vs(pm, _faces(pm, "apronA"))
    led = [r for r in rows if r.a in air]
    assert led and all(r.cap == pytest.approx(bs) and r.follows == (r.b,)
                       and r.b in inner for r in led)
    own = [r for r in rows if r.a not in air]
    assert own and all(r.cap == pytest.approx(bs) and r.follows == (r.a,) for r in own)
    plane = platform.platform_plane_rows(pm, bank_law, airport)
    assert plane and all(platform.PLANE_RULING in r.source.ruling for r in plane)
    assert platform.STATS["platform_collar_rows"]["collars"] == 1


def test_the_solved_bank_pair_is_one_plane_led_by_its_contacts(banked, bank_law):
    """29s (A) on a solve: the flat face is one plane (residual <= 0.01 m)
    within the 1 % ceiling, and its record carries the bank's width and the
    relief the bank carries at its welded rim."""
    from auto_patch_v2.solve import solve_design
    pm, airport = banked
    cs, _c, _w = generate(pm, bank_law, airport)
    z = np.asarray(solve_design(pm, cs, bank_law)[0].z, float)
    rec, = platform.platform_records(pm, bank_law, z)
    assert rec["ref"] == LANDING and rec["collar_m"] == pytest.approx(5.0, abs=0.5)
    assert rec["plane_residual_max_m"] <= 0.01
    assert rec["tilt_pct"] <= 100.0 * float(
        bank_law.tables.emit.within_shape.pad_slope_max) + 0.01
    assert rec["welded"] > 0 and "rim_relief_max_m" in rec


def _coverage_collar_vertices(pm, ref):
    """The bank's OWN vertices on the coverage edge (an edge with no face
    beyond): issue #223's population."""
    col = set(_faces(pm, ref + COLLAR_SUFFIX))
    out = set()
    for e in pm.edges.values():
        if (e.left_face is None) == (e.right_face is None):
            continue
        if (e.left_face if e.left_face is not None else e.right_face) not in col:
            continue
        out.update(v for v in (e.a, e.b) if set(pm.vertices[v].incident_faces) <= col)
    return out


def test_a_coverage_edge_bank_vertex_keeps_the_bank_and_the_ground(banked, bank_law):
    """Issue #223 / #302 (master ruling 2026-10-08 R3 (2): a landing's bank
    is a ``#collar`` face and can stand on the coverage edge): such a vertex
    keeps a ONE-WAY 1:3 row with the flat side leading, and carries the §23
    ground datum."""
    from auto_patch_v2.solve.design_ground import (coverage_edge_collar_vertices,
                                                   ground_datum_vertices)
    pm, airport = banked
    cov = _coverage_collar_vertices(pm, LANDING)
    assert cov
    rows = [r for r in platform.platform_collar_rows(pm, bank_law, airport) if r.a in cov]
    assert rows and all(r.follows == (r.a,) for r in rows)
    assert platform.STATS["platform_collar_rows"]["rows_coverage_edge_follows"] == len(rows)
    assert cov <= coverage_edge_collar_vertices(pm) <= ground_datum_vertices(pm, bank_law)


def test_a_walled_ramp_cut_into_a_pad_is_a_declared_step(law, monkeypatch):
    """A PAD HOSTING A WALLED RAMP (lane pads65; owner RULINGS 2026-10-07e).
    The ramp's vertices on the pad stand at the ramp's level; the pad's own
    vertex beside one is the wall's top rim and stays ON THE PAD, so the
    pad's edge between them is the WALL — a declared step.  No plate row,
    no 1 % ceiling, no pavement fallback and no 5 % ceiling twin is stated
    across it (until spec §56 (3) the collar face kept them out as a bank).
    MEASURED at three OTHH ramp portals without the exemption: 31 stage-2
    hard conflicts over 0.5-6.0 m chords and 28 rim vertices down by up to
    1.35 m, four below the ramp top.  The fixture stands a face in for the
    ramp by its ROLE and pins it 1.40 m under the pad."""
    from auto_patch_v2.constraints import pads as cpads
    from auto_patch_v2.constraints.pavement_cap import GEN as CAP_GEN
    from auto_patch_v2.constraints.ceiling import GEN as CEIL_GEN
    from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
    from auto_patch_v2.model.platform import structure_vertices
    from auto_patch_v2.solve import solve_design
    from auto_patch_v2.solve import feasibility
    cells = _cells() + [Cell(3, "parking_lot", "lotN", _rect(-60.0, 300.0, 60.0, 340.0),
                             (), None, None, "groundside", "lot", {})]
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    monkeypatch.setattr("auto_patch_v2.law.tables.is_structure_role",
                        lambda _law, role: role == "parking_lot")
    pad = _vs(pm, _faces(pm, "padU"))
    ramp = structure_vertices(pm, law)
    top = ramp & pad
    assert top and ramp == _vs(pm, _faces(pm, "lotN"))
    assert all(not top & set(g) for _f, _r, g in cpads._pad_groups(pm, law))
    cs, _c, _w = generate(pm, law, airport)
    for r in cs.rows():
        named = ({r.a, r.b} if isinstance(r, Diff) else
                 {v for v, _c2 in getattr(r, "terms", ())})
        if named & top and named & (pad - top):
            assert r.source.generator not in (cpads.GEN, CAP_GEN, CEIL_GEN), r
    (_ref, flat, weld), = platform.platform_contacts(pm, law)
    dv = datum_vertices(pm, law)["padU"]
    assert dv not in top and not top & set(flat)
    src = Source("twin", "twin ramp pin", ())
    free = solve_design(pm, cs, law)[0].z
    level = float(free[dv])
    pinned = cs.merged(ConstraintSet.from_rows(
        Pin(v, level - 1.40, src) for v in sorted(ramp)))
    z = np.asarray(solve_design(pm, pinned, law)[0].z, float)
    assert abs(float(z[dv]) - level) <= 0.01
    assert max(abs(float(z[v]) - float(z[dv])) for v in flat) <= 0.01   # the rim
    assert all(abs(float(z[dv]) - float(z[v]) - 1.40) <= 0.01 for v in top)  # the wall
    assert not feasibility.HARD_CONFLICT
