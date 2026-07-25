"""Unit tests for ``auto_patch.agp_reader`` and the DSF ``.agp`` OBJECT
walker.

Pure hermetic tests — they build tiny ``.agp`` files and ``library.txt``
maps under ``tmp_path`` and feed synthetic DSF text to the OBJECT walker,
so they need no X-Plane install and always run.  They pin the encoded
``.agp`` footprint math (TILE/CROP_POLY × TEXTURE_WIDTH/HEIGHT ÷
TEXTURE_SCALE, anchored at ANCHOR_PT), the ``library.txt`` resolution +
priority, the persistent library-index sidecar cache and its
invalidation, and the placement→lon/lat transform.
"""
from __future__ import annotations

import math
import os
import threading

import pytest

from auto_patch import agp_reader as A
from auto_patch.dsf_reader import _read_dsf_object_placements


@pytest.fixture(autouse=True)
def sandbox_ortho4xp_data_root(tmp_path, monkeypatch):
    """The library-index sidecar lands under the Ortho4XP data root,
    which in a source checkout resolves to the current working directory
    — without this pin every test that builds a library index would
    write ``Airport_mod_cache/`` into the repository (same fixture, same
    reason, as ``test_dsf_object_buildings.py``)."""
    monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "o4_data_root"))


@pytest.fixture(autouse=True)
def clear_library_index_memo():
    """The in-process index memo is keyed on ``xplane_root`` alone, and
    ``tmp_path`` roots differ per test — but these tests deliberately
    rebuild the SAME root repeatedly, so drop the memo around each one."""
    A._LIB_INDEX_CACHE.clear()
    A._LIB_INDEX_LOCKS.clear()
    yield
    A._LIB_INDEX_CACHE.clear()
    A._LIB_INDEX_LOCKS.clear()


# ── .agp footprint parsing ───────────────────────────────────────────
# A 128px tile spanning 60 m (mpp = 60/128 = 0.46875), anchored low so
# the parsed footprint is asymmetric in y — exactly the stock
# hangar_40x26_1 layout.
_AGP_60x60 = """A
1000
AG_POINT

TEXTURE ../../textures/transparent.png
TEXTURE_SCALE 128 128

HIDE_TILES

OBJECT app_hangar2_ext1.obj

#id: 1 / tile name: TILE.016
TEXTURE_WIDTH 60.0
TEXTURE_HEIGHT 60.0

TILE 0.0 0.0 128.0 128.0
ROTATION 0
CROP_POLY 0.0 128.0 0.0 0.0 128.0 0.0 128.0 128.0
ANCHOR_PT 64.0 29.867
"""

_MPP = 60.0 / 128.0


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_parse_agp_tile_meters(tmp_path):
    fp = A.parse_agp(_write(tmp_path, "h.agp", _AGP_60x60))
    assert fp is not None
    xs = [x for x, _ in fp.local_poly]
    ys = [y for _, y in fp.local_poly]
    # Full 128px tile → 60 m on each axis.
    assert (max(xs) - min(xs)) == pytest.approx(60.0, abs=1e-6)
    assert (max(ys) - min(ys)) == pytest.approx(60.0, abs=1e-6)
    # Anchor at pixel (64, 29.867) → x centred, y offset low.
    assert min(xs) == pytest.approx(-64.0 * _MPP, abs=1e-6)
    assert min(ys) == pytest.approx(-29.867 * _MPP, abs=1e-6)
    assert max(ys) == pytest.approx((128.0 - 29.867) * _MPP, abs=1e-6)
    assert fp.rotation == 0.0


def test_parse_agp_default_anchor_is_tile_centre(tmp_path):
    text = _AGP_60x60.replace("ANCHOR_PT 64.0 29.867\n", "")
    fp = A.parse_agp(_write(tmp_path, "noanchor.agp", text))
    assert fp is not None
    xs = [x for x, _ in fp.local_poly]
    ys = [y for _, y in fp.local_poly]
    # No ANCHOR_PT → tile centre (64,64) → symmetric ±30 m on both axes.
    assert min(xs) == pytest.approx(-30.0, abs=1e-6)
    assert max(xs) == pytest.approx(30.0, abs=1e-6)
    assert min(ys) == pytest.approx(-30.0, abs=1e-6)
    assert max(ys) == pytest.approx(30.0, abs=1e-6)


def test_parse_agp_crop_tighter_than_tile(tmp_path):
    # CROP_POLY covering only pixels 32..96 (64 px → 30 m) inside the
    # 128px tile: the footprint follows the CROP_POLY, not the TILE.
    text = _AGP_60x60.replace(
        "CROP_POLY 0.0 128.0 0.0 0.0 128.0 0.0 128.0 128.0",
        "CROP_POLY 32.0 96.0 32.0 32.0 96.0 32.0 96.0 96.0")
    fp = A.parse_agp(_write(tmp_path, "crop.agp", text))
    xs = [x for x, _ in fp.local_poly]
    ys = [y for _, y in fp.local_poly]
    assert (max(xs) - min(xs)) == pytest.approx(64.0 * _MPP, abs=1e-6)
    assert (max(ys) - min(ys)) == pytest.approx(64.0 * _MPP, abs=1e-6)


def test_parse_agp_memoized(tmp_path):
    p = _write(tmp_path, "memo.agp", _AGP_60x60)
    assert A.parse_agp(p) is A.parse_agp(p)


def test_parse_agp_missing_scale_returns_none(tmp_path):
    text = _AGP_60x60.replace("TEXTURE_WIDTH 60.0\n", "")
    assert A.parse_agp(_write(tmp_path, "bad.agp", text)) is None


# ── library.txt resolution ───────────────────────────────────────────
def _make_xplane_root(tmp_path):
    root = tmp_path / "XP"
    (root / "Custom Scenery").mkdir(parents=True)
    (root / "Resources" / "default scenery" / "airport scenery").mkdir(
        parents=True)
    return root


def test_library_resolve_and_memoization(tmp_path):
    root = _make_xplane_root(tmp_path)
    pack = root / "Custom Scenery" / "MyPack"
    pack.mkdir()
    (pack / "h.agp").write_text(_AGP_60x60)
    (pack / "library.txt").write_text(
        "EXPORT lib/airport/Common_Elements/Hangars/Test.agp\th.agp\n")

    virtual = "lib/airport/Common_Elements/Hangars/Test.agp"
    phys = A.resolve_library_path(virtual, str(root))
    assert phys is not None
    assert phys.endswith("MyPack/h.agp")
    # Built once and shared.
    assert (A.get_library_index(str(root))
            is A.get_library_index(str(root)))


def test_custom_scenery_overrides_default(tmp_path):
    root = _make_xplane_root(tmp_path)
    virtual = "lib/airport/Common_Elements/Hangars/Test.agp"

    default_dir = root / "Resources" / "default scenery" / "airport scenery"
    (default_dir / "from_default.agp").write_text(_AGP_60x60)
    (default_dir / "library.txt").write_text(
        f"EXPORT {virtual}\tfrom_default.agp\n")

    pack = root / "Custom Scenery" / "Override"
    pack.mkdir()
    (pack / "from_custom.agp").write_text(_AGP_60x60)
    (pack / "library.txt").write_text(
        f"EXPORT {virtual}\tfrom_custom.agp\n")

    phys = A.resolve_library_path(virtual, str(root))
    assert phys.endswith("Override/from_custom.agp")


def test_resolve_missing_returns_none(tmp_path):
    root = _make_xplane_root(tmp_path)
    assert A.resolve_library_path(
        "lib/airport/Common_Elements/Hangars/Nope.agp", str(root)) is None


# ── persistent library-index sidecar cache ───────────────────────────
#
# Parsing every library.txt of a real install costs ~0.57 s per COLD
# process (337 files / ~135 k entries), which every per-airport build
# paid afresh.  The sidecar re-serves the merged index in milliseconds,
# so what these tests must pin is that a cached read is INDISTINGUISHABLE
# from a fresh parse, and that every way the install can change makes the
# fingerprint miss.
def _install(tmp_path, packs, ini_order=None, default=None):
    """Build an X-Plane root: ``packs`` maps pack name → EXPORT lines,
    ``default`` the same for one default-scenery folder.  ``ini_order``
    (pack names, highest priority first) writes a scenery_packs.ini."""
    root = tmp_path / "XP"
    custom = root / "Custom Scenery"
    custom.mkdir(parents=True)
    default_dir = root / "Resources" / "default scenery" / "airport scenery"
    default_dir.mkdir(parents=True)
    if default:
        (default_dir / "library.txt").write_text(default)
    for name, exports in packs.items():
        pack = custom / name
        pack.mkdir()
        (pack / "library.txt").write_text(exports)
    if ini_order is not None:
        (custom / "scenery_packs.ini").write_text(
            "I\n1000 Version\nSCENERY\n\n" + "".join(
                f"SCENERY_PACK Custom Scenery/{name}/\n"
                for name in ini_order))
    return root


def _fresh_parse(root):
    """The merged index computed straight from the files, cache of any
    kind bypassed — the oracle a cached read must equal."""
    index: dict[str, str] = {}
    for source in A._library_source_files(str(root)):
        A._parse_library_txt(source, index)
    return index


def _cold_index(root, counter=None):
    """One COLD ``get_library_index``: drop the in-process memo so the
    call goes to the sidecar (or rebuilds), as a fresh build process
    would.  ``counter`` (a list) collects the library.txt files parsed,
    so a caller can tell a cache hit from a rebuild."""
    A._LIB_INDEX_CACHE.clear()
    if counter is None:
        return A.get_library_index(str(root))
    original = A._parse_library_txt

    def counted(lib_path, index):
        counter.append(lib_path)
        return original(lib_path, index)

    A._parse_library_txt = counted
    try:
        return A.get_library_index(str(root))
    finally:
        A._parse_library_txt = original


_PACKS = {
    "Alpha": "EXPORT lib/a.agp\ta.agp\nEXPORT lib/shared.agp\talpha.agp\n",
    "Bravo": "EXPORT lib/b.agp\tb.agp\nEXPORT lib/shared.agp\tbravo.agp\n",
}
_DEFAULT = "EXPORT lib/d.agp\td.agp\nEXPORT lib/shared.agp\tdefault.agp\n"


def _sidecars(tmp_path):
    cache_dir = tmp_path / "o4_data_root" / "Airport_mod_cache"
    if not cache_dir.is_dir():
        return []
    return sorted(p.name for p in cache_dir.iterdir())


def test_sidecar_hit_equals_fresh_parse(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Bravo", "Alpha"],
                    default=_DEFAULT)
    expected = _fresh_parse(root)

    first_parses: list[str] = []
    first = _cold_index(root, first_parses)
    assert first == expected
    assert len(first_parses) == 3          # default + both packs, parsed

    second_parses: list[str] = []
    second = _cold_index(root, second_parses)
    assert second_parses == []             # served from the sidecar
    assert second == expected              # ...and byte-for-byte the same
    # Priority survives the round trip: Bravo leads the ini, so it wins
    # the shared virtual path over Alpha and over default scenery.
    assert second["lib/shared.agp"].endswith("Bravo/bravo.agp")


def test_sidecar_written_under_the_data_root_not_the_install(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    _cold_index(root)
    assert len(_sidecars(tmp_path)) == 1
    assert _sidecars(tmp_path)[0].startswith("o4_library_index_")
    # Nothing written into the X-Plane install (user ruling 2026-07-15).
    assert sorted(p.name for p in (root / "Custom Scenery").iterdir()) == [
        "Alpha", "Bravo", "scenery_packs.ini"]
    assert sorted(p.name for p in
                  (root / "Custom Scenery" / "Alpha").iterdir()
                  ) == ["library.txt"]


def test_no_temp_files_left_behind(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    _cold_index(root)
    # The write is temp-file + os.replace; the temp must not survive it.
    assert not [n for n in _sidecars(tmp_path) if n.endswith(".tmp")]


def test_two_installs_get_separate_sidecars(tmp_path):
    first = _install(tmp_path / "one", _PACKS, ini_order=["Alpha"])
    second = _install(tmp_path / "two", {"Alpha": "EXPORT lib/z.agp\tz.agp\n"},
                      ini_order=["Alpha"])
    assert _cold_index(first) == _fresh_parse(first)
    assert _cold_index(second) == _fresh_parse(second)
    assert len(_sidecars(tmp_path)) == 2
    # Neither install served the other's index.
    assert _cold_index(first) == _fresh_parse(first)
    assert "lib/z.agp" not in _cold_index(first)


# ── invalidation matrix ──────────────────────────────────────────────
# Every way the install can change must miss the fingerprint, rebuild,
# and rewrite — each case asserts BOTH that a rebuild happened and that
# the resulting index equals a fresh parse of the changed install.
def _assert_rebuilds_to_truth(root):
    parses: list[str] = []
    index = _cold_index(root, parses)
    assert parses, "expected a rebuild, got a sidecar hit"
    assert index == _fresh_parse(root)
    # ...and the rewritten sidecar now serves the NEW index.
    reparses: list[str] = []
    assert _cold_index(root, reparses) == index
    assert reparses == []
    return index


def test_invalidates_when_a_library_txt_is_touched(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    _cold_index(root)
    library = root / "Custom Scenery" / "Alpha" / "library.txt"
    stat = library.stat()
    os.utime(library, (stat.st_atime + 120, stat.st_mtime + 120))
    _assert_rebuilds_to_truth(root)


def test_invalidates_when_a_library_txt_is_edited(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    assert "lib/new.agp" not in _cold_index(root)
    (root / "Custom Scenery" / "Alpha" / "library.txt").write_text(
        _PACKS["Alpha"] + "EXPORT lib/new.agp\tnew.agp\n")
    assert "lib/new.agp" in _assert_rebuilds_to_truth(root)


def test_invalidates_when_a_pack_is_added(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    _cold_index(root)
    added = root / "Custom Scenery" / "Charlie"
    added.mkdir()
    (added / "library.txt").write_text("EXPORT lib/c.agp\tc.agp\n")
    assert "lib/c.agp" in _assert_rebuilds_to_truth(root)


def test_invalidates_when_a_pack_is_removed(tmp_path):
    import shutil
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    assert "lib/b.agp" in _cold_index(root)
    shutil.rmtree(root / "Custom Scenery" / "Bravo")
    assert "lib/b.agp" not in _assert_rebuilds_to_truth(root)


def test_invalidates_when_scenery_packs_ini_is_reordered(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    assert _cold_index(root)["lib/shared.agp"].endswith("Alpha/alpha.agp")
    # Same packs, same library.txt files — only the priority order moves.
    (root / "Custom Scenery" / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n"
        "SCENERY_PACK Custom Scenery/Bravo/\n"
        "SCENERY_PACK Custom Scenery/Alpha/\n")
    index = _assert_rebuilds_to_truth(root)
    assert index["lib/shared.agp"].endswith("Bravo/bravo.agp")


def test_invalidates_when_scenery_packs_ini_is_removed(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Bravo", "Alpha"])
    assert _cold_index(root)["lib/shared.agp"].endswith("Bravo/bravo.agp")
    (root / "Custom Scenery" / "scenery_packs.ini").unlink()
    # No ini → packs fall back to sorted (highest priority first) order,
    # so the winner flips from ini-led Bravo to alphabetical Alpha.
    assert _assert_rebuilds_to_truth(root)["lib/shared.agp"].endswith(
        "Alpha/alpha.agp")


def test_invalidates_on_a_cache_version_bump(tmp_path, monkeypatch):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    _cold_index(root)
    monkeypatch.setattr(A, "_LIB_INDEX_CACHE_VERSION",
                        A._LIB_INDEX_CACHE_VERSION + 1)
    _assert_rebuilds_to_truth(root)


def test_corrupt_sidecar_rebuilds(tmp_path):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    _cold_index(root)
    cache_dir = tmp_path / "o4_data_root" / "Airport_mod_cache"
    sidecar = next(cache_dir.iterdir())
    sidecar.write_bytes(b"not a pickle at all")
    _assert_rebuilds_to_truth(root)


def test_gate_off_neither_reads_nor_writes(tmp_path, monkeypatch):
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    monkeypatch.setenv("O4_LIBRARY_INDEX_CACHE", "0")
    parses: list[str] = []
    assert _cold_index(root, parses) == _fresh_parse(root)
    assert len(parses) == 2
    assert _sidecars(tmp_path) == []        # nothing written
    # A pre-existing sidecar is not read either.
    monkeypatch.delenv("O4_LIBRARY_INDEX_CACHE")
    _cold_index(root)
    assert len(_sidecars(tmp_path)) == 1
    monkeypatch.setenv("O4_LIBRARY_INDEX_CACHE", "0")
    reparses: list[str] = []
    _cold_index(root, reparses)
    assert len(reparses) == 2


def test_missing_install_yields_empty_index(tmp_path):
    absent = tmp_path / "no-such-xplane"
    assert A.get_library_index(str(absent)) == {}
    # Nothing to cache — no sidecar junk for a bogus root.
    assert _sidecars(tmp_path) == []


# ── concurrency ──────────────────────────────────────────────────────
def test_concurrent_cold_builds_parse_once(tmp_path):
    """Threads that miss the memo together must wait for the first build
    (the object readers' per-DSF lock precedent), not each re-parse every
    library.txt."""
    root = _install(tmp_path, _PACKS, ini_order=["Alpha", "Bravo"])
    A._LIB_INDEX_CACHE.clear()
    original = A._parse_library_txt
    parsed: list[str] = []
    barrier = threading.Barrier(4)

    def slow_parse(lib_path, index):
        parsed.append(lib_path)
        return original(lib_path, index)

    A._parse_library_txt = slow_parse
    results: list[dict] = []
    try:
        def worker():
            barrier.wait()
            results.append(A.get_library_index(str(root)))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        A._parse_library_txt = original

    assert len(parsed) == 2                # one build total, not four
    assert all(result is results[0] for result in results)
    assert results[0] == _fresh_parse(root)


# ── placement → lon/lat transform ────────────────────────────────────
def test_footprint_lonlat_heading_rotation(tmp_path):
    root = _make_xplane_root(tmp_path)
    pack = root / "Custom Scenery" / "P"
    pack.mkdir()
    (pack / "h.agp").write_text(_AGP_60x60)
    virtual = "lib/airport/Common_Elements/Hangars/T.agp"
    (pack / "library.txt").write_text(f"EXPORT {virtual}\th.agp\n")

    lon0, lat0 = -81.0, 28.0
    ring0 = A.agp_footprint_lonlat(virtual, lon0, lat0, 0.0, str(root))
    ring90 = A.agp_footprint_lonlat(virtual, lon0, lat0, 90.0, str(root))
    assert ring0 and len(ring0) == 4
    assert ring90 and len(ring90) == 4

    # The local east extent at heading 0 should become a (south-going)
    # north extent at heading 90: the lon-span and lat-span swap roughly.
    def span(ring):
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        m_per_deg = A._LAT_M_PER_DEG
        lon_m = (max(lons) - min(lons)) * m_per_deg * math.cos(
            math.radians(lat0))
        lat_m = (max(lats) - min(lats)) * m_per_deg
        return lon_m, lat_m

    lon_m0, lat_m0 = span(ring0)
    lon_m90, lat_m90 = span(ring90)
    assert lon_m0 == pytest.approx(lat_m90, abs=0.5)
    assert lat_m0 == pytest.approx(lon_m90, abs=0.5)


# ── DSF OBJECT walker ────────────────────────────────────────────────
_DSF_LINES = [
    "OBJECT_DEF lib/airport/Common_Elements/Hangars/Lg_Maint_Gray.agp\n",
    "OBJECT_DEF lib/cars/car_static.obj\n",
    "OBJECT_DEF lib/airport/Common_Elements/Hangars/Med_Gray_Hangar.agp\n",
    "OBJECT 0 -81.10 28.20 12.5\n",          # accepted (idx 0, agp)
    "OBJECT 1 -81.11 28.21 0.0\n",           # rejected (not agp)
    "OBJECT_MSL 2 -81.12 28.22 30.0 270.0\n",  # accepted, heading at tok[5]
    "OBJECT 0 -81.13 28.23 90.0\n",          # second placement of idx 0
]


def test_object_walker_filters_and_parses_heading():
    placements = _read_dsf_object_placements(
        _DSF_LINES, A.is_agp_building_def)
    # idx 1 (the .obj) is filtered out; 3 agp placements remain.
    assert len(placements) == 3
    paths = {p[0].split("/")[-1] for p in placements}
    assert paths == {"Lg_Maint_Gray.agp", "Med_Gray_Hangar.agp"}
    # Plain OBJECT heading = tok[4].
    first = placements[0]
    assert first[1:] == pytest.approx((-81.10, 28.20, 12.5))
    # OBJECT_MSL heading = tok[5] (after the elevation field).
    msl = [p for p in placements if p[3] == 270.0]
    assert msl and msl[0][1] == pytest.approx(-81.12)


def test_object_walker_no_accepted_defs():
    lines = ["OBJECT_DEF lib/cars/car_static.obj\n",
             "OBJECT 0 -81.0 28.0 0.0\n"]
    assert _read_dsf_object_placements(lines, A.is_agp_building_def) == []


def test_is_agp_building_def_prefix_and_ext():
    assert A.is_agp_building_def(
        "lib/airport/Common_Elements/Hangars/Foo.agp")
    # wrong extension
    assert not A.is_agp_building_def(
        "lib/airport/Common_Elements/Hangars/Foo.obj")
    # right ext, wrong prefix (not the hangars scope)
    assert not A.is_agp_building_def(
        "lib/airport/Common_Elements/Parking_Items/Row_of_Cars_2.agp")
