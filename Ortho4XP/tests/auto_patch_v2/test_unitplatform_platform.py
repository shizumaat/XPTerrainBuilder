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
