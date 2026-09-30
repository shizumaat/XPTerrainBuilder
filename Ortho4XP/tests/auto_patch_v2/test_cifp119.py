"""#119 THE CIFP COORDINATE JOIN (lane ``cifp119``).

``airport/load.join_cifp`` joins apt.dat runway ends to CIFP ``RWY:``
records by DESIGNATOR, then — only for an end that matched nothing — by its
landing THRESHOLD within ``[identity] cifp_threshold_join_m``.  KCLT's
Custom Data CIFP renumbered 18R/36L -> 01L/19R and 18C/36C -> 01R/19L; both
runways were built with no pins (the #117 floating-runway mechanism).
"""
from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

import pytest

from auto_patch_v2.airport import cifp as C
from auto_patch_v2.airport.load import Inputs, _vector_to_xy, join_cifp, load_with_report
from auto_patch_v2.law import Law

FIX = Path(__file__).resolve().parent / "fixtures" / "CYXY"


def test_the_join_radius_is_a_law_key():
    tol = Law.for_airport("CYXY").tables.emit.identity.cifp_threshold_join_m
    assert 14.4 * 2 <= tol < 375.0 / 10          # measured band (emit.toml)


def test_match_threshold_joins_refuses_and_misses():
    recs = {"19R": (0.0, 0.0), "01L": (0.0, 3000.0), "19L": (300.0, 0.0)}
    assert C.match_threshold((5.8, 0.0), recs, 30.0)[:2] == ("19R", "joined")
    assert C.match_threshold((0.0, 2994.2), recs, 30.0)[:2] == ("01L", "joined")
    # two records inside the radius: refused, never the nearer by luck
    got, verdict, d = C.match_threshold((0.0, 0.0), {"A": (1.0, 0.0), "B": (0.0, 20.0)}, 30.0)
    assert (got, verdict) == (None, "ambiguous") and d == pytest.approx(1.0)
    # a plain miss stays None
    got, verdict, d = C.match_threshold((1000.0, 1000.0), recs, 30.0)
    assert (got, verdict) == (None, "none") and d > 30.0
    assert C.match_threshold((0.0, 0.0), {}, 30.0) == (None, "none", math.inf)


def _renumbered_cifp(tmp_path: Path, rename: dict[str, str]) -> str:
    """The CYXY fixture's CIFP with runways RENAMED (coordinates kept)."""
    d = tmp_path / "CIFP"
    d.mkdir()
    lines = []
    for raw in (FIX / "CIFP" / "CYXY.dat").read_text(errors="replace").splitlines():
        for old, new in rename.items():
            raw = raw.replace(f"RWY:RW{old:<3s}", f"RWY:RW{new:<3s}")
        lines.append(raw)
    (d / "CYXY.dat").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(d)


def _inputs(cifp_dir: str) -> Inputs:
    return Inputs(xplane_root=str(FIX), cifp_dir=cifp_dir,
                  osm_root=str(FIX / "OSM_data"),
                  elevation_root=str(FIX / "Elevation_data"), dem_frame="authored",
                  mod_cache_root=str(FIX / "Airport_mod_cache"))


def test_a_renumbered_runway_is_joined_by_its_threshold_both_ends(tmp_path):
    """14R/32L renamed 15R/33L in the CIFP: the designators miss, the
    thresholds join — both ends pinned at their own records' elevations,
    every join NAMED on the report; the untouched runways join by name."""
    base, _ = load_with_report("CYXY", _inputs(str(FIX / "CIFP")), Law.for_airport("CYXY"))
    a, rep = load_with_report("CYXY", _inputs(_renumbered_cifp(tmp_path, {"14R": "15R", "32L": "33L"})),
                              Law.for_airport("CYXY"))
    assert rep.cifp_missing_ends == ()
    want = {e.name: e.threshold_elev_m for r in base.runways for e in r.ends}
    got = {e.name: e.threshold_elev_m for r in a.runways for e in r.ends}
    assert got == want
    assert len(rep.cifp_coordinate_joins) == 2
    assert any(" 14R -> 15R joined" in s for s in rep.cifp_coordinate_joins)
    assert any(" 32L -> 33L joined" in s for s in rep.cifp_coordinate_joins)


def test_an_end_with_no_record_near_it_stays_pinless(tmp_path):
    """Delete 14R's record: nothing is within the radius of 14R (the other
    thresholds are >= 375 m away), so it stays unpinned — never borrowed."""
    d = tmp_path / "CIFP"
    d.mkdir()
    keep = [ln for ln in (FIX / "CIFP" / "CYXY.dat").read_text(errors="replace").splitlines()
            if not ln.startswith("RWY:RW14R")]
    (d / "CYXY.dat").write_text("\n".join(keep) + "\n", encoding="utf-8", newline="\n")
    a, rep = load_with_report("CYXY", _inputs(str(d)), Law.for_airport("CYXY"))
    assert rep.cifp_missing_ends == ("14R",)
    assert rep.cifp_coordinate_joins == ()


_XP = Path(os.environ.get("O4_XPLANE_ROOT", "/Users/noah/X-Plane 12"))
_KCLT_CIFP = _XP / "Custom Data" / "CIFP" / "KCLT.dat"


@pytest.mark.skipif(not _KCLT_CIFP.is_file(), reason="needs the X-Plane Custom Data CIFP")
def test_kclt_renumbered_parallels_carry_two_pins_each():
    """THE SITE (#117/#119): with KCLT's own apt.dat and the renumbered
    Custom Data CIFP, 18R/36L and 18C/36C each carry TWO threshold pins."""
    from auto_patch_v2.airport import apt_dat as A, pack as P
    from auto_patch_v2.model.frame import Frame
    law = Law.for_airport("KCLT")
    sel = P.select_pack(str(_XP), "KCLT", law)
    if sel is None:
        pytest.skip("no KCLT apt.dat")
    apt = A.parse_airport_block(A.read_airport_block(sel.apt_dat_path, "KCLT"))
    to_xy = _vector_to_xy(Frame("KCLT", apt.reference_point(), 11))
    recs, missing, joins = join_cifp("KCLT", apt.runways, C.read_cifp_runways(str(_KCLT_CIFP)),
                                     to_xy, law.tables.emit.identity.cifp_threshold_join_m)
    by = {e[0]: recs[(i, k)] for i, rw in enumerate(apt.runways) for k, e in enumerate(rw.ends)}
    for rw in ("18R", "36L", "18C", "36C"):
        assert by[rw] is not None, (rw, missing)
    assert {by[r].designator for r in ("18R", "36L", "18C", "36C")} == {"19R", "01L", "19L", "01R"}
    assert missing == [] and len(joins) == 4
