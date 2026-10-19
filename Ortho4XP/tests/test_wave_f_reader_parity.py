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
from auto_patch_v2.airport import cifp as V2_CIFP
from object_stage_support import write_text

# ── cifp: v1 cifp_reader retired onto airport/cifp ──────────────────────
# Owner 2026-10-18 (#911 Q1): tile selection and the flat-site S1 consensus
# read below-sea-level thresholds, as the v2 airport load does.  The twins
# below hold the RULED behaviour.
RWY_16L = "RWY:RW16L,+0580,      ,00044, ,IJCH,3,   ;S12002744,W077071686,0000;"
RWY_34R = "RWY:RW34R,+2380,      ,00113, ,IJCZ,1,   ;S12021200,W077064500,0984;"
#: BELOW-SEA-LEVEL thresholds: ARINC 424 signs the elevation field
RWY_18R_BELOW_SEA = ("RWY:RW18R,+1835,      ,-0011, ,ISNA,3,   ;"
                     "N52215800,E004422200,0000;")
RWY_36L_BELOW_SEA = ("RWY:RW36L,+0035,      ,-0013, ,    , ,   ;"
                     "N52192000,E004422400,0000;")
#: the malformed rows the reader skips
SKIPPED = [
    "RWY:XX99,+0000,      ,00010, ,    , ,   ;S12000000,W077000000,0000;",
    "RWY:RW09,+0900,      ,     , ,    , ,   ;S12000000,W077000000,0000;",
    "RWY:RW27,+2700,      ,00010, ,    , ,   ;S12,W077,0000;",
    "RWY:RW01,+0100",
    "APPCH:010,A,I16L ,AER,...",
]


def test_the_selection_shape_is_read_cifp_runways_rekeyed(tmp_path):
    """Same records, same numbers: ``read_threshold_dicts`` is
    ``read_cifp_runways`` in the ``{"RW16L": {lat, lon, elevation_m,
    displaced_m}}`` shape selection and the object-anchor worklist read."""
    path = write_text(tmp_path / "ZZZZ.dat",
                      "\n".join([RWY_16L, RWY_34R] + SKIPPED) + "\n")
    shaped = V2_CIFP.read_threshold_dicts(str(path))
    v2 = V2_CIFP.read_cifp_runways(str(path))
    assert sorted(shaped) == ["RW16L", "RW34R"]
    assert {"RW" + k: {"lat": r.lat, "lon": r.lon,
                       "elevation_m": r.elevation_m,
                       "displaced_m": r.displaced_m}
            for k, r in v2.items()} == shaped


def test_cifp_below_sea_thresholds_are_read(tmp_path):
    """RULED (owner 2026-10-18, #911 Q1): a signed threshold elevation is
    read by the selection shape and by the flat-site S1 consensus — v1
    ``parse_cifp_file`` (``elev.isdigit()``) dropped it.  S1 is the v2
    detector's since issue #932: it reads ``read_cifp_runways`` through
    the join (``flat_site_prep.site_inputs``)."""
    path = str(write_text(tmp_path / "ZZZZ.dat",
                          RWY_18R_BELOW_SEA + "\n" + RWY_16L + "\n"))
    shaped = V2_CIFP.read_threshold_dicts(path)
    assert sorted(shaped) == ["RW16L", "RW18R"]
    assert shaped["RW18R"]["elevation_m"] == pytest.approx(-11 * 0.3048)
    assert sorted(r.elevation_m for r in V2_CIFP.read_cifp_runways(path).values()) == (
        pytest.approx(sorted([-11 * 0.3048, 44 * 0.3048])))


def test_selection_patches_an_airport_whose_thresholds_are_all_below_sea(
        tmp_path, monkeypatch):
    """RULED (owner 2026-10-18, #911 Q1): an airport whose every runway
    threshold is below sea level is SELECTED for patching (v1 parsed its
    runways to ``{}`` and never patched it)."""
    from auto_patch import selection

    cifp = tmp_path / "CIFP"
    write_text(cifp / "ZZZZ.dat",
               RWY_18R_BELOW_SEA + "\n" + RWY_36L_BELOW_SEA + "\n")
    monkeypatch.setattr(V2_CIFP, "xplane_root_from_cifp_path",
                        lambda path: "/fake/xplane")
    monkeypatch.setattr(
        "auto_patch.build_support._pick_best_apt_dat_against_osm",
        lambda root, icao, *a, **k: "/fake/apt.dat")
    tile = type("Tile", (), {"lat": 52, "lon": 4})()
    got = selection.select_patch_airports(tile, str(cifp), "ICAO",
                                          manual_icaos=())
    assert [(c.icao, c.disposition) for c in got] == [("ZZZZ", "patch")]
    assert sorted(got[0].runways) == ["RW18R", "RW36L"]


def test_an_unreadable_cifp_file_skips_the_airport_not_the_tile(tmp_path):
    """The OSError choice: v2 ``read_cifp_runways`` raises (the airport
    load checks ``isfile`` first); the selection shape keeps v1's caller-
    visible behaviour — a vanished file is no runways, so selection skips
    that airport instead of failing the tile."""
    missing = str(tmp_path / "GONE.dat")
    assert V2_CIFP.read_threshold_dicts(missing) == {}
    with pytest.raises(OSError):
        V2_CIFP.read_cifp_runways(missing)


# ── obj8_reader <-> airport/obj8 ─────────────────────────────────────────
#: a tiny OBJ8: TAB-separated VT rows, IDX10 + IDX, an indented TRIS (the
#: XPlane2Blender LOD shape), a hard-deck run, a draped run and an ANIM
#: block — every state the two parsers both track
TINY_OBJ8 = "\n".join([
    "I", "800", "OBJ", "", "POINT_COUNTS\t6 0 0 12",
    "VT\t0 0 0\t0 1 0\t0 0",
    "VT\t10 0 0\t0 1 0\t0 0",
    "VT\t0 0 10\t0 1 0\t0 0",
    "VT 10 2 10 0 1 0 0 0",
    "VT 20 2 10 0 1 0 0 0",
    "VT 20 -1 0 0 1 0 0 0",
    "IDX10 0 1 2 1 3 2 3 4 1",
    "IDX 5 4 3",
    "\tTRIS\t0 3",
    "ATTR_hard_deck",
    "TRIS 3 3",
    "ATTR_no_hard",
    "ANIM_begin",
    "TRIS 6 3",
    "ANIM_end",
    "ATTR_draped",
    "TRIS 0 3",
    "LIGHT_NAMED amb_street_light2 0 9.5 0.9",
]) + "\n"


def test_obj8_readers_agree_on_their_shared_geometry(tmp_path):
    """The subset BOTH readers carry — vertices, solid triangles with their
    hardness, draped triangles — is identical.  v1 ``ObjectGeometry``
    carries more (``vertex_line_indices`` for the rebake's in-place y
    rewrite, ``positional_commands`` that ride with their structure, the
    draped layer group, LOD/ANIM counts); v2 ``ObjGeometry`` carries the
    per-triangle ANIM flag.  So the PAIR is not a duplicate: v1 is the
    object stage's reader and leaves with that stage (wave A), not here."""
    from auto_patch import obj8_reader as V1_OBJ8
    from auto_patch_v2.airport import obj8 as V2_OBJ8

    path = write_text(tmp_path / "tiny.obj", TINY_OBJ8)
    v1 = V1_OBJ8.load_object_file(path)
    v2 = V2_OBJ8.parse_obj8(path)
    assert [tuple(v) for v in v2.vertices.tolist()] == \
        [tuple(map(float, v)) for v in v1.vertices]
    assert [tuple(t) for t in v2.solid.tolist()] == \
        [tuple(t) for t in v1.solid_triangles]
    assert [tuple(t) for t in v2.draped.tolist()] == \
        [tuple(t) for t in v1.draped_triangles]
    names = {0: "", V2_OBJ8.HARD: "hard", V2_OBJ8.HARD_DECK: "hard_deck"}
    assert [names[int(h)] for h in v2.hardness] == \
        list(v1.solid_triangle_hardness)
    # what only v1 carries (the object stage's needs)
    assert len(v1.vertex_line_indices) == len(v1.vertices)
    assert [c.keyword for c in v1.positional_commands] == ["LIGHT_NAMED"]
    assert not hasattr(v2, "positional_commands")


# ── apt_dat_reader <-> airport/apt_dat (the block reader) ────────────────
#: three land airports, a seaplane base (row 16) and a heliport (row 17)
#: between them, and the 99 terminator
APT_DAT = "\n".join([
    "I", "1200 Version", "",
    "1 100 0 0 AAAA First",
    "100 45.00 1 0 0.25 0 2 1 09 10.0 20.0 0 0 1 0 0 0 27 10.0 20.1 0 0 1 0 0 0",
    "1302 datum_lat 10.0",
    "",
    "1 200 0 0 BBBB Second",
    "110 1 0.25 0 Apron",
    "111 10.0 20.0",
    "16 0 0 0 SSSS Seaplane base",
    "1302 datum_lat 11.0",
    "17 0 0 0 HHHH Heliport",
    "1302 datum_lat 12.0",
    "1 300 0 0 CCCC Third",
    "1302 datum_lat 13.0",
    "99",
]) + "\n"


def test_apt_dat_block_readers_agree_between_land_airports(tmp_path):
    from auto_patch import apt_dat_reader as V1_APT
    from auto_patch_v2.airport import apt_dat as V2_APT

    path = write_text(tmp_path / "apt.dat", APT_DAT)
    v1 = V1_APT._read_airport_block(path, "aaaa")
    v2 = V2_APT.read_airport_block(path, "aaaa")
    assert [ln.rstrip("\n") for ln in v1] == v2
    assert V1_APT._read_airport_block(path, "ZZZZ") is None
    assert V2_APT.read_airport_block(path, "ZZZZ") is None


def test_apt_dat_block_readers_differ_at_row_16_17_and_99(tmp_path):
    """v1 knows only row-1 headers: BBBB's block swallows the seaplane base
    and the heliport behind it (their 1302 datum rows included), CCCC's
    swallows the ``99`` terminator, and neither SSSS nor HHHH can be read.
    v2 — the reader the BUILD uses — stops at every 1/16/17/99 boundary.
    The three tool callers re-pointed in this wave (harness ARP sanity,
    harness tile resolution, the inset witness) select their file with v2
    ``select_apt_dat`` already; reading the block with v1 was the mismatch.
    No engine caller reads ``_read_airport_block``."""
    from auto_patch import apt_dat_reader as V1_APT
    from auto_patch_v2.airport import apt_dat as V2_APT

    path = write_text(tmp_path / "apt.dat", APT_DAT)
    v1 = [ln.rstrip("\n") for ln in V1_APT._read_airport_block(path, "BBBB")]
    v2 = V2_APT.read_airport_block(path, "BBBB")
    assert v2 == v1[:3]
    assert "1302 datum_lat 12.0" in v1 and "1302 datum_lat 12.0" not in v2
    assert V1_APT._read_airport_block(path, "HHHH") is None
    assert V2_APT.read_airport_block(path, "HHHH")[1] == "1302 datum_lat 12.0"
    assert V1_APT._read_airport_block(path, "CCCC")[-1].rstrip() == "99"
    assert V2_APT.read_airport_block(path, "CCCC")[-1] == "1302 datum_lat 13.0"
