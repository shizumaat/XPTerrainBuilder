"""The law-table twin (RULINGS 2026-09-03d; owner amendment 2026-09-03).

Cross-checks every numeric value in ``auto_patch_v2/law/*.toml`` against
v1's constants — v1 (``auto_patch.config``, ``layout``, ``check_grade``)
is imported HERE ONLY, never in v2 — so the two law sources cannot drift
silently; asserts every v1 law family has a v2 family with a resolving
parameter; asserts the TOML schema round-trips; and asserts the loader
refuses malformed tables loudly.
"""
from __future__ import annotations

import math
import os
import shutil
import sys
from pathlib import Path

import pytest

from auto_patch_v2.law import DEFAULT_LAW_DIR, Law, LawError, load_tables
from auto_patch_v2.law import tables as T

# v1 — test-only imports (the oracle side of the cross-check)
from auto_patch import config as v1  # noqa: E402
from auto_patch import layout as v1_layout  # noqa: E402
from auto_patch import road_transition as v1_rt  # noqa: E402
from auto_patch import emit_decimate as v1_dec  # noqa: E402

_TOOLS = str(Path(__file__).resolve().parents[2] / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
import check_grade as v1_cg  # noqa: E402

LETTERS = "ABCDEF"
CODES = (1, 2, 3, 4)


class Checks:
    """Accumulates (name, v1, v2) comparisons; one assertion at the end
    so a drift report names every mismatch at once."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, object, object]] = []

    def eq(self, name: str, a: object, b: object) -> None:
        self.rows.append((name, a, b))

    def table(self, name: str, v1_ct, v2_ct, keys) -> None:
        """Compare a v1 CodeTable with a v2 CodeTable class by class;
        v1 ``None`` == v2 absent-with-None-default or 0.0 (FAA
        vertical-curve "always")."""
        for k in keys:
            kw = {"code_number": k} if isinstance(k, int) else \
                {"code_letter": k}
            a = v1_ct.value(**kw)
            b = v2_ct.value(**kw)
            if a is None and b in (None, 0.0):
                b = None
            self.eq(f"{name}[{k}]", a, b)

    def mismatches(self) -> list[tuple[str, object, object]]:
        out = []
        for name, a, b in self.rows:
            if isinstance(a, float) or isinstance(b, float):
                ok = a is not None and b is not None and \
                    math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-12)
            else:
                ok = a == b
            if not ok:
                out.append((name, a, b))
        return out


@pytest.fixture(scope="module")
def tables():
    return load_tables(DEFAULT_LAW_DIR)


def _ruleset_checks(c: Checks, key: str, rs, v1rs, zones) -> None:
    keys = CODES if v1rs.runway_max_grade.by_code is not None else LETTERS
    c.table(f"{key}.runway.longitudinal", v1rs.runway_max_grade,
            rs.runway.longitudinal, keys)
    c.table(f"{key}.runway.end_zone", v1rs.runway_end_grade,
            rs.runway.end_zone, keys)
    c.eq(f"{key}.runway.end_zone_fraction", v1rs.runway_end_zone_fraction,
         rs.runway.end_zone_fraction)
    c.eq(f"{key}.runway.end_zone_max_length_m",
         v1rs.runway_end_zone_max_length_m, rs.runway.end_zone_max_length_m)
    c.eq(f"{key}.runway.end_zone_precision_only_codes",
         set(v1rs.runway_end_grade_precision_only_codes),
         set(rs.runway.end_zone_precision_only_codes))
    c.table(f"{key}.runway.max_grade_change", v1rs.runway_max_grade_change,
            rs.runway.max_grade_change, keys)
    c.table(f"{key}.runway.vertical_curve_k_m",
            v1rs.runway_vertical_curve_k_m, rs.runway.vertical_curve_k_m,
            keys)
    if rs.runway.vertical_curve_min_change is not None:
        c.table(f"{key}.runway.vertical_curve_min_change",
                v1rs.runway_vertical_curve_min_change,
                rs.runway.vertical_curve_min_change, LETTERS)
    else:
        for k in keys:
            kw = {"code_number": k} if isinstance(k, int) else \
                {"code_letter": k}
            c.eq(f"{key}.runway.vertical_curve_min_change[{k}]",
                 v1rs.runway_vertical_curve_min_change.value(**kw), None)
    c.table(f"{key}.runway.transverse_max", v1rs.runway_transverse_max,
            rs.runway.transverse_max, LETTERS)
    c.eq(f"{key}.runway.transverse_min", v1rs.runway_transverse_min,
         rs.runway.transverse_min)
    c.table(f"{key}.taxi.longitudinal", v1rs.taxi_max_grade,
            rs.taxi.longitudinal, LETTERS)
    c.table(f"{key}.taxi.transverse", v1rs.taxi_transverse_max,
            rs.taxi.transverse, LETTERS)
    c.eq(f"{key}.taxi.transverse_min", v1rs.taxi_transverse_min,
         rs.taxi.transverse_min)
    c.table(f"{key}.strip.longitudinal", v1rs.strip_max_longitudinal_slope,
            rs.strip.longitudinal, keys)
    c.eq(f"{key}.strip.arc_rate", v1rs.strip_arc_rate_per_m,
         rs.strip.arc_rate.per_metre)
    c.eq(f"{key}.strip.arc_rate_provisional", v1rs.strip_arc_rate_provisional,
         rs.strip.arc_rate_provisional)
    c.eq(f"{key}.end_skirt.near_zone_m", v1rs.end_skirt_near_zone_m,
         rs.end_skirt.near_zone_m)
    c.eq(f"{key}.end_skirt.near_max_down_grade",
         v1rs.end_skirt_near_max_down_grade, rs.end_skirt.near_max_down_grade)
    c.eq(f"{key}.end_skirt.max_down_grade", v1rs.end_skirt_max_down_grade,
         rs.end_skirt.max_down_grade)
    c.eq(f"{key}.end_skirt.rate", v1rs.end_skirt_max_grade_change_per_m,
         rs.end_skirt.rate.per_metre)
    c.eq(f"{key}.end_skirt.rate_provisional", v1rs.end_skirt_rate_provisional,
         rs.end_skirt.rate_provisional)
    c.eq(f"{key}.resa.transverse_max", v1rs.resa_transverse_max,
         rs.resa.transverse_max)
    if v1rs.resa_transverse_near is not None:
        c.table(f"{key}.resa.transverse_near_min", v1rs.resa_transverse_near,
                rs.resa.transverse_near_min, LETTERS)
        c.table(f"{key}.resa.transverse_near_max",
                v1rs.resa_transverse_near_max, rs.resa.transverse_near_max,
                LETTERS)
    else:
        c.eq(f"{key}.resa.transverse_near", None, rs.resa.transverse_near_min)
    c.eq(f"{key}.drainage.apron_min_grade", v1rs.apron_min_drainage_grade,
         rs.drainage.apron_min_grade)
    c.eq(f"{key}.drainage.apron_max_grade_change",
         v1rs.apron_max_grade_change, rs.drainage.apron_max_grade_change)
    if v1rs.raoa_length_m is None:
        c.eq(f"{key}.raoa", None, rs.raoa)
    else:
        c.eq(f"{key}.raoa.length_m", v1rs.raoa_length_m, rs.raoa.length_m)
        c.eq(f"{key}.raoa.half_width_m", v1rs.raoa_half_width_m,
             rs.raoa.half_width_m)
        c.eq(f"{key}.raoa.rate", v1rs.raoa_max_grade_change_per_m,
             rs.raoa.max_grade_change.per_metre)
    c.eq(f"{key}.stand_max_grade == common.apron", v1rs.stand_max_grade,
         None)  # placeholder replaced below
    c.rows.pop()
    # zones (the strip geometry lives in the ruleset in v1, zones.toml in v2)
    ag = zones.adjacent_ground
    c.eq(f"{key}.zones.lip_width_m", v1rs.strip_lip_width_m, ag.lip_width_m)
    c.eq(f"{key}.zones.lip_min_down", v1rs.strip_lip_min_down_slope,
         ag.lip_min_down)
    c.eq(f"{key}.zones.lip_max_down", v1rs.strip_lip_max_down_slope,
         ag.lip_max_down)
    c.eq(f"{key}.zones.ungraded_max_up", v1rs.ungraded_strip_max_up_slope,
         ag.ungraded_max_up)
    c.eq(f"{key}.zones.runway.band_min_down", v1rs.strip_band_min_down_slope,
         ag.runway.band_min_down)
    c.table(f"{key}.zones.runway.band_max_down", v1rs.strip_band_max_down_slope,
            ag.runway.band_max_down, CODES)
    if v1rs.strip_half_width_m.by_code is not None:
        c.table(f"{key}.zones.runway.half_width_m", v1rs.strip_half_width_m,
                ag.runway.half_width_m, CODES)
    else:
        c.table(f"{key}.zones.runway.half_width_faa_m",
                v1rs.strip_half_width_m, ag.runway.half_width_faa_m, LETTERS)
    for L in LETTERS:
        c.eq(f"{key}.zones.taxi.half_width_m[{L}]",
             v1rs.taxiway_strip_graded_half_width_m[L],
             ag.taxi.half_width_m.value(code_letter=L))
    c.eq(f"{key}.zones.taxi.band_min_down",
         v1rs.taxiway_strip_band_min_down_slope, ag.taxi.band_min_down)
    c.eq(f"{key}.zones.taxi.band_max_down",
         v1rs.taxiway_strip_band_max_down_slope,
         ag.taxi.band_max_down.value(code_letter="C"))


def _common_checks(c: Checks, t) -> None:
    roles = t.common.roles
    for role in ("apron", "building", "tunnel_ramp", "service_road",
                 "service_junction", "groundside_pavement"):
        c.eq(f"common.roles.{role}.longitudinal",
             v1.ROLE_GRADE_LIMITS[role], roles[role].longitudinal)
    c.eq("common.roles.service_road.transverse",
         v1.SERVICE_ROAD_MAX_TRANSVERSE, roles["service_road"].transverse)
    c.eq("common.roles.apron.transverse", v1.APRON_MAX_GRADE,
         roles["apron"].transverse)
    c.eq("common.apron_fan_ramp_max", v1.FAN_RAMP_CAP, t.common.apron_fan_ramp_max)
    c.eq("common.road_transverse_axis_min_deg", v1.ROAD_TRANSVERSE_AXIS_MIN_DEG,
         t.common.road_transverse_axis_min_deg)
    c.eq("common.runway_crown_transverse", v1.RUNWAY_CROWN_TRANSVERSE,
         t.common.runway_crown_transverse)
    c.eq("icao stand == apron", v1.ICAO_RULESET.stand_max_grade,
         roles["apron"].longitudinal)
    c.eq("faa stand == apron", v1.FAA_RULESET.stand_max_grade,
         roles["apron"].longitudinal)
    # roles with NO within-shape cap in v1 are exactly v2's family "none"
    v1_none = {r for r, cap in v1.ROLE_GRADE_LIMITS.items()
               if cap is None}
    v2_none = {r for r, s in t.precedence.roles.items() if s.family == "none"}
    c.eq("no-cap roles", v1_none - {"terminal"} | {"tunnel_trench"}, v2_none)
    # value roles: every v1 capped role is registered with a cap
    for r, cap in v1.ROLE_GRADE_LIMITS.items():
        if cap is None or r == "terminal":
            continue
        law = Law(tables=t, ruleset_key="faa")
        got = T.role_cap(law, r, code_letter="C")
        c.eq(f"role_cap({r}, FAA/C).longitudinal", cap, got.longitudinal)
    c.eq("precedence.order", tuple(v1_layout.AUTHORITY_PRECEDENCE),
         t.precedence.order)
    gs = {r for r, s in t.precedence.roles.items() if s.side == "groundside"}
    c.eq("groundside partition", set(v1_cg._GROUNDSIDE_ROLES), gs)
    c.eq("resolution.default", v1.DEFAULT_RULESET, t.resolution.default)
    c.eq("resolution.faa_first_letters", set(v1.FAA_RULESET_FIRST_LETTERS),
         set(t.resolution.faa_first_letters))
    c.eq("resolution.faa_two_letter_prefixes",
         set(v1.FAA_RULESET_TWO_LETTER_PREFIXES),
         set(t.resolution.faa_two_letter_prefixes))
    c.eq("runway K 305 == faa wide k", v1.RUNWAY_VERTICAL_CURVE_K_M,
         t.rulesets["faa"].runway.vertical_curve_k_m.value(code_letter="D"))
    c.eq("RUNWAY_END_FRACTION", v1.RUNWAY_END_FRACTION,
         t.rulesets["icao"].runway.end_zone_fraction)
    c.eq("RUNWAY_MAX_GRADE == faa wide", v1.RUNWAY_MAX_GRADE,
         t.rulesets["faa"].runway.longitudinal.value(code_letter="C"))
    c.eq("RUNWAY_END_GRADE == faa wide", v1.RUNWAY_END_GRADE,
         t.rulesets["faa"].runway.end_zone.value(code_letter="C"))
    c.eq("TAXI_MAX_GRADE_NARROW == icao A", v1.TAXI_MAX_GRADE_NARROW,
         t.rulesets["icao"].taxi.longitudinal.value(code_letter="A"))
    c.eq("TAXI_MAX_TRANSVERSE_NARROW == icao A", v1.TAXI_MAX_TRANSVERSE_NARROW,
         t.rulesets["icao"].taxi.transverse.value(code_letter="A"))


def _structures_emit_checks(c: Checks, t) -> None:
    s, e = t.structures, t.emit
    c.eq("tunnel.bore_datum_m", v1.BRIDGE_ROAD_CLEARANCE_M, s.tunnel.bore_datum_m)
    c.eq("tunnel.ramp_max_grade", v1.TUNNEL_RAMP_MAX_GRADE, s.tunnel.ramp_max_grade)
    c.eq("bridge.clearance_m", v1.BRIDGE_ROAD_CLEARANCE_M, s.bridge.clearance_m)
    c.eq("bridge.clearance_minimum_m", v1.BRIDGE_ROAD_CLEARANCE_MINIMUM_M,
         s.bridge.clearance_minimum_m)
    c.eq("bridge.floor_below_object_deck_m", v1.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M,
         s.bridge.floor_below_object_deck_m)
    c.eq("building_pad.min_area_m2", v1.PAD_MIN_AREA_M2, s.building_pad.min_area_m2)
    c.eq("chords.pavement_max_chord_m (emit_decimate)", v1_dec.MAX_CHORD_M,
         e.chords.pavement_max_chord_m)
    c.eq("chords.pavement_max_chord_m (layout)", v1_layout.PAVEMENT_NODE_MAX_CHORD_M,
         e.chords.pavement_max_chord_m)
    c.eq("chords.apron_interior_spacing_m", v1.APRON_LATTICE_SPACING_M,
         e.chords.apron_interior_spacing_m)
    c.eq("identity.min_distinct_spacing_m", v1_layout.SHARED_VERTEX_TOL_M,
         e.identity.min_distinct_spacing_m)
    c.eq("identity.min_distinct_spacing_m (knob)",
         v1_cg.LAW_TRUE_KNOBS["proximity_m"], e.identity.min_distinct_spacing_m)
    c.eq("materiality.step_m", v1_cg.LAW_TRUE_KNOBS["edge_step_m"],
         e.materiality.step_m)
    c.eq("materiality.elevation_m", v1_rt.MATERIALITY_M, e.materiality.elevation_m)
    c.eq("no_step.window_m", v1.AIRSIDE_NO_STEP_WINDOW_M, e.no_step.window_m)
    c.eq("no_step.k", v1.AIRSIDE_NO_STEP_K, e.no_step.k)


def test_every_value_equals_v1(tables, capsys):
    """THE cross-check: every numeric value in the TOML equals v1's."""
    c = Checks()
    _ruleset_checks(c, "icao", tables.rulesets["icao"], v1.ICAO_RULESET,
                    tables.zones)
    _ruleset_checks(c, "faa", tables.rulesets["faa"], v1.FAA_RULESET,
                    tables.zones)
    _common_checks(c, tables)
    _structures_emit_checks(c, tables)
    bad = c.mismatches()
    assert not bad, "law drift vs v1:\n" + "\n".join(
        f"  {n}: v1={a!r} v2={b!r}" for n, a, b in bad)
    print(f"\n[law-twin] {len(c.rows)} constants verified equal to v1")
    assert len(c.rows) >= 200


def test_every_v1_family_has_a_v2_family(tables):
    """Every ``check_grade.LAW_FAMILIES`` key is a v2 family with the
    same bucket, and every v2 family's parameter resolves."""
    v1_fams = {k: bucket for k, _title, bucket in v1_cg.LAW_FAMILIES}
    assert set(v1_fams) == set(tables.families)
    for k, bucket in v1_fams.items():
        assert tables.families[k].pairs == bucket, k
        assert tables.families[k].ruling
        assert tables.families[k].measures


def test_step_exemption_is_pad_to_pad_only(tables):
    assert set(v1_cg.STEP_EXEMPTIONS) == {"building_to_building"}
    assert tables.structures.building_pad.step_exemption_pad_to_pad is True


@pytest.mark.parametrize("icao", ["CYXY", "KCLT", "KDFW", "PHNL", "PANC",
                                  "PGUM", "PKMJ", "SPJC", "HECA", "OTHH",
                                  "LEMD", "MMMX", "", "k"])
def test_resolve_ruleset_matches_v1(icao, monkeypatch):
    monkeypatch.delenv("O4_RULESET", raising=False)
    assert Law.for_airport(icao).ruleset_key == v1.resolve_ruleset(icao)


def test_schema_round_trips(tables, tmp_path):
    """Copying the six files elsewhere and reloading yields an equal
    LawTables; the loader depends on nothing but the files."""
    for f in os.listdir(DEFAULT_LAW_DIR):
        if f.endswith(".toml"):
            shutil.copy(DEFAULT_LAW_DIR / f, tmp_path / f)
    again = load_tables(tmp_path)
    assert again == tables
    assert Law.load(tmp_path, ruleset="faa").ruleset.authority == "FAA"


def _mutated(tmp_path, fname, old, new):
    for f in os.listdir(DEFAULT_LAW_DIR):
        if f.endswith(".toml"):
            shutil.copy(DEFAULT_LAW_DIR / f, tmp_path / f)
    p = tmp_path / fname
    text = p.read_text()
    assert old in text, old
    p.write_text(text.replace(old, new, 1))
    return tmp_path


@pytest.mark.parametrize("fname, old, new, needle", [
    ("emit.toml", "coordinate_dp           = 11",
     "coordinate_dp           = 11\nbogus = 1", "unknown key"),
    ("emit.toml", "coordinate_dp           = 11     #", "#", "missing"),
    ("rulesets.toml", "apron_fan_ramp_max = 0.050", 'apron_fan_ramp_max = "5%"',
     "expected a number"),
    ("rulesets.toml", "apron_fan_ramp_max = 0.050", "apron_fan_ramp_max = 5.0",
     "grade fraction"),
    ("families.toml", 'parameter = "common.runway_crown_transverse"',
     'parameter = "common.no_such_key"', "does not resolve"),
    ("precedence.toml", '"apron", "building",', '"apron", "apron",',
     "duplicate"),
    ("zones.toml", 'beyond_zone2   = "dem"', 'beyond_zone2   = "graded"',
     "beyond_zone2"),
    ("structures.toml", "bore_datum_m      = 5.1", "bore_datum_m      = -5.1",
     ">= 0"),
])
def test_loader_refuses_malformed_tables(tmp_path, fname, old, new, needle):
    d = _mutated(tmp_path, fname, old, new)
    with pytest.raises(LawError, match=needle):
        load_tables(d)


def test_no_numeric_literal_in_law_python():
    """The amendment's letter: no cap value lives in Python."""
    import re
    for name in ("model.py", "tables.py"):
        src = (DEFAULT_LAW_DIR / name).read_text()
        body = "\n".join(l for l in src.splitlines()
                         if not l.strip().startswith("#"))
        floats = re.findall(r"(?<![\w.])\d+\.\d+(?![\w.])", body)
        assert floats in ([], ["0.0", "0.2"]) or \
            set(floats) <= {"0.0", "0.2", "1.0"}, (name, floats)


def test_accessors(tables):
    law = Law(tables=tables, ruleset_key="icao")
    assert T.role_cap(law, "runway", code_number=4).longitudinal == \
        v1.ICAO_RULESET.runway_max_grade.value(code_number=4)
    assert T.role_cap(law, "graded_strip") is None
    assert T.senior_role(law, ["building", "apron", "runway"]) == "runway"
    assert T.authority_rank(law, "boundary") == len(tables.precedence.order)
    lo, hi = T.zone_bounds(law, "runway", 10.0, code_number=3)
    assert lo < hi < 0
    assert T.zone_bounds(law, "runway", 1000.0, code_number=3) == (None, None)
    assert T.zone_bounds(law, "apron", 1.0) == (None, None)
    assert T.chord_cap_m(law, "apron") <= T.chord_cap_m(law, "junction")
    assert {f.key for f in T.families_for_role(law, "runway")} >= \
        {"within_shape", "runway_crown", "raoa", "airside_no_step"}
    faa = Law(tables=tables, ruleset_key="faa")
    assert T.runway_end_zone_length_m(faa, 4000.0) == \
        v1.FAA_RULESET.runway_end_zone_max_length_m
