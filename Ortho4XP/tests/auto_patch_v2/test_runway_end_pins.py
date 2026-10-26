"""THE RUNWAY-END PIN RULE (owner RULINGS 2026-10-25a, 2026-10-26a,
2026-10-26e; issues #1342, #1358, #1394; ``airport/end_pins``,
``constraints/runway_profile.end_pin_cases``; spec
``docs/findings/lrwypin-runway-end-pins.md``).

Synthetic, on the CYXY-shaped one-runway fixture: a 1,200 m runway along
x.  The sites the rule was found at (VNLK, CBR2: placeholder CIFP at the
field elevation; KDIJ: a CIFP threshold 594 m from the apt.dat end; PAAQ:
an apt.dat-only runway under the lidar) are its closing builds, never its
scope (RULINGS 2026-10-05e).
"""
from __future__ import annotations

import dataclasses as _dc
import json
import math
import os
import sys
from pathlib import Path

import pytest
from auto_patch_v2.airport import end_pins as EP
from auto_patch_v2.airport import runway_ref_ourairports as OA
from auto_patch_v2.airport import runway_refs as REFS
from auto_patch_v2.airport.runway_ref_record import REFS_DIR, RefEnd
from auto_patch_v2.constraints import runway_end_report
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.runway_profile import (
    CASE_DATUM,
    CASE_FLAGGED,
    CASE_LIDAR,
    CASE_UNMATCHED,
    _datum_slope_cap,
    end_pin_cases,
    runway_profile,
    threshold_pins,
)
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Pin
from tests.auto_patch_v2.test_v2cyxy import RUN_LEN, _PlaneDem
from tests.auto_patch_v2.test_v2rwycurve import _one_runway

FT = 0.3048


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _Lidar:
    """A credible-lidar sampler: ``z = 700 + slope · x`` with a 1 m pixel."""

    provenance = {"synthetic": "lidar plane"}

    def __init__(self, slope: float):
        self.slope = slope

    def z(self, x: float, y: float) -> float:
        return 700.0 + self.slope * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)

    def source_pixel_m(self):
        return 1.0, "inset"


def _site(law, dem, thresholds, elev=None):
    airport, pm = _one_runway(law, dem, thresholds=thresholds)
    if elev is not None:
        airport = _dc.replace(airport, elevation_m=elev)
    return airport, pm


def _cifp_airport(airport, along=(None, None)):
    """The loader's stamp: every end with a CIFP value is ``cifp``-sourced,
    its pin at ``along`` (``None`` = the apt.dat threshold)."""
    rw = airport.runways[0]
    ends = tuple(_dc.replace(e, pin_along_m=a,
                             pin_source="cifp" if e.threshold_elev_m is not None else "")
                 for e, a in zip(rw.ends, along, strict=True))
    return _dc.replace(airport, runways=(_dc.replace(rw, ends=ends),))


# ── WHERE: the CIFP point projected onto the axis (#1358) ────────────────

def test_cifp_station_projects_onto_the_axis_and_clamps_to_the_runway():
    assert EP.cifp_station((0.0, 0.0), (1000.0, 0.0), (593.5, 4.0)) == pytest.approx(593.5)
    assert EP.cifp_station((0.0, 0.0), (1000.0, 0.0), (-12.0, 1.0)) == 0.0
    assert EP.cifp_station((1000.0, 0.0), (0.0, 0.0), (400.0, -3.0)) == pytest.approx(600.0)


def test_a_cifp_pin_sits_at_its_own_threshold_not_the_apt_dat_end(law):
    """KDIJ's class: the CIFP threshold lies 300 m in from the apt.dat end
    (and apt.dat says no displacement) — the Pin row's vertex is the ridge
    station nearest 300 m in, and the value is the CIFP's."""
    airport, pm = _site(law, _PlaneDem(), (701.2, 704.8))
    airport = _cifp_airport(airport, along=(300.0, None))
    rw = airport.runways[0]
    vw = view(pm, law)
    pins = threshold_pins(pm, law, airport)
    a = rw.ends[0].xy
    d = {round(math.dist(vw.xy[v], a)): z for v, z in pins.items()}
    near = min(d, key=lambda s: abs(s - 300.0))
    assert abs(near - 300.0) < 30.0 and d[near] == 701.2, d
    assert not any(s < 100.0 for s in d), "the pin left the apt.dat end"
    row = [r for r in runway_profile(pm, law, airport)
           if isinstance(r, Pin) and r.z == 701.2]
    assert len(row) == 1 and "CIFP threshold" in row[0].source.ruling


# ── WHETHER: verification and resolution (#1342) ─────────────────────────

def test_placeholder_cifp_at_the_field_elevation_is_flagged_and_follows_the_dem(law):
    """VNLK / CBR2's class: both CIFP ends = the field elevation; the lidar
    climbs 3 % (36 m over the runway).  Rules (a) and (b) fire; no cache,
    so both ends follow the DEM — a 3 % runway, steeper than its cap, and
    NOT clamped to it (the caps yield to hard pins)."""
    airport, pm = _site(law, _Lidar(0.03), (700.0, 700.0), elev=700.0)
    airport, recs, lines = EP.verify(_cifp_airport(airport), law)
    rw = airport.runways[0]
    assert [e.pin_source for e in rw.ends] == ["dem", "dem"]
    assert all(e.threshold_elev_m is None and e.cifp_elev_m == 700.0 for e in rw.ends)
    assert rw.ends[0].pin_flags == "a,b"
    assert len(lines) == 1 and "FLAGGED" in lines[0] and "follow the DEM" in lines[0]
    assert [r["source"] for r in recs] == ["dem", "dem"]
    cases = end_pin_cases(pm, law, airport)
    assert {p.case for p in cases.values()} == {CASE_FLAGGED}
    vw = view(pm, law)
    for v, p in cases.items():
        assert p.z == pytest.approx(_Lidar(0.03).z(*vw.xy[v]), abs=0.3), (v, p)
    zs = sorted(p.z for p in cases.values())
    lim = _datum_slope_cap(law, rw)
    assert (zs[1] - zs[0]) / RUN_LEN > lim             # steeper than the cap: not clamped
    out = runway_end_report.records(pm, law, airport)
    assert {r["source"] for r in out} == {CASE_FLAGGED}
    assert all(r["cifp_m"] == 700.0 and r["flags"] == ["a", "b"] for r in out)
    assert len(runway_end_report.lines("ZZZZ", out)) == 2


def test_cifp_that_agrees_with_the_dem_stays_truth(law):
    """A 0.4 % lidar runway whose CIFP ends carry the same 4.8 m: nothing
    fires, the pins are the CIFP values (09-18d (3) stands)."""
    airport, pm = _site(law, _Lidar(0.004), (697.6, 702.4), elev=702.4)
    airport, recs, lines = EP.verify(_cifp_airport(airport), law)
    assert lines == [] and all(r["flags"] == [] for r in recs)
    assert [e.threshold_elev_m for e in airport.runways[0].ends] == [697.6, 702.4]


def test_a_dem_of_unknown_quality_judges_nothing(law):
    """The authored sampler states no source class: (a) and (b) need a DEM
    of known quality, so a placeholder there stands."""
    airport, pm = _site(law, _PlaneDem(), (700.0, 700.0), elev=700.0)
    _ap, _recs, lines = EP.verify(_cifp_airport(airport), law)
    assert lines == []


def test_a_cross_check_that_fits_the_dem_no_better_leaves_cifp_standing(law):
    """Rule (c) with RULINGS 2026-10-26m (PAAQ 34's class): the source sits
    5 ft under CIFP at both ends — the same grade, so it fits the lidar no
    better than CIFP does.  (c) is recorded; the CIFP pins stand."""
    airport, pm = _site(law, _Lidar(0.004), (697.6, 702.4), elev=702.4)
    refs = [("ourairports", {"09": RefEnd("09", 697.6 - 5 * FT, None, None, 0.0, "ourairports"),
                             "27": RefEnd("27", 702.4 - 5 * FT, None, None, 0.0, "ourairports")})]
    airport, recs, lines = EP.verify(_cifp_airport(airport), law, refs)
    rw = airport.runways[0]
    assert [e.pin_source for e in rw.ends] == ["cifp", "cifp"]
    assert [e.threshold_elev_m for e in rw.ends] == [697.6, 702.4]
    assert rw.ends[0].pin_flags == "c" and "CIFP stands" in lines[0]


def test_a_cross_check_that_fits_the_dem_better_overrides_cifp(law):
    """Rule (c) with RULINGS 2026-10-26m: CIFP's grade is 1.0 m off the
    lidar's (inside (b)'s 1.5 m), the source's is on it — the source's
    values pin the runway, at ITS points (the runway ends)."""
    airport, pm = _site(law, _Lidar(0.004), (697.6, 703.4), elev=703.4)
    refs = [("ourairports", {"09": RefEnd("09", 697.6, None, None, 0.0, "ourairports"),
                             "27": RefEnd("27", 702.4, None, None, 0.0, "ourairports")})]
    airport, recs, lines = EP.verify(_cifp_airport(airport), law, refs)
    rw = airport.runways[0]
    assert [e.pin_source for e in rw.ends] == ["ourairports", "ourairports"]
    assert rw.ends[1].threshold_elev_m == pytest.approx(702.4)
    assert rw.ends[0].pin_along() == 0.0 and rw.ends[0].pin_flags == "c"
    assert "cross-check ourairports" in lines[0] and "take ourairports" in lines[0]
    assert recs[1]["crosscheck"] == {"ourairports": pytest.approx(702.4, abs=1e-3)}


def test_a_cross_check_that_disagrees_with_the_dem_is_not_taken(law):
    """The source is flat where the lidar climbs: CIFP is flagged by (b), the
    source is refused, the DEM decides."""
    airport, pm = _site(law, _Lidar(0.03), (700.0, 700.0), elev=700.0)
    refs = [("ourairports", {"09": RefEnd("09", 700.0, None, None, 0.0, "ourairports"),
                             "27": RefEnd("27", 700.0, None, None, 0.0, "ourairports")})]
    airport, _recs, _lines = EP.verify(_cifp_airport(airport), law, refs)
    assert [e.pin_source for e in airport.runways[0].ends] == ["dem", "dem"]


def test_zero_ft_cifp_is_a_placeholder_whatever_the_dem(law):
    """Rule (d) (owner RULINGS 2026-10-26j): both CIFP ends 0 ft are
    untrusted even over a DEM of unknown quality and a flat runway — the
    ends follow the DEM (no cross-check cached)."""
    airport, pm = _site(law, _PlaneDem(), (0.0, 0.0), elev=702.0)
    airport, recs, lines = EP.verify(_cifp_airport(airport), law)
    rw = airport.runways[0]
    assert [e.pin_source for e in rw.ends] == ["dem", "dem"]
    assert rw.ends[0].pin_flags == "d" and "rule (d)" in lines[0]
    assert {p.case for p in end_pin_cases(pm, law, airport).values()} == {CASE_FLAGGED}


# ── apt.dat-only ends (#1394, 26e) and the unmatched end (22a) ───────────

def test_an_apt_dat_only_end_gives_way_to_the_lidar(law):
    """No CIFP: the datum line puts the high end at the 712.5 m record, 10 m
    over the lidar — both ends follow the lidar, and say so."""
    airport, pm = _site(law, _Lidar(0.004), (None, None), elev=712.5)
    cases = end_pin_cases(pm, law, airport)
    assert {p.case for p in cases.values()} == {CASE_LIDAR}
    vw = view(pm, law)
    for v, p in cases.items():
        assert p.z == pytest.approx(_Lidar(0.004).z(*vw.xy[v]), abs=0.05)
        assert p.datum_z is not None and abs(p.datum_z - p.z) > 0.5
    lines = runway_end_report.lines("ZZZZ", runway_end_report.records(pm, law, airport))
    assert len(lines) == 2 and all("GIVES WAY TO THE LIDAR" in ln for ln in lines)


def test_an_apt_dat_only_end_keeps_its_datum_off_lidar_or_within_noise(law):
    """No lidar (the plain sampler), or a datum within the lidar's noise:
    30z (2)'s datum line stands."""
    airport, pm = _site(law, _PlaneDem(), (None, None), elev=712.5)
    assert {p.case for p in end_pin_cases(pm, law, airport).values()} == {CASE_DATUM}
    top = 700.0 + 0.004 * RUN_LEN / 2
    airport, pm = _site(law, _Lidar(0.004), (None, None), elev=top + 0.2)
    assert {p.case for p in end_pin_cases(pm, law, airport).values()} == {CASE_DATUM}


def test_the_unmatched_end_beside_a_survey_is_unchanged(law):
    """22a: one CIFP pin, the other end follows the DEM (pulled toward the
    pin within the cap) — its case is ``unmatched``."""
    airport, pm = _site(law, _Lidar(0.004), (697.6, None), elev=0.0)
    cases = end_pin_cases(pm, law, airport)
    assert [p.case for p in cases.values()] == [CASE_UNMATCHED]


# ── the cross-check cache: read only, filled only by the harness scope ───

_HEADER = ('"id","airport_ref","airport_ident","length_ft","width_ft","surface",'
           '"lighted","closed","le_ident","le_latitude_deg","le_longitude_deg",'
           '"le_elevation_ft","le_heading_degT","le_displaced_threshold_ft","he_ident",'
           '"he_latitude_deg","he_longitude_deg","he_elevation_ft","he_heading_degT",'
           '"he_displaced_threshold_ft"\n')
_ROWS = ('1,2,"ZZZZ",1772,66,"ASP",1,0,"06",27.68,86.72,9134,60,,"24",27.69,86.73,9334,240,\n'
         '3,4,"ZZZY",3000,75,"ASP",1,0,"09",1,2,100,90,,"27",1,2,,270,\n'
         '5,6,"ZZZZ",900,50,"GRS",0,1,"01",1,2,9000,10,,"19",1,2,9001,190,\n')


def test_the_ourairports_reader_takes_ends_with_an_elevation(tmp_path):
    path = Path(OA.cache_path(str(tmp_path)))
    path.parent.mkdir(parents=True)
    path.write_text(_HEADER + _ROWS, encoding="utf-8", newline="")
    got = OA.lookup("ZZZZ", str(tmp_path))
    assert set(got) == {"06", "24"}                         # the closed runway is not a record
    assert got["06"].elevation_m == pytest.approx(9134 * FT)
    assert set(OA.lookup("ZZZY", str(tmp_path))) == {"09"}  # 27 has no elevation
    got = REFS.lookup("ZZZZ", str(tmp_path), ("nasr", "openaip", "ourairports"))
    assert got[0][0] == "ourairports"
    assert REFS.lookup("ZZZZ", str(tmp_path / "absent"), ("ourairports",)) == []


def test_refresh_writes_the_cache_and_its_stamp_through_the_given_transport(tmp_path):
    body = (_HEADER + _ROWS).encode("utf-8")
    stamp = OA.refresh(str(tmp_path), fetch=lambda url: body)
    assert stamp["bytes"] == len(body) and len(stamp["sha256"]) == 64
    assert "public domain" in stamp["attribution"].lower()
    path = OA.cache_path(str(tmp_path))
    assert Path(path).read_bytes() == body
    with open(os.path.splitext(path)[0] + ".json", encoding="utf-8") as fh:
        assert json.load(fh)["sha256"] == stamp["sha256"]
    with pytest.raises(ValueError):
        OA.refresh(str(tmp_path), fetch=lambda url: b"<html>not a csv</html>")


def test_the_harness_scope_names_the_engine_cache_directory():
    """The guard QUOTES the engine's directory name (it must not import the
    engine); a rename on either side would unmap the scope."""
    root = Path(__file__).resolve().parents[2] / "tools" / "harness"
    sys.path.insert(0, str(root))
    try:
        import shared_repo_guard as G
    finally:
        sys.path.remove(str(root))
    assert G.RUNWAY_REFS_DIR == REFS_DIR
    assert G.scope_of(f"Airport_mod_cache/{REFS_DIR}/ourairports/runways.csv") == "runway_refs"
    assert G.scope_of("Airport_mod_cache/some_pack/index.json") == "airport_mod_cache"
