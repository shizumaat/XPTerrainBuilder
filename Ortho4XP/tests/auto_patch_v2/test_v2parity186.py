"""ISSUE #186 — the eight census families that gained a v2 ``verify`` reader,
each in LOCKSTEP with the oracle over ONE synthetic layout, and the two that
gained a reasoned ``NOT_IMPLEMENTED`` entry instead.

#186 was #108's class, ten times over: ``seam_residual``,
``bank_across_seam``, ``ramp_in_road``, ``object_cut_offset``,
``object_cut_depth``, ``ramp_in_strip``, ``road_coverage_join``,
``sea_wall``, ``zone_on_pavement`` and ``sentinel_elevation`` had neither a
reader in ``verify.census.READERS`` nor an entry in ``NOT_IMPLEMENTED`` —
"any one of them reading non-zero on a built airport is the next #108".

THE BAR THIS FILE HOLDS is the one ``test_v2cutback`` set for #108: the two
instruments must agree ROW FOR ROW on geometry small enough to need no
corpus.  A reader that merely runs is not parity; a reader that counts what
``check_grade`` counts, on the same rings, is.

ONE LAYOUT, EIGHT FAMILIES (``_LAYOUT``): an apron and a code-E taxi rect,
a zone band standing 2 m onto the apron, a service road with a tunnel ramp
cut into it, a second ramp inside the taxi rect's graded strip, a third
ramp inside an authored object cut and standing out of its wall line, one
sentinel vertex 60 m under the ground band, and the two pin lists in the
sidecar.  The families do not need to be isolated for the twin to have
teeth: lockstep asserts the two READERS agree, and each ``test_*_lockstep``
also asserts its family is non-zero, so a reader that returned ``[]`` could
not pass.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.verify import keepout, pins
from auto_patch_v2.verify.census import NOT_IMPLEMENTED, READERS
from auto_patch_v2.verify.frame import R_EARTH, Patch, Shape

ROOT = Path(__file__).resolve().parents[2]

#: The ten families of issue #186, in the issue's own order.
FAMILIES_186: tuple[str, ...] = (
    "seam_residual", "bank_across_seam", "ramp_in_road", "object_cut_offset",
    "object_cut_depth", "ramp_in_strip", "road_coverage_join", "sea_wall",
    "zone_on_pavement", "sentinel_elevation")

#: The two the register declares unreadable, with the construction cited.
UNREADABLE_186: frozenset[str] = frozenset({"bank_across_seam", "sea_wall"})

_LAT, _LON = 25.2660000, 51.6110000
_BASE_Z_M = 80.0
#: The sentinel: ``emit.cockpit.sentinel_drop_m`` is 50 m, so 60 m under the
#: band is a crater and 1 m under it is terrain.
_SENTINEL_DROP_M = 60.0
#: The seam pin and the coverage join are PINS: a pin holds exactly, so the
#: residual is the stand-off the twin reads back.
_SEAM_RESIDUAL_M = 0.40
_ROAD_JOIN_RESIDUAL_M = 0.75
#: The zone band stands this far onto the apron (§41 (2) bar is 0.5 m²).
_ZONE_OVERLAP_M = 2.0
#: How far INSIDE the road ribbon / the strip / outside the wall line the
#: three ramp vertices stand — all well over the 0.5 m weld tolerance.
_RAMP_IN_ROAD_M = 2.0
_RAMP_IN_STRIP_M = 6.0
_OBJECT_OFFSET_M = 4.0
#: The authored floor, and the emitted floor that misses it (bar 0.10 m).
_OBJECT_FLOOR_M = 70.0
_OBJECT_FLOOR_MISS_M = 0.90

_MLAT = 111_320.0
_MLON = 111_320.0 * math.cos(math.radians(_LAT))


def _at(dx_m: float, dy_m: float, z: float):
    return (_LAT + dy_m / _MLAT, _LON + dx_m / _MLON, z)


def _rect(x0, y0, w, h, z):
    return [_at(x0, y0, z), _at(x0 + w, y0, z),
            _at(x0 + w, y0 + h, z), _at(x0, y0 + h, z)]


def _layout(*, clean: bool = False):
    """``(rings, sidecar)`` — the one layout, or its LAWFUL twin.

    ``clean=True`` moves every offender into compliance and leaves the two
    pins at their held values: both readers must then report nothing, which
    is the other half of each family's twin."""
    z = _BASE_Z_M
    # the apron, and the code-E taxi rect 60 m north of it (its graded
    # strip is 19.0 m, so a ramp 6 m out from its edge is inside it)
    apron = _rect(0, 0, 120, 60, z)
    taxi = _rect(0, 120, 120, 40, z)
    # the zone band north of the apron, standing 2 m ONTO it unless clean
    over = 0.0 if clean else _ZONE_OVERLAP_M
    zone = _rect(0, 60 - over, 120, 30, z + 0.2)
    # the service road, and a ramp whose far vertex sits inside the ribbon
    road = _rect(0, -30, 120, 10, z)
    into = 0.0 if clean else _RAMP_IN_ROAD_M
    ramp_road = [_at(40, -45, z), _at(60, -45, z),
                 _at(60, -30 + into, z - 3.0), _at(40, -30 + into, z - 3.0)]
    # the ramp in the taxi rect's strip: north of the rect by 6 m when dirty,
    # by 25 m (clear of the 19.0 m strip) when clean
    out_m = 25.0 if clean else (19.0 - _RAMP_IN_STRIP_M)
    ramp_strip = [_at(40, 160 + out_m, z), _at(60, 160 + out_m, z),
                  _at(60, 160 + out_m + 15, z - 4.0),
                  _at(40, 160 + out_m + 15, z - 4.0)]
    # the object cut: an authored 20 x 20 wall line, and the ramp in it.
    # DIRTY: one vertex 4 m outside the wall line, floor 0.90 m off the
    # authored plate.  CLEAN: inside, and on the plate.
    wall = _rect(200, 0, 20, 20, 0.0)
    off = 0.0 if clean else _OBJECT_OFFSET_M
    fz = _OBJECT_FLOOR_M + (0.0 if clean else _OBJECT_FLOOR_MISS_M)
    ramp_obj = [_at(205, 5, fz), _at(215, 5, fz),
                _at(215, 15, fz), _at(205, 20 + off, fz)]
    rings = [
        ("apron", "pav1", apron, 4, "E"),
        ("junction", "pav2", taxi, 4, "E"),
        ("graded_strip", "adjacent_ground:taxi:E:zone2#1", zone, None, None),
        ("service_road", "R1", road, None, None),
        ("tunnel_ramp", "tunnel_ramp", ramp_road, None, None),
        ("tunnel_ramp", "tunnel_ramp", ramp_strip, None, None),
        ("tunnel_ramp", "tunnel_ramp", ramp_obj, None, None),
    ]
    # THE PINS: the apron's first vertex is a seam pin, the road's first a
    # coverage join.  A pin holds exactly, so the sidecar states the value
    # the solve HELD and the layout emits it (clean) or stands off it.
    seam = z - (0.0 if clean else _SEAM_RESIDUAL_M)
    join = z - (0.0 if clean else _ROAD_JOIN_RESIDUAL_M)
    sidecar = {
        "seam_pins": [[apron[0][0], apron[0][1], round(seam, 4)]],
        "road_coverage_join": [[road[0][0], road[0][1], round(join, 4)]],
        "object_cuts": [{"id": "obj1", "wall_ref": "tunnel_wall",
                         "ramp_refs": ["tunnel_ramp"],
                         "floor_m": _OBJECT_FLOOR_M,
                         "outline_ll": [[la, lo] for la, lo, _z in wall]}],
    }
    # THE SENTINEL: ONE apron vertex 60 m under the ground band, on a ring
    # 300 m clear of every other family.  ONE vertex and not a whole ring,
    # and that is the 5th-PERCENTILE FLOOR's own arithmetic: with 32 valued
    # nodes the percentile index is 2, so four crater nodes would put the
    # floor INSIDE the crater (``zs[2]`` is a sentinel) and the family
    # reports nothing on either instrument — measured, which is exactly why
    # ``check_grade`` prices against a percentile and not the minimum.
    far = _rect(300, 0, 10, 10, z - 1.0)
    if not clean:
        la, lo, _z = far[0]
        far[0] = (la, lo, z - _SENTINEL_DROP_M)
    rings.append(("apron", "pav3", far, 4, "E"))
    return rings, sidecar


def _patch(rings, sidecar) -> Patch:
    """The rings as a :class:`Patch` in the census's mean-centred frame."""
    pts = [p for _r, _f, ring, _n, _l in rings for p in ring]
    lat0 = sum(p[0] for p in pts) / len(pts)
    lon0 = sum(p[1] for p in pts) / len(pts)
    cos0 = math.cos(math.radians(lat0))
    xy: dict[int, tuple[float, float]] = {}
    z: dict[int, float] = {}
    ll: dict[int, tuple[float, float]] = {}
    shapes: list[Shape] = []
    vid = 0
    for k, (role, ref, ring, cn, cl) in enumerate(rings):
        ids = []
        for la, lo, zz in ring:
            xy[vid] = (math.radians(lo - lon0) * R_EARTH * cos0,
                       math.radians(la - lat0) * R_EARTH)
            z[vid] = zz
            ll[vid] = (la, lo)
            ids.append(vid)
            vid += 1
        shapes.append(Shape(k, role, ref, tuple(ids),
                            tuple(xy[i] for i in ids), tuple(z[i] for i in ids),
                            None, cl, cn))
    return Patch(Law.for_airport("HECA"), lat0, lon0, xy, z, ll,
                 tuple(shapes), (), dict(sidecar))


def _osm(tmp_path: Path, name: str, rings, sidecar) -> Path:
    """THE SAME rings as an emitted patch + its ``.axes.json`` sidecar."""
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='v2-parity186-lockstep-twin'>"]
    nid = -1
    ways: list[tuple[int, list[int], dict[str, str]]] = []
    for k, (role, ref, ring, cn, cl) in enumerate(rings):
        ids = []
        for la, lo, zz in ring:
            out.append(f"  <node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'>"
                       f"<tag k='alt_abs' v='{zz:.2f}' /></node>")
            ids.append(nid)
            nid -= 1
        tags = {"role": role, "shapeID": str(k), "ref": ref}
        if cn is not None:
            tags["code_number"] = str(cn)
        if cl is not None:
            tags["code_letter"] = str(cl)
        if role in ("apron", "junction"):
            tags["aeroway"] = "apron" if role == "apron" else "taxiway"
        ways.append((nid, ids + [ids[0]], tags))
        nid -= 1
    for wid, nids, tags in ways:
        out.append(f"  <way id='{wid}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    side = {"anchor": [_LAT, _LON], "ruleset": "icao"}
    side.update(sidecar)
    Path(str(osm) + ".axes.json").write_text(
        json.dumps(side), encoding="utf-8", newline="")
    return osm


@pytest.fixture(scope="module")
def cg():
    for p in (ROOT / "tools" / "harness", ROOT / "tools"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return pytest.importorskip("check_grade")


@pytest.fixture(scope="module")
def dirty():
    rings, side = _layout()
    return _patch(rings, side), rings, side


@pytest.fixture(scope="module")
def clean():
    rings, side = _layout(clean=True)
    return _patch(rings, side), rings, side


def _oracle(cg, tmp_path, name, rings, side) -> dict:
    fo: dict = {}
    cg.run_checks_law_true(_osm(tmp_path, name, rings, side),
                           family_out=fo, quiet=True, top_n=0)
    return fo


@pytest.fixture(scope="module")
def dirty_oracle(cg, tmp_path_factory, dirty):
    _p, rings, side = dirty
    return _oracle(cg, tmp_path_factory.mktemp("dirty"), "dirty", rings, side)


@pytest.fixture(scope="module")
def clean_oracle(cg, tmp_path_factory, clean):
    _p, rings, side = clean
    return _oracle(cg, tmp_path_factory.mktemp("clean"), "clean", rings, side)


# ── THE REGISTER: all ten are classified, and the inventory is empty ─────

def test_all_ten_families_of_186_are_classified(cg):
    keys = {k for k, _t, _b in cg.LAW_FAMILIES}
    for fam in FAMILIES_186:
        assert fam in keys, f"{fam} is no longer a census family"
        read, declared = fam in READERS, fam in NOT_IMPLEMENTED
        assert read != declared, (
            f"{fam} must be read XOR declared unreadable, not both/neither")
        assert (fam in UNREADABLE_186) == declared, fam


def test_the_two_unreadable_entries_cite_their_construction():
    """The bar #186 set: "a reason that is merely 'no reader yet' is not
    acceptable".  Both name the SECOND surface the geometry is minted into,
    which is not the one ``census_frame`` is handed."""
    for fam in sorted(UNREADABLE_186):
        why = NOT_IMPLEMENTED[fam]
        assert "surf_out" in why and "surf" in why, why
        assert "no reader" not in why.lower()


def test_the_declared_construction_is_the_builds_own():
    """The citation is checked against ``pipeline/build``, not trusted: the
    terrain-edge ways and the shore weld go into ``surf_out`` and the verify stage reads
    ``surf``.  A refactor that fed ``surf_out`` to ``census_frame`` would
    make both families readable, and must fail here."""
    import inspect

    from auto_patch_v2.pipeline import build as B
    src = inspect.getsource(B)
    assert "surf_out = with_terrain_edges(surf," in src
    assert "surf_out = weld_to_shore(surf_out," in src
    assert "census_frame(surf, law, pub," in src


# ── THE CONSTANTS ARE THE ORACLE'S OWN (the census-wrapper precedent) ────

def test_the_pin_readers_join_at_the_oracles_identity(cg):
    assert pins.ROAD_JOIN_TOL_M == cg._ROAD_JOIN_TOL_M
    assert pins.SENTINEL_FLOOR_PCTL == cg.SENTINEL_FLOOR_PCTL
    assert pins.SENTINEL_MIN_NODES == cg.SENTINEL_MIN_NODES
    law = Law.for_airport("HECA")
    assert float(law.tables.emit.materiality.elevation_m) \
        == cg._SEAM_RESIDUAL_TOL_M
    assert float(law.tables.emit.cockpit.sentinel_drop_m) == cg.sentinel_drop_m()


def test_the_keepout_populations_are_the_oracles_own(cg, dirty):
    p, _r, _s = dirty
    assert keepout.weld_tol_m(p) == cg.SHARED_VERTEX_TOL_M
    assert keepout.ramp_roles(p) == cg._RAMP_ROLES
    assert keepout.pavement_roles(p) == cg._ZONE_ON_PAVEMENT_ROLES
    assert keepout.strip_roles(p) == (cg._RAMP_IN_STRIP_RUNWAY_ROLES
                                      | cg._RAMP_IN_STRIP_TAXI_ROLES)
    assert keepout.ZONE_ON_PAVEMENT_MIN_AREA_M2 == cg.ZONE_ON_PAVEMENT_MIN_AREA_M2
    assert keepout.OBJECT_CUT_OFFSET_M == cg.OBJECT_CUT_OFFSET_M
    assert keepout.OBJECT_CUT_DEPTH_M == cg.OBJECT_CUT_DEPTH_M
    assert keepout.OBJECT_CUT_RIM_FEATURES == cg._OBJECT_CUT_RIM_CLASSES
    assert keepout.ZONE_REF_PREFIX == cg.V2_ADJACENT_GROUND_REF_PREFIX


def test_the_strip_half_width_is_the_oracles_own(cg, dirty):
    """The zone-2 band a code-E taxi rect declares, both ways."""
    p, _r, _s = dirty
    taxi = next(sh for sh in p.shapes if sh.ref == "pav2")
    assert keepout.strip_half_width_m(p, taxi) == pytest.approx(
        cg._strip_half_width_m(taxi.role, taxi.code_number, taxi.code_letter))
    zone = next(sh for sh in p.shapes if sh.role == "graded_strip")
    assert keepout.strip_half_width_m(p, zone) == 0.0


# ── THE LOCKSTEP, family by family ──────────────────────────────────────

#: family -> (the v2 reader, how many rows the layout owes it).  The count
#: is stated so a reader that silently returned ``[]`` cannot pass; the
#: lockstep below is what makes it the ORACLE's count too.
_LOCKSTEP: dict[str, tuple[object, int]] = {
    "seam_residual": (pins.seam_residual, 1),
    "road_coverage_join": (pins.road_coverage_join, 1),
    "sentinel_elevation": (pins.sentinel_elevation, 1),
    "ramp_in_road": (keepout.ramp_in_road, 2),
    "ramp_in_strip": (keepout.ramp_in_strip, 2),
    "zone_on_pavement": (keepout.zone_on_pavement, 1),
    "object_cut_offset": (keepout.object_cut_offset, 1),
    "object_cut_depth": (keepout.object_cut_depth, 1),
}


@pytest.mark.parametrize("family", sorted(_LOCKSTEP))
def test_the_reader_matches_the_oracle_row_for_row(family, dirty,
                                                   dirty_oracle):
    """#186's own reading, on a layout small enough to need no corpus: the
    oracle's count and ``verify``'s must agree, and be non-zero."""
    p, _r, _s = dirty
    reader, owed = _LOCKSTEP[family]
    v2 = reader(p)
    v1 = dirty_oracle[family]
    assert len(v2) == owed, [r["magnitude_m"] for r in v2]
    assert len(v1) == len(v2), (family, len(v1), len(v2))


@pytest.mark.parametrize("family", sorted(_LOCKSTEP))
def test_the_reader_prices_the_same_magnitudes_as_the_oracle(family, dirty,
                                                             dirty_oracle):
    """Same rows, same metric: the magnitude a row carries is the oracle's
    ``de_m`` (metres, or m² for the AREA family ``zone_on_pavement``)."""
    p, _r, _s = dirty
    reader, _owed = _LOCKSTEP[family]
    v2 = sorted(round(float(r["magnitude_m"]), 2) for r in reader(p))
    v1 = sorted(round(float(r.de_m), 2) for r in dirty_oracle[family])
    assert v1 == v2, (family, v1, v2)


@pytest.mark.parametrize("family", sorted(_LOCKSTEP))
def test_a_lawful_layout_prices_nothing_on_either_reader(family, clean,
                                                         clean_oracle):
    """The other half of every twin: with each offender in compliance and
    both pins at the value they hold, neither instrument speaks."""
    p, _r, _s = clean
    reader, _owed = _LOCKSTEP[family]
    assert reader(p) == [], [r["magnitude_m"] for r in reader(p)]
    assert clean_oracle[family] == []
