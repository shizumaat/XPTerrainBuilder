"""Twins for the airport code list (issue #542).

The resolve rule runs against the SHARED vectors in
``tests/fixtures/airport_code_list_cases.json`` -- the macOS twin
(``Tests/SceneryKitTests/AirportCodeListTests.swift``) reads the same
file.  The extent half runs against a synthetic apt.dat through
:mod:`O4_Airport_Index` (cache v5).
"""
import json
import os

import pytest

import O4_Airport_Batch as BATCH
import O4_Airport_Index as AI

_CASES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures", "airport_code_list_cases.json")
with open(_CASES_PATH, encoding="utf-8") as _fh:
    CASES = json.load(_fh)


def _index_entries():
    return [
        AI.AirportEntry(row["code"], row["code"], "", "", row["lat"],
                        row["lon"], extent=tuple(row["extent"])
                        if row["extent"] else None)
        for row in CASES["index"]
    ]


@pytest.mark.parametrize("case", CASES["split"], ids=lambda c: c["query"])
def test_split_codes(case):
    assert BATCH.split_codes(case["query"]) == case["codes"]


@pytest.mark.parametrize("case", CASES["tiles"],
                         ids=lambda c: "%s,%s" % (c["lat"], c["lon"]))
def test_airport_tiles(case):
    tiles = BATCH.airport_tiles(case["lat"], case["lon"], case["extent"])
    assert sorted(tiles) == [tuple(t) for t in case["tiles"]]


@pytest.mark.parametrize("case", CASES["resolve"], ids=lambda c: c["query"])
def test_resolve_codes(case):
    batch = BATCH.resolve_codes(case["query"],
                                BATCH.code_lookup(_index_entries()))
    want = case["batch"]
    if want is None:
        assert batch is None
        return
    assert batch is not None
    assert batch.codes == want["codes"]
    assert batch.unknown == want["unknown"]
    assert batch.tiles == [tuple(t) for t in want["tiles"]]


def test_alert_message_only_when_a_code_is_unknown():
    lookup = BATCH.code_lookup(_index_entries())
    assert BATCH.unknown_codes_message(
        BATCH.resolve_codes("KCLT, OTHH", lookup)) is None
    assert BATCH.unknown_codes_message(
        BATCH.resolve_codes("KCLT, kzzz", lookup)) == (
        "Not identified: KZZZ. The tiles of KCLT are selected.")
    assert BATCH.unknown_codes_message(
        BATCH.resolve_codes("KZZZ, QQQQ", lookup)) == (
        "Not identified: KZZZ, QQQQ. No tiles were selected.")


def test_lookup_is_case_blind_and_first_entry_wins():
    entries = [AI.AirportEntry("kclt", "a", "", "", 35.2, -80.9),
               AI.AirportEntry("KCLT", "b", "", "", 10.5, 10.5)]
    assert BATCH.code_lookup(entries)("Kclt") == [(35, -81)]


# ---------------------------------------------------------------------------
# Cache v5: the extent that makes an airport select every tile it touches
# ---------------------------------------------------------------------------
# EDGE straddles 48N / 9E: datum in 47/8, boundary reaching into 48/9.
# RWYS has no boundary; its runway's far end crosses into 48/8.
# A taxiway (110) and a marking line (120) never grow the extent.
_APT_DAT = """I
1000 Generated

1    100 0 0 XXXX Edge Field
1302 icao_code EDGE
1302 datum_lat 47.95
1302 datum_lon 8.95
110 1 0.25 0.0 Taxiway far away
111 40.0 1.0
113 40.1 1.1
130 Airport Boundary
111 47.90 8.90
111 48.02 8.90
112 48.02 9.01 48.03 9.02
113 47.90 9.01
120 Line far away
111 30.0 2.0
115 30.1 2.1

1    50 0 0 RWYS Runway Only
100 30.0 1 0 0.25 1 3 0 09 47.9900 7.5000 0 0 0 0 0 0 27 48.0100 7.5100 0 0 0 0 0 0
"""


def test_index_v5_records_the_extent(tmp_path):
    apt = tmp_path / "apt.dat"
    apt.write_text(_APT_DAT, encoding="utf-8", newline="\n")
    cache = str(tmp_path / "index.tsv")
    assert AI.build_index([str(apt)], cache) == 2
    with open(cache, encoding="utf-8") as fh:
        assert fh.readline().split()[:2] == ["O4AIRPORTIDX", "5"]
    by_code = {e.code: e for e in AI.load_index(cache)}

    edge = by_code["EDGE"]
    assert edge.extent == pytest.approx((47.90, 8.90, 48.02, 9.01))
    assert sorted(BATCH.airport_tiles(edge.lat, edge.lon, edge.extent)) == [
        (47, 8), (47, 9), (48, 8), (48, 9)]

    rwys = by_code["RWYS"]
    assert rwys.extent == pytest.approx((47.99, 7.50, 48.01, 7.51))
    assert BATCH.resolve_codes("edge, rwys", BATCH.code_lookup(
        by_code.values())).tiles == [(47, 7), (47, 8), (47, 9), (48, 7),
                                     (48, 8), (48, 9)]


def test_pre_v5_rows_load_without_extent(tmp_path):
    cache = tmp_path / "v4.tsv"
    cache.write_text("O4AIRPORTIDX 4 1\nKCLT\tCharlotte\t\t\t35.2\t-80.9"
                     "\ticao_airport\n", encoding="utf-8", newline="\n")
    (entry,) = AI.load_index(str(cache))
    assert entry.extent is None
    assert AI.index_is_stale([], str(cache))
