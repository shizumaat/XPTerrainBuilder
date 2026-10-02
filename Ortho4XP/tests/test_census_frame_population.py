"""A CENSUS VERDICT NEVER DEPENDS ON THE PATCH'S NODE POPULATION (#215).

THE RULE.  A census verdict depends only on the geometry it judges and
the sidecar law context.  The patch's node POPULATION — how many
vertices it happens to carry, and where the unrelated ones sit — is not
law and must move nothing.

THE DEFECT.  ``check_grade._ll_to_m_factory``'s fallback origin is the
MEAN OF NODES.  Adding or removing a vertex anywhere moves ``lat0``, and
the frame's x scale is ``cos(lat0)``, so moving ``lat0`` RESCALES every
projected x.  v2's sidecar register publishes no ``anchor``
(``auto_patch_v2.emit.osm_adapter.SIDECAR_KEYS``), so every current
patch was censused in that moving frame.

It is not a last-bit effect.  ``_runway_strip_groups`` derives the
runway's length from the runway ring IN THIS FRAME, so the length drifts
with the population — measured below at 1200.975 m against 1198.982 m
from 400 unrelated apron nodes 40 km away, with no strip or runway
coordinate touched.  ``config.runway_code_number`` steps at 1200 m, so
that is aerodrome code 3 against code 2, which is
``ruleset_strip_half_width_m`` 75 m against 40 m and
``grade_law.strip_longitudinal_law`` 1.75 % against 1.5 %: the strip
footprint moved 35 m and the ``strip_arc`` reading went 1 row over 198
stations to 0 rows over 99.  That is issue #215's signature
(``sw1003_HECA`` 0 rows, ``sw1004b_HECA`` 1 row) with its mechanism in
the open.

THE FIX.  ``check_grade.sidecar_anchor`` — THE one frame-origin
accessor — falls through to ``_sidecar_frame_datum``, a
population-independent origin taken from the patch's own
SIDECAR-DECLARED geometry (``SIDECAR_FRAME_DATUM_KEYS``).  Every census
caller already reads its anchor through it.

NOT CLOSED HERE.  ``grade_law.runway_axis_and_width`` is
vertex-count-weighted (issue #190, ``needs-owner``), so the derived
length still drifts with the RUNWAY's own vertex multiset.  #215 is the
FRAME; #190 is the fit.  ``test_the_legacy_frame_still_flips_the_code``
below pins the frame coupling as REAL, so these twins can never pass
vacuously.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_R_EARTH = 6378137.0
#: Issue #215's own site.
_ANCHOR = (30.0996269, 31.3974530)
_RULESET = "icao"
#: A runway whose derived length sits just ABOVE ``runway_code_number``'s
#: 1200 m step, so the frame's own drift is what decides the code.
_RUNWAY_LENGTH_M = 1201.0
_RUNWAY_HALF_WIDTH_M = 22.5
_RUNWAY_VERTICES_PER_SIDE = 41
#: The band's outer rim sits EXACTLY on the strip footprint's lateral
#: edge at code 3 (75 m) — the configuration the emitter produces, and
#: the vertex whose membership issue #215 watched flip.
_STRIP_HALF_M = 75.0
_BAND_FROM_M = 100.0
_BAND_TO_M = 1101.0
_BAND_SPACING_M = 10.0
_BASE_ELEV_M = 10.0
_RAMP_FROM_INDEX = 40
_RAMP_RISE_PER_STATION_M = 0.36
#: The unrelated population: apron rings this far away, in a patch whose
#: tile is 1 degree (~111 km) across, so the distance is ordinary.
_FAR_OFFSET_M = 40_000.0
_FAR_NODES = 400


@pytest.fixture(scope="module")
def cg():
    spec = importlib.util.spec_from_file_location(
        "census_frame_check_grade", ROOT / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ll(x: float, y: float):
    cos0 = math.cos(math.radians(_ANCHOR[0]))
    return (_ANCHOR[0] + math.degrees(y / _R_EARTH),
            _ANCHOR[1] + math.degrees(x / (_R_EARTH * cos0)))


def _patch(tmp_path: Path, *, far_population: bool = False,
           reverse_runway_axes: bool = False, name: str = "FRAME"):
    """A runway ring plus ONE ``graded_strip`` band whose outer rim sits
    exactly on the code-3 strip footprint's lateral edge.

    ``far_population`` adds ``_FAR_NODES`` unrelated apron vertices
    ``_FAR_OFFSET_M`` away — not one runway or strip coordinate changes.
    ``reverse_runway_axes`` writes the sidecar's ``runway_axes`` ends the
    other way round, so the twins can show the datum is order-free.

    Returns ``(osm_path, local_surface)`` where ``local_surface`` is the
    runway's and the band's own (lat, lon, alt) triples — the twins
    assert them identical across arms, so "the local geometry did not
    change" is measured and not asserted by inspection.
    """
    nodes: list = []
    nid = [0]
    ways: list = []
    local: list = []

    def add(x, y, alt, *, local_shape: bool):
        nid[0] -= 1
        lat, lon = _ll(x, y)
        nodes.append((str(nid[0]), lat, lon, alt))
        if local_shape:
            local.append((round(lat, 11), round(lon, 11), round(alt, 3)))
        return str(nid[0])

    step = _RUNWAY_LENGTH_M / (_RUNWAY_VERTICES_PER_SIDE - 1)
    xs = [i * step for i in range(_RUNWAY_VERTICES_PER_SIDE)]
    rw = [add(x, -_RUNWAY_HALF_WIDTH_M, _BASE_ELEV_M, local_shape=True)
          for x in xs]
    rw += [add(x, _RUNWAY_HALF_WIDTH_M, _BASE_ELEV_M, local_shape=True)
           for x in reversed(xs)]
    ways.append((rw + [rw[0]],
                 {"role": "runway", "ref": "rwyX", "shapeID": "RW"}))

    n_band = int((_BAND_TO_M - _BAND_FROM_M) / _BAND_SPACING_M) + 1
    bxs = [_BAND_FROM_M + i * _BAND_SPACING_M for i in range(n_band)]
    gs: list = []
    for i, x in enumerate(bxs):
        z = _BASE_ELEV_M + (0.0 if i < _RAMP_FROM_INDEX else
                            _RAMP_RISE_PER_STATION_M
                            * (i - _RAMP_FROM_INDEX + 1))
        gs.append(add(x, _STRIP_HALF_M, z, local_shape=True))
    for x in reversed(bxs):
        gs.append(add(x, _RUNWAY_HALF_WIDTH_M, _BASE_ELEV_M,
                      local_shape=True))
    ways.append((gs + [gs[0]],
                 {"role": "graded_strip", "ref": "graded_strip:rwyX",
                  "shapeID": "GS"}))

    if far_population:
        for k in range(_FAR_NODES // 4):
            far = [add(_FAR_OFFSET_M + 20.0 * k + dx, _FAR_OFFSET_M + dy,
                       _BASE_ELEV_M, local_shape=False)
                   for dx, dy in ((0.0, 0.0), (15.0, 0.0),
                                  (15.0, 15.0), (0.0, 15.0))]
            ways.append((far + [far[0]],
                         {"role": "apron", "shapeID": f"FAR{k}"}))

    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='census-frame-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.3f}' /></node>")
    for nids, tags in ways:
        nid[0] -= 1
        out.append(f"  <way id='{nid[0]}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")

    # The sidecar v2 writes: NO ``anchor`` (its register publishes none),
    # but the ``runway_axes`` declaration off the apt.dat ends.
    a_ll = _ll(0.0, 0.0)
    b_ll = _ll(_RUNWAY_LENGTH_M, 0.0)
    ends = [b_ll, a_ll] if reverse_runway_axes else [a_ll, b_ll]
    Path(str(osm) + ".axes.json").write_text(
        json.dumps({"ruleset": _RULESET,
                    "runway_axes": [["rwyX", ends[0][0], ends[0][1],
                                     ends[1][0], ends[1][1],
                                     _RUNWAY_HALF_WIDTH_M]]}),
        encoding="utf-8", newline="")
    return osm, sorted(local)


def _reading(cg, osm, *, legacy_frame: bool = False):
    """``(rows, n_stations, code, derived_length_m)`` — the strip_arc
    reading of one patch.

    ``legacy_frame`` reads it in the pre-#215 mean-of-nodes frame
    (``anchor=None``), which is what the non-vacuity twin needs; the
    default is the census's own path: the anchor THE accessor hands back
    from the sidecar.
    """
    sidecar = json.loads(
        Path(str(osm) + ".axes.json").read_text(encoding="utf-8"))
    anchor = None if legacy_frame else cg.sidecar_anchor(sidecar)
    nodes, ways = cg._parse_osm(osm)
    cg._set_active_ruleset(_RULESET)
    ll_to_m = cg._ll_to_m_factory(nodes, anchor=anchor)
    rows, n_stations, _n_ways = cg._check_strip_arc_rate(ways, nodes, ll_to_m)
    groups = cg._runway_strip_groups(ways, nodes, ll_to_m)
    assert len(groups) == 1, "the fixture must read as exactly one runway"
    _rings, _axis, code, length, _letter = groups[0]
    row_set = {(round(r.grade_pct, 6), round(r.excess_pct, 6),
                round(r.distance_m, 6), round(r.de_m, 6))
               for r in rows}
    assert len(row_set) == len(rows), "two rows share a key"
    return row_set, n_stations, code, length


# ══════════════════════════════════════════════════════════════════════
# THE FIXTURE IS NOT VACUOUS
# ══════════════════════════════════════════════════════════════════════

def test_the_fixture_prices_a_row_over_real_stations(cg, tmp_path):
    """A station set of zero, or a row set of zero, makes every
    invariance twin below assert nothing."""
    osm, _local = _patch(tmp_path)
    rows, n_stations, code, length = _reading(cg, osm)
    assert n_stations > 0, "the reader visited no strip station"
    assert len(rows) >= 1, "the fixture prices no strip_arc row"
    assert code == 3, f"the fixture must read as code 3, read {code}"
    assert length > 1200.0, (
        f"the derived length {length:.4f} m must sit ABOVE the 1200 m "
        f"code step for the step to be the thing under test")


def test_the_far_population_leaves_the_local_geometry_byte_identical(
        cg, tmp_path):
    """MEASURED, not asserted by inspection: the runway's and the band's
    own vertices are identical across the two arms."""
    _base, base_local = _patch(tmp_path, name="BASE")
    _far, far_local = _patch(tmp_path, far_population=True, name="FAR")
    assert base_local == far_local, (
        "the far population changed a local coordinate — the twin would "
        "then be measuring a geometry change, not a population change")


# ══════════════════════════════════════════════════════════════════════
# THE DEFECT IS REAL (so the twins above cannot pass vacuously)
# ══════════════════════════════════════════════════════════════════════

def test_the_legacy_frame_still_flips_the_code(cg, tmp_path):
    """THE ARM THAT BITES.  In the pre-#215 mean-of-nodes frame the
    unrelated far population alone decides the aerodrome code, and with
    it the strip footprint, the rate law and the row.

    This twin asserts the DEFECT, not the fix: if it ever goes green the
    fixture has stopped exercising the coupling and every invariance twin
    here has gone vacuous.
    """
    base_osm, _b = _patch(tmp_path, name="LBASE")
    far_osm, _f = _patch(tmp_path, far_population=True, name="LFAR")
    b_rows, b_st, b_code, b_len = _reading(cg, base_osm, legacy_frame=True)
    f_rows, f_st, f_code, f_len = _reading(cg, far_osm, legacy_frame=True)
    assert b_code != f_code, (
        f"the legacy frame no longer flips the code (both {b_code}) — "
        f"derived lengths {b_len:.4f} / {f_len:.4f} m")
    assert (b_code, f_code) == (3, 2)
    assert b_rows != f_rows, "the legacy frame no longer moves the rows"
    assert (len(b_rows), len(f_rows)) == (1, 0)
    assert b_st != f_st, "the legacy frame no longer moves the stations"


# ══════════════════════════════════════════════════════════════════════
# THE VERDICT IS A FUNCTION OF THE GEOMETRY AND THE SIDECAR ONLY
# ══════════════════════════════════════════════════════════════════════

def test_strip_arc_rows_do_not_move_with_node_population(cg, tmp_path):
    """#215's own twin: the same patch judged twice — once as-is, once
    with unrelated far-away nodes added — yields IDENTICAL strip_arc
    rows, the same station count, the same code and the same derived
    length."""
    base_osm, _b = _patch(tmp_path, name="ABASE")
    far_osm, _f = _patch(tmp_path, far_population=True, name="AFAR")
    base = _reading(cg, base_osm)
    far = _reading(cg, far_osm)
    assert base[0] == far[0], "the strip_arc row set moved with the population"
    assert base[1] == far[1], "the station count moved with the population"
    assert base[2] == far[2], "the aerodrome code moved with the population"
    assert base[3] == pytest.approx(far[3], abs=1e-9), (
        "the derived runway length moved with the population")


def test_the_frame_datum_is_order_free(cg, tmp_path):
    """The datum is the ``min()`` over the key's points, so the order the
    sidecar happens to list a runway's ends in cannot move the frame
    (the ``_strip_chain_start`` lesson: a canonical choice, never an
    array's first element)."""
    fwd_osm, _a = _patch(tmp_path, name="OFWD")
    rev_osm, _b = _patch(tmp_path, reverse_runway_axes=True, name="OREV")
    assert _reading(cg, fwd_osm) == _reading(cg, rev_osm)


def test_the_accessor_prefers_a_declared_anchor_and_names_each_frame(cg):
    """``sidecar_anchor`` is THE frame-origin accessor and
    ``sidecar_frame_name`` THE naming site: a declared ``anchor`` wins,
    the sidecar datum is next, and only a sidecar declaring neither
    falls through to the population-dependent mean of nodes."""
    axes = [["rwyX", 30.2, 31.5, 30.1, 31.4, 22.5]]
    assert cg.sidecar_anchor({"anchor": [10.0, 20.0],
                              "runway_axes": axes}) == (10.0, 20.0)
    assert cg.sidecar_frame_name(
        {"anchor": [10.0, 20.0]}) == cg.FRAME_BUILDER_ANCHOR
    # no anchor: the declared geometry, canonically
    assert cg.sidecar_anchor({"runway_axes": axes}) == (30.1, 31.4)
    assert cg.sidecar_frame_name(
        {"runway_axes": axes}) == cg.FRAME_SIDECAR_DATUM
    # neither
    assert cg.sidecar_anchor({"ruleset": "icao"}) is None
    assert cg.sidecar_frame_name({}) == cg.FRAME_MEAN_OF_NODES
    assert cg.sidecar_anchor(None) is None


def test_every_frame_datum_key_is_a_published_sidecar_key(cg):
    """A datum key absent from the emitter's own register would make the
    frame derivation dead code the day the key was renamed."""
    from auto_patch_v2.emit.osm_adapter import SIDECAR_KEYS
    for key in cg.SIDECAR_FRAME_DATUM_KEYS:
        assert key in SIDECAR_KEYS or key in cg.SIDECAR_LAW_KEYS, (
            f"frame datum key {key!r} is in no sidecar register")


def test_each_datum_key_shape_is_read_by_its_own_published_shape(cg):
    """``_frame_datum_points`` reads each key by that key's OWN shape —
    explicit per key, never a guessing walk that could mistake a cap or
    a half-width for a latitude."""
    assert cg._frame_datum_points(
        "runway_axes", [["r", 1.0, 2.0, 3.0, 4.0, 22.5]]) == [
            (1.0, 2.0), (3.0, 4.0)]
    assert cg._frame_datum_points(
        "axes", [[[[5.0, 6.0], [7.0, 8.0]], 1.0, 2.0, 0, False]]) == [
            (5.0, 6.0), (7.0, 8.0)]
    assert cg._frame_datum_points("seam_pins", [[9.0, 10.0]]) == [(9.0, 10.0)]
    # a malformed record is skipped, never guessed at
    assert cg._frame_datum_points("runway_axes", [["r", 1.0]]) == []
    assert cg._frame_datum_points("axes", [[]]) == []
    assert cg._sidecar_frame_datum({"runway_axes": [["r", 1.0]]}) is None
