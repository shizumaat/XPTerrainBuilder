"""THE UNIT PLATFORM — the twins (unit-platform spec §1 (2)-(5), §3 P1 / P3 /
P9 / P15 / P20 / P21; owner RULINGS 2026-09-28a (1); issues #66 / #4 / #10;
lane ``unitplatform2``).

A unit pad (>= ``[placement] cluster_pad_min_m2``) that FRONTS AIRSIDE is
minted as PLATFORM pieces (the pad eroded by C) inside a COLLAR
(``<ref>#collar``): the collar keeps the welded rim (airside unmoved), the
platform is ONE plane, and the collar is a 1:3 bank between them that no
plate, no within-shape reading and no pavement ceiling prices.

The fixture: an apron (-100..100, 100..200) on ground FALLING 4 % across x,
a 120 x 100 m pad welded to its north edge, the runway far south.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate, platform
from auto_patch_v2.constraints.cluster_pad import plane_groups
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import COLLAR_SUFFIX, is_collar_ref
from auto_patch_v2.planar import platform as pplat
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.overlay import Region

from test_v2frontage import HALF_W, RUN_LEN, _airport, _rect  # noqa: E402

APRON = _rect(-100.0, 100.0, 100.0, 200.0)
PAD = _rect(-60.0, 200.0, 60.0, 300.0)


class _Dem:
    provenance = {"synthetic": "falling 4 % across x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 0.04 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _cells(pad=PAD):
    return [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                 (), 3, "D", "airside", "runway", {}),
            Cell(1, "apron", "apronA", APRON, (), None, None, "airside", "apron", {}),
            Cell(2, "building", "padU", pad, (), None, None, "airside", "pad", {})]


@pytest.fixture(scope="module")
def law():
    # the subject is the pre-hold platform / plate path: the flat-pad hold
    # (RULINGS 2026-09-30f/r) is disarmed for it, never for its own twins
    from tests.auto_patch_v2._plate import contact_led_law
    return contact_led_law(Law.for_airport("ZZZZ"))


@pytest.fixture(scope="module")
def built(law):
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    return pm, airport


def _faces(pm, ref):
    return [f.id for f in pm.faces.values() if f.ref == ref]


def _vs(pm, fids):
    return {v for v, vx in pm.vertices.items() if set(vx.incident_faces) & set(fids)}


def test_the_pad_is_minted_as_a_platform_inside_a_collar(built, law):
    """§1 (2)/(3): the platform keeps the pad's ref, the collar is
    ``<ref>#collar``; the platform stands C = bank_min_width_m inside the
    rim; the collar keeps the welded rim, the platform touches no apron."""
    pm, _a = built
    plat, col = _faces(pm, "padU"), _faces(pm, "padU" + COLLAR_SUFFIX)
    assert plat and col
    assert [p.ref for p in pplat.PLATFORMS] == ["padU"] and not pplat.PLATFORMS[0].refused
    C = float(law.tables.emit.design.bank_min_width_m)
    rim = Polygon(PAD).exterior
    from shapely.geometry import Point
    inner = _vs(pm, plat)
    assert min(rim.distance(Point(pm.vertices[v].xy)) for v in inner) >= C - 0.5
    apron = _vs(pm, _faces(pm, "apronA"))
    assert not (inner & apron)                      # the platform is not welded
    assert _vs(pm, col) & apron                     # the collar keeps the weld
    assert all(pm.faces[q].role == "building" for q in plat + col)


def test_a_pad_fronting_no_airside_or_too_narrow_gets_no_platform(law):
    """§1 (2): a pad whose erosion by C leaves nothing is REFUSED and keeps
    its plate; a pad fronting no airside is left alone."""
    air = [Region("apron", "a", Polygon(APRON), None, None, "airside", "cell")]
    thin = Region("building", "thin", Polygon(_rect(-60.0, 200.0, 60.0, 208.0)),
                  None, None, "airside", "cell")
    big = _rect(-100.0, 200.0, 100.0, 245.0)            # 9,000 m2, 45 m deep
    far = Region("building", "far", Polygon(_rect(-60.0, 600.0, 60.0, 700.0)),
                 None, None, "airside", "cell")
    got, counts = pplat.platform_split(air, [thin, far], law, 0.5)
    assert [r.ref for r in got] == ["thin", "far"]        # thin < min area
    assert counts["platforms"] == 0
    ok = Region("building", "big", Polygon(big), None, None, "airside", "cell")
    narrow = _dc.replace(ok, ref="narrow", polygon=Polygon(_rect(-400.0, 200.0, 400.0, 209.0)))
    got, counts = pplat.platform_split(air, [ok, narrow], law, 0.5)
    refs = sorted(r.ref for r in got)
    assert "big" in refs and "big" + COLLAR_SUFFIX in refs
    assert [(p.ref, p.refused) for p in pplat.PLATFORMS] == [
        ("big", ""), ("narrow", "eroded_away")]


def test_a_draped_facade_footprint_takes_no_collar(law):
    """Issue #223 (owner read 2026-10-02, SPJC ``building14`` = ``dsf:fac170``
    floating): a pad whose polygon is a DRAPED FACADE's footprint (a
    ``dsf:fac:*`` building covering >= ``DRAPED_FACADE_COVER`` of it) is
    REFUSED ``draped_facade`` and keeps its plate WHOLE — no ``#collar``
    region, no platform — so flat-pad spec v2 §4 holds the whole footprint
    flat at its frontage datum and the sim's one-floor facade sits on it.
    An OSM building's pad, a pad a facade merely touches, and a run with no
    airport keep today's platform + collar."""
    from types import SimpleNamespace as NS
    air = [Region("apron", "a", Polygon(APRON), None, None, "airside", "cell")]
    pad = Region("building", "fac", Polygon(PAD), None, None, "airside", "cell")
    osm = _dc.replace(pad, ref="osm", polygon=Polygon(_rect(-60.0, 320.0, 60.0, 420.0)))
    air2 = air + [Region("apron", "b", Polygon(_rect(-100.0, 300.0, 100.0, 320.0)),
                         None, None, "airside", "cell")]
    fac = NS(source="dsf:fac:building", outer=tuple(PAD), holes=())
    touch = NS(source="dsf:fac:building",
               outer=tuple(_rect(50.0, 400.0, 80.0, 440.0)), holes=())   # grazes ``osm``
    airport = NS(buildings=(fac, touch))
    got, counts = pplat.platform_split(air2, [pad, osm], law, 0.5, airport=airport)
    refs = sorted(r.ref for r in got)
    assert "fac" in refs and "fac" + COLLAR_SUFFIX not in refs
    assert "osm" in refs and "osm" + COLLAR_SUFFIX in refs
    assert [(p.ref, p.refused, p.collar_m) for p in pplat.PLATFORMS
            if p.ref == "fac"] == [("fac", pplat.REFUSED_DRAPED_FACADE, 0.0)]
    assert counts["platforms"] == 1 and counts["platforms_refused"] == 1
    # the one derivation both the mint and this twin read
    assert pplat.draped_facade_pads([pad, osm], airport) == {id(pad)}
    assert pplat.draped_facade_pads([pad, osm], None) == set()
    # no airport: today's path, a platform inside a collar
    got, counts = pplat.platform_split(air, [pad], law, 0.5)
    assert "fac" + COLLAR_SUFFIX in {r.ref for r in got} and counts["platforms"] == 1


def test_a_second_region_of_a_platform_ref_is_collar(law):
    """ONE REF, ONE PAD: a sliver the 23a cut left under the same ref is
    collar, never a platform piece (HECA ``building4``'s rim slivers)."""
    air = [Region("apron", "a", Polygon(APRON), None, None, "airside", "cell")]
    main = Region("building", "u", Polygon(PAD), None, None, "airside", "cell")
    sliver = _dc.replace(main, polygon=Polygon(_rect(60.0, 200.0, 61.0, 201.0)))
    got, _c = pplat.platform_split(air, [main, sliver], law, 0.5)
    assert [r.ref for r in got if r.polygon.equals(sliver.polygon)] == ["u" + COLLAR_SUFFIX]


def test_the_collar_never_joins_the_plate(built, law):
    """§3 P1 / P9: the platform's plane group holds the platform's vertices
    only; the collar's face rides it (for the frontage) and adds none."""
    pm, airport = built
    plat, col = _faces(pm, "padU"), _faces(pm, "padU" + COLLAR_SUFFIX)
    grp = [g for g in plane_groups(pm, law, airport) if set(g[3]) & set(plat)]
    assert len(grp) == 1
    _fid, _ref, vs, fids = grp[0]
    assert set(col) <= set(fids)
    assert set(vs) == _vs(pm, plat)


def test_the_collar_rows_are_a_one_way_bank_and_the_platform_one_plane(built, law):
    """§3 P3: every airside rim vertex leads a 1:3 row to the platform (the
    platform follows); the platform is one HARD plane; P11: neither is
    twinned into the 5 % pavement ceiling."""
    pm, airport = built
    rows = platform.platform_collar_rows(pm, law, airport)
    bs = float(law.tables.emit.design.bank_slope)
    inner = _vs(pm, _faces(pm, "padU"))
    air = _vs(pm, _faces(pm, "apronA"))
    led = [r for r in rows if r.a in air]
    assert led and all(r.cap == pytest.approx(bs) and r.follows == (r.b,)
                       and r.b in inner for r in led)
    plane = platform.platform_plane_rows(pm, law, airport)
    assert plane and all(platform.PLANE_RULING in r.source.ruling for r in plane)
    cs, _c, _w = generate(pm, law, airport)
    from auto_patch_v2.constraints.ceiling import GEN as CEIL
    from auto_patch_v2.model.constraints import Diff
    col_v = _vs(pm, _faces(pm, "padU" + COLLAR_SUFFIX))
    for r in cs.rows():
        if r.source.generator == CEIL and isinstance(r, Diff):
            assert not ({r.a, r.b} <= col_v and ({r.a, r.b} & inner)
                        and ({r.a, r.b} - inner)), "the collar bank was ceilinged"


def test_the_solved_platform_is_one_plane_and_the_rim_stays_the_aprons(built, law):
    """§1 (1)/(4) on a solve: the platform is one plane (residual <= 0.01 m)
    tilting at most 1 %; its rim vertices are the apron's."""
    from auto_patch_v2.solve import solve_design
    pm, airport = built
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    z = np.asarray(sol.z, float)
    recs = platform.platform_records(pm, law, z)
    assert [r["ref"] for r in recs] == ["padU"]
    r = recs[0]
    assert r["plane_residual_max_m"] <= 0.01
    assert r["tilt_pct"] <= 100.0 * float(law.tables.emit.within_shape.pad_slope_max) + 0.01
    assert r["welded"] > 0 and "rim_relief_max_m" in r
    assert r["collar_m"] >= float(law.tables.emit.design.bank_min_width_m) - 0.5


def test_the_object_stage_reads_the_collar_as_the_platform(built, law):
    """§3 P15: ``pads_rims_from_graded_doc`` publishes the collar under the
    PLATFORM's ref with its OUTER ring and the platform plane's heights, so
    containment is the unit footprint and every min / median is the
    platform's."""
    from auto_patch_v2.airport import anchor_rule as _ar
    from auto_patch_v2.airport.placement_read import pads_rims_from_graded_doc
    pm, _a = built
    # a graded document: every vertex id, lat, lon, z; the pad faces' rings
    z = {v: (100.0 if v in _vs(pm, _faces(pm, "padU")) else 97.0) for v in pm.vertices}
    doc = {"vertices": [[v, vx.key[0], vx.key[1], z[v]] for v, vx in pm.vertices.items()],
           "faces": [{"ref": f.ref, "role": f.role,
                      "ring": list(pm.ring_vertices(f.ring))}
                     for f in pm.faces.values() if f.role == "building"],
           "breaklines": []}
    pads, _rims = pads_rims_from_graded_doc(doc)
    assert {p.ref for p in pads} == {"padU"}
    folded = _ar.fold_pad_ref(pads, "padU")
    assert min(folded.z) == pytest.approx(100.0, abs=1e-6)
    # a point in the collar annulus is on the pad
    rim_v = next(v for v in _vs(pm, _faces(pm, "padU" + COLLAR_SUFFIX))
                 if v not in _vs(pm, _faces(pm, "padU")))
    la, lo = pm.vertices[rim_v].key
    cy = sum(p[0] for p in folded.ring) / len(folded.ring)
    cx = sum(p[1] for p in folded.ring) / len(folded.ring)
    assert _ar.pad_contains(folded, la + 0.02 * (cy - la), lo + 0.02 * (cx - lo))


def test_the_census_reads_the_collar_as_a_bank(built, law):
    """§3 P20: verify's within_shape and pad_flat never read a collar; the
    census families report one row per platform / refusal."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import check_grade as CG
    assert "platform_rim_relief" in dict((k, d) for k, d, _p in CG.LAW_FAMILIES)
    assert CG.SIDECAR_LAW_KEYS["platforms"] == "platforms_ll"
    recs = [{"ref": "padU", "collar_m": 5.0, "level": 100.0, "rim_relief_max_m": 1.2,
             "worst_ll": [60.5, -135.5], "worst_z": 101.2},
            {"ref": "thin", "refused": "eroded_away", "pad_m2": 960.0}]
    rr = CG._check_platform_rim_relief(recs)
    assert len(rr) == 1 and rr[0].de_m == pytest.approx(1.2)
    assert len(CG._check_platform_refused(recs)) == 1
    w = CG.Way("x", "building", "padU#collar", "", [], [], {"role": "building"})
    assert CG._is_platform_collar(w)
    assert is_collar_ref("padU#collar") and not is_collar_ref("padU")
    assert math.isfinite(rr[0].elev_b)


def test_a_platform_is_one_face_when_a_foreign_ring_edge_crosses_the_pad(law):
    """ONE PLATFORM, ONE FACE (owner RULINGS 2026-09-29n (4), issue #94).
    The ``_mixed_rim_cells`` shape: an apron whose hole covers only the
    pad's western half, touching its own shell along x = 20 — a ring edge
    that runs THROUGH the pad.  Measured before the fix: the platform came
    out as TWO faces of ref ``padU`` (6 + 8 vertices) and the collar as two
    C-shapes with no hole.  After it: ONE platform face, ONE collar face
    whose hole IS the platform's ring, and no vertex of the dividing edge
    left inside the platform."""
    pad = _rect(-60.0, 180.0, 60.0, 240.0)
    cells = [_cells(pad)[0],
             Cell(1, "apron", "apronA", _rect(-260.0, 140.0, 20.0, 260.0),
                  (_rect(-60.0, 180.0, 20.0, 240.0),), None, None, "airside",
                  "apron", {}),
             Cell(2, "building", "padU", pad, (), None, None, "airside", "pad", {})]
    pm, _st = build(_airport(law, _Dem()), Classification(tuple(cells), (), {}, ()), law)
    assert [p.ref for p in pplat.PLATFORMS] == ["padU"] and not pplat.PLATFORMS[0].refused
    plat, col = _faces(pm, "padU"), _faces(pm, "padU" + COLLAR_SUFFIX)
    assert len(plat) == 1, [len(pm.faces[q].ring) for q in plat]
    assert len(col) == 1
    pf, cf = pm.faces[plat[0]], pm.faces[col[0]]
    assert not pf.holes and len(cf.holes) == 1
    assert set(pm.ring_vertices(cf.holes[0])) == set(pm.ring_vertices(pf.ring))
    # the platform is the pad eroded by C: no vertex of it stands at x = 20
    # strictly inside the ring (the dropped edge's own nodes are gone)
    P = Polygon([pm.vertices[v].xy for v in pm.ring_vertices(pf.ring)])
    assert abs(P.area - pplat.PLATFORMS[0].platform_m2) < 1.0
    assert P.exterior.distance(Polygon(pad).exterior) >= 4.5


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


# ── SPEC-AUTHOR RULINGS 2026-09-29s (A) (#96): the plane is CONTACT-LED ──


class _Dem1pct:
    provenance = {"synthetic": "falling 1 % across x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 0.01 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _contact_read(pm, law, z):
    """Per platform: the plane at every welded contact minus the contact."""
    out = {}
    for ref, inner, weld in platform.platform_contacts(pm, law):
        X = np.array([pm.vertices[v].xy for v in inner])
        c0 = X.mean(axis=0)
        A = np.c_[X - c0, np.ones(len(X))]
        co, *_ = np.linalg.lstsq(A, z[inner], rcond=None)
        W = np.array([pm.vertices[v].xy for v in weld])
        out[ref] = (np.c_[W - c0, np.ones(len(W))] @ co) - z[weld]
    return out


def test_a_platform_over_a_1pct_apron_follows_it(law):
    """29s (A): one ONE-WAY level row per welded contact against the plane
    AT that contact (the contact leads, the platform follows), and the
    cap-0 zero-tilt target released — so a platform fronting an apron that
    falls 1 % along the frontage tilts with it instead of sitting flat at
    the contacts' mean (the flat plane missed the ends by 0.6 m on this
    120 m frontage; HECA ``building4`` by 3.4 m)."""
    from auto_patch_v2.constraints.pads import LEVEL_RULING, pad_flats
    from auto_patch_v2.solve import solve_design
    airport = _airport(law, _Dem1pct())
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    rows = platform.platform_level_rows(pm, law, airport)
    inner = _vs(pm, _faces(pm, "padU"))
    air = _vs(pm, _faces(pm, "apronA"))
    assert rows and all(r.source.ruling.startswith(LEVEL_RULING) for r in rows)
    for r in rows:
        feet = {v for v, _c in r.terms}
        assert set(r.follows) <= inner and len(feet & air) == 1
    # the cap-0 plate prices no pair of the platform (its tilt is free)
    assert not [r for r in pad_flats(pm, law, airport)
                if {r.a, r.b} <= inner]
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    z = np.asarray(sol.z, float)
    rec = platform.platform_records(pm, law, z)[0]
    assert rec["plane_residual_max_m"] <= 0.01
    assert 0.5 <= rec["tilt_pct"] <= 100.0 * float(
        law.tables.emit.within_shape.pad_slope_max) + 0.01
    rel = _contact_read(pm, law, z)["padU"]
    assert float(np.max(np.abs(rel))) <= 0.25


def test_a_refused_platform_fronting_airside_takes_the_contact_led_fit(law):
    """29s (E): a platform REFUSED ``under_min_area`` (120 x 50 m: 6,000 m2
    of pad, 4,400 m2 after the 5 m erosion) stays a plain welded plate with
    its min-area unchanged, and takes the same contact-led fit: one hard
    plane over its OWN vertices (never an airside one — 10y), one one-way
    level row per welded contact, the cap-0 target released — so it tilts
    with the 1 % apron it fronts."""
    from auto_patch_v2.constraints.pads import pad_flats
    from auto_patch_v2.solve import solve_design
    # vertexed along its sides, as a pack footprint ring is (a rim-only
    # plate whose own vertices were all on one line would carry no plane)
    narrow = ((-60.0, 200.0), (60.0, 200.0), (60.0, 225.0),
              (60.0, 250.0), (-60.0, 250.0), (-60.0, 225.0))
    airport = _airport(law, _Dem1pct())
    pm, _st = build(airport, Classification(tuple(_cells(narrow)), (), {}, ()), law)
    assert [(p.ref, p.refused) for p in pplat.PLATFORMS] == [("padU", "under_min_area")]
    assert not any(is_collar_ref(f.ref) for f in pm.faces.values())
    (ref, own, weld), = platform.refused_plates(pm, law)
    air = _vs(pm, _faces(pm, "apronA"))
    assert ref == "padU" and not (set(own) & air) and set(weld) <= air
    assert platform.platform_plane_rows(pm, law, airport)
    assert platform.platform_level_rows(pm, law, airport)
    pad_v = _vs(pm, _faces(pm, "padU"))
    assert not [r for r in pad_flats(pm, law, airport) if {r.a, r.b} <= pad_v]
    cs, _c, _w = generate(pm, law, airport)
    z = np.asarray(solve_design(pm, cs, law)[0].z, float)
    X = np.array([pm.vertices[v].xy for v in own])
    c0 = X.mean(axis=0)
    A = np.c_[X - c0, np.ones(len(X))]
    co, *_ = np.linalg.lstsq(A, z[own], rcond=None)
    assert float(np.max(np.abs(A @ co - z[own]))) <= 0.01      # one plane
    assert 0.5 <= 100.0 * math.hypot(co[0], co[1]) <= 100.0 * float(
        law.tables.emit.within_shape.pad_slope_max) + 0.02
    W = np.array([pm.vertices[v].xy for v in weld])
    rel = (np.c_[W - c0, np.ones(len(W))] @ co) - z[weld]
    assert float(np.max(np.abs(rel))) <= 0.25


def _coverage_collar_vertices(pm, ref):
    """The collar's OWN vertices on the coverage edge (an edge with no face
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


def test_a_coverage_edge_collar_vertex_keeps_the_bank_and_the_ground(built, law):
    """Issue #223 (SPJC building14#collar at -12.02514481, -77.10577155:
    46.26 m over a 24.7 m platform and a 30.04 m DEM): a collar vertex on the
    COVERAGE EDGE carried no row at all — the bank exempted it ("the DEM
    governs") while nothing fixes the DEM since 09-09b (3) — so the bending
    stencil alone extrapolated it.  It now takes the 1:3 bank ONE-WAY (it
    follows; the platform leads), and the solve holds it inside the bank from its platform and never above every ring
    neighbour by more than the bank allows."""
    from auto_patch_v2.solve import solve_design
    pm, airport = built
    cov = _coverage_collar_vertices(pm, "padU")
    assert cov, "the fixture's pad rim must reach the coverage edge"
    bs = float(law.tables.emit.design.bank_slope)
    inner = _vs(pm, _faces(pm, "padU"))
    rows = platform.platform_collar_rows(pm, law, airport)
    for v in cov:
        mine = [r for r in rows if r.a == v]
        assert mine and all(r.cap == pytest.approx(bs) and r.follows == (v,)
                            and r.b in inner for r in mine), v
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    z = np.asarray(sol.z, float)
    # the priced bank's own slack (a one-sided penalty, never a hard row)
    tol = 0.5
    edges = pm.edges_of_vertex()
    for v in cov:
        for r in (r for r in rows if r.a == v):
            assert abs(z[v] - z[r.b]) <= bs * r.d + tol, (v, z[v], z[r.b], r.d)
        nb = [pm.edges[e].b if pm.edges[e].a == v else pm.edges[e].a for e in edges[v]]
        reach = max(bs * math.dist(pm.vertices[v].xy, pm.vertices[o].xy) for o in nb)
        assert z[v] <= max(z[o] for o in nb) + reach + tol, (v, z[v])


# --------------------------------------------------------------------------
# THE TOE IS PLACED BY THE SOLVE (issue #86; owner RULINGS 2026-10-02v (5)).
# The collar is minted at the CAP and its rows are one-way INEQUALITIES at
# the 1:3 bank, so ONE pass puts the toe where the relief allows.  The
# fixture: an apron SOUTH and an apron NORTH of the pad on ground falling
# across y — the two aprons solve to their own levels, so the pad's welded
# rim carries a relief its 1 %-bounded plane cannot follow.
# --------------------------------------------------------------------------

#: The fall that makes the SOLVED rim relief 4.638 m at this pad — SPJC
#: ``building5``'s 4.62 m, the site the DEM-minted C under-read (C 5.99 m,
#: 14.0 m needed).
RELIEF_FALL = 0.06
APRON_S = _rect(-200.0, 100.0, 200.0, 200.0)
APRON_N = _rect(-200.0, 300.0, 200.0, 400.0)


class _DemFallY:
    """Ground falling ``s`` across y (the twin's relief knob)."""

    provenance = {"synthetic": "falling across y"}

    def __init__(self, s: float) -> None:
        self.s = float(s)

    def z(self, x: float, y: float) -> float:
        return 700.0 - self.s * y

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _two_apron_cells(pad=PAD):
    return [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                 (), 3, "D", "airside", "runway", {}),
            Cell(1, "apron", "apronS", APRON_S, (), None, None, "airside", "apron", {}),
            Cell(2, "apron", "apronN", APRON_N, (), None, None, "airside", "apron", {}),
            Cell(3, "building", "padU", pad, (), None, None, "airside", "pad", {})]


def _solved(law, cells, dem):
    """``(planar map, airport, z)`` — ONE solve, the only one these twins
    run (RULINGS 2026-09-29l refuses the two-pass re-mint)."""
    from auto_patch_v2.solve import solve_design
    airport = _airport(law, dem)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    return pm, airport, np.asarray(sol.z, float)


def test_a_pad_that_carries_the_cap_is_minted_at_the_cap(law):
    """§1 (2) as re-ruled (10-02v (5), amended 10-02z): C is
    ``platform_collar_max_m`` — the law's widest, whatever the DEM relief
    reads — on every pad whose erosion by it still leaves a platform.  ONE
    derivation (``planar.platform._collar_for_pad``), whose ceiling is
    ``collar_width_m``.  This 200 x 120 m pad leaves 170 x 90 m."""
    cap = float(law.tables.structures.building_pad.platform_collar_max_m)
    assert pplat.collar_width_m(law) == pytest.approx(cap)
    air = [Region("apron", "a", Polygon(APRON), None, None, "airside", "cell")]
    pad = Region("building", "u", Polygon(_rect(-100.0, 200.0, 100.0, 320.0)),
                 None, None, "airside", "cell")
    for dem in (None, _Dem()):
        got, counts = pplat.platform_split(air, [pad], law, 0.5, dem=dem)
        assert counts["platforms"] == 1
        assert [p.collar_m for p in pplat.PLATFORMS] == [pytest.approx(cap)]
        assert [p.collar_why for p in pplat.PLATFORMS] == ["cap"]
        assert counts["platform_collar_why"] == {"cap": 1, "area": 0, "floor": 0}
        plat = next(r for r in got if r.ref == "u")
        # the platform stands exactly the cap inside the rim
        assert Polygon(pad.polygon.exterior).exterior.distance(
            plat.polygon.exterior) == pytest.approx(cap, abs=0.1)


def test_the_solve_places_the_toe_under_a_4_6_m_rim_relief(law):
    """#86's bar: at a SOLVED rim relief of 4.6 m (SPJC ``building5``) every
    collar row is inside the 1:3 bank after ONE solve.  Measured on the
    DEM-minted C (``origin/main`` 0b3da356, the same fixture): C 7.58 m, the
    bank missed by 2.2385 m; at the cap it misses 0.0."""
    pm, airport, z = _solved(law, _two_apron_cells(), _DemFallY(RELIEF_FALL))
    recs = platform.platform_records(pm, law, z)
    assert [r["ref"] for r in recs] == ["padU"]
    r = recs[0]
    cap = float(law.tables.structures.building_pad.platform_collar_max_m)
    assert r["collar_m"] == pytest.approx(cap, abs=0.5)
    assert r["rim_relief_max_m"] == pytest.approx(4.6, abs=0.3)
    # the width the DEM proxy would have had to find, and did not
    assert r["collar_needed_m"] > 10.0
    rows = platform.platform_collar_rows(pm, law, airport)
    assert rows
    worst = max(abs(z[q.a] - z[q.b]) - q.cap * q.d for q in rows)
    assert worst <= 0.01, worst          # the 0.01 m materiality floor


def test_a_flat_site_pad_is_unchanged_by_the_cap_mint(law):
    """The cap mint costs a FLAT site nothing: the rim sits on the platform
    because the ground does, not because a cap-0 equality nailed it there.
    Measured against ``origin/main`` 0b3da356 on this fixture: level 700.0,
    every collar vertex 0.0 m off it, on both arms."""
    pm, _a, z = _solved(law, _two_apron_cells(), _DemFallY(0.0))
    recs = platform.platform_records(pm, law, z)
    assert recs[0]["level"] == pytest.approx(700.0, abs=1e-3)
    assert recs[0]["rim_relief_max_m"] == pytest.approx(0.0, abs=1e-3)
    col = _vs(pm, _faces(pm, "padU" + COLLAR_SUFFIX))
    assert col
    assert max(abs(z[v] - 700.0) for v in col) <= 0.001


def test_the_cap_width_collar_never_claims_an_airside_face(law):
    """AIRSIDE IS KING: the collar is ``P.difference(the platform pieces)``
    of a pad the 23a cut already took every airside overlap out of, so a
    WIDER C moves area from the platform to the collar and claims nothing
    new.  Checked on the arrangement: no collar face overlaps an airside
    one, and every collar vertex that an airside face carries is a rim
    vertex the two SHARE (the weld), never an interior one."""
    from shapely.geometry import Polygon as _P
    pm, _a, _z = _solved(law, _two_apron_cells(), _DemFallY(RELIEF_FALL))
    from auto_patch_v2.law.tables import rolled_on_roles
    air_roles = set(rolled_on_roles(law))
    col = _faces(pm, "padU" + COLLAR_SUFFIX)
    assert col
    def _poly(fid):
        ring = [pm.vertices[v].xy for v in pm.ring_vertices(pm.faces[fid].ring)]
        holes = [[pm.vertices[v].xy for v in pm.ring_vertices(h)]
                 for h in (pm.faces[fid].holes or ())]
        return _P(ring, [h for h in holes if len(h) >= 3])
    cols = [_poly(q) for q in col]
    for f in pm.faces.values():
        if f.role not in air_roles:
            continue
        a = _poly(f.id)
        for c in cols:
            assert c.intersection(a).area <= 1e-6, (f.ref, c.intersection(a).area)


# The pad's OWN rim needs a GROUNDSIDE face beyond it (a rectangle welded
# into an apron gap has no rim vertex of its own): the notched pad with a
# service road in each notch.  Measured: 48 airside-led rows, 6 own-rim, 6
# coverage-edge.
NOTCHED = ((-200.0, 200.0), (200.0, 200.0), (200.0, 230.0), (150.0, 230.0),
           (150.0, 260.0), (-150.0, 260.0), (-150.0, 230.0), (-200.0, 230.0))


def _notched_cells():
    return [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                 (), 3, "D", "airside", "runway", {}),
            Cell(1, "apron", "apronS", _rect(-400.0, 100.0, 400.0, 200.0), (),
                 None, None, "airside", "apron", {}),
            Cell(2, "apron", "apronN", _rect(-400.0, 260.0, 400.0, 360.0), (),
                 None, None, "airside", "apron", {}),
            Cell(3, "building", "padU", NOTCHED, (), None, None, "airside", "pad", {}),
            Cell(4, "service_road", "road1", _rect(150.0, 230.0, 200.0, 260.0), (),
                 None, None, "groundside", "road", {}),
            Cell(5, "service_road", "road2", _rect(-200.0, 230.0, -150.0, 260.0), (),
                 None, None, "groundside", "road", {})]


def test_the_pads_own_rim_row_is_a_one_way_bank_not_a_fixed_toe(law):
    """10-02v (5): the pad's OWN rim row was a cap-0 EQUALITY that fixed the
    toe at the rim.  It is now the 1:3 bank, BOTH SIGNS, ONE-WAY with the
    PLATFORM leading — the ``follows=(o,)`` the coverage edge takes (#223) —
    so the rim follows the ground objective inside the bank and the plate
    still never follows the rim."""
    from auto_patch_v2.solve.design_roles import one_way_rulings, pad_flat_rulings
    pm, airport, z = _solved(law, _notched_cells(), _DemFallY(RELIEF_FALL))
    rows = platform.platform_collar_rows(pm, law, airport)
    own = [r for r in rows if platform.RIM_RULING in r.source.ruling]
    assert own, platform.STATS
    bs = float(law.tables.emit.design.bank_slope)
    inner = _vs(pm, _faces(pm, "padU"))
    for r in own:
        assert r.cap == pytest.approx(bs) and r.cap > 0.0   # never the cap-0 toe
        assert r.follows == (r.a,) and r.b in inner         # the platform leads
    # the direction is a LAW read, and the price is still the plate's
    assert platform.RIM_RULING in one_way_rulings(law)
    assert platform.RIM_RULING in pad_flat_rulings(law)
    for r in own:
        assert abs(z[r.a] - z[r.b]) <= bs * r.d + 0.5


# --------------------------------------------------------------------------
# ROUND 2 (owner RULINGS 2026-10-02z, issue #86).  Round 1 minted the cap
# UNCONDITIONALLY and the sweep MEASURED the cost: live platforms KCLT
# 10 -> 3, SPJC 8 -> 5, HECA 14 -> 8, the plateaus lost with them.  C is
# now the WIDEST width at or under the cap that still leaves a platform,
# searched UP from the width ``origin/main`` minted — so round 2 may only
# WIDEN a collar, and the set of pads that get a platform is main's set
# exactly (the refusal is judged at that same status-quo width).
# --------------------------------------------------------------------------


def _widths(air, pads, law, grid=0.5, dem=None):
    """``{ref: (C, why)}`` per MINTED platform and ``{ref: refused}``."""
    pplat.platform_split(air, pads, law, grid, dem=dem)
    return ({p.ref: (p.collar_m, p.collar_why) for p in pplat.PLATFORMS
             if not p.refused},
            {p.ref: p.refused for p in pplat.PLATFORMS if p.refused})


def _main_collar_m(law, P, air, near, dem, slope_max) -> float:
    """``origin/main``'s (pre-collar86) C for this pad: the DEM-relief
    proxy ``clamp(relief / bank_slope, bank_min_width_m,
    platform_collar_max_m)``, written out here — INDEPENDENTLY of
    ``_collar_for_pad``'s own floor — so the invariant twin compares round
    2 against the width main really minted, not against a number copied
    into the assertion."""
    cmin = float(law.tables.emit.design.bank_min_width_m)
    cmax = float(law.tables.structures.building_pad.platform_collar_max_m)
    bank = float(law.tables.emit.design.bank_slope)
    rel = pplat.rim_relief_m(P, air, near, dem, slope_max)
    return cmin if rel is None else min(cmax, max(cmin, rel / bank))


def test_a_narrow_pad_the_cap_would_erode_away_keeps_its_platform(law):
    """THE ROUND-1 DEFECT, closed.  This 9,000 m2 pad (the twin file's own
    ``big`` fixture) leaves 70 x 15 m = 1,050 m2 under the cap — far under
    ``cluster_pad_min_m2`` — and round 1 REFUSED it ``under_min_area``.
    Round 2 narrows C station by station until the platform fits and mints
    it, at a C never under ``bank_min_width_m`` and never under the width
    ``origin/main`` gave."""
    air = [Region("apron", "a", Polygon(APRON), None, None, "airside", "cell")]
    mid = Region("building", "mid", Polygon(_rect(-100.0, 200.0, 100.0, 245.0)),
                 None, None, "airside", "cell")
    cmin = float(law.tables.emit.design.bank_min_width_m)
    cap = float(law.tables.structures.building_pad.platform_collar_max_m)
    minted, refused = _widths(air, [mid], law)
    assert refused == {}
    (C, why), = minted.values()
    assert list(minted) == ["mid"]
    assert cmin <= C < cap                 # narrowed, never round 1's bare cap
    assert why in ("area", "floor")
    # >= what main gives: DEM-less, main's proxy reads no relief and takes
    # its own floor (``test_round_2_never_refuses_a_platform_main_grants``
    # sweeps the DEM arm)
    assert C >= _main_collar_m(law, mid.polygon, Polygon(APRON), 2.0, None, 0.0)
    # and the platform the narrowed C leaves is over the gate
    plat = next(p for p in pplat.PLATFORMS if not p.refused)
    assert plat.platform_m2 >= float(law.tables.structures.placement.cluster_pad_min_m2)


def test_the_width_search_is_monotone_and_takes_the_widest_station(law):
    """C is THE WIDEST passing width, not merely a passing one: one station
    of ``emit.identity.input_quantum_m`` wider refuses the pad, and the
    width sits on that lattice off ``bank_min_width_m`` — a named law
    resolution, no literal of its own."""
    cmin = float(law.tables.emit.design.bank_min_width_m)
    cap = float(law.tables.structures.building_pad.platform_collar_max_m)
    step = float(law.tables.emit.identity.input_quantum_m)
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    min_m2 = float(law.tables.structures.placement.cluster_pad_min_m2)
    bank = float(law.tables.emit.design.bank_slope)
    P = Polygon(_rect(-100.0, 200.0, 100.0, 245.0))
    C, why, _parts, plats, tot = pplat._collar_for_pad(
        P, 0.5, cap, cmin, bank, None, step, pmin, min_m2)
    assert plats and tot >= min_m2
    assert why == "area" and cmin < C < cap
    assert (C - cmin) % step == pytest.approx(0.0, abs=1e-6)   # on the lattice
    # one station wider does not fit
    _p2, pl2, t2 = pplat._eroded(P, C + step, 0.5, pmin)
    assert not pl2 or t2 < min_m2
    # and a sample of narrower widths all do (the predicate is monotone)
    for w in (cmin, 0.5 * (cmin + C), C - step):
        _p3, pl3, t3 = pplat._eroded(P, w, 0.5, pmin)
        assert pl3 and t3 >= min_m2, w


def test_a_pad_main_already_refuses_stays_refused(law):
    """The other direction: a pad whose status-quo collar already erodes it
    past the gates gets no platform, exactly as ``origin/main`` gives none
    — the refusal is judged at that same width and the predicate is
    monotone, so no width round 2 could pick would mint it.  5,600 m2,
    28 m deep: the floor leaves 18 m x 190 m = 3,420 m2."""
    air = [Region("apron", "a", Polygon(APRON), None, None, "airside", "cell")]
    thinner = Region("building", "thin2", Polygon(_rect(-100.0, 200.0, 100.0, 228.0)),
                     None, None, "airside", "cell")
    minted, refused = _widths(air, [thinner], law)
    assert minted == {} and refused == {"thin2": "under_min_area"}
    assert [p.collar_m for p in pplat.PLATFORMS] == [
        pytest.approx(float(law.tables.emit.design.bank_min_width_m))]
    assert [p.collar_why for p in pplat.PLATFORMS] == ["floor"]


def test_round_2_never_refuses_a_platform_main_grants(law):
    """THE INVARIANT (owner RULINGS 2026-10-02z): the set of pads that get a
    platform is EXACTLY the set ``origin/main`` (pre-collar86) gives, and
    every C is at or over main's.  Swept over the pad depths 24-120 m at
    4 m, DEM-less and on the falling DEM (50 pads) — main's own derivation
    is written out independently above and the two verdicts compared pad
    for pad."""
    near = 2.0
    slope_max = float(law.tables.emit.within_shape.pad_slope_max)
    cmin = float(law.tables.emit.design.bank_min_width_m)
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    min_m2 = float(law.tables.structures.placement.cluster_pad_min_m2)
    cap = float(law.tables.structures.building_pad.platform_collar_max_m)
    step = float(law.tables.emit.identity.input_quantum_m)
    airP = Polygon(APRON)
    air = [Region("apron", "a", airP, None, None, "airside", "cell")]
    bank = float(law.tables.emit.design.bank_slope)
    seen = {"both": 0, "neither": 0, "widened": 0}
    for depth in range(24, 124, 4):
        P = Polygon(_rect(-100.0, 200.0, 100.0, 200.0 + depth))
        for dem in (None, _Dem()):
            Cm = _main_collar_m(law, P, airP, near, dem, slope_max)
            _pm, plm, tm = pplat._eroded(P, Cm, 0.5, pmin)
            main_ok = bool(plm) and tm >= min_m2
            rel = pplat.rim_relief_m(P, airP, near, dem, slope_max)
            Cb, _why, _pb, plb, tb = pplat._collar_for_pad(
                P, 0.5, cap, cmin, bank, rel, step, pmin, min_m2)
            b_ok = bool(plb) and tb >= min_m2
            # THE SET IS IDENTICAL, pad for pad, on both DEM arms
            assert b_ok == main_ok, (depth, dem is not None, Cm, Cb)
            if main_ok:
                # and NEVER a narrower collar: the lattice is §46 (4)'s own
                # input quantum, so the search's granularity is below every
                # materiality in the system (``hard_tol_m`` 0.02)
                assert Cb >= Cm - step, (depth, Cm, Cb)
                assert Cb <= cap + 1e-9
                seen["both"] += 1
                if Cb > Cm + step:
                    seen["widened"] += 1
            else:
                seen["neither"] += 1
    assert seen["both"] and seen["neither"]
    # and the point of round 2: where the pad carries it, the collar WIDENS
    assert seen["widened"], seen
