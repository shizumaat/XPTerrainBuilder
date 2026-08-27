"""Tests for :mod:`O4_Custom_Scenery` (the installed-scenery survey).

Headless: a synthetic Custom Scenery tree under ``tmp_path``, no network,
no X-Plane install, no GUI toolkit.  What is guarded here is exactly what
a front end draws from the survey — coverage, kind, status, airports —
plus the exclusions that keep OUR OWN tiles out of it (a built tile is
already its own square on the map; drawn twice it reads as a foreign
package covering the ground we just built).
"""

import os
import textwrap

import O4_Custom_Scenery as PACKS


APT_DAT = textwrap.dedent(
    """\
    I
    1100 Version
    1 25 0 0 EGLL London Heathrow
    1302 icao_code EGLL
    1302 datum_lat 51.4706
    1302 datum_lon -0.4619
    """
)


def _make_pack(scenery_dir, name, tiles=(), apt_dat=None,
               ter=0, images=0, library=False):
    """Build one Custom Scenery entry and return its path."""
    pack = os.path.join(scenery_dir, name)
    nav = os.path.join(pack, "Earth nav data")
    os.makedirs(nav, exist_ok=True)
    for (lat, lon) in tiles:
        group = os.path.join(nav, "%+03d%+04d" % (lat // 10 * 10,
                                                  lon // 10 * 10))
        os.makedirs(group, exist_ok=True)
        with open(os.path.join(group, "%+03d%+04d.dsf" % (lat, lon)),
                  "w") as f:
            f.write("dsf")
    if apt_dat is not None:
        with open(os.path.join(nav, "apt.dat"), "w") as f:
            f.write(apt_dat)
    if ter or images:
        terrain = os.path.join(pack, "terrain")
        os.makedirs(terrain, exist_ok=True)
        for index in range(ter):
            open(os.path.join(terrain, "t%d.ter" % index), "w").close()
        for index in range(images):
            open(os.path.join(terrain, "t%d.dds" % index), "w").close()
    if library:
        open(os.path.join(pack, "library.txt"), "w").close()
    return pack


def _scenery_dir(tmp_path):
    path = tmp_path / "Custom Scenery"
    path.mkdir()
    return str(path)


def test_empty_or_missing_folder_is_no_packs(tmp_path):
    assert PACKS.scan_packs("") == []
    assert PACKS.scan_packs(str(tmp_path / "nope")) == []
    assert PACKS.scan_packs(_scenery_dir(tmp_path)) == []


def test_kinds_are_content_first(tmp_path):
    scenery = _scenery_dir(tmp_path)
    _make_pack(scenery, "Aerosoft EGLL", tiles=[(51, -1)], apt_dat=APT_DAT)
    # Photo-tile texture volume makes it ortho, with no "ortho" in the name.
    _make_pack(scenery, "z_SpainUHD", tiles=[(40, -4)], ter=30, images=30)
    _make_pack(scenery, "SomeMesh", tiles=[(45, 5)], ter=30, images=2)
    _make_pack(scenery, "Landmarks NYC", tiles=[(40, -74)])
    kinds = {pack.name: pack.kind for pack in PACKS.scan_packs(scenery)}
    assert kinds == {
        "Aerosoft EGLL": "airport",
        "z_SpainUHD": "ortho",
        "SomeMesh": "mesh",
        "Landmarks NYC": "landmark",
    }


def test_coverage_and_airports(tmp_path):
    scenery = _scenery_dir(tmp_path)
    _make_pack(scenery, "z_SpainUHD", tiles=[(40, -4), (40, -3)],
               ter=30, images=30)
    _make_pack(scenery, "Aerosoft EGLL", tiles=[(51, -1)], apt_dat=APT_DAT)
    packs = {pack.name: pack for pack in PACKS.scan_packs(scenery)}
    spain = packs["z_SpainUHD"]
    assert spain.tiles == frozenset({(40, -4), (40, -3)})
    assert spain.covers(40, -4) and not spain.covers(41, -4)
    assert [p.name for p in PACKS.packs_covering(packs.values(), 40, -3)] == [
        "z_SpainUHD"
    ]
    airport = packs["Aerosoft EGLL"].airports
    assert [(a.icao, round(a.lat, 4), round(a.lon, 4)) for a in airport] == [
        ("EGLL", 51.4706, -0.4619)
    ]


def test_dsf_date_is_the_packs_own_file(tmp_path):
    scenery = _scenery_dir(tmp_path)
    pack_path = _make_pack(scenery, "SomeMesh", tiles=[(45, 5)],
                           ter=30, images=2)
    pack = PACKS.scan_packs(scenery)[0]
    expected = os.path.join(pack_path, "Earth nav data", "+40+000",
                            "+45+005.dsf")
    assert pack.dsf_path(45, 5) == expected
    assert pack.dsf_modified(45, 5) == os.path.getmtime(expected)
    assert pack.dsf_modified(46, 5) is None


def test_disabled_packs_are_reported_dimmed_not_hidden(tmp_path):
    scenery = _scenery_dir(tmp_path)
    _make_pack(scenery, "SomeMesh", tiles=[(45, 5)], ter=30, images=2)
    with open(os.path.join(scenery, "scenery_packs.ini"), "w") as f:
        f.write("SCENERY_PACK Custom Scenery/Other/\n"
                "SCENERY_PACK_DISABLED Custom Scenery/SomeMesh/\n")
    assert PACKS.disabled_pack_names(scenery) == {"SomeMesh"}
    (pack,) = PACKS.scan_packs(scenery)
    assert pack.status == "disabled"


def test_our_own_entries_and_laminar_are_not_packs(tmp_path):
    """Tile links, the overlay link, Global Airports and pure libraries
    are never third-party scenery."""
    scenery = _scenery_dir(tmp_path)
    _make_pack(scenery, "Global Airports", tiles=[(0, 0)], apt_dat=APT_DAT)
    _make_pack(scenery, "zOrtho4XP_+48-006", tiles=[(48, -6)])
    _make_pack(scenery, "yOrtho4XP_Overlays", tiles=[(48, -6)])
    _make_pack(scenery, "MyLibrary", library=True)
    assert PACKS.scan_packs(scenery) == []


def test_excluded_build_dirs_drop_out_under_either_spelling(tmp_path):
    """A tile built straight into Custom Scenery, and one LINKED there,
    are both ours — the map already draws them green."""
    scenery = _scenery_dir(tmp_path)
    # Built directly into Custom Scenery under a foreign name.
    direct = _make_pack(scenery, "MyTiles", tiles=[(10, 10)],
                        ter=30, images=30)
    # Linked in from the working dir under a foreign name.
    elsewhere = _make_pack(str(tmp_path), "elsewhere", tiles=[(11, 11)],
                           ter=30, images=30)
    os.symlink(elsewhere, os.path.join(scenery, "LinkedTiles"))
    assert {p.name for p in PACKS.scan_packs(scenery)} == {
        "MyTiles", "LinkedTiles"
    }
    assert PACKS.scan_packs(scenery, [direct, elsewhere]) == []


def test_iter_packs_reports_progress_over_the_whole_listing(tmp_path):
    scenery = _scenery_dir(tmp_path)
    _make_pack(scenery, "SomeMesh", tiles=[(45, 5)], ter=30, images=2)
    _make_pack(scenery, "zOrtho4XP_+48-006", tiles=[(48, -6)])
    rows = list(PACKS.iter_packs(scenery))
    assert [done for (done, _total, _pack) in rows] == [1, 2]
    assert {total for (_done, total, _pack) in rows} == {2}
    assert [p.name for (_d, _t, p) in rows if p is not None] == ["SomeMesh"]
