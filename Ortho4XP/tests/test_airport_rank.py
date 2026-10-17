"""Twin of ``Tests/SceneryKitTests/AirportRankTests.swift`` (#815, #817).

Both read ``fixtures/airport_rank_cases.json``: the size classes, the
largest airports of a tile, a progress row's title codes and the v6 index
cache's size columns, so the Mac and Qt apps cannot rank differently.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Airport_Index as AI  # noqa: E402
import O4_Airport_Rank as RANK  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "fixtures",
                       "airport_rank_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)


def _entry(row):
    return AI.AirportEntry(
        code=row["code"], name="", city="", country="", lat=row["lat"],
        lon=row["lon"],
        extent=tuple(row["extent"]) if row["extent"] else None,
        runway_m=row["runway_m"], size_class=row["size_class"])


@pytest.mark.parametrize("case", CASES["size_class"])
def test_size_class(case):
    assert RANK.size_class(case["category"], case["longest_m"],
                           case["paved_m"]) == case["class"]


def test_largest_by_tile():
    largest = RANK.largest_by_tile([_entry(r) for r in CASES["index"]])
    for case in CASES["largest"]:
        assert largest[tuple(case["tile"])] == case["codes"]
    assert set(largest) == {tuple(c["tile"]) for c in CASES["largest"]}


@pytest.mark.parametrize("case", CASES["titles"])
def test_title_codes(case):
    assert RANK.title_codes(case["largest"], case["searched"]) == case["codes"]


@pytest.mark.parametrize("case", CASES["cache_rows"])
def test_cache_rows_read_their_size(tmp_path, case):
    cache = tmp_path / "index.tsv"
    cache.write_text("O4AIRPORTIDX 6 1\n" + case["row"] + "\n",
                     encoding="utf-8", newline="\n")
    (entry,) = AI.load_index(str(cache))
    want_m = case["runway_m"] if case["runway_m"] is not None else 0
    want_class = (case["size_class"] if case["size_class"] is not None
                  else RANK.UNKNOWN_SIZE_CLASS)
    assert (entry.runway_m, entry.size_class) == (want_m, want_class)
    assert entry.extent is not None


_APT_DAT = """I
1100 Version

1    50 0 0 BIGG Big Field
100 45.0 1 0 0.25 1 3 0 09 30.0000 31.0000 0 0 0 0 0 0 27 30.0000 31.0400 0 0 0 0 0 0
100 30.0 3 0 0.25 1 3 0 18 30.0100 31.0000 0 0 0 0 0 0 36 29.9800 31.0000 0 0 0 0 0 0

1    50 0 0 GRAS Grass Strip
100 30.0 3 0 0.25 1 3 0 09 31.0000 31.0000 0 0 0 0 0 0 27 31.0000 31.0400 0 0 0 0 0 0

16   0 0 0 SEAP Seaplane Base
101 50 0 09 32.0000 31.0000 27 32.0000 31.0200

17   0 0 0 HELI Heliport
102 H1 33.0000 31.0000 0 10 10 1 0 0 0.25 0
"""


def test_build_index_writes_runway_length_and_class(tmp_path):
    apt = tmp_path / "apt.dat"
    apt.write_text(_APT_DAT, encoding="utf-8", newline="\n")
    cache = str(tmp_path / "index.tsv")
    assert AI.build_index([str(apt)], cache) == 4
    by_code = {e.code: e for e in AI.load_index(cache)}
    # 0.04 deg of longitude at 30 N is ~3.85 km of asphalt: major.
    assert 3800 < by_code["BIGG"].runway_m < 3900
    assert by_code["BIGG"].size_class == 0
    # As long, but turf: never above "small".
    assert by_code["GRAS"].size_class == 3
    assert 1800 < by_code["SEAP"].runway_m < 2000
    assert by_code["SEAP"].size_class == 3
    assert (by_code["HELI"].runway_m, by_code["HELI"].size_class) == (0, 4)


def test_rank_key_orders_largest_first():
    keys = [RANK.rank_key("BBBB", 1, 2000), RANK.rank_key("AAAA", 0, 3000),
            RANK.rank_key("CCCC", 1, 2500)]
    assert [k[2] for k in sorted(keys)] == ["AAAA", "CCCC", "BBBB"]
