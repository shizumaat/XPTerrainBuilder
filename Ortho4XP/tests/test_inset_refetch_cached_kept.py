"""#924 -- a failed inset REFETCH that keeps the cached inset is not "no inset".

When re-fetching an airport inset fails but the cached one is kept and
used, the home tile's pass used to say the airport had NO inset twice: a
loud WARNING and the degraded failure code ``inset_fetch_failed``.  The
two cases are now told apart:

* fetch failed, cached inset used -> an INFO line naming the cached inset
  and its age; no warning, no degraded row;
* fetch failed, no inset -> the loud warning and ``inset_fetch_failed``
  (``degraded``), as before.

Either way the pass stays unstamped, so the next build retries the fetch.
No network: the per-airport fetch is faked at its row contract.
"""
import os
import time

import O4_Airport_Elevation_Insets as INSETS
import O4_Tile_Failures as FAIL
import O4_UI_Utils as UI
import O4_Unpatched_Airports as UNPATCHED

from test_inset_fetch_scratch import (WIDER_BOX, _corpus, _inset_dir,
                                      littering_strategy,  # noqa: F401
                                      requires_gdal)
from test_inset_resolution_ladder import BOX

ICAO, CODE = "KASE", "FAKESCR"
KEPT = "KASE_fakescr.tif (cached 2026-09-01, 48 days old)"


class _Tile:
    lat, lon = 39, -107
    airport_elevation_providers = "auto"
    airport_elevation_level = "auto"


def _run_pass(monkeypatch, rows):
    """Run the home pass with a fetch that reports ``rows``; return
    (loud lines, console lines, stamped tiles, the tile)."""
    loud, said, stamped = [], [], []

    def _fake_fetch(lat, lon, boxes, definitions, resolution, **kwargs):
        kwargs["fetch_failures"].extend(rows)

    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda tile: True)
    monkeypatch.setattr(INSETS, "resolved_inset_mode", lambda tile: "ICAO")
    monkeypatch.setattr(INSETS, "inset_keys", lambda dico, mode: {ICAO})
    monkeypatch.setattr(INSETS, "_airport_bounding_boxes",
                        lambda tile, dico, only=None: {ICAO: BOX})
    monkeypatch.setattr(INSETS, "ensure_airport_insets", _fake_fetch)
    monkeypatch.setattr(INSETS, "_write_inset_completion_stamp",
                        lambda tile: stamped.append(tile))
    monkeypatch.setattr(UI, "loud_warning",
                        lambda *args: loud.append(" ".join(map(str, args))))
    monkeypatch.setattr(UI, "vprint",
                        lambda level, *args: said.append(
                            " ".join(map(str, args))))
    tile = _Tile()
    INSETS.ensure_insets_for_tile(tile, {ICAO: {}})
    return loud, said, stamped, tile


def test_a_failed_refetch_with_the_cached_inset_used_is_a_note(monkeypatch):
    loud, said, stamped, tile = _run_pass(
        monkeypatch, [(ICAO, CODE, "server went away", KEPT)])
    assert loud == []                                  # no "NO inset"
    assert UNPATCHED.read_degraded(tile) == []         # no degraded code
    note = [line for line in said if "cached inset" in line]
    assert len(note) == 1
    assert ICAO in note[0] and CODE in note[0] and KEPT in note[0]
    assert "WARNING" not in note[0] and "NO inset" not in note[0]
    assert stamped == []                               # retried next run


def test_a_failed_fetch_with_no_inset_stays_degraded(monkeypatch):
    loud, _said, stamped, tile = _run_pass(
        monkeypatch, [(ICAO, CODE, "server went away")])
    assert len(loud) == 1 and "NO inset" in loud[0]
    rows = UNPATCHED.read_degraded(tile)
    assert [(r["code"], r["airport"]) for r in rows] == [
        ("inset_fetch_failed", ICAO)]
    assert [FAIL.severity_of(r["code"]) for r in rows] == ["degraded"]
    assert stamped == []


def test_the_two_cases_split_within_one_pass(monkeypatch):
    loud, said, _stamped, tile = _run_pass(monkeypatch, [
        (ICAO, CODE, "server went away", KEPT),
        ("KEGE", CODE, "server went away")])
    assert len(loud) == 1 and "KEGE" in loud[0]
    assert [r["airport"] for r in UNPATCHED.read_degraded(tile)] == ["KEGE"]
    assert any(KEPT in line for line in said)


def test_the_note_names_the_cached_inset_and_its_age(tmp_path):
    path = tmp_path / "KASE_fakescr.tif"
    path.write_bytes(b"x")
    stamp = time.time() - 3 * 86400 - 60
    os.utime(path, (stamp, stamp))
    note = INSETS._cached_inset_age_note(str(path))
    assert note.startswith("KASE_fakescr.tif (cached ")
    assert note.endswith(", 3 days old)")
    assert INSETS._cached_inset_age_note(
        str(tmp_path / "gone.tif")) == "gone.tif (age unknown)"


@requires_gdal
def test_the_fetch_rows_tell_kept_from_missing(
        tmp_path, monkeypatch, littering_strategy):  # noqa: F811 (fixture)
    """End to end through the fetch loop: a refetch that fails over a
    cached inset reports the kept inset; a first fetch that fails reports
    a bare (no inset) row."""
    plan, _calls, definition = littering_strategy
    _corpus(tmp_path, monkeypatch)
    plan["raise"] = True
    failures = []
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition], None,
                                 fetch_failures=failures)
    assert failures == [("KASE", "FAKESCR",
                         failures[0][2])]               # 3 elements: none
    assert not os.path.exists(os.path.join(_inset_dir(), "KASE_fakescr.tif"))
    plan["raise"] = False
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition], None)
    plan["raise"] = True
    failures = []
    INSETS.ensure_airport_insets(39, -107, {"KASE": WIDER_BOX}, [definition],
                                 None, fetch_failures=failures)
    assert len(failures) == 1 and len(failures[0]) == 4
    assert failures[0][3].startswith("KASE_fakescr.tif (cached ")
