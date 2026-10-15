"""THE GROUND BEYOND A RUNWAY END (#620; owner RULINGS 2026-10-12q (1)
(a)-(d); audit ``docs/findings/runway-end-law-audit-20261012.md``).

(a) ICAO: the strip's longitudinal cap governs the strip's end length
    beyond each end (60 m code 2-4, 30 m code 1), the RESA's 5 % beyond;
(b) FAA (AC 150/5300-13B §3.16.5 items 2-5, read from the primary text
    2026-10-12): 0 to -3 % over the first 61 m, downward only; -5 %
    beyond; ±2 % per 30.5 m;
(c) the fall caps bind FALLING ground only — rising ground is bound by
    the take-off climb / departure surface with no tail height;
(d) the census reads the end band v2 emits (family ``runway_end_skirt``
    over ``graded_strip`` rings), one profile with the generator.
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.constraints import GENERATORS, strips
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import load_default, runway_end_profile
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.solve.design_roles import one_way_rulings, ruling_head
from auto_patch_v2.verify import strips as vstrips

# the synthetic runway with a falling DEM beyond its end and the §35
# corner quadrant — ONE fixture with the corner twins
from tests.auto_patch_v2.test_v2rwycorner import law, synthetic  # noqa: F401


@pytest.fixture(scope="module")
def icao():
    return load_default()


@pytest.fixture(scope="module")
def faa():
    return Law.load(ruleset="faa")


# ── (a) ICAO: the strip's cap over its end length, the 5 % beyond ──────────

def test_icao_profile_is_the_strip_cap_then_the_resa(icao):
    rs = icao.ruleset
    for code in (2, 3, 4):
        prof = runway_end_profile(icao, code, "D")
        cap = rs.strip.longitudinal.value(code, "D")
        assert prof.break_m == 60.0
        assert prof.fall_m(60.0) == pytest.approx(cap * 60.0)
        assert prof.fall_m(75.0) == pytest.approx(cap * 60.0 + rs.end_skirt.max_down_grade * 15.0)
        assert prof.down_cap_at(10.0) == cap
        assert prof.down_cap_at(70.0) == rs.end_skirt.max_down_grade
    # code 1: the 30 m (non-instrument) strip length from the text
    prof1 = runway_end_profile(icao, 1, "A")
    assert prof1.break_m == 30.0
    assert prof1.fall_m(30.0) == pytest.approx(rs.strip.longitudinal.value(1, "A") * 30.0)


def test_icao_states_no_rate_number(icao):
    assert icao.ruleset.end_skirt.rate_provisional is True
    assert runway_end_profile(icao, 3, "D").rate is None


# ── (b) FAA: 0 to -3 % over 61 m, -5 % beyond, ±2 %/30.5 m ────────────────

def test_faa_profile_is_the_near_end_rule_then_five_percent(faa):
    rs = faa.ruleset
    prof = runway_end_profile(faa, 4, "D")
    assert prof.break_m == pytest.approx(61.0)
    assert prof.fall_m(61.0) == pytest.approx(0.03 * 61.0)
    assert prof.fall_m(76.0) == pytest.approx(0.03 * 61.0 + 0.05 * 15.0)
    # "any slope being downward from the ends": no rise in the near zone
    assert prof.hold_m == pytest.approx(61.0)
    assert prof.rise_m(30.0) == 0.0
    assert prof.rise_m(61.0) == 0.0
    # beyond it the departure surface (40:1 from the DER, no setback)
    assert prof.rise_m(80.0) == pytest.approx(rs.eat.slope.value(4) * 80.0)
    # the grade-change rate is stated and read
    assert rs.end_skirt.rate_provisional is False
    assert prof.rate == pytest.approx(0.02 / 30.5)


# ── (c) rising ground: the climb surface, no tail height ───────────────────

def test_icao_rising_ground_is_the_takeoff_climb_surface(icao):
    rs = icao.ruleset
    prof = runway_end_profile(icao, 3, "D")
    # level with the end for the first setback_m, then the slope
    assert prof.rise_m(0.0) == 0.0
    assert prof.rise_m(rs.eat.setback_m.value(3)) == 0.0
    assert prof.rise_m(rs.eat.setback_m.value(3) + 100.0) == pytest.approx(
        rs.eat.slope.value(3) * 100.0)


def test_pair_bounds_are_one_sided_in_each_direction(icao):
    prof = runway_end_profile(icao, 3, "D")
    q = 0.14
    lo, hi = strips.end_pair_bounds(prof, 10.0, 40.0, q)
    # falling: the strip cap's increment; rising: nothing (level to 60 m)
    assert hi == pytest.approx(0.0175 * 30.0 + q)
    assert lo == pytest.approx(-q)
    lo2, hi2 = strips.end_pair_bounds(prof, 60.0, 75.0, q)
    assert hi2 == pytest.approx(0.05 * 15.0 + q)
    assert lo2 == pytest.approx(-(0.02 * 15.0) - q)


def test_the_rows_follow_the_runway_and_never_pull_it(synthetic, icao):  # noqa: F811
    airport, pm = synthetic
    law = icao
    rows = strips.end_corridor_longitudinal(pm, law, airport)
    assert rows
    vw = view(pm, law)
    runway = {v for f in vw.faces_of_role(("runway",)) for v in vw.rings[f.id]}
    ow = one_way_rulings(law)
    for r in rows:
        assert isinstance(r, Linear)
        feet = {v for v, _c in r.terms}
        if feet & runway:
            # the chord from the end edge: one-way, the strip vertex follows
            assert r.follows is not None and r.follows not in runway
            assert ruling_head(r) in ow
        else:
            assert r.hi is not None


def test_the_rate_generator_is_registered_and_faa_only(synthetic, icao, faa):  # noqa: F811
    assert "end_corridor_rate" in dict(GENERATORS)
    airport, pm = synthetic
    assert strips.end_corridor_rate(pm, icao, airport) == []
    # under FAA law the same geometry mints rate rows (the end-edge
    # parabola against the runway's own last chord, one-way)
    faa_rows = strips.end_corridor_rate(pm, faa, airport)
    assert faa_rows
    assert any(r.follows is not None for r in faa_rows)
    assert all(ruling_head(r) in one_way_rulings(faa) for r in faa_rows if r.follows is not None)


# ── (d) the census reads the end band ─────────────────────────────────────

def test_verify_reads_a_falling_end_band_and_passes_a_lawful_one(icao):
    """One synthetic patch frame: a runway and its end band on a chord
    falling 3 % over 60 m is OVER the code-3 strip cap (1.75 %); the same
    band at 1.5 % is lawful; a band RISING 1 m at 40 m is over the climb
    surface (level to 60 m)."""
    from auto_patch_v2.verify.frame import Patch, Shape
    law = icao
    L, half = 1500.0, 22.5

    def frame(dz_at_60: float, dz_at_75: float):
        xy = {}
        z = {}
        ids = {}
        n = 0

        def v(x, y, zz):
            nonlocal n
            n += 1
            xy[n], z[n] = (x, y), zz
            return n
        rw = [v(0.0, -half, 100.0), v(L, -half, 100.0), v(L, half, 100.0), v(0.0, half, 100.0)]
        band = [v(L, -half, 100.0), v(L + 60.0, -half, 100.0 + dz_at_60),
                v(L + 75.0, -half, 100.0 + dz_at_75), v(L + 75.0, half, 100.0 + dz_at_75),
                v(L + 60.0, half, 100.0 + dz_at_60), v(L, half, 100.0)]
        # the band shares the runway's end-edge vertices by identity
        xy[band[0]], z[band[0]] = xy[rw[1]], z[rw[1]]
        xy[band[-1]], z[band[-1]] = xy[rw[2]], z[rw[2]]
        band[0], band[-1] = rw[1], rw[2]
        shapes = (
            Shape(0, "runway", "09/27", tuple(rw), tuple(xy[i] for i in rw),
                  tuple(z[i] for i in rw), code_letter="D", code_number=3),
            Shape(1, "graded_strip", "adjacent_ground:runway:3:zone2#0", tuple(band),
                  tuple(xy[i] for i in band), tuple(z[i] for i in band), code_number=3),
        )
        return Patch(law, 0.0, 0.0, xy, z, {}, shapes, (), {})

    over = vstrips.runway_end_skirt(frame(-0.03 * 60.0, -0.03 * 60.0 - 0.05 * 15.0))
    assert over, "a 3 % fall over the first 60 m must be read against the 1.75 % cap"
    assert all(r["family"] == "runway_end_skirt" for r in over)
    lawful = vstrips.runway_end_skirt(frame(-0.015 * 60.0, -0.015 * 60.0 - 0.04 * 15.0))
    assert lawful == []
    rising = vstrips.runway_end_skirt(frame(+1.0, +1.0))
    assert rising, "ground 1 m above the end inside the 60 m setback is over the climb surface"


def test_the_family_is_registered_in_both_censuses(icao):
    import importlib
    census = importlib.import_module("auto_patch_v2.verify.census")
    from auto_patch_v2.law.tables import family
    assert census.READERS["runway_end_skirt"] is vstrips.runway_end_skirt
    assert "graded_strip" in family(icao, "runway_end_skirt").roles
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import check_grade
    assert any(k == "runway_end_skirt" for k, _d, _b in check_grade.LAW_FAMILIES)


def test_the_planar_stage_breaks_the_end_band_at_the_strip_length(synthetic, icao):  # noqa: F811
    """The breakline: a graded_strip vertex stands at the strip's end
    length beyond the runway end on the extended centre line."""
    airport, pm = synthetic
    law = icao
    vw = view(pm, law)
    (g,) = strips.runway_groups(vw, airport)
    brk = runway_end_profile(law, g.code_number, g.code_letter).break_m
    ux, uy = g.unit
    hits = []
    for f in vw.faces_of_role(("graded_strip",)):
        for v in vw.rings[f.id]:
            x, y = vw.xy[v]
            s = (x - g.axis_a[0]) * ux + (y - g.axis_a[1]) * uy
            if abs(s - g.length_m - brk) <= 0.5 or abs(s + brk) <= 0.5:
                hits.append(v)
    assert hits, f"no strip vertex at {brk} m beyond an end"


def test_the_chord_projection_names_the_generators_own_head():
    """``solve/project.CORRIDOR_RULINGS`` spells the strips chord head as a
    literal (solve imports nothing of constraints); it is the generator's."""
    from auto_patch_v2.solve.project import CORRIDOR_RULINGS
    assert (strips.GEN, ruling_head_of(strips.END_PROFILE_RULING)) in CORRIDOR_RULINGS
    assert (strips.GEN, ruling_head_of(strips.END_PROFILE_PAIR_RULING)) not in CORRIDOR_RULINGS


def ruling_head_of(ruling: str) -> str:
    return ruling.split(" (")[0].strip()


# ── lane kase620: both ends, the pad beyond an end, the slab frame, the key ──

def test_the_transect_pairs_are_minted_at_both_ends(synthetic, icao):  # noqa: F811
    """The break vertex and the outer ring are not ring-consecutive: only
    the TRANSECT pair prices the last piece of the band.  The pair block
    once read the ring loop's leaked index and priced the far end only
    (KASE 15: −9.2 % over the last 15 m with no row on the pair)."""
    airport, pm = synthetic
    vw = view(pm, icao)
    (g,) = strips.runway_groups(vw, airport)
    brk = runway_end_profile(icao, g.code_number, g.code_letter).break_m
    rows = strips.end_corridor_longitudinal(pm, icao, airport)
    paired = {frozenset(v for v, _c in r.terms) for r in rows if len(r.terms) == 2}
    for ring_idx in (1, 2):
        st = strips._end_stations(vw, g, ring_idx)
        want = [(a, b) for a, b in strips.end_transect_pairs(
                    [(v, d, t) for v, (d, t) in st.items()], 0.5)
                if abs(st[a][0] - brk) <= 0.5]
        assert want, f"end {ring_idx}: no transect pair leaves the break"
        assert all(frozenset(p) in paired for p in want), f"end {ring_idx}: unpriced"


def test_the_transect_foot_is_the_nearest_pavement_edge_inward():
    """Runway pavement that continues past the end (a paved pad) leads the
    ground behind it: the foot is where the vertex's own line crosses the
    pad's FAR edge — never the end edge itself, never an edge outward."""
    pad_far = ((60.0, -21.0), (60.0, 21.0))
    pad_side = ((0.0, 21.0), (60.0, 21.0))
    end_edge = ((0.0, -20.0), (0.0, 20.0))
    outward = ((90.0, -30.0), (90.0, 30.0))
    edges = [end_edge, pad_side, pad_far, outward]
    k, tau, de = strips.end_transect_foot(61.0, 0.0, edges, 0.5)
    assert (k, de) == (2, 60.0) and tau == pytest.approx(0.5)
    # lateral of the pad: no pavement on its line beyond the end
    assert strips.end_transect_foot(61.0, 48.0, edges, 0.5) is None
    # the end edge alone is the chord's, not a transect foot
    assert strips.end_transect_foot(30.0, 0.0, [end_edge], 0.5) is None


def test_the_readers_frame_is_the_published_slab(icao):
    """``runway_axes`` rows carry each end's overrun; the end frame is the
    apt.dat ends pushed out by them — never a fit to the runway-role rings
    (a shoulder beyond the end would lengthen it)."""
    def to_m(lat, lon):
        return (lon * 1000.0, lat * 1000.0)
    rows = [["09/27", 0.0, 0.0, 0.0, 2.0, 22.5, 60.0, 0.0],
            ["old", 0.0, 0.0, 0.0, 1.0, 15.0]]            # predates the overruns
    slabs = vstrips.published_slabs(rows, to_m)
    assert set(slabs) == {"09/27"}
    a, b, width = slabs["09/27"]
    assert a == pytest.approx((-60.0, 0.0)) and b == pytest.approx((2000.0, 0.0))
    assert width == pytest.approx(45.0)


def test_the_tolerance_is_one_key(icao):
    """#620: ``emit.instrument.strip_edge_noise_m`` is the generator's
    slack (less the rounding envelope a held pair carries, never negative)
    and the readers' forgiveness (never under that rounding) — 0 prices
    the cap exactly."""
    import dataclasses as dc
    from auto_patch_v2.law.tables import end_profile_noise_m
    ins = icao.tables.emit.instrument
    assert end_profile_noise_m(icao) == pytest.approx(
        ins.strip_edge_noise_m - ins.rounding_noise_m)
    assert end_profile_noise_m(icao, reader=True) == pytest.approx(ins.strip_edge_noise_m)
    emit0 = dc.replace(icao.tables.emit, instrument=dc.replace(ins, strip_edge_noise_m=0.0))
    exact = dc.replace(icao, tables=dc.replace(icao.tables, emit=emit0))
    assert end_profile_noise_m(exact) == 0.0
    assert end_profile_noise_m(exact, reader=True) == pytest.approx(ins.rounding_noise_m)


def test_no_two_way_end_row_holds_a_pavement_vertex(synthetic, icao, faa):  # noqa: F811
    """AIRSIDE IS KING: the end profile is the GROUND's.  A two-way row
    (the pair head, the FAA corridor-rate head) never names a pavement
    vertex — a pair with one is one-way under the chord head, the ground
    following; a rate triple with one is not stated (KBFI: an apron edge
    inside an end band moved with the tolerance until this held)."""
    airport, pm = synthetic
    for law_ in (icao, faa):
        vw = view(pm, law_)
        ow = one_way_rulings(law_)
        rows = (strips.end_corridor_longitudinal(pm, law_, airport)
                + strips.end_corridor_rate(pm, law_, airport))
        assert rows
        for r in rows:
            if ruling_head(r) in ow:
                assert r.follows is not None and r.follows not in vw.pavement_vertices
            else:
                assert not {v for v, _c in r.terms} & vw.pavement_vertices


def test_the_end_profile_readers_measure_in_the_engines_metric():
    """THE READERS' FRAME (lane rwyzone15c phase 4, RULINGS 2026-10-15h):
    the end profile's bounds are functions of plan distance, so both
    readers measure it in the engine's transverse-Mercator metric, not the
    census's spherical equirectangular — at CYXY's 60.7 N the latter read
    the engine's 128.34 m chord 0.17 m short and a chord held exactly at
    its bound as a breach.  The rows' points go back to the census frame."""
    import math
    import sys
    from pathlib import Path
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.verify.frame import Patch, metric_frame
    lat0, lon0 = 60.72, -135.07
    a, b = (60.7215, -135.0710), (60.7225, -135.0726)
    to_xy, _ = Frame("", (lat0, lon0), 11).transformers()
    engine = math.dist(to_xy(a[1], a[0]), to_xy(b[1], b[0]))
    fwd, _inv = metric_frame(lat0, lon0)
    assert math.dist(fwd(*a), fwd(*b)) == pytest.approx(engine, abs=1e-6)
    law = Law.load(ruleset="icao")
    p = Patch(law, lat0, lon0, {}, {}, {1: a, 2: b}, (), (), {})
    census = {1: p.to_m(*a), 2: p.to_m(*b)}
    p = Patch(law, lat0, lon0, census, {1: 0.0, 2: 0.0}, {1: a, 2: b}, (), (), {})
    assert abs(math.dist(census[1], census[2]) - engine) > 0.1   # the defect's size
    pm, back = p.in_metric_frame()
    assert math.dist(pm.xy[1], pm.xy[2]) == pytest.approx(engine, abs=1e-6)
    assert back(pm.xy[1]) == census[1] and back(pm.xy[2]) == census[2]
    # the census side: the same metric, and its points back exactly
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import check_grade as cg
    ll_to_m = cg._ll_to_m_factory({}, anchor=(lat0, lon0))
    to_m, to_census = cg._engine_metric(ll_to_m)
    assert math.dist(to_m(*a), to_m(*b)) == pytest.approx(engine, abs=1e-6)
    assert to_census(to_m(*a)) == ll_to_m(*a)
