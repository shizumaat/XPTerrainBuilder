"""§50 THE RUNWAY CAP YIELDS TO ITS PINS, UNIFORMLY (owner RULINGS
2026-09-18d (3), answered 2026-09-18f; spec ``docs/specs/auto-patch-v2/
design-surface-spec.md`` §50; lane ``tffjcap``, founded on ``tffjverify``
and ``docs/findings/tffj-verify-20260918.md``).

The twins of §50.6's test plan, headless and tmp_path-only:

* T1  a two-pin OVER-GRADE runway (600 m code 1, thresholds 13.2 m apart
      = 2.2 % against a 2.0 % table): ``derive`` yields, every profile
      ``Diff`` carries the effective cap, the projection is feasible with
      NO elastic row, and the DEFECT families read 0;
* T2  the SAME runway at 1.0 %: not yielded, the law inert — the rows are
      byte-identical to a build with ``pm.runway_caps`` emptied;
* T3  the table is code-aware (Annex 14 §3.1.13), and the FAA table does
      NOT move (18f (3) has no FAA counterpart);
* T3b the CODE-4 twin: 2,400 m, pins under 1.25 % (not yielded, priced at
      1.25 %) and pins at 1.40 % (YIELDED where the old table read
      lawful) — the TIGHTENING direction of Y20;
* T4  THREE pins (a §17 crossing anchor mid-runway): ONE cap for the
      runway, the steeper span's, and the record names that span;
* T5  the CEILING never re-imposes what the pins refuse (§50.1 (6));
* T6  the projection REFUSES a surface worse than the one it was given
      (§50.3), with the yield disabled;
* T7  the sidecar round trip: ``runway_caps`` published for every runway,
      read back by ``law_context_from_sidecar``, and the census prices the
      ring pairs of a 2.2 % runway at the PUBLISHED cap.

T8 (the ruled-deviation register) lives with the table it guards, in
``test_law_tables.py`` — the ``icao.runway.longitudinal`` entry is DELETED
there because the table now equals v1's own Annex 14 values.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints import roads
from auto_patch_v2.constraints.ceiling import pavement_ceiling
from auto_patch_v2.constraints.precedence import cap_of, view
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.runway_profile import ridge_chains, runway_profile
from auto_patch_v2.constraints.runway_yield import (KIND_CROSSING,
                                                    KIND_THRESHOLD, derive,
                                                    yielded_lines)
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import design as design_law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import DEFECT_KEYS

ROOT = Path(__file__).resolve().parents[2]

#: the DEFECT families §50 is accepted on — none of them reads the
#: longitudinal cap, which is the point (§50.2 Y19)
RUNWAY_DEFECTS = ("runway_vertical_curve", "runway_transverse", "runway_step")


class _Flat:
    """Flat terrain: the fixture reads the PINS, never the ground."""

    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _one_runway(law, *, length_m=600.0, drop_m=13.2, code=1, letter="A",
                width_m=30.0):
    """ONE straight runway, two CIFP thresholds ``drop_m`` apart over
    ``length_m`` — §50's minimal shape (TFFJ 10/28's, scaled)."""
    half = length_m / 2.0
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("10", (-half, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("28", (half, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0 + drop_m, "fixture"))
    rw = Runway("10/28", width_m, 1, ends, code, letter)
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, _Flat(),
                      law.ruleset_key)
    cells = (Cell(0, "runway", "10/28",
                  _rect(-half, -width_m / 2, half, width_m / 2), (), code,
                  letter, "airside", "runway", {}),)
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    return airport, pm


def _solved(law, airport, pm):
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return pm, cs, sol, rep


def _ridge_in_order(pm, law, ref="10/28"):
    vw = view(pm, law)
    ch = [v for c in ridge_chains(vw).get(ref, []) for v in c]
    return sorted(set(ch), key=lambda v: vw.xy[v][0])


# ── T1 THE SYNTHETIC TWIN ────────────────────────────────────────────

@pytest.fixture(scope="module")
def over(law):
    return _one_runway(law)


def test_t1_a_two_pin_over_grade_runway_yields_and_reads_zero(over, law):
    """The whole §50 mechanism on one runway: the pins demand 2.2 %, the
    table allows 2.0 %, the cap yields to 2.22 %, the projection is
    FEASIBLE with no elastic row, and every DEFECT family reads 0."""
    airport, pm0 = over
    caps = derive(pm0, law, airport)
    rc = caps["10/28"]
    assert rc.cap_law == 0.020                      # ICAO code 1 (18f (1))
    assert rc.g_pin == pytest.approx(0.022, abs=1e-6)
    assert rc.cap == pytest.approx(0.0222, abs=1e-9)
    assert rc.yielded and rc.span_m == pytest.approx(600.0, abs=0.5)
    assert rc.pin_a.kind == rc.pin_b.kind == KIND_THRESHOLD
    assert {rc.pin_a.name, rc.pin_b.name} == {"RWY 10", "RWY 28"}

    # the map carries it, and ``cap_of`` answers through it
    pm, cs, sol, rep = _solved(law, airport, pm0)
    assert pm.runway_caps["10/28"].cap == rc.cap
    assert cap_of(pm, law, "10/28", 1, "A") == pytest.approx(rc.cap)

    # EVERY profile Diff carries the effective cap, not the table's
    prof = [r for r in runway_profile(pm, law, airport)
            if isinstance(r, Diff) and r.soft is None]
    assert prof and all(r.cap == pytest.approx(rc.cap) for r in prof)

    # the projection: feasible, no elastic arm, no refusal
    pr = rep.runway_projection
    assert pr.elastic_rows == 0, pr.line()
    assert pr.status.startswith("optimal") or "held by the solve" in pr.status
    assert pr.after_m <= design_law(law).hard_tol_m + 1e-9, pr.line()

    # the DEFECT families read 0, and so does within_shape on the runway
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))
    for fam in RUNWAY_DEFECTS:
        assert rows.get(fam) == [], (fam, rows.get(fam))
    assert rows.get("within_shape") == [], rows.get("within_shape")
    assert all(rows.get(k) == [] for k in DEFECT_KEYS), \
        {k: len(rows.get(k) or []) for k in DEFECT_KEYS if rows.get(k)}

    # the BUILT ridge runs at the yielded grade, uniformly, between the pins
    z = np.asarray(sol.z, float)
    vw = view(pm, law)
    ridge = _ridge_in_order(pm, law)
    for a, b in zip(ridge, ridge[1:]):
        d = vw.dist(a, b)
        if d <= 0.0:
            continue
        g = abs(float(z[b]) - float(z[a])) / d
        assert g <= rc.cap + 1e-4, (g, rc.cap)          # G1: 0.01 pp
    # ... and it really does climb the 13.2 m the thresholds demand
    assert float(z[ridge[-1]]) - float(z[ridge[0]]) == pytest.approx(13.2, abs=0.05)


def test_t1b_the_line_names_the_pins_the_grade_and_the_cap(over, law):
    """§50.4: ONE loud line per over-grade runway — the pin-to-pin grade,
    the two pins BY KIND, and the cap it exceeded."""
    airport, pm0 = over
    pm = with_runway_chord(pm0, law, airport)
    lines = yielded_lines("ZZZZ", pm.runway_caps, law.ruleset.authority)
    assert len(lines) == 1
    ln = lines[0]
    assert "RUNWAY OVER GRADE 10/28" in ln
    assert "2.200 %" in ln and "2.000 %" in ln and "2.220 %" in ln
    assert "ICAO code 1" in ln and "CIFP" in ln
    assert "RWY 10 700.000 m -> RWY 28 713.200 m" in ln


# ── T2 THE LAW IS INERT WHERE IT IS NOT NEEDED ───────────────────────

def test_t2_a_runway_whose_pins_fit_never_yields_and_prices_identically(law):
    """At 1.0 % the pins fit under the table: ``cap == cap_law``, no line,
    and the rows are IDENTICAL to a build with ``runway_caps`` emptied."""
    airport, pm0 = _one_runway(law, drop_m=6.0)      # 1.0 % over 600 m
    rc = derive(pm0, law, airport)["10/28"]
    assert rc.g_pin == pytest.approx(0.010, abs=1e-6)
    assert not rc.yielded and rc.cap == rc.cap_law == 0.020
    pm = with_runway_chord(pm0, law, airport)
    assert yielded_lines("ZZZZ", pm.runway_caps, law.ruleset.authority) == []

    def _key(rows):
        return sorted((type(r).__name__, getattr(r, "cap", None),
                       round(getattr(r, "d", 0.0), 6), r.source.ruling)
                      for r in rows)

    bare = _dc.replace(pm, runway_caps={})
    assert _key(runway_profile(pm, law, airport)) == \
        _key(runway_profile(bare, law, airport))


# ── T3 / T3b THE TABLE IS CODE-AWARE ─────────────────────────────────

def test_t3_the_icao_table_is_annex_14_and_the_faa_table_does_not_move(law):
    """§50.1 (1)/(2), owner RULINGS 2026-09-18f (1)/(3)."""
    for code, want in ((1, 0.020), (2, 0.020), (3, 0.015), (4, 0.0125)):
        assert role_cap(law, "runway", code_number=code).longitudinal == want
    # an UNKNOWN code (a fixture, a twin) answers the default, which STAYS
    # 1.5 % — decided in §50.1 (2), never read in production
    assert role_cap(law, "runway").longitudinal == 0.015
    faa = Law.for_airport("KZZZ")
    assert faa.ruleset_key == "faa"
    for letter, want in (("A", 0.020), ("B", 0.020), ("C", 0.015),
                         ("D", 0.015), ("E", 0.015), ("F", 0.015)):
        assert role_cap(faa, "runway", code_letter=letter).longitudinal == want


def test_t3b_a_code_4_runway_is_priced_at_1_25_percent_and_yields_above_it(law):
    """18f (3), the TIGHTENING direction: at 2,400 m the runway is code 4.
    Pins at 1.0 % do not yield and are priced at 1.25 %; pins at 1.40 % —
    LAWFUL under the old flat 1.5 % table — now YIELD and print the
    line."""
    airport, pm = _one_runway(law, length_m=2400.0, drop_m=24.0, code=4,
                              letter="E", width_m=45.0)
    rc = derive(pm, law, airport)["10/28"]
    assert rc.cap_law == 0.0125 and not rc.yielded
    assert rc.cap == 0.0125 and rc.g_pin == pytest.approx(0.010, abs=1e-6)
    rows4 = [r for r in runway_profile(with_runway_chord(pm, law, airport),
                                       law, airport) if isinstance(r, Diff)]
    body = [r for r in rows4 if r.soft is None]
    assert body and all(r.cap == pytest.approx(0.0125) for r in body)
    # §50.2 Y2, the 18f (3) consequence: the END-ZONE preference escalates
    # up to the MAIN cap, which for code 4 is now 1.25 % (was 1.5 %)
    ends = [r for r in rows4 if r.soft is not None]
    assert ends and all(r.cap == pytest.approx(0.008) for r in ends)
    assert all(r.ceiling == pytest.approx(0.0125) for r in ends)

    airport4, pm4 = _one_runway(law, length_m=2400.0, drop_m=33.6, code=4,
                                letter="E", width_m=45.0)     # 1.40 %
    rc4 = derive(pm4, law, airport4)["10/28"]
    assert rc4.yielded and rc4.cap_law == 0.0125
    assert rc4.g_pin == pytest.approx(0.014, abs=1e-6)
    assert rc4.cap == pytest.approx(0.0142, abs=1e-9)
    ln = yielded_lines("ZZZZ", {"10/28": rc4}, law.ruleset.authority)[0]
    assert "1.250 % (ICAO code 4)" in ln and "1.420 %" in ln
    # the published record carries both numbers for the census (Y20)
    rec = rc4.as_dict(law.ruleset_key)
    assert (rec["cap_law"], rec["cap"]) == (0.0125, rc4.cap)
    assert rec["ruleset"] == "icao" and rec["yielded"] is True


# ── T4 THREE PINS, ONE CAP ───────────────────────────────────────────

def test_t4_three_pins_take_one_cap_and_the_record_names_the_span(law):
    """§50.1 (5) UNIFORM PER RUNWAY: with a §17 crossing anchor mid-runway
    the cap is the STEEPEST span's grade plus the margin — one cap for the
    whole runway — and the record names that span's two pins."""
    from tests.auto_patch_v2.test_v2cyxy import _PlaneDem, _crossing_airport
    airport, _r, cells = _crossing_airport(law, _PlaneDem(),
                                           primary=(700.0, 715.0))
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    caps = derive(pm, law, airport)
    rc = caps["09/27"]
    # 700 -> node 701 over 600 m (0.17 %), node 701 -> 715 over 600 m
    # (2.33 %): ONE cap, the steeper span's
    assert rc.cap_law == 0.015 and rc.yielded
    assert rc.g_pin == pytest.approx(14.0 / 600.0, abs=2e-4)
    assert rc.cap == pytest.approx(rc.g_pin + 0.0002, abs=1e-9)
    kinds = {rc.pin_a.kind, rc.pin_b.kind}
    assert kinds == {KIND_CROSSING, KIND_THRESHOLD}, kinds
    assert rc.span_m == pytest.approx(600.0, abs=25.0)
    # the GOVERNING runway (whose threshold is nearer the node) is flat
    assert not caps["18/36"].yielded
    ln = yielded_lines("ZZZZ", {"09/27": rc}, law.ruleset.authority)[0]
    assert "crossing anchor of 09/27+18/36" in ln


# ── T5 THE CEILING ───────────────────────────────────────────────────

def test_t5_the_pavement_ceiling_never_re_imposes_what_the_pins_refuse(law):
    """§50.1 (6): at 6 % pin to pin the effective cap exceeds
    ``common.pavement_max_grade`` 5 %, and the ceiling's twin of a profile
    row takes the ROW'S OWN cap — so the problem stays feasible."""
    airport, pm0 = _one_runway(law, drop_m=36.0)      # 6.0 % over 600 m
    rc = derive(pm0, law, airport)["10/28"]
    assert rc.cap == pytest.approx(0.0602, abs=1e-9) and rc.yielded
    ceil = float(law.tables.common.pavement_max_grade)
    assert rc.cap > ceil
    pm, cs, sol, rep = _solved(law, airport, pm0)
    # the twin is stated over PAVEMENT RING pairs (the ridge is interior),
    # so §50.1 (6) is read at its own site on a row carrying the yielded
    # cap: a row the law prices ABOVE the ceiling keeps its own cap.
    edge = [v for v in pm.vertices
            if abs(abs(pm.vertices[v].xy[1]) - 15.0) < 0.01]
    a, b = sorted(edge, key=lambda v: pm.vertices[v].xy[0])[:2]
    src = Source("runway_profile", "rulesets.runway.longitudinal",
                 ("rwy:10/28",))
    d = math.dist(pm.vertices[a].xy, pm.vertices[b].xy)
    assert 0.0 < d <= float(law.tables.emit.within_shape.withdrawn_chord_min_m)
    twins = pavement_ceiling([Diff(a, b, rc.cap, d, src)], pm, law)
    assert len(twins) == 1
    assert twins[0].cap == pytest.approx(rc.cap)   # never below its own cap
    lawful = pavement_ceiling([Diff(a, b, 0.001, d, src)], pm, law)
    assert lawful[0].cap == pytest.approx(ceil)    # every other row: the 5 %
    assert rep.runway_projection.elastic_rows == 0, rep.runway_projection.line()


# ── T6 THE PROJECTION'S CONTRACT ─────────────────────────────────────

def test_t6_the_projection_refuses_a_worse_surface_than_it_was_given(
        law, monkeypatch):
    """§50.3, the arm §50.1 removes at its root: with the YIELD DISABLED
    the TFFJ class returns — the cap is enforced exactly between pins that
    demand more, the elastic arm withdraws the pin-footed rows and the
    projection would return a WORSE worst hard row.  It must refuse and
    keep the design surface."""
    import auto_patch_v2.constraints.runway_yield as ry
    monkeypatch.setattr(ry, "derive", lambda pm, law, airport: {})
    airport, pm0 = _one_runway(law, drop_m=13.2)
    pm = with_runway_chord(pm0, law, airport)
    assert not pm.runway_caps                       # the yield is disabled
    cs, _c, _w = generate(pm, law, airport)
    _sol, rep = solve_design(pm, cs, law)
    pr = rep.runway_projection
    assert pr.status.startswith("refused"), pr.line()
    assert pr.elastic_rows > 0              # the arm that withdrew the rows
    assert not pr.ran and pr.after_m == pr.before_m
    assert pr.max_move_m == 0.0             # the DESIGN vector came back
    assert pr.after_m <= pr.before_m + design_law(law).hard_tol_m + 1e-9, \
        pr.line()
    # the OTHER arm of §50.3 — the 4 m ridge-kink fixture, where the
    # elastic arm IMPROVES the surface and the guard stays silent — is
    # ``tests/auto_patch_v2/test_v2settle.py``'s own twin, run beside this
    # file (§50.6: each touched twin run ONCE).


# ── T7 THE SIDECAR ROUND TRIP ────────────────────────────────────────

def test_t7_the_sidecar_carries_the_cap_and_the_census_prices_at_it(
        over, law, tmp_path):
    """§50.1 (4) / Y20-Y21: ``runway_caps`` is published for EVERY runway,
    ``law_context_from_sidecar`` returns it, and the census prices the
    2.2 % runway's ring pairs at the PUBLISHED cap — counted, never
    hidden, in ``_RUNWAY_CAP_STATS``."""
    airport, pm0 = over
    pm, cs, sol, _rep = _solved(law, airport, pm0)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    recs = pub["runway_caps"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec["ref"] == "10/28" and rec["ruleset"] == "icao"
    assert rec["code_number"] == 1 and rec["cap_law"] == 0.020
    assert rec["cap"] == pytest.approx(0.0222) and rec["yielded"] is True
    assert [p["kind"] for p in rec["pins"]] == ["threshold", "threshold"]
    assert all("ll" in p for p in rec["pins"])

    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    ctx = cg.law_context_from_sidecar(paths.patch)
    assert cg.SIDECAR_LAW_KEYS["runway_caps"] == "runway_caps"
    assert ctx["runway_caps"] and ctx["runway_caps"][0]["ref"] == "10/28"

    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    st = dict(cg._RUNWAY_CAP_STATS)
    assert st["ways"] >= 1, st
    assert st["pairs"] >= 1 and st["looser"] == st["pairs"], st
    # and with the published cap in hand the ring pairs are LAWFUL
    assert fam.get("within_shape") == [], fam.get("within_shape")
