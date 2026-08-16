"""Unit tests for :mod:`O4_Airport_Index`.

All tests are self-contained: a synthetic ``apt.dat`` fixture string is
written into ``tmp_path`` so nothing depends on a real X-Plane install or
the network.  The module is imported directly -- ``tests/conftest.py``
already inserts the project ``src/`` directory onto ``sys.path``.
"""
import os
import sys

import pytest

# conftest.py adds ../src to sys.path; keep an explicit fallback so this
# module also imports when run in isolation.
_SRC = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import O4_Airport_Index as AI  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------
# AAAA -- full 1302 metadata incl. icao_code override, city, country, datum.
# BBBB -- no metadata; reference coords come from a land runway (100).
# HHHH -- heliport (row code 17) with a helipad (102) fallback.
# SSSS -- seaplane base (row code 16) with ONLY a water runway (101); the
#         101 fallback (cache v4) is what makes it indexable at all.
# NNNN -- land airport with no coordinate row at all; must be skipped.
_APT_DAT_1 = """I
1000 Generter apt.dat

1    100 0 0 XXXX Header Should Be Overridden
1302 icao_code AAAA
1302 city Testville
1302 country Testland
1302 datum_lat 48.5
1302 datum_lon -6.25
100 45.0 1 0 0.25 1 3 0 01 48.4999 -6.2501 0 0 0 0 0 0 19 48.5100 -6.2400 0 0 0 0 0 0

1    50 0 0 BBBB Runway Fallback Field
100 30.0 1 0 0.25 1 3 0 09 12.5000 77.7000 0 0 0 0 0 0 27 12.5100 77.7100 0 0 0 0 0 0

17   20 0 0 HHHH Heliport Fallback
102 H1 51.5000 -0.1000 0 20 20 1 0 0 0.5

16   0 0 0 SSSS Seaplane No Land Runway
101 60 1 07 59.0000 10.0000 25 58.9000 10.1000

1    10 0 0 NNNN No Coordinates Here
1302 city Nowhere
"""

# Second file: AAAA duplicated (different name) to prove first-file-wins,
# plus a unique airport CCCC.
_APT_DAT_2 = """I
1000 Generter apt.dat

1    100 0 0 XXXX Duplicate Should Lose
1302 icao_code AAAA
1302 datum_lat 10.0
1302 datum_lon 10.0

1    5 0 0 CCCC Second File Only
1302 datum_lat -33.9000
1302 datum_lon 151.2000
"""


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return str(path)


@pytest.fixture()
def apt1(tmp_path):
    return _write(tmp_path / "apt1.dat", _APT_DAT_1)


@pytest.fixture()
def apt2(tmp_path):
    return _write(tmp_path / "apt2.dat", _APT_DAT_2)


# ---------------------------------------------------------------------------
# find_apt_dats
# ---------------------------------------------------------------------------
def test_find_apt_dats_empty(tmp_path):
    assert AI.find_apt_dats(str(tmp_path)) == []


def test_find_apt_dats_priority_order(tmp_path):
    xp12 = tmp_path / "Global Scenery" / "Global Airports" / "Earth nav data"
    xp11 = tmp_path / "Custom Scenery" / "Global Airports" / "Earth nav data"
    os.makedirs(xp12)
    os.makedirs(xp11)
    p12 = _write(xp12 / "apt.dat", "I\n")
    p11 = _write(xp11 / "apt.dat", "I\n")
    found = AI.find_apt_dats(str(tmp_path))
    assert found == [p12, p11]


def test_find_apt_dats_only_xp11(tmp_path):
    xp11 = tmp_path / "Custom Scenery" / "Global Airports" / "Earth nav data"
    os.makedirs(xp11)
    p11 = _write(xp11 / "apt.dat", "I\n")
    assert AI.find_apt_dats(str(tmp_path)) == [p11]


def test_find_apt_dats_shipped_default_is_the_last_candidate(tmp_path):
    # The airports X-Plane itself ships: found when nothing else is, and
    # ranked behind BOTH Global Airports locations when they exist.
    shipped_dir = (tmp_path / "Resources" / "default scenery"
                   / "default apt dat" / "Earth nav data")
    os.makedirs(shipped_dir)
    shipped = _write(shipped_dir / "apt.dat", "I\n")
    assert AI.find_apt_dats(str(tmp_path)) == [shipped]

    xp11_dir = tmp_path / "Custom Scenery" / "Global Airports" / "Earth nav data"
    os.makedirs(xp11_dir)
    xp11 = _write(xp11_dir / "apt.dat", "I\n")
    assert AI.find_apt_dats(str(tmp_path)) == [xp11, shipped]

    xp12_dir = tmp_path / "Global Scenery" / "Global Airports" / "Earth nav data"
    os.makedirs(xp12_dir)
    xp12 = _write(xp12_dir / "apt.dat", "I\n")
    assert AI.find_apt_dats(str(tmp_path)) == [xp12, xp11, shipped]


def test_find_apt_dats_alternate_nav_data_spelling(tmp_path):
    # "Earth Nav Data" is the other spelling in the wild; on a
    # case-sensitive filesystem it is the ONLY name that exists.  The file
    # must be FOUND -- which spelling comes back is the filesystem's
    # business (a case-insensitive volume answers the first one tried).
    xp12 = tmp_path / "Global Scenery" / "Global Airports" / "Earth Nav Data"
    os.makedirs(xp12)
    p12 = _write(xp12 / "apt.dat", "I\n")
    (found,) = AI.find_apt_dats(str(tmp_path))
    assert os.path.isfile(found)
    assert os.path.samefile(found, p12)


def test_find_apt_dats_never_returns_the_same_file_twice(tmp_path):
    # Both spellings of one candidate's nav-data folder: exactly one path
    # comes back (a duplicate would stream the same 380 MB file twice in
    # build_index).  This also covers a case-insensitive volume, where
    # both spellings answer for the SAME file.
    base = tmp_path / "Global Scenery" / "Global Airports"
    os.makedirs(base / "Earth nav data")
    lower = _write(base / "Earth nav data" / "apt.dat", "I\n")
    upper_dir = base / "Earth Nav Data"
    if not os.path.isdir(upper_dir):        # case-sensitive volume
        os.makedirs(upper_dir)
        _write(upper_dir / "apt.dat", "I\n")
    found = AI.find_apt_dats(str(tmp_path))
    assert found == [lower]
    assert len(found) == len({os.path.realpath(p) for p in found})


# ---------------------------------------------------------------------------
# build_index / load_index round-trip
# ---------------------------------------------------------------------------
def test_build_index_count_and_skips(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    count = AI.build_index([apt1], cache)
    # AAAA + BBBB + HHHH + SSSS indexed; only NNNN (no coordinate row of
    # any kind) is skipped -> 4.
    assert count == 4
    assert os.path.isfile(cache)
    codes = {e.code for e in AI.load_index(cache)}
    assert codes == {"AAAA", "BBBB", "HHHH", "SSSS"}
    assert "SSSS" in codes      # water runway (101) is a position too
    assert "NNNN" not in codes  # no coordinate row


def test_cache_header_line(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    with open(cache, encoding="utf-8") as fh:
        header = fh.readline().strip()
    # Cache format v4: the version integer is now 4.
    assert header == "O4AIRPORTIDX 4 4"


def test_field_integrity_roundtrip(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    by_code = {e.code: e for e in AI.load_index(cache)}

    a = by_code["AAAA"]
    # icao_code metadata overrides the header ID "XXXX".
    assert a.code == "AAAA"
    assert a.name == "Header Should Be Overridden"
    assert a.city == "Testville"
    assert a.country == "Testland"
    assert a.lat == pytest.approx(48.5)
    assert a.lon == pytest.approx(-6.25)

    b = by_code["BBBB"]
    assert b.city == ""
    assert b.country == ""
    # Falls back to runway-100 end-1 coords (fields 9,10).
    assert b.lat == pytest.approx(12.5000)
    assert b.lon == pytest.approx(77.7000)

    h = by_code["HHHH"]
    # Helipad-102 fallback (fields 2,3).
    assert h.lat == pytest.approx(51.5000)
    assert h.lon == pytest.approx(-0.1000)

    s = by_code["SSSS"]
    # Water-runway-101 fallback (fields 4,5).
    assert s.lat == pytest.approx(59.0000)
    assert s.lon == pytest.approx(10.0000)

    # v3 category column: icao_code metadata makes AAAA an icao_airport,
    # BBBB (no metadata) a plain airport, header code 17 a heliport and
    # header code 16 a seaplane base.
    assert a.category == "icao_airport"
    assert b.category == "airport"
    assert h.category == "heliport"
    assert s.category == "seaplane_base"


def test_load_missing_cache(tmp_path):
    assert AI.load_index(str(tmp_path / "nope.tsv")) == []


def test_atomic_write_leaves_no_tmp(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    assert not os.path.isfile(cache + ".tmp")


# ---------------------------------------------------------------------------
# Duplicate handling across files (first file wins)
# ---------------------------------------------------------------------------
def test_duplicate_first_file_wins(apt1, apt2, tmp_path):
    cache = str(tmp_path / "index.tsv")
    count = AI.build_index([apt1, apt2], cache)
    by_code = {e.code: e for e in AI.load_index(cache)}
    # AAAA appears in both; the apt1 version (datum 48.5/-6.25) must win.
    assert by_code["AAAA"].lat == pytest.approx(48.5)
    assert by_code["AAAA"].name == "Header Should Be Overridden"
    # CCCC is unique to apt2.
    assert "CCCC" in by_code
    assert by_code["CCCC"].lat == pytest.approx(-33.9)
    # 4 from apt1 + 1 new from apt2 (AAAA duplicate not recounted).
    assert count == 5


# ---------------------------------------------------------------------------
# search ranking
# ---------------------------------------------------------------------------
def _entries():
    return [
        AI.AirportEntry("KJFK", "John F Kennedy Intl", "New York",
                        "United States", 40.6, -73.8),
        AI.AirportEntry("KJFA", "Jefferson Airfield", "Jeffrey",
                        "United States", 39.0, -95.0),
        AI.AirportEntry("EGLL", "London Heathrow", "London",
                        "United Kingdom", 51.5, -0.5),
        AI.AirportEntry("LFPG", "Charles de Gaulle Kennedy Annex", "Paris",
                        "France", 49.0, 2.5),
        AI.AirportEntry("ZZKJ", "Zeta Field", "Kjburg", "Kjland",
                        1.0, 1.0),
    ]


def test_search_exact_code_first():
    res = AI.search(_entries(), "KJFK")
    assert res[0].code == "KJFK"


def test_search_code_prefix_beats_name_substring():
    # "KJ" is a code prefix for KJFK/KJFA, and also a name/city/country
    # substring elsewhere; code-prefix matches must sort ahead.
    res = AI.search(_entries(), "KJ")
    top_two = {res[0].code, res[1].code}
    assert top_two == {"KJFK", "KJFA"}


def test_search_name_prefix_and_substring_order():
    res = AI.search(_entries(), "kennedy")
    codes = [e.code for e in res]
    # "John F Kennedy" contains kennedy as a substring; no name STARTS with
    # kennedy, so both KJFK and LFPG are name-substring rank, input order.
    assert codes.index("KJFK") < codes.index("LFPG")


def test_search_exact_beats_prefix():
    entries = [
        AI.AirportEntry("KJFKX", "Prefix Match", "", "", 0.0, 0.0),
        AI.AirportEntry("KJFK", "Exact Match", "", "", 0.0, 0.0),
    ]
    res = AI.search(entries, "kjfk")
    assert res[0].code == "KJFK"
    assert res[1].code == "KJFKX"


def test_search_limit():
    entries = [AI.AirportEntry("AA%02d" % i, "Alpha %d" % i, "", "",
                               0.0, 0.0) for i in range(20)]
    res = AI.search(entries, "aa", limit=5)
    assert len(res) == 5


def test_search_short_query_returns_empty():
    assert AI.search(_entries(), "k") == []
    assert AI.search(_entries(), "") == []


def test_search_stable_within_rank():
    entries = [
        AI.AirportEntry("ZZ01", "Foobar One", "", "", 0.0, 0.0),
        AI.AirportEntry("ZZ02", "Foobar Two", "", "", 0.0, 0.0),
        AI.AirportEntry("ZZ03", "Foobar Three", "", "", 0.0, 0.0),
    ]
    res = AI.search(entries, "foobar")
    assert [e.code for e in res] == ["ZZ01", "ZZ02", "ZZ03"]


# ---------------------------------------------------------------------------
# parse_coordinate_query
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("query,expected", [
    ("48 -6", (48, -6)),
    ("48,-6", (48, -6)),
    ("+48-006", (48, -6)),
    ("-34+151", (-34, 151)),
    ("48.7 -5.2", (48, -6)),        # floats floored to the containing tile
    ("0 0", (0, 0)),
    ("-1 -1", (-1, -1)),
    ("-85 -180", (-85, -180)),      # inclusive lower bounds
    ("84 179", (84, 179)),          # inclusive upper bounds
])
def test_parse_coordinate_query_valid(query, expected):
    assert AI.parse_coordinate_query(query) == expected


@pytest.mark.parametrize("query", [
    "abc",
    "99 200",       # both out of range
    "90 0",         # lat too high
    "48 999",       # lon too high
    "-86 0",        # lat too low
    "48",           # single number, no lon
    "",
    "   ",
    "48 -6 12",     # three tokens
])
def test_parse_coordinate_query_invalid(query):
    assert AI.parse_coordinate_query(query) is None


# ---------------------------------------------------------------------------
# Full pipeline: find -> build -> load -> search
# ---------------------------------------------------------------------------
def test_end_to_end(tmp_path):
    xp12 = tmp_path / "Global Scenery" / "Global Airports" / "Earth nav data"
    os.makedirs(xp12)
    _write(xp12 / "apt.dat", _APT_DAT_1)
    paths = AI.find_apt_dats(str(tmp_path))
    assert len(paths) == 1
    cache = str(tmp_path / "cache.tsv")
    n = AI.build_index(paths, cache)
    assert n == 4
    entries = AI.load_index(cache)
    hit = AI.search(entries, "AAAA")
    assert hit and hit[0].code == "AAAA"


# ---------------------------------------------------------------------------
# Cache v2 format: #SRC provenance lines
# ---------------------------------------------------------------------------
def _read_lines(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


def test_v2_header_and_src_lines_written(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    lines = _read_lines(cache)
    assert lines[0] == "O4AIRPORTIDX 4 4"
    # Exactly one source was read -> exactly one #SRC line, right after the
    # header and before the first data row.
    src_lines = [ln for ln in lines if ln.startswith("#SRC")]
    assert len(src_lines) == 1
    assert lines[1].startswith("#SRC")
    parts = src_lines[0].split(None, 3)
    assert parts[0] == "#SRC"
    stat = os.stat(apt1)
    assert int(parts[1]) == stat.st_mtime_ns
    assert int(parts[2]) == stat.st_size
    assert parts[3] == apt1


def test_v2_src_line_path_with_spaces(tmp_path):
    # A source path containing spaces must round-trip: the path is written
    # last so split(None, 3) recovers it intact.
    spaced_dir = tmp_path / "path with spaces"
    os.makedirs(spaced_dir)
    apt = _write(spaced_dir / "apt.dat", _APT_DAT_1)
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt], cache)
    src_lines = [ln for ln in _read_lines(cache) if ln.startswith("#SRC")]
    assert len(src_lines) == 1
    parts = src_lines[0].split(None, 3)
    assert parts[3] == apt
    assert " " in parts[3]
    # And it is not stale when checked with the very same path.
    assert AI.index_is_stale([apt], cache) is False


def test_v2_src_line_per_source(apt1, apt2, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1, apt2], cache)
    src_lines = [ln for ln in _read_lines(cache) if ln.startswith("#SRC")]
    assert len(src_lines) == 2
    recorded_paths = [ln.split(None, 3)[3] for ln in src_lines]
    assert recorded_paths == [apt1, apt2]


# ---------------------------------------------------------------------------
# load_index: v2 and hand-written v1 caches
# ---------------------------------------------------------------------------
def test_load_index_reads_v2(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    codes = {e.code for e in AI.load_index(cache)}
    assert codes == {"AAAA", "BBBB", "HHHH", "SSSS"}


def test_load_index_reads_handwritten_v1(tmp_path):
    # A v1 cache has no #SRC lines; load_index must still read it.
    cache = str(tmp_path / "v1.tsv")
    with open(cache, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("O4AIRPORTIDX 1 2\n")
        fh.write("\t".join(("AAAA", "Alpha", "Aville", "Aland",
                            repr(48.5), repr(-6.25))) + "\n")
        fh.write("\t".join(("BBBB", "Bravo", "", "",
                            repr(12.5), repr(77.7))) + "\n")
    by_code = {e.code: e for e in AI.load_index(cache)}
    assert set(by_code) == {"AAAA", "BBBB"}
    assert by_code["AAAA"].city == "Aville"
    assert by_code["AAAA"].lat == pytest.approx(48.5)
    assert by_code["BBBB"].lon == pytest.approx(77.7)
    # Pre-v3 rows carry no category column: the default applies.
    assert by_code["AAAA"].category == "icao_airport"


# ---------------------------------------------------------------------------
# index_is_stale matrix
# ---------------------------------------------------------------------------
def test_stale_fresh_cache_is_false(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    assert AI.index_is_stale([apt1], cache) is False


def test_stale_missing_cache_is_true(apt1, tmp_path):
    cache = str(tmp_path / "nope.tsv")
    assert AI.index_is_stale([apt1], cache) is True


def test_stale_v1_cache_is_true(apt1, tmp_path):
    # Hand-written v1 cache carries no source info -> always stale.
    cache = str(tmp_path / "v1.tsv")
    with open(cache, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("O4AIRPORTIDX 1 1\n")
        fh.write("\t".join(("AAAA", "Alpha", "", "",
                            repr(48.5), repr(-6.25))) + "\n")
    assert AI.index_is_stale([apt1], cache) is True


def test_stale_malformed_header_is_true(apt1, tmp_path):
    cache = str(tmp_path / "bad.tsv")
    _write(tmp_path / "bad.tsv", "NOT A HEADER\ngarbage\n")
    assert AI.index_is_stale([apt1], cache) is True


def test_stale_touched_source_mtime_is_true(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    stat = os.stat(apt1)
    # Move mtime forward by 10 s (unambiguous change in st_mtime_ns).
    new_time = stat.st_mtime + 10
    os.utime(apt1, (new_time, new_time))
    assert AI.index_is_stale([apt1], cache) is True


def test_stale_size_change_with_restored_mtime_is_true(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    recorded = os.stat(apt1)
    # Append a byte (size grows), then restore the recorded mtime so only
    # the size differs -- size alone must still trigger a rebuild.
    with open(apt1, "a", encoding="utf-8") as fh:
        fh.write("X")
    os.utime(apt1, ns=(recorded.st_atime_ns, recorded.st_mtime_ns))
    now = os.stat(apt1)
    assert now.st_mtime_ns == recorded.st_mtime_ns
    assert now.st_size != recorded.st_size
    assert AI.index_is_stale([apt1], cache) is True


def test_stale_source_added_is_true(apt1, apt2, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    # Cache recorded only apt1; asking about apt1+apt2 is a set mismatch.
    assert AI.index_is_stale([apt1, apt2], cache) is True


def test_stale_source_removed_is_true(apt1, apt2, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1, apt2], cache)
    # Cache recorded apt1+apt2; asking about only apt1 is a set mismatch.
    assert AI.index_is_stale([apt1], cache) is True


def test_stale_recorded_source_deleted_is_true(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    os.remove(apt1)
    assert AI.index_is_stale([apt1], cache) is True


def test_stale_abspath_vs_relative_equivalent_is_false(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt1], cache)
    # Build recorded the absolute apt1 path; a relative path to the same
    # file must normalize equal -> not stale.
    rel = os.path.relpath(apt1)
    assert os.path.abspath(rel) == os.path.abspath(apt1)
    assert AI.index_is_stale([rel], cache) is False


def test_stale_empty_paths_no_cache_is_true(tmp_path):
    cache = str(tmp_path / "nope.tsv")
    assert AI.index_is_stale([], cache) is True


def test_stale_empty_paths_v2_empty_sources_is_false(tmp_path):
    # A v2 cache built from an empty source list records zero #SRC lines;
    # comparing an empty request against it is fresh.
    cache = str(tmp_path / "index.tsv")
    count = AI.build_index([], cache)
    assert count == 0
    lines = _read_lines(cache)
    assert lines[0] == "O4AIRPORTIDX 4 0"
    assert not any(ln.startswith("#SRC") for ln in lines)
    assert AI.index_is_stale([], cache) is False


def _write_old_cache(path, version, apt_path):
    """A hand-written cache of an OLDER format version, otherwise fresh."""
    stat = os.stat(apt_path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("O4AIRPORTIDX %d 1\n" % version)
        fh.write("#SRC %d %d %s\n" % (stat.st_mtime_ns, stat.st_size,
                                      apt_path))
        fh.write("\t".join(("AAAA", "Alpha", "", "",
                            repr(48.5), repr(-6.25))) + "\n")
    return path


def test_stale_v2_cache_is_true(apt1, tmp_path):
    # A v2 cache predates the category column and must rebuild once.
    cache = _write_old_cache(str(tmp_path / "v2.tsv"), 2, apt1)
    assert AI.index_is_stale([apt1], cache) is True


def test_stale_v3_cache_is_true(apt1, tmp_path):
    # A v3 cache was built without the water-runway fallback and from a
    # smaller candidate set: fresh sources, stale CONTENT -> rebuild once.
    cache = _write_old_cache(str(tmp_path / "v3.tsv"), 3, apt1)
    assert AI.index_is_stale([apt1], cache) is True


# ---------------------------------------------------------------------------
# 101 (water runway) fallback
# ---------------------------------------------------------------------------
def test_water_runway_fields_and_datum_precedence(tmp_path):
    apt = _write(tmp_path / "apt_water.dat", """I
1000 Generter apt.dat

16   0 0 0 WAT1 Water Only
101 60 1 07 59.0000 10.0000 25 58.9000 10.1000

16   0 0 0 WAT2 Water With Datum
1302 datum_lat 12.0
1302 datum_lon 34.0
101 60 1 07 59.0000 10.0000 25 58.9000 10.1000

16   0 0 0 WAT3 Two Water Runways
101 60 1 07 41.5000 -70.2500 25 41.6000 -70.3000
101 60 1 25 -8.0000 -9.0000 07 -8.1000 -9.1000

16   0 0 0 WAT4 Short Water Row
101 60 1 07
""")
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt], cache)
    by_code = {e.code: e for e in AI.load_index(cache)}

    # Fields 4 and 5 (0-based) are end-1's lat/lon.
    assert by_code["WAT1"].lat == pytest.approx(59.0)
    assert by_code["WAT1"].lon == pytest.approx(10.0)
    # Datum metadata still wins over the runway fallback.
    assert by_code["WAT2"].lat == pytest.approx(12.0)
    assert by_code["WAT2"].lon == pytest.approx(34.0)
    # Only the FIRST fallback row counts (shared rwy_lat gate).
    assert by_code["WAT3"].lat == pytest.approx(41.5)
    assert by_code["WAT3"].lon == pytest.approx(-70.25)
    # A truncated 101 row yields no position at all -> skipped.
    assert "WAT4" not in by_code


def test_water_runway_does_not_displace_an_earlier_land_runway(tmp_path):
    # 100/101/102 share one "first fallback wins" gate: whichever row
    # comes first in the airport's block is the position.
    apt = _write(tmp_path / "apt_mixed.dat", """I
1000 Generter apt.dat

1    5 0 0 MIX1 Land Then Water
100 30.0 1 0 0.25 1 3 0 09 12.5000 77.7000 0 0 0 0 0 0 27 12.5100 77.7100 0 0 0 0 0 0
101 60 1 07 59.0000 10.0000 25 58.9000 10.1000
""")
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt], cache)
    (entry,) = AI.load_index(cache)
    assert entry.lat == pytest.approx(12.5)
    assert entry.lon == pytest.approx(77.7)


# ---------------------------------------------------------------------------
# index_count (header-only read)
# ---------------------------------------------------------------------------
def test_index_count_reads_the_header(apt1, tmp_path):
    cache = str(tmp_path / "index.tsv")
    written = AI.build_index([apt1], cache)
    assert AI.index_count(cache) == written == 4


def test_index_count_missing_file_is_none(tmp_path):
    assert AI.index_count(str(tmp_path / "nope.tsv")) is None


def test_index_count_junk_file_is_none(tmp_path):
    junk = _write(tmp_path / "junk.tsv", "NOT A HEADER\ngarbage\n")
    assert AI.index_count(junk) is None
    # Right magic, unparseable count.
    bad_count = _write(tmp_path / "bad.tsv", "O4AIRPORTIDX 4 many\n")
    assert AI.index_count(bad_count) is None
    # Right magic, count missing entirely.
    short = _write(tmp_path / "short.tsv", "O4AIRPORTIDX 4\n")
    assert AI.index_count(short) is None
    # An empty file has no header at all.
    empty = _write(tmp_path / "empty.tsv", "")
    assert AI.index_count(empty) is None


def test_seaplane_base_category_with_datum(tmp_path):
    # A seaplane base (header 16) gets its category from the header code,
    # whichever way its position was found (datum here, a 101 row for the
    # SSSS fixture).
    apt = _write(tmp_path / "apt_sea.dat", """I
1000 Generter apt.dat

16   0 0 0 SEAA Seaplane With Datum
1302 icao_code SEAA
1302 datum_lat 59.0
1302 datum_lon 10.0
""")
    cache = str(tmp_path / "index.tsv")
    AI.build_index([apt], cache)
    (entry,) = AI.load_index(cache)
    # Header code 16 wins over icao presence: floats anchor differently.
    assert entry.category == "seaplane_base"
