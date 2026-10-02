"""``verify.cutback.groundside_cutback`` — the v2 reader of issue #97 M1's
stand-off strip, and THE PARITY REGISTER that would have caught its
absence (issue #108).

#108 was ``test_cyxy_verify_matches_v1_census`` reading
``('groundside_cutback', 9, 0)``: the census family landed (#97 M1, round
7) with no v2 ``verify`` reader AND no ``NOT_IMPLEMENTED`` entry, so the
gap could only surface as a count mismatch on a built CYXY surface.  Two
twins here:

* the READER, both ways on a synthetic strip, in LOCKSTEP with the oracle
  over the same geometry (``check_grade._check_groundside_cutback``);
* the REGISTER: every family of ``check_grade.LAW_FAMILIES`` is either
  read by ``verify`` or named in ``verify.census.NOT_IMPLEMENTED`` with a
  non-empty reason, or named in :data:`OPEN_PARITY_GAPS` below — so the
  NEXT family added without a counterpart fails here, at the register.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.verify.census import NOT_IMPLEMENTED, READERS
from auto_patch_v2.verify.cutback import (FAMILY, OUT_OF_SCOPE,
                                          groundside_cutback, horizon_m)
from auto_patch_v2.verify.frame import R_EARTH, Patch, Shape

ROOT = Path(__file__).resolve().parents[2]

#: the HECA route19 strip (scout road97): a zone band cut back 0.95 m from
#: a 6 x 40 m service road, carrying +0.81 m across it
_LAT, _LON = 25.2660000, 51.6110000
_ROAD_LEN_M, _ROAD_WIDTH_M = 40.0, 6.0
_ZONE_DEPTH_M = 24.0
_GAP_M = 0.95
_STEP_M = 0.81
_BASE_Z_M = 80.0
_ROAD_ROLE = "service_road"
_ZONE_ROLE = "graded_strip"
_ZONE_REF = "adjacent_ground:taxi:E:zone2#1"
_ROAD_REF = "R1"
#: the row count the strip owes: one per road vertex ON the stand-off edge
_PAIRED_ROAD_VERTICES = 2

#: Families of ``check_grade.LAW_FAMILIES`` that ``verify`` neither reads
#: nor declares unreadable — the parity gaps OPEN as of issue #108, each
#: owed either a reader or a reasoned ``NOT_IMPLEMENTED`` entry by whoever
#: rules on it.  This list is an INVENTORY, not an exemption: it is frozen
#: so that a family added to the census without a v2 counterpart fails
#: this file instead of surfacing as a count mismatch on a built airport.
OPEN_PARITY_GAPS: frozenset[str] = frozenset({
    "seam_residual", "bank_across_seam", "ramp_in_road", "object_cut_offset",
    "object_cut_depth", "ramp_in_strip", "road_coverage_join", "sea_wall",
    "zone_on_pavement", "sentinel_elevation",
})

#: ``census_patch`` serves these three outside the ``READERS`` table
#: (``within_shape`` yields two families; ``pad_flat`` is called by name).
_SERVED_BESIDE_READERS: frozenset[str] = frozenset(
    {"within_shape", "road_cross_section", "pad_flat"})


def _rings(*, gap_m: float = _GAP_M, step_m: float = _STEP_M):
    """ONE geometry for both readers: ``[(role, ref, [(lat, lon, z)…])…]``
    — a road rectangle and a zone band standing off it by ``gap_m``."""
    mlat = 111_320.0
    mlon = 111_320.0 * math.cos(math.radians(_LAT))

    def at(dx_m: float, dy_m: float, z: float):
        return (_LAT + dy_m / mlat, _LON + dx_m / mlon, z)

    zr = _BASE_Z_M
    zz = _BASE_Z_M + step_m
    road = [at(0.0, 0.0, zr), at(_ROAD_LEN_M, 0.0, zr),
            at(_ROAD_LEN_M, _ROAD_WIDTH_M, zr), at(0.0, _ROAD_WIDTH_M, zr)]
    y0 = _ROAD_WIDTH_M + gap_m
    zone = [at(0.0, y0, zz), at(_ROAD_LEN_M, y0, zz),
            at(_ROAD_LEN_M, y0 + _ZONE_DEPTH_M, zz),
            at(0.0, y0 + _ZONE_DEPTH_M, zz)]
    return [(_ROAD_ROLE, _ROAD_REF, road), (_ZONE_ROLE, _ZONE_REF, zone)]


def _patch(**kw) -> Patch:
    """The rings as a :class:`Patch` in the census's mean-centred frame."""
    rings = _rings(**kw)
    pts = [p for _r, _f, ring in rings for p in ring]
    lat0 = sum(p[0] for p in pts) / len(pts)
    lon0 = sum(p[1] for p in pts) / len(pts)
    cos0 = math.cos(math.radians(lat0))
    xy: dict[int, tuple[float, float]] = {}
    z: dict[int, float] = {}
    ll: dict[int, tuple[float, float]] = {}
    shapes: list[Shape] = []
    vid = 0
    for k, (role, ref, ring) in enumerate(rings):
        ids = []
        for la, lo, zz in ring:
            xy[vid] = (math.radians(lo - lon0) * R_EARTH * cos0,
                       math.radians(la - lat0) * R_EARTH)
            z[vid] = zz
            ll[vid] = (la, lo)
            ids.append(vid)
            vid += 1
        shapes.append(Shape(k, role, ref, tuple(ids),
                            tuple(xy[i] for i in ids), tuple(z[i] for i in ids)))
    return Patch(Law.for_airport("CYXY"), lat0, lon0, xy, z, ll,
                 tuple(shapes), (), {})


def _osm(tmp_path: Path, name: str, **kw) -> Path:
    """The SAME rings as an emitted patch + its ``.axes.json`` sidecar,
    for the oracle."""
    rings = _rings(**kw)
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='v2-cutback-lockstep-twin'>"]
    nid = -1
    ways: list[tuple[int, list[int], dict[str, str]]] = []
    for role, ref, ring in rings:
        ids = []
        for la, lo, zz in ring:
            out.append(f"  <node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'>"
                       f"<tag k='alt_abs' v='{zz:.2f}' /></node>")
            ids.append(nid)
            nid -= 1
        tags = {"role": role, "shapeID": ref}
        if role == _ZONE_ROLE:
            tags["aeroway"] = "apron"
            tags["ref"] = ref
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
    Path(str(osm) + ".axes.json").write_text(
        json.dumps({"anchor": [_LAT, _LON], "ruleset": "icao"}),
        encoding="utf-8", newline="")
    return osm


@pytest.fixture(scope="module")
def cg():
    for p in (ROOT / "tools" / "harness", ROOT / "tools"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return pytest.importorskip("check_grade")


# ── the reader, both ways ────────────────────────────────────────────────

def test_a_flat_cutback_strip_prices_nothing():
    assert groundside_cutback(_patch(step_m=0.0)) == []


def test_a_stepped_cutback_strip_is_reported_per_road_vertex():
    rows = groundside_cutback(_patch())
    assert len(rows) == _PAIRED_ROAD_VERTICES, rows
    for r in rows:
        assert r["family"] == FAMILY
        assert abs(r["magnitude_m"] - _STEP_M) < 0.02
        assert abs(r["distance_m"] - _GAP_M) < 0.02
        # REPORT-ONLY: named, never adjudicated (Q-97 on #58)
        assert r["out_of_scope"] == OUT_OF_SCOPE


def test_a_zone_beyond_the_stand_off_horizon_is_not_the_strip():
    far = horizon_m(_patch()) + 0.5
    assert groundside_cutback(_patch(gap_m=far)) == []


def test_the_out_of_scope_stamp_is_the_oracles_own(cg):
    """The two readers' rows must join: same family, same stamp."""
    assert OUT_OF_SCOPE == cg.GROUNDSIDE_CUTBACK_OUT_OF_SCOPE
    assert FAMILY == cg.GROUNDSIDE_CUTBACK_FAMILY
    assert OUT_OF_SCOPE in cg.OUT_OF_SCOPE_CLASSES


def test_the_horizon_is_the_oracles_own(cg):
    h, ramp_max = cg.groundside_cutback_frame()
    p = _patch()
    assert abs(horizon_m(p) - h) < 1e-9
    assert abs(float(p.law.tables.emit.terrace.groundside_ramp_max)
               - ramp_max) < 1e-12


# ── THE LOCKSTEP: both readers over the same rings ───────────────────────

def test_the_reader_matches_the_oracle_row_for_row(cg, tmp_path):
    """#108's own reading, on a strip small enough to need no corpus: the
    oracle's count and ``verify``'s must agree."""
    fo: dict = {}
    cg.run_checks_law_true(_osm(tmp_path, "step"), family_out=fo, quiet=True,
                           top_n=0)
    v1 = fo[FAMILY]
    v2 = groundside_cutback(_patch())
    assert len(v1) == len(v2) == _PAIRED_ROAD_VERTICES, (len(v1), len(v2))
    assert sorted(round(r.de_m, 3) for r in v1) \
        == sorted(round(r["magnitude_m"], 3) for r in v2)
    assert sorted(round(r.distance_m, 2) for r in v1) \
        == sorted(round(r["distance_m"], 2) for r in v2)


def test_a_flat_strip_prices_nothing_on_either_reader(cg, tmp_path):
    fo: dict = {}
    cg.run_checks_law_true(_osm(tmp_path, "flat", step_m=0.0),
                           family_out=fo, quiet=True, top_n=0)
    assert fo[FAMILY] == [] == groundside_cutback(_patch(step_m=0.0))


# ── THE REGISTER (the structural fix: #108 could only fail on a build) ───

def test_every_census_family_is_read_or_declared_unreadable(cg):
    """A census family with no v2 reader must SAY why — or stand in the
    frozen :data:`OPEN_PARITY_GAPS` inventory.  A family added to
    ``LAW_FAMILIES`` without a counterpart fails HERE."""
    served = set(READERS) | set(_SERVED_BESIDE_READERS)
    keys = [k for k, _t, _b in cg.LAW_FAMILIES]
    unclassified = sorted(k for k in keys if k not in served
                          and k not in NOT_IMPLEMENTED
                          and k not in OPEN_PARITY_GAPS)
    assert unclassified == [], (
        "census families with no v2 verify reader and no reasoned "
        f"NOT_IMPLEMENTED entry: {unclassified} — give each a reader or a "
        "reason (issue #108)")
    # the inventory is frozen: a gap that got a reader leaves it
    closed = sorted(k for k in OPEN_PARITY_GAPS
                    if k in served or k in NOT_IMPLEMENTED)
    assert closed == [], (
        f"{closed} are now served — drop them from OPEN_PARITY_GAPS")
    stale = sorted(k for k in OPEN_PARITY_GAPS if k not in keys)
    assert stale == [], f"{stale} are no longer census families"


def test_every_not_implemented_entry_carries_a_reason(cg):
    keys = {k for k, _t, _b in cg.LAW_FAMILIES}
    assert set(NOT_IMPLEMENTED) <= keys, sorted(set(NOT_IMPLEMENTED) - keys)
    empty = sorted(k for k, why in NOT_IMPLEMENTED.items() if not why.strip())
    assert empty == [], f"NOT_IMPLEMENTED entries with no reason: {empty}"
    both = sorted(k for k in NOT_IMPLEMENTED if k in READERS)
    assert both == [], f"{both} are both read and declared unreadable"


def test_groundside_cutback_is_no_longer_a_parity_gap(cg):
    """#108: the family reads on BOTH instruments now."""
    assert FAMILY in READERS and FAMILY not in NOT_IMPLEMENTED
    assert FAMILY not in OPEN_PARITY_GAPS
    assert FAMILY in {k for k, _t, _b in cg.LAW_FAMILIES}
