"""WAVE F BEHAVIOUR WITNESSES (#852; code-quality-beta3-spec §1, the
unused-code plan's wave-F addendum): each v1 reader under ``auto_patch/``
against its ``auto_patch_v2`` counterpart, on committed SYNTHETIC inputs
only (never the corpus).

A pair whose outputs are identical is re-pointed and the v1 copy goes; a
pair whose outputs DIFFER in a way that could change an emitted patch is an
OWNER QUESTION (the #740 wave-E rule), and the twin below that pins the
difference is its witness — when the owner rules, the twin flips with the
re-pointing, never before.
"""
from __future__ import annotations

import pytest

from auto_patch import cifp_reader as V1_CIFP
from auto_patch_v2.airport import cifp as V2_CIFP

from object_stage_support import write_text

# ── cifp_reader <-> airport/cifp ─────────────────────────────────────────
RWY_16L = "RWY:RW16L,+0580,      ,00044, ,IJCH,3,   ;S12002744,W077071686,0000;"
RWY_34R = "RWY:RW34R,+2380,      ,00113, ,IJCZ,1,   ;S12021200,W077064500,0984;"
#: a BELOW-SEA-LEVEL threshold: ARINC 424 signs the elevation field
RWY_18R_BELOW_SEA = ("RWY:RW18R,+1835,      ,-0011, ,ISNA,3,   ;"
                     "N52215800,E004422200,0000;")
#: the malformed rows both readers must skip the same way
SKIPPED = [
    "RWY:XX99,+0000,      ,00010, ,    , ,   ;S12000000,W077000000,0000;",
    "RWY:RW09,+0900,      ,     , ,    , ,   ;S12000000,W077000000,0000;",
    "RWY:RW27,+2700,      ,00010, ,    , ,   ;S12,W077,0000;",
    "RWY:RW01,+0100",
    "APPCH:010,A,I16L ,AER,...",
]


@pytest.mark.parametrize("s", ["S12002744", "N25153000", "n00000001",
                               "S89595999"])
def test_cifp_latitude_parsers_are_identical(s):
    assert V1_CIFP.parse_cifp_lat(s) == V2_CIFP.parse_lat(s)


@pytest.mark.parametrize("s", ["W077071686", "E051361200", "w000000001",
                               "E179595999"])
def test_cifp_longitude_parsers_are_identical(s):
    assert V1_CIFP.parse_cifp_lon(s) == V2_CIFP.parse_lon(s)


def test_cifp_runway_readers_agree_on_unsigned_records(tmp_path):
    """Same records, same numbers; the SHAPE differs (v1 ``{"RW16L":
    {lat, lon, elevation_m, displaced_m}}``, v2 ``{"16L": CifpRunway}``),
    which is an adapter, not a behaviour."""
    path = write_text(tmp_path / "SPJC.dat",
                      "\n".join([RWY_16L, RWY_34R] + SKIPPED) + "\n")
    v1 = V1_CIFP.parse_cifp_file(str(path))
    v2 = V2_CIFP.read_cifp_runways(str(path))
    assert sorted(v1) == ["RW16L", "RW34R"]
    assert {"RW" + k: {"lat": r.lat, "lon": r.lon,
                       "elevation_m": r.elevation_m,
                       "displaced_m": r.displaced_m}
            for k, r in v2.items()} == v1


def test_OWNER_QUESTION_cifp_below_sea_threshold(tmp_path):
    """THE DIFFERENCE THAT STOPS THE PAIR.  v1 ``parse_cifp_file`` requires
    ``elev.isdigit()`` and DROPS a signed (below-sea-level) threshold; v2
    ``read_cifp_runways`` reads it.  v1's reader feeds tile SELECTION
    (``selection.select_patch_airports``: an airport with no parsed runway
    is never patched) and the flat-site S1 consensus that seeds the DEM
    plateau (``flat_site_mode``) — so re-pointing changes emitted output
    at every airport with a below-sea threshold."""
    path = write_text(tmp_path / "BELOW.dat", RWY_18R_BELOW_SEA + "\n")
    assert V1_CIFP.parse_cifp_file(str(path)) == {}
    v2 = V2_CIFP.read_cifp_runways(str(path))
    assert list(v2) == ["18R"]
    assert v2["18R"].elevation_m == pytest.approx(-11 * 0.3048)


def test_OWNER_QUESTION_cifp_unreadable_file(tmp_path):
    """v1 swallows ``OSError`` (``{}`` and a log line); v2 raises it.
    Every v1 caller except ``selection`` already wraps the call; selection
    would turn a vanished CIFP file from "airport skipped" into a failed
    selection."""
    missing = str(tmp_path / "GONE.dat")
    assert V1_CIFP.parse_cifp_file(missing) == {}
    with pytest.raises(OSError):
        V2_CIFP.read_cifp_runways(missing)
