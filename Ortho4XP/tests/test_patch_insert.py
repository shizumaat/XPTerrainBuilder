""""Insert shape" (issue #1314, protocol 1.17): the 20 m square, the
airport it goes to, the corners' elevations and appending it to a patch
on disk.  Headless: patches under ``tmp_path``, the airport index and the
elevation sources stubbed; no X-Plane, no network."""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine import patch_commands as PC  # noqa: E402
from o4_engine import patch_file as PF  # noqa: E402
from o4_engine import patch_insert as PI  # noqa: E402

TILE = "+30+031"
_AUTO = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="o4" o4_apt_dat="abc">
  <node id="-1" lat="30.1" lon="31.4"><tag k="alt_abs" v="100.125"/></node>
  <node id="-2" lat="30.1" lon="31.41"><tag k="alt_abs" v="101"/></node>
  <node id="-3" lat="30.11" lon="31.41"><tag k="alt_abs" v="102"/></node>
  <way id="-10"><nd ref="-1"/><nd ref="-2"/><nd ref="-3"/><nd ref="-1"/><tag k="aeroway" v="apron"/></way>
</osm>
"""


@pytest.fixture
def patches(tmp_path, monkeypatch):
    """A Patches root with one auto patch (ZZZZ, box 30.1-30.11 x
    31.4-31.41); the index holds ZZZZ, a larger ZZZY around it and ZZZX
    elsewhere; every corner stands at 50 m + its index."""
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    monkeypatch.setattr(PC, "_staleness", lambda tile, icao, doc, source: (False, []))
    monkeypatch.setattr(PI, "_index_airports", lambda: [
        ("ZZZY", (30.0, 31.3, 30.3, 31.6)), ("ZZZZ", (30.1, 31.4, 30.11, 31.41)),
        ("ZZZX", (30.5, 31.5, 30.6, 31.6))])
    asked = []

    def elevation(lat, lon, build_dir=None):
        asked.append((lat, lon, build_dir))
        return {"elevation_m": 50.0 + len(asked) - 1, "source": "mesh", "pending": False}
    monkeypatch.setattr(PI, "cursor_elevation", elevation)
    directory = FNAMES.patch_dir(30, 31)
    os.makedirs(directory)
    with open(os.path.join(directory, "ZZZZ_auto.patch.osm"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(_AUTO)
    return directory


# ─── the square ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lat", [0.0, 30.05, 45.5, -45.5, 60.2, 71.3])
def test_the_square_is_four_ccw_corners_20_m_apart(lat):
    pyproj = pytest.importorskip("pyproj")
    geod = pyproj.Geod(ellps="WGS84")
    ring = PI.square_ring(lat, -122.6)
    assert len(ring) == 4 and len(set(ring)) == 4
    area2 = sum(a[1] * b[0] - b[1] * a[0] for a, b in zip(ring, ring[1:] + ring[:1]))
    assert area2 > 0                                     # CCW with x = lon, y = lat
    for a, b in zip(ring, ring[1:] + ring[:1]):
        _f, _b, d = geod.inv(a[1], a[0], b[1], b[0])
        assert d == pytest.approx(PI.SQUARE_SIDE_M, abs=0.01)
    assert sum(p[0] for p in ring) / 4 == pytest.approx(lat, abs=1e-12)
    assert sum(p[1] for p in ring) / 4 == pytest.approx(-122.6, abs=1e-12)


def test_the_side_is_20_m():
    assert PI.SQUARE_SIDE_M == 20.0


# ─── the airport ───────────────────────────────────────────────────────────

def test_a_point_in_a_patch_goes_to_that_patch(patches):
    got = PI.insert_target(30.105, 31.405)
    assert got == {"tile": TILE, "icao": "ZZZZ", "source": "auto",
                   "path": os.path.join(patches, "ZZZZ_auto.patch.osm")}


def test_a_point_only_in_the_index_goes_to_the_smallest_extent_holding_it(patches):
    got = PI.insert_target(30.2, 31.35)
    assert got == {"tile": TILE, "icao": "ZZZY", "source": None, "path": None}


def test_a_point_in_no_airport_is_refused_with_the_users_sentence(patches):
    with pytest.raises(ValueError, match=r"No airport's boundary holds 30\.800000000, "
                                         r"31\.800000000.*right-click inside an airport"):
        PI.insert_target(30.8, 31.8)


# ─── the plan ──────────────────────────────────────────────────────────────

def test_insert_shape_plans_the_corners_at_the_elevation_under_them(patches):
    reply = PI.patch_insert_shape(30.105, 31.405, build_dir="/b")
    assert reply["pending"] is False and reply["icao"] == "ZZZZ" and reply["side_m"] == 20.0
    ring = PI.square_ring(30.105, 31.405)
    assert [c[:2] for c in reply["corners"]] == [list(p) for p in ring]
    assert [c[2] for c in reply["corners"]] == [50.0, 51.0, 52.0, 53.0]


def test_insert_shape_is_pending_while_a_source_loads(patches, monkeypatch):
    monkeypatch.setattr(PI, "cursor_elevation", lambda lat, lon, build_dir=None:
                        {"elevation_m": None, "source": None, "pending": True})
    assert PI.patch_insert_shape(30.105, 31.405) == {"pending": True}


def test_insert_shape_without_any_elevation_is_refused(patches, monkeypatch):
    monkeypatch.setattr(PI, "cursor_elevation", lambda lat, lon, build_dir=None:
                        {"elevation_m": None, "source": None, "pending": False})
    with pytest.raises(ValueError, match="no elevation|There is no elevation"):
        PI.patch_insert_shape(30.105, 31.405)


@pytest.mark.parametrize("lat, lon", [(math.nan, 0.0), (91.0, 0.0), ("x", 0.0)])
def test_insert_shape_refuses_a_point_off_the_globe(lat, lon):
    with pytest.raises(ValueError, match="patch_insert_shape"):
        PI.patch_insert_shape(lat, lon)


# ─── appending to a patch on disk ──────────────────────────────────────────

def _corners():
    return [[*p, 60.0 + k] for k, p in enumerate(PI.square_ring(30.105, 31.405))]


def test_add_shape_to_an_auto_patch_saves_the_edited_patch(patches):
    reply = PI.patch_add_shape(TILE, "zzzz", _corners())
    edited = os.path.join(patches, "ZZZZ_edited.patch.osm")
    message = reply.pop("message")
    assert reply == {"path": edited, "way_id": -11, "created": False}
    assert message == ("Added a 20 m square to ZZZZ's patch, saved as ZZZZ_edited.patch.osm. "
                       "Rebuild tile +30+031 to see it in X-Plane.")
    doc = PF.read_patch(edited)
    assert [w["id"] for w in doc.ways] == [-10, -11]
    new = doc.ways[-1]
    assert new["refs"] == [-4, -5, -6, -7, -4] and new["tags"] == {}
    alts = {n[0]: n[3] for n in doc.nodes}
    assert [alts[r] for r in new["refs"][:4]] == [60.0, 61.0, 62.0, 63.0]
    assert doc.header["o4_user_edited"] == "1" and doc.header["o4_edited_from_apt_dat"] == "abc"
    assert os.path.isfile(os.path.join(patches, "ZZZZ_auto.patch.osm"))   # never touched


def test_add_shape_where_there_is_no_patch_starts_the_edited_patch(patches):
    reply = PI.patch_add_shape(TILE, "ZZZY", _corners())
    path = os.path.join(patches, "ZZZY_edited.patch.osm")
    assert reply.pop("message").startswith("Started ZZZY's custom patch ZZZY_edited.patch.osm "
                                           "with a 20 m square. The next build of tile +30+031")
    assert reply == {"path": path, "way_id": -1, "created": True}
    listed = {a["icao"]: a for a in PC.patch_list(TILE)["airports"]}
    assert listed["ZZZY"]["source"] == "manual" and listed["ZZZY"]["nodes"] == 4
    loaded = PC.patch_load(TILE, "ZZZY")
    assert [w["refs"] for w in loaded["ways"]] == [[-1, -2, -3, -4, -1]]
    assert loaded["header"]["o4_user_edited"] == "1"
    assert not any(k.startswith("o4_edited_from_") for k in loaded["header"])


def test_a_refused_new_patch_leaves_no_file(patches):
    with pytest.raises(ValueError):
        PI.patch_add_shape(TILE, "ZZZY", _corners()[:2])
    assert not os.path.exists(os.path.join(patches, "ZZZY_edited.patch.osm"))


def test_the_transport_has_both_commands_from_protocol_1_17():
    from unittest import mock
    table = jsonl.command_table(mock.MagicMock())
    assert table["patch_insert_shape"] is PI.patch_insert_shape
    assert table["patch_add_shape"] is PI.patch_add_shape
    assert tuple(int(p) for p in EV.PROTOCOL_VERSION.split(".")) >= (1, 17)
