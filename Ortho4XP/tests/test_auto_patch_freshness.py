"""Auto-patch freshness — build-input stamps + rebuild-skip logic.

``driver._auto_patch_is_current`` reuses an existing ``*_auto.patch.osm``
only when every input that can change the emitted patch is unchanged.
This module proves BOTH directions for each of them: unchanged input
reuses, changed input rebuilds.

Inputs covered (owner requirement 2026-07-24):

1. the selected apt.dat (path + mtime)
2. the airport scenery pack's DSF file(s) the build read
3. any config setting / gate that affects the emitted patch
4. the DEM inputs (source spec, elevation/smoothing settings, baked
   airport-elevation insets)
5. the CIFP data
6. the pack supplying the apt.dat being DISABLED in scenery_packs.ini
7. the Ortho4XP engine version

Plus the invariants around them: an old-format patch (legacy stamps
only) rebuilds exactly once and is then stable, ``to_osm`` writes
atomically so an interrupted write cannot leave a valid-looking
truncated patch, ``O4_AUTO_PATCH_REBUILD=1`` still forces, and manual
patches still suppress auto-patching entirely.

Everything is hermetic: tmp_path only, no network, no X-Plane install.
"""
import os
import types
from pathlib import Path

import pytest

import auto_patch.driver as driver
import auto_patch.osm_load as osm_load
import auto_patch.provenance as provenance
from auto_patch.driver import _auto_patch_is_current
from auto_patch.layout import PavementLayout, read_patch_source


# ──────────────────────────────────────────────────────────────────────
# Fixtures — a fake X-Plane install and a stamped patch
# ──────────────────────────────────────────────────────────────────────
TILE_LAT, TILE_LON = 40, -100


def _make_apt_dat(tmp_path: Path, name: str = "apt.dat") -> Path:
    p = tmp_path / name
    p.write_text("I\n1000 Version\n1 100 0 0 KFAKE Fake Airport\n")
    return p


def _touch_newer(path: Path, delta: float = 10.0) -> None:
    """Move a file's mtime forward — an in-place content update."""
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + delta))


@pytest.fixture
def fresh_env(monkeypatch):
    monkeypatch.delenv("O4_AUTO_PATCH_REBUILD", raising=False)


class FakeInstall:
    """A minimal X-Plane tree + tile object the freshness gate can read."""

    def __init__(self, root: Path):
        self.root = root
        self.custom_scenery = root / "Custom Scenery"
        self.pack = self.custom_scenery / "TestPack"
        self.earth_nav_data = self.pack / "Earth nav data"
        self.earth_nav_data.mkdir(parents=True)
        self.apt_dat = _make_apt_dat(self.earth_nav_data)
        self.ini = self.custom_scenery / "scenery_packs.ini"
        self.set_pack_enabled(True)

        # The pack's DSF for the airport's tile, at the real
        # <Earth nav data>/<10deg block>/<tile>.dsf layout.
        block = self.earth_nav_data / "+40-100"
        block.mkdir()
        self.dsf = block / "+40-100.dsf"
        self.dsf.write_bytes(b"XPLNEDSF-not-really")

        cifp_dir = root / "Custom Data" / "CIFP"
        cifp_dir.mkdir(parents=True)
        self.cifp = cifp_dir / "KFAKE.dat"
        self.cifp.write_text("SUSAP KFAKEK2G RW09 ...\n")

        # DEM inputs: a base raster plus one cached airport-elevation
        # inset that "baked" into the tile DEM.
        self.dem_source = root / "Elevation_data" / "N40W100.hgt"
        self.dem_source.parent.mkdir(parents=True)
        self.dem_source.write_bytes(b"\0" * 64)
        self.inset = root / "Airport_mod_cache" / "KFAKE_3DEP.tif"
        self.inset.parent.mkdir(parents=True)
        self.inset.write_bytes(b"\0" * 64)
        self.tile = self.make_tile()

    # -- scenery_packs.ini -------------------------------------------
    def set_pack_enabled(self, enabled: bool) -> None:
        keyword = "SCENERY_PACK" if enabled else "SCENERY_PACK_DISABLED"
        self.ini.write_text(
            "I\n1000 Version\nSCENERY_PACK_INI\n\n"
            f"{keyword} Custom Scenery/TestPack/\n")

    # -- tile / DEM ---------------------------------------------------
    def make_tile(self, **overrides):
        dem = types.SimpleNamespace(
            source_path=str(self.dem_source) + ";" + str(self.inset),
            airport_inset_provenance=[
                {"icao": "KFAKE", "path": str(self.inset),
                 "provider": "3DEP", "source_ids": ["x"]},
            ],
        )
        settings = dict(
            lat=TILE_LAT, lon=TILE_LON, dem=dem,
            custom_dem="", fill_nodata=True, elevation_level="auto",
            elevation_coastline_band_km=5.0, apt_smoothing_pix=8,
            apt_smoothing_auto=True, airport_elevation_insets=True,
            airport_elevation_providers="auto", airport_elevation_level=10,
            airport_elevation_inset_margin_m=1500.0,
            airport_elevation_inset_feather_m=60.0, airport_inset_water=True,
            working_grid_arc_seconds=1.0,
        )
        settings.update(overrides)
        self.tile = types.SimpleNamespace(**settings)
        return self.tile

    # -- patch emission ------------------------------------------------
    def emit_patch(self, path: Path, *, stamped: bool = True,
                   dsf_sources=..., dsf_tiles=...) -> Path:
        """Write a patch exactly as a driver-driven build would."""
        layout = PavementLayout(icao="KFAKE", anchor=(40.0, -100.0),
                                apt_dat_path=str(self.apt_dat))
        if stamped:
            layout.freshness = driver._freshness_stamps_now(
                self.tile, str(self.root), "KFAKE", str(self.apt_dat),
                str(self.cifp))
            layout.dsf_sources_read = (
                [str(self.dsf)] if dsf_sources is ... else dsf_sources)
            layout.dsf_tiles_scanned = (
                [(TILE_LAT, TILE_LON)] if dsf_tiles is ... else dsf_tiles)
        layout.to_osm(str(path))
        return path

    def is_current(self, path: Path) -> bool:
        return _auto_patch_is_current(str(path), str(self.root), "KFAKE",
                                      tile=self.tile, cifp_file=str(self.cifp))


@pytest.fixture
def install(tmp_path, monkeypatch, fresh_env):
    """A fake install whose apt.dat is what the selector returns."""
    fake = FakeInstall(tmp_path / "X-Plane 12")
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda xp_root, icao: str(fake.apt_dat))
    return fake


@pytest.fixture
def patch_file(install, tmp_path):
    """A freshly built, fully stamped patch — the reuse baseline."""
    path = install.emit_patch(tmp_path / "KFAKE_auto.patch.osm")
    assert install.is_current(path), "a just-built patch must be current"
    return path


# ──────────────────────────────────────────────────────────────────────
# Provenance stamp round-trip
# ──────────────────────────────────────────────────────────────────────
def _emit_legacy_patch(tmp_path: Path, apt_dat: Path | None) -> Path:
    """A patch with the two LEGACY stamps only (no freshness block)."""
    layout = PavementLayout(
        icao="KFAKE", anchor=(40.0, -100.0),
        apt_dat_path=str(apt_dat) if apt_dat else None)
    patch = tmp_path / "KFAKE_auto.patch.osm"
    layout.to_osm(str(patch))
    return patch


def test_to_osm_stamps_apt_dat_provenance(tmp_path):
    apt = _make_apt_dat(tmp_path)
    patch = _emit_legacy_patch(tmp_path, apt)

    meta = read_patch_source(str(patch))
    assert meta is not None
    assert meta["apt_dat"] == str(apt)
    assert meta["apt_dat_mtime"] == pytest.approx(
        os.path.getmtime(apt), abs=1e-6)


def test_to_osm_stamp_survives_spaces_and_quotes_in_path(tmp_path):
    pack = tmp_path / "Pilot's Custom Scenery"
    pack.mkdir()
    apt = _make_apt_dat(pack)
    patch = _emit_legacy_patch(tmp_path, apt)

    # The attribute value must stay quote-free (percent-encoded) so
    # the single-quote-delimited OSM line parsers are unaffected.
    header = patch.read_text().splitlines()[1]
    assert "<osm " in header
    assert header.count("'") % 2 == 0
    meta = read_patch_source(str(patch))
    assert meta["apt_dat"] == str(apt)


def test_read_patch_source_none_without_stamp(tmp_path):
    patch = _emit_legacy_patch(tmp_path, None)
    assert read_patch_source(str(patch)) is None
    assert read_patch_source(str(tmp_path / "missing.osm")) is None


def test_freshness_stamps_round_trip(install, tmp_path):
    patch = install.emit_patch(tmp_path / "KFAKE_auto.patch.osm")
    header = patch.read_text().splitlines()[1]
    # Every stamp is present, and none of them can break the
    # single-quote-delimited attribute syntax the OSM readers assume.
    assert header.count("'") % 2 == 0
    stamped = read_patch_source(str(patch))["freshness"]
    assert set(stamped) == set(provenance.FRESHNESS_KEYS)
    assert stamped["o4_fresh_v"] == provenance.FRESHNESS_SCHEMA_VERSION
    for key, value in stamped.items():
        assert value and " " not in value and "'" not in value, key


# ──────────────────────────────────────────────────────────────────────
# Input 1 — the selected apt.dat (pre-existing behaviour, preserved)
# ──────────────────────────────────────────────────────────────────────
def test_current_when_same_apt_and_mtime(install, patch_file):
    assert install.is_current(patch_file)


def test_stale_when_apt_dat_touched(install, patch_file):
    _touch_newer(install.apt_dat)
    assert not install.is_current(patch_file)


def test_stale_when_different_apt_selected(install, patch_file, monkeypatch,
                                           tmp_path):
    newer_pack = tmp_path / "NewPack"
    newer_pack.mkdir()
    other = _make_apt_dat(newer_pack)
    monkeypatch.setattr(osm_load, "_pick_best_apt_dat_against_osm",
                        lambda xp_root, icao: str(other))
    assert not install.is_current(patch_file)


def test_stale_when_patch_missing_or_unstamped(install, tmp_path):
    missing = tmp_path / "nothing_auto.patch.osm"
    assert not install.is_current(missing)
    # No apt.dat stamp at all (pre-provenance patch) → rebuild.
    plain = tmp_path / "plain_auto.patch.osm"
    PavementLayout(icao="KFAKE", anchor=(40.0, -100.0)).to_osm(str(plain))
    assert not install.is_current(plain)


def test_stale_when_no_apt_selectable(install, patch_file, monkeypatch):
    monkeypatch.setattr(osm_load, "_pick_best_apt_dat_against_osm",
                        lambda xp_root, icao: None)
    assert not install.is_current(patch_file)


# ──────────────────────────────────────────────────────────────────────
# Input 2 — the scenery pack's DSF file(s) the build read
# ──────────────────────────────────────────────────────────────────────
def test_dsf_unchanged_reuses(install, patch_file):
    assert install.is_current(patch_file)


def test_dsf_modified_rebuilds(install, patch_file):
    _touch_newer(install.dsf)
    assert not install.is_current(patch_file)


def test_dsf_resized_rebuilds(install, patch_file):
    st = os.stat(install.dsf)
    install.dsf.write_bytes(b"XPLNEDSF-not-really-but-longer")
    os.utime(install.dsf, (st.st_atime, st.st_mtime))   # size-only change
    assert not install.is_current(patch_file)


def test_dsf_removed_rebuilds(install, patch_file):
    install.dsf.unlink()
    assert not install.is_current(patch_file)


def test_dsf_added_for_scanned_tile_rebuilds(install, tmp_path):
    """A DSF that APPEARS after the build must also rebuild.

    The gate re-resolves the recorded TILE set against the pack rather
    than merely re-stat'ing the recorded file list, so a pack that gains
    a tile DSF is seen even though nothing the build read has changed.
    """
    install.dsf.unlink()
    patch = install.emit_patch(tmp_path / "KFAKE_auto.patch.osm",
                               dsf_sources=[])
    assert install.is_current(patch)
    install.dsf.write_bytes(b"XPLNEDSF-new-arrival")
    assert not install.is_current(patch)


def test_dsf_never_recorded_rebuilds(install, tmp_path):
    """A build that never recorded its DSF reads is unverifiable."""
    patch = install.emit_patch(tmp_path / "KFAKE_auto.patch.osm",
                               dsf_sources=None, dsf_tiles=None)
    stamped = read_patch_source(str(patch))["freshness"]
    assert stamped["o4_dsf"] == "?" and stamped["o4_dsf_tiles"] == "?"
    assert not install.is_current(patch)


def test_pipeline_records_dsf_reads_even_when_gated_off():
    """The pipeline must record ``[]`` (looked, read nothing), not None.

    ``None`` means "never recorded" and forces a rebuild forever; a build
    with the DSF pavement reader gated off has genuinely read no DSF and
    must still be cacheable.
    """
    import inspect

    from auto_patch import pipeline

    source = inspect.getsource(pipeline.build_airport_pavement)
    init = source.index("layout.dsf_sources_read = []")
    gate = source.index("if not LOAD_DSF_PAVEMENT:")
    assert init < gate, "the empty-list init must precede the skip gate"
    # The tile record must be built AS the sweep visits tiles, so an
    # aborted sweep never claims a tile it did not look in (which would
    # make the gate find an unread DSF and rebuild on every run).
    assert "layout.dsf_tiles_scanned.append(" in source


# ──────────────────────────────────────────────────────────────────────
# Input 3 — configuration (gates + standards/tuning constants)
# ──────────────────────────────────────────────────────────────────────
def test_config_gate_flip_rebuilds(install, patch_file, monkeypatch):
    monkeypatch.setenv("O4_CROWN_TAXI", "1")
    assert not install.is_current(patch_file)


def test_config_constant_change_rebuilds(install, patch_file, monkeypatch):
    from auto_patch import config

    monkeypatch.setattr(config, "RUNWAY_MAX_GRADE", 0.0125)
    assert not install.is_current(patch_file)


def test_config_role_table_change_rebuilds(install, patch_file, monkeypatch):
    from auto_patch import config

    limits = dict(config.ROLE_GRADE_LIMITS)
    limits["apron"] = 0.99
    monkeypatch.setattr(config, "ROLE_GRADE_LIMITS", limits)
    assert not install.is_current(patch_file)


@pytest.mark.parametrize(
    "name,value",
    [("LOG_VERBOSITY", 3), ("BUILD_PROGRESS", False),
     ("REPORT_GRADE_AUDIT", True), ("PARALLEL_AIRPORTS", False)])
def test_output_only_config_does_not_rebuild(install, patch_file, monkeypatch,
                                             name, value):
    """Verbosity / progress / audit / scheduling must NOT invalidate.

    Each of these is declared output-only at its definition site (the
    emitted patch is byte-identical either way); invalidating on them
    would rebuild every airport in the world when a user turns up the
    log level.
    """
    from auto_patch import config

    monkeypatch.setattr(config, name, value)
    assert install.is_current(patch_file)


@pytest.mark.parametrize(
    "gate", ["O4_LOG_VERBOSITY", "O4_BUILD_PROGRESS",
             "O4_REPORT_GRADE_AUDIT", "O4_PARALLEL_AIRPORTS"])
def test_output_only_gates_do_not_rebuild(install, patch_file, monkeypatch,
                                          gate):
    monkeypatch.setenv(gate, "1")
    assert install.is_current(patch_file)


def test_config_digest_covers_every_gate_and_constant():
    """The digest tracks config.py automatically — no hand-kept list."""
    gates = provenance.introspect_config_gates()
    assert len(gates) > 100, "gate introspection collapsed"
    # The exclusions are an argued, deliberately short list; anything added
    # here is a claim that the setting cannot change the emitted patch.
    assert provenance.CONFIG_DIGEST_EXCLUDED_CONSTANTS == frozenset({
        "LOG_VERBOSITY", "BUILD_PROGRESS", "REPORT_GRADE_AUDIT",
        "PARALLEL_AIRPORTS"})
    assert provenance.CONFIG_DIGEST_EXCLUDED_GATES == frozenset({
        "O4_LOG_VERBOSITY", "O4_BUILD_PROGRESS", "O4_REPORT_GRADE_AUDIT",
        "O4_PARALLEL_AIRPORTS", "O4_AUTO_PATCH_REBUILD",
        "O4_PATCH_PROVENANCE"})


def test_config_digest_sees_gates_without_readable_source(monkeypatch):
    """A FROZEN engine ships no config.py — a gate flip must still count.

    The packaged app has only the compiled module, so the source-scanning
    gate introspection returns nothing there.  The digest folds in the live
    ``O4_`` environment as well, which is what keeps a gate flip visible.
    """
    monkeypatch.setattr(provenance, "_config_source_path", lambda: None)
    monkeypatch.delenv("O4_CROWN_TAXI", raising=False)
    assert provenance.introspect_config_gates() == {}
    frozen_default = provenance.config_digest()
    monkeypatch.setenv("O4_CROWN_TAXI", "1")
    assert provenance.config_digest() != frozen_default


def test_config_digest_distinguishes_readable_from_unreadable_source(
        monkeypatch):
    with_source = provenance.config_digest()
    monkeypatch.setattr(provenance, "_config_source_path", lambda: None)
    assert provenance.config_digest() != with_source


def test_config_digest_ignores_the_force_rebuild_flag(install, patch_file,
                                                      monkeypatch):
    """The gate's own force flag is not a build input.

    ``O4_AUTO_PATCH_REBUILD=0`` (explicitly off) must read exactly like
    unset, or turning the flag off once would rebuild the world.
    """
    monkeypatch.setenv("O4_AUTO_PATCH_REBUILD", "0")
    assert install.is_current(patch_file)


# ──────────────────────────────────────────────────────────────────────
# Input 4 — DEM inputs
# ──────────────────────────────────────────────────────────────────────
def test_dem_inset_touched_rebuilds(install, patch_file):
    _touch_newer(install.inset)
    install.make_tile()
    assert not install.is_current(patch_file)


def test_dem_new_inset_baked_rebuilds(install, patch_file, tmp_path):
    second = install.root / "Airport_mod_cache" / "KFAKE_NED13.tif"
    second.write_bytes(b"\0" * 32)
    install.tile.dem.airport_inset_provenance.append(
        {"icao": "KFAKE", "path": str(second), "provider": "NED13"})
    assert not install.is_current(patch_file)


def test_dem_no_inset_differs_from_never_baked(install, tmp_path):
    """"Baked nothing" and "the bake never ran" must not compare equal.

    The silent-raw-DEM case (bake ran, found no inset) is a real,
    reproducible state; a DEM that never saw the bake step at all is a
    different one, and a patch stamped from either must not be reused
    against the other.
    """
    install.tile.dem.airport_inset_provenance = []
    patch = install.emit_patch(tmp_path / "KFAKE_auto.patch.osm")
    baked_none = read_patch_source(str(patch))["freshness"]["o4_dem"]
    assert baked_none.endswith(";insets:none")
    assert install.is_current(patch)

    del install.tile.dem.airport_inset_provenance
    never_baked = provenance.dem_fingerprint(install.tile, icao="KFAKE")
    assert never_baked.endswith(";insets:unbaked")
    assert never_baked != baked_none
    assert not install.is_current(patch)


def test_dem_inset_bake_record_is_filtered_to_this_airport(install):
    """The baked-inset facet names only THIS airport's insets."""
    other = install.root / "Airport_mod_cache" / "KOTHR_3DEP.tif"
    other.write_bytes(b"\0" * 16)
    install.tile.dem.airport_inset_provenance.append(
        {"icao": "KOTHR", "path": str(other), "provider": "3DEP"})
    stamp = provenance.dem_fingerprint(install.tile, icao="KFAKE")
    assert "KFAKE_3DEP" in stamp and "KOTHR_3DEP" not in stamp


def test_dem_inset_arriving_elsewhere_on_the_tile_rebuilds(install,
                                                           patch_file):
    """A new inset ANYWHERE on the tile invalidates every airport on it.

    Deliberate, not sloppy: the inset set drives the tile-wide working-grid
    densification, so an inset fetched for a neighbouring airport really can
    change this airport's sampled elevations.
    """
    other = install.root / "Airport_mod_cache" / "KOTHR_3DEP.tif"
    other.write_bytes(b"\0" * 16)
    install.tile.dem.source_path += ";" + str(other)
    assert not install.is_current(patch_file)


def test_dem_source_spec_change_rebuilds(install, patch_file):
    install.tile.dem.source_path = str(install.dem_source)   # inset dropped
    assert not install.is_current(patch_file)


def test_dem_base_raster_touched_rebuilds(install, patch_file):
    _touch_newer(install.dem_source)
    assert not install.is_current(patch_file)


@pytest.mark.parametrize(
    "setting,value",
    [("apt_smoothing_pix", 4), ("apt_smoothing_auto", False),
     ("elevation_level", "10"), ("custom_dem", "/some/where.tif"),
     ("airport_elevation_insets", False),
     ("airport_elevation_inset_feather_m", 90.0),
     ("working_grid_arc_seconds", 0.333), ("fill_nodata", False)])
def test_dem_setting_change_rebuilds(install, patch_file, setting, value):
    setattr(install.tile, setting, value)
    assert not install.is_current(patch_file)


def test_dem_fingerprint_ignores_derived_alt_raster(install, patch_file):
    """The gate must NOT key on the tile build's own output.

    ``Data<tile>.alt`` is rewritten by the vector/mesh steps of the very
    build that consumes these patches; keying on it would self-invalidate
    every patch on every tile build and destroy caching entirely.
    """
    derived = install.root / "Tiles" / "zOrtho4XP_+40-100" / "Data+40-100.alt"
    derived.parent.mkdir(parents=True)
    derived.write_bytes(b"\0" * 128)
    assert install.is_current(patch_file)
    _touch_newer(derived)
    derived.write_bytes(b"\0" * 256)
    assert install.is_current(patch_file), (
        "a rewritten derived .alt must never invalidate a patch")
    assert ".alt" not in provenance.dem_fingerprint(install.tile, "KFAKE")


def test_dem_missing_tile_rebuilds(install, patch_file):
    """A gate with no tile cannot verify the DEM inputs — fail safe."""
    assert not _auto_patch_is_current(
        str(patch_file), str(install.root), "KFAKE",
        cifp_file=str(install.cifp))


# ──────────────────────────────────────────────────────────────────────
# Input 5 — CIFP data
# ──────────────────────────────────────────────────────────────────────
def test_cifp_unchanged_reuses(install, patch_file):
    assert install.is_current(patch_file)


def test_cifp_updated_rebuilds(install, patch_file):
    _touch_newer(install.cifp)
    assert not install.is_current(patch_file)


def test_cifp_removed_rebuilds(install, patch_file):
    install.cifp.unlink()
    assert not install.is_current(patch_file)


def test_cifp_covers_both_readers(install):
    """Driver scan and elevation solve resolve CIFP independently."""
    files = driver._cifp_files_for(str(install.cifp), str(install.root),
                                   "KFAKE")
    # Same file by both routes → recorded once, not twice.
    assert len(files) == 1
    elsewhere = install.root / "elsewhere" / "KFAKE.dat"
    elsewhere.parent.mkdir()
    elsewhere.write_text("x\n")
    files = driver._cifp_files_for(str(elsewhere), str(install.root), "KFAKE")
    assert len(files) == 2


# ──────────────────────────────────────────────────────────────────────
# Input 6 — scenery_packs.ini enablement
# ──────────────────────────────────────────────────────────────────────
def test_pack_disabled_rebuilds(install, patch_file):
    install.set_pack_enabled(False)
    assert not install.is_current(patch_file)


def test_pack_reenabled_rebuilds_then_settles(install, tmp_path):
    install.set_pack_enabled(False)
    patch = install.emit_patch(tmp_path / "KFAKE_auto.patch.osm")
    assert install.is_current(patch)          # stable while disabled
    install.set_pack_enabled(True)
    assert not install.is_current(patch)      # coming back is a change too
    install.emit_patch(patch)
    assert install.is_current(patch)          # and then settles


def test_disabling_a_pack_moves_the_SELECTION_too(install):
    """Owner RULINGS 2026-09-17b closed the hole where only the freshness
    STAMP saw the toggle: with the selector honouring the ini, disabling
    the only pack invalidates the patch by BOTH routes — the stamp
    (``<pack>|disabled``) and the selected apt.dat PATH, which is now the
    fallback rather than the pack's."""
    from auto_patch_v2.airport import apt_dat as V2APT
    before = V2APT.find_apt_dat(str(install.root), "KFAKE")
    assert before == str(install.apt_dat)
    install.set_pack_enabled(False)
    after = V2APT.find_apt_dat(str(install.root), "KFAKE")
    assert after != str(install.apt_dat)
    assert driver._scenery_pack_state(str(install.apt_dat)) \
        == "TestPack|disabled"


def test_pack_state_reads_the_ini_keywords(install):
    state = driver._scenery_pack_state(str(install.apt_dat))
    assert state == "TestPack|enabled"
    install.set_pack_enabled(False)
    assert driver._scenery_pack_state(str(install.apt_dat)) \
        == "TestPack|disabled"


def test_pack_state_external_for_non_custom_scenery(tmp_path):
    """Global Airports / default scenery are not governed by the ini."""
    global_pack = (tmp_path / "Global Scenery" / "Global Airports"
                   / "Earth nav data")
    global_pack.mkdir(parents=True)
    apt = _make_apt_dat(global_pack)
    assert driver._scenery_pack_state(str(apt)) == "external"
    assert driver._scenery_pack_state(None) == "unknown"


def test_ini_parse_reports_order_and_disabled(tmp_path):
    ini = tmp_path / "scenery_packs.ini"
    ini.write_text(
        "I\n1000 Version\nSCENERY_PACK_INI\n\n"
        "SCENERY_PACK Custom Scenery/A/\n"
        "SCENERY_PACK_DISABLED Custom Scenery/B/\n"
        "SCENERY_PACK Custom Scenery/C/\n"
        "SCENERY_PACK Custom Scenery/A/\n")
    ordered, disabled = driver._parse_scenery_packs_ini(str(ini))
    assert ordered == ["A", "C"]          # order kept, duplicate collapsed
    assert disabled == {"B"}
    assert driver._parse_scenery_packs_ini(str(tmp_path / "none.ini")) \
        == ([], set())


# ──────────────────────────────────────────────────────────────────────
# Input 7 — engine version
# ──────────────────────────────────────────────────────────────────────
def test_engine_version_change_rebuilds(install, patch_file, monkeypatch):
    import O4_Version

    monkeypatch.setattr(O4_Version, "version", "1.50.999", raising=False)
    assert not install.is_current(patch_file)


def test_engine_version_stamped_from_o4_version(install, patch_file):
    import O4_Version

    stamped = read_patch_source(str(patch_file))["freshness"]["o4_engine"]
    assert stamped == O4_Version.version


# ──────────────────────────────────────────────────────────────────────
# Old-format patches, forced rebuilds, atomic writes
# ──────────────────────────────────────────────────────────────────────
def test_old_format_patch_rebuilds_once_then_is_stable(install, tmp_path):
    """A pre-freshness patch (legacy stamps only) rebuilds exactly once."""
    patch = tmp_path / "KFAKE_auto.patch.osm"
    _emit_legacy_patch(tmp_path, install.apt_dat)
    legacy = read_patch_source(str(patch))
    assert legacy["apt_dat"] == str(install.apt_dat)
    assert legacy["freshness"] == {}
    assert not install.is_current(patch)

    install.emit_patch(patch)             # the one rebuild
    assert install.is_current(patch)
    assert install.is_current(patch)      # and no thrash afterwards


def test_unknown_schema_version_rebuilds(install, patch_file):
    """A stamp set this engine does not recognise is not comparable."""
    text = patch_file.read_text().replace(
        f"o4_fresh_v='{provenance.FRESHNESS_SCHEMA_VERSION}'",
        "o4_fresh_v='99'")
    patch_file.write_text(text)
    assert not install.is_current(patch_file)


def test_force_rebuild_env_overrides(install, patch_file, monkeypatch):
    monkeypatch.setenv("O4_AUTO_PATCH_REBUILD", "1")
    assert not install.is_current(patch_file)


def test_repeated_gate_calls_do_not_thrash(install, patch_file):
    """The steady state is stable: nothing in the gate perturbs its inputs."""
    for _ in range(5):
        assert install.is_current(patch_file)


def _stray_temp_files(patch: Path) -> list[str]:
    """Anything left next to a patch that is not a NAMED artifact of it.

    ``<patch>.axes.json`` is the law-contract sidecar, not a leftover:
    it is written on every successful emit (2026-08-05 — it used to be
    gated on ``LOG_VERBOSITY``, which made every default-verbosity
    census silently context-free) and ``check_grade`` / ``flex_audit``
    read it by that exact name.  Everything else beside a patch is the
    temp-file leak these tests exist to catch.
    """
    named = {patch.name, patch.name + ".axes.json"}
    return sorted(p.name for p in patch.parent.iterdir()
                  if p.name not in named)


def test_atomic_write_leaves_no_temp_files(install, tmp_path):
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    patch = install.emit_patch(patch_dir / "KFAKE_auto.patch.osm")
    assert patch.read_text().rstrip().endswith("</osm>")
    assert _stray_temp_files(patch) == []


def test_atomic_write_keeps_the_readable_file_mode(install, tmp_path):
    """The temp-file write must not silently make patches owner-only.

    ``tempfile.mkstemp`` creates 0600 and ``os.replace`` carries that mode
    to the destination — a patch dir full of 0600 files is a real change
    from the plain write this replaced.
    """
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    patch = install.emit_patch(patch_dir / "KFAKE_auto.patch.osm")
    mode = os.stat(patch).st_mode & 0o777
    assert mode & 0o044, f"new patch is not group/other readable: {mode:o}"

    os.chmod(patch, 0o640)                     # a mode the user chose
    install.emit_patch(patch)
    assert os.stat(patch).st_mode & 0o777 == 0o640, "rewrite lost the mode"


def test_interrupted_write_keeps_the_previous_patch(install, tmp_path,
                                                    monkeypatch):
    """A write killed mid-flight must not leave a truncated patch.

    A truncated patch keeps a valid-looking header, so the freshness gate
    would keep reusing the fragment forever and the mesher would consume
    it.  The temp-file + rename write makes that unreachable.
    """
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    patch = install.emit_patch(patch_dir / "KFAKE_auto.patch.osm")
    good = patch.read_text()

    import auto_patch.layout as layout_module

    def _boom(src, dst):
        raise OSError("simulated crash between write and rename")

    monkeypatch.setattr(layout_module.os, "replace", _boom)
    with pytest.raises(OSError):
        install.emit_patch(patch)

    assert patch.read_text() == good, "the previous patch must survive"
    assert _stray_temp_files(patch) == [], \
        "the partial temp file must be cleaned up"
    assert install.is_current(patch)


def test_interrupted_write_when_the_body_fails(install, tmp_path, monkeypatch):
    """Same guarantee when the failure happens during the body write."""
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    patch = install.emit_patch(patch_dir / "KFAKE_auto.patch.osm")
    good = patch.read_text()

    import auto_patch.layout as layout_module

    real_fdopen = layout_module.os.fdopen

    class _HalfWriter:
        def __init__(self, handle):
            self._file = real_fdopen(handle, "w", encoding="utf-8")

        def write(self, text):
            self._file.write(text[:len(text) // 2])
            raise OSError("simulated disk full")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._file.close()
            return False

    monkeypatch.setattr(layout_module.os, "fdopen",
                        lambda handle, *a, **kw: _HalfWriter(handle))
    with pytest.raises(OSError):
        install.emit_patch(patch)

    assert patch.read_text() == good
    assert _stray_temp_files(patch) == []


# ──────────────────────────────────────────────────────────────────────
# Lazy tile-level inputs — taxiway/building/road extraction callables
# resolve only when an airport actually needs a rebuild
# ──────────────────────────────────────────────────────────────────────
class _CountingProvider:
    def __init__(self, value=None):
        self.calls = 0
        self.value = value

    def __call__(self):
        self.calls += 1
        return self.value


def _select(monkeypatch, path):
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda xp_root, icao: str(path) if path else None)


def _stub_the_engine(tmp_path, monkeypatch):
    """Put a STUB v2 pipeline under the real ``build_write_verify_one_v2``.

    v2 is the only engine (RULINGS 2026-09-13au), and the stamps this
    file's gate reads back are written by ``engine_v2._stamp_header``
    into the patch root — so the round-trip these tests defend only
    exists when the REAL v2 adapter runs.  The stub is the one in
    ``test_auto_patch_engine_dispatch`` (a single definition, shared,
    never a second copy): its ``build`` writes the patch + sidecar with
    ``config.header_extra`` on the ``<osm>`` root, exactly as the real
    emitter does.  Serial, and the pipeline's scratch under ``tmp_path``.
    """
    from auto_patch import config as CFG
    from auto_patch import engine_v2 as E2
    from test_auto_patch_engine_dispatch import _stub_v2

    monkeypatch.setattr(CFG, "PARALLEL_AIRPORTS", False, raising=False)
    monkeypatch.setattr(E2, "_scratch_dir",
                        lambda task: str(tmp_path / "v2scratch" / task["icao"]))
    return _stub_v2(monkeypatch)


def _drive_generate(tmp_path, monkeypatch, apt, tile=None,
                    cifp_file="dummy.dat"):
    """Run generate_auto_patches over one fake CIFP airport (KFAK).

    The CIFP/apt.dat plumbing is stubbed at the driver-module level;
    the build itself runs the real v2 adapter over a stub v2 pipeline,
    so the patch is written with the production freshness stamps.
    Returns (auto_patched, providers) so callers assert on both.
    """
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir(exist_ok=True)
    rwy = {"lat": 40.1, "lon": -100.2}
    monkeypatch.setattr(driver.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(driver, "discover_cifp_airports",
                        lambda path: {"KFAK": cifp_file})
    monkeypatch.setattr(driver, "parse_cifp_file",
                        lambda path: {"04": rwy, "22": rwy})
    monkeypatch.setattr(driver, "airport_in_tile",
                        lambda runways, lat, lon: True)
    monkeypatch.setattr(driver, "pair_runways",
                        lambda runways: [("04", rwy, "22", rwy)])
    monkeypatch.setattr(driver, "xplane_root_from_cifp_path",
                        lambda path: "xp_root")

    _stub_the_engine(tmp_path, monkeypatch)
    _select(monkeypatch, apt)

    if tile is None:
        tile = types.SimpleNamespace(lat=40.0, lon=-100.0, dem=None)
    providers = (_CountingProvider({}), _CountingProvider({}),
                 _CountingProvider(None))
    auto_patched = driver.generate_auto_patches(
        tile, str(tmp_path),
        taxiway_data=providers[0],
        building_data=providers[1],
        road_data=providers[2],
        mode="All",
    )
    return auto_patched, providers


def test_lazy_inputs_skipped_when_patch_current(
        tmp_path, monkeypatch, fresh_env):
    apt = _make_apt_dat(tmp_path)
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    tile = types.SimpleNamespace(lat=40.0, lon=-100.0, dem=None)
    layout = PavementLayout(icao="KFAK", anchor=(40.0, -100.0),
                            apt_dat_path=str(apt))
    layout.freshness = driver._freshness_stamps_now(
        tile, "xp_root", "KFAK", str(apt), "dummy.dat")
    layout.dsf_sources_read = []
    layout.dsf_tiles_scanned = []
    layout.to_osm(str(patch_dir / "KFAK_auto.patch.osm"))

    auto_patched, providers = _drive_generate(tmp_path, monkeypatch, apt,
                                              tile=tile)

    assert auto_patched == []  # reused, not rebuilt
    assert [p.calls for p in providers] == [0, 0, 0]


def test_generate_then_regenerate_reuses(tmp_path, monkeypatch, fresh_env):
    """End-to-end: a tile built twice in a row rebuilds nothing the
    second time.  This is the anti-thrash guarantee — the stamps a build
    WRITES must be exactly what the next gate COMPUTES."""
    apt = _make_apt_dat(tmp_path)
    tile = types.SimpleNamespace(lat=40.0, lon=-100.0, dem=None)

    first, _ = _drive_generate(tmp_path, monkeypatch, apt, tile=tile)
    assert first == ["KFAK"]

    second, providers = _drive_generate(tmp_path, monkeypatch, apt, tile=tile)
    assert second == []
    assert [p.calls for p in providers] == [0, 0, 0]


def test_lazy_inputs_resolved_once_on_rebuild(
        tmp_path, monkeypatch, fresh_env):
    apt = _make_apt_dat(tmp_path)
    # No existing auto-patch → KFAK needs a rebuild.
    auto_patched, providers = _drive_generate(tmp_path, monkeypatch, apt)

    assert auto_patched == ["KFAK"]
    assert [p.calls for p in providers] == [1, 1, 1]


def test_lazy_inputs_skipped_when_manual_patch_covers(
        tmp_path, monkeypatch, fresh_env):
    apt = _make_apt_dat(tmp_path)
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    # A user-provided manual patch (no _auto suffix) covers KFAK: the
    # airport must be skipped before CIFP parsing and the tile-level
    # extraction must never resolve.
    (patch_dir / "KFAK.patch.osm").write_text("<osm version='0.6'></osm>\n")

    auto_patched, providers = _drive_generate(tmp_path, monkeypatch, apt)

    assert auto_patched == []
    assert not (patch_dir / "KFAK_auto.patch.osm").exists()
    assert [p.calls for p in providers] == [0, 0, 0]


def test_manual_patch_still_wins_over_a_stale_auto_patch(
        tmp_path, monkeypatch, fresh_env):
    """Manual suppression runs BEFORE the freshness gate, so a stale
    auto-patch next to a manual one is still never rebuilt."""
    apt = _make_apt_dat(tmp_path)
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    (patch_dir / "KFAK.patch.osm").write_text("<osm version='0.6'></osm>\n")
    stale = patch_dir / "KFAK_auto.patch.osm"
    PavementLayout(icao="KFAK", anchor=(40.0, -100.0),
                   apt_dat_path=str(apt)).to_osm(str(stale))
    before = stale.read_text()

    auto_patched, providers = _drive_generate(tmp_path, monkeypatch, apt)

    assert auto_patched == []
    assert stale.read_text() == before
    assert [p.calls for p in providers] == [0, 0, 0]


# ──────────────────────────────────────────────────────────────────────
# Not buildable is not a failure (2026-09-03 beta regression)
# ──────────────────────────────────────────────────────────────────────
def test_no_apt_dat_airport_is_skipped_not_fatal(
        tmp_path, monkeypatch, fresh_env):
    """A CIFP airport no enabled apt.dat defines is SKIPPED, never queued.

    Pre-H1 the pipeline raised "No apt.dat found" per airport and the tile
    continued.  Under H1 (c1c5cccb) that raise became a ``build``-stage
    ``AutoPatchBuildFailure`` and aborted all three of the owner's
    2026-09-03 beta tiles (HECP / OTBT / LECU+LECV).  The gate now decides
    in the main process, before the airport is in ``tasks``: no
    exception, no ``AutoPatchFailed`` event, nothing built, nothing owed.
    """
    import O4_UI_Utils as UI
    events = []
    monkeypatch.setattr(UI, "auto_patch_failed",
                        lambda icao, stage, error: events.append(icao))
    lines = []
    monkeypatch.setattr(UI, "lvprint",
                        lambda level, *parts: lines.append(" ".join(
                            str(p) for p in parts)))

    auto_patched, providers = _drive_generate(tmp_path, monkeypatch, None)

    assert auto_patched == []
    assert events == []
    # The lazy OSM extraction is never paid for an airport that will not
    # be built.
    assert [p.calls for p in providers] == [0, 0, 0]
    assert any("KFAK" in line and "no apt.dat" in line for line in lines)
    assert not (tmp_path / "Patches" / "KFAK_auto.patch.osm").exists()


def test_no_apt_dat_neighbour_does_not_block_a_buildable_airport(
        tmp_path, monkeypatch, fresh_env):
    """The tile keeps building its other airports (HECA beside HECP)."""
    apt = _make_apt_dat(tmp_path)
    tile = types.SimpleNamespace(lat=40.0, lon=-100.0, dem=None)
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir(exist_ok=True)
    rwy = {"lat": 40.1, "lon": -100.2}
    monkeypatch.setattr(driver.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(driver, "discover_cifp_airports",
                        lambda path: {"KFAK": "a.dat", "KNON": "b.dat"})
    monkeypatch.setattr(driver, "parse_cifp_file",
                        lambda path: {"04": rwy, "22": rwy})
    monkeypatch.setattr(driver, "airport_in_tile",
                        lambda runways, lat, lon: True)
    monkeypatch.setattr(driver, "pair_runways",
                        lambda runways: [("04", rwy, "22", rwy)])
    monkeypatch.setattr(driver, "xplane_root_from_cifp_path",
                        lambda path: "xp_root")
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda xp_root, icao: str(apt) if icao == "KFAK" else None)
    _stub_the_engine(tmp_path, monkeypatch)
    auto_patched = driver.generate_auto_patches(
        tile, str(tmp_path), taxiway_data={}, building_data={},
        road_data=None, mode="All")

    assert auto_patched == ["KFAK"]
    assert (patch_dir / "KFAK_auto.patch.osm").exists()
    assert not (patch_dir / "KNON_auto.patch.osm").exists()


# ──────────────────────────────────────────────────────────────────────
# ONE SELECTOR, ONE DATUM (lane ``aptstamp`` 2026-09-17)
#
# auto_patch used to carry TWO apt.dat policies: the gate/stamp
# re-derived v1's ``_pick_best_apt_dat_against_osm`` (custom pack with a
# 1201/1202 taxi network, ELSE Global Airports) while the BUILD read
# ``auto_patch_v2.airport.apt_dat.find_apt_dat`` (§44 (1): the first
# custom pack with row-110 pavement, never a Global fallback).  Measured
# on the owner's install 2026-09-17: 225 of 1,327 CIFP airports carried
# by a custom pack disagreed, and for each of those the freshness gate
# watched a file the build never opened.
#
# These two packs are the disagreement in miniature: the custom pack has
# pavement but no taxi network, so the OLD gate fell back to Global
# Airports.  Editing the pack v2 READS must invalidate the patch;
# editing the one it does not must not.
# ──────────────────────────────────────────────────────────────────────
_PAVEMENT_BLOCK = (
    "110 1 0.25 0.00 pavement\n"
    "111 40.001000 -100.001000\n"
    "111 40.001000 -100.000000\n"
    "111 40.000000 -100.000000\n"
    "113 40.000000 -100.001000\n"
)
_TAXI_NETWORK = (
    "1201 40.000500 -100.000500 both 1 node_a\n"
    "1201 40.000600 -100.000600 both 2 node_b\n"
    "1202 1 2 twoway taxiway\n"
)


def _write_block(path: Path, *, pavement: bool, taxi: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "I\n1000 Version\n1 100 0 0 KFAKE Fake Airport\n"
    if pavement:
        text += _PAVEMENT_BLOCK
    if taxi:
        text += _TAXI_NETWORK
    text += "99\n"
    path.write_text(text)
    return path


@pytest.fixture
def two_pack_install(tmp_path, fresh_env):
    """A FakeInstall plus the two disagreeing packs, NO selector stub."""
    fake = FakeInstall(tmp_path / "X-Plane 12")
    # v1's candidate walk reads every Custom Scenery pack: FakeInstall's
    # own bare ``TestPack`` must not be a candidate for either policy.
    fake.apt_dat.unlink()
    cs = fake.custom_scenery
    fake.pack_apt = _write_block(
        cs / "A Custom Pack" / "Earth nav data" / "apt.dat",
        pavement=True, taxi=False)
    fake.global_apt = _write_block(
        cs / "Global Airports" / "Earth nav data" / "apt.dat",
        pavement=True, taxi=True)
    return fake


def _selected(root: Path) -> str:
    """Exactly what ``driver.generate_auto_patches`` selects (:1467)."""
    return osm_load._pick_best_apt_dat_against_osm(str(root), "KFAKE")


def test_gate_selector_is_the_build_selector(two_pack_install):
    """The gate's datum IS what v2 will read — one function, one answer."""
    from auto_patch_v2.airport.apt_dat import find_apt_dat
    root = str(two_pack_install.root)
    assert find_apt_dat(root, "KFAKE") == str(two_pack_install.pack_apt)
    assert _selected(two_pack_install.root) == find_apt_dat(root, "KFAKE")


def _two_pack_patch(fake, tmp_path) -> Path:
    """A patch stamped the way the driver stamps one (task apt.dat =
    what the selector answered), with the DSF half empty."""
    fake.apt_dat = Path(_selected(fake.root))
    patch = fake.emit_patch(tmp_path / "KFAKE_auto.patch.osm",
                            dsf_sources=[], dsf_tiles=[])
    assert fake.is_current(patch), "a just-built patch must be current"
    return patch


def test_editing_the_apt_dat_v2_read_invalidates_the_patch(
        two_pack_install, tmp_path):
    patch = _two_pack_patch(two_pack_install, tmp_path)
    _touch_newer(two_pack_install.pack_apt)
    assert not two_pack_install.is_current(patch)


def test_editing_the_apt_dat_v2_did_not_read_leaves_the_patch_current(
        two_pack_install, tmp_path):
    patch = _two_pack_patch(two_pack_install, tmp_path)
    _touch_newer(two_pack_install.global_apt)
    assert two_pack_install.is_current(patch)


def test_stamped_pack_is_the_pack_v2_reads(two_pack_install, tmp_path):
    """``o4_apt_dat`` / ``o4_pack`` name the CUSTOM pack, not Global."""
    patch = _two_pack_patch(two_pack_install, tmp_path)
    meta = read_patch_source(str(patch))
    assert meta["apt_dat"] == str(two_pack_install.pack_apt)
    assert meta["freshness"]["o4_pack"].startswith("A%20Custom%20Pack|")


def test_apt_dat_reads_are_utf8_not_locale(tmp_path, monkeypatch):
    """v2's apt.dat reads pin utf-8 (v1's reader always has): a frozen
    app with no LANG must not decode a pack's non-ASCII name its own
    way."""
    import auto_patch_v2.airport.apt_dat as v2_apt
    p = tmp_path / "apt.dat"
    p.write_bytes(
        "I\n1000 Version\n1 100 0 0 KFAKE Aérodrome Fâké\n99\n"
        .encode("utf-8"))
    opened = {}
    real_open = open

    def _spy(path, *a, **kw):
        opened.update(kw)
        return real_open(path, *a, **kw)

    monkeypatch.setattr(v2_apt, "open", _spy, raising=False)
    assert v2_apt.file_has_airport(str(p), "KFAKE")
    assert opened.get("encoding") == "utf-8"
    block = v2_apt.read_airport_block(str(p), "KFAKE")
    assert opened.get("encoding") == "utf-8"
    assert "Aérodrome Fâké" in "\n".join(block)


# ──────────────────────────────────────────────────────────────────────
# Input 1b — §44's BORROWED Global Airports apt.dat
# (lane ``borrowstamp``, the follow-up chip of RULINGS 2026-09-17a)
#
# The borrow is decided in v2's load stage, so ``pipeline/build.py``
# writes ``o4_apt_dat_borrowed`` / ``o4_apt_dat_borrowed_mtime`` into
# the ``<osm>`` header itself.  v1's ``to_osm`` (what these fixtures
# emit through) never writes them, so the header attribute is added
# here exactly as v2's emitter renders it — through the emitter's OWN
# attribute quoter, so the encoding under test is the shipped one.
# ──────────────────────────────────────────────────────────────────────
def _add_header_attrs(patch: Path, **attrs: str) -> Path:
    """Append ``<osm>`` root attributes, rendered by v2's emitter."""
    from auto_patch_v2.emit.osm_adapter import _q
    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if "<osm " in line:
            head, sep, tail = line.rstrip("\n").rpartition(">")
            assert sep, line
            extra = " ".join(f"{k}={_q(v)}" for k, v in attrs.items())
            lines[i] = f"{head} {extra}>{tail}\n"
            break
    else:                                                # pragma: no cover
        raise AssertionError("no <osm> root element")
    patch.write_text("".join(lines), encoding="utf-8")
    return patch


@pytest.fixture
def global_apt(tmp_path):
    """A stand-in Global Airports apt.dat to borrow from."""
    d = tmp_path / "Global Scenery" / "Global Airports" / "Earth nav data"
    d.mkdir(parents=True)
    return _make_apt_dat(d)


def _borrowed_patch(install, tmp_path, global_apt, *, with_mtime=True) -> Path:
    """A patch that BORROWED ``global_apt``, stamped as v2 stamps one."""
    from auto_patch_v2.pipeline.build import borrowed_apt_dat_stamp
    patch = install.emit_patch(tmp_path / "KFAKE_auto.patch.osm")
    attrs = {"o4_apt_dat_borrowed": str(global_apt)}
    if with_mtime:
        attrs.update(borrowed_apt_dat_stamp(str(global_apt)))
    return _add_header_attrs(patch, **attrs)


def test_borrowed_stamp_renders_like_the_selected_apt_dat_mtime(global_apt):
    from auto_patch_v2.pipeline.build import borrowed_apt_dat_stamp
    stamp = borrowed_apt_dat_stamp(str(global_apt))
    assert stamp == {"o4_apt_dat_borrowed_mtime":
                     f"{os.path.getmtime(global_apt):.6f}"}
    # nothing borrowed, and a path that does not stat(): no key at all
    assert borrowed_apt_dat_stamp("") == {}
    assert borrowed_apt_dat_stamp(None) == {}
    assert borrowed_apt_dat_stamp(str(global_apt) + ".gone") == {}


def test_borrowed_keys_round_trip_through_read_patch_source(
        install, tmp_path):
    """The path rides RAW (XML-escaped), not percent-encoded — and comes
    back byte-identical through spaces and an apostrophe."""
    odd = tmp_path / "Pilot's Global Scenery"
    odd.mkdir()
    borrowed = _make_apt_dat(odd, "apt.dat")
    patch = _borrowed_patch(install, tmp_path, borrowed)
    header = patch.read_text().splitlines()[1]
    assert "o4_apt_dat_borrowed='" in header and "&apos;" in header
    assert header.count("'") % 2 == 0
    meta = read_patch_source(str(patch))
    assert meta["apt_dat_borrowed"] == str(borrowed)
    assert meta["apt_dat_borrowed_mtime"] == pytest.approx(
        os.path.getmtime(borrowed), abs=1e-6)


def test_borrowed_keys_do_not_capture_the_selected_apt_dat(
        install, tmp_path, global_apt):
    """``o4_apt_dat`` / ``o4_apt_dat_mtime`` must keep NOT matching the
    longer borrowed names (and vice versa)."""
    patch = _borrowed_patch(install, tmp_path, global_apt)
    meta = read_patch_source(str(patch))
    assert meta["apt_dat"] == str(install.apt_dat)
    assert meta["apt_dat_mtime"] == pytest.approx(
        os.path.getmtime(install.apt_dat), abs=1e-6)
    assert meta["apt_dat_borrowed"] == str(global_apt)
    assert meta["apt_dat_borrowed"] != str(install.apt_dat)


def test_current_when_borrowed_apt_dat_untouched(install, tmp_path,
                                                 global_apt):
    patch = _borrowed_patch(install, tmp_path, global_apt)
    assert install.is_current(patch)


def test_stale_when_borrowed_apt_dat_touched(install, tmp_path, global_apt):
    """THE DEFECT: a Global Airports update in place left a borrowed
    patch reading current."""
    patch = _borrowed_patch(install, tmp_path, global_apt)
    assert install.is_current(patch)
    _touch_newer(global_apt)
    assert not install.is_current(patch)


def test_stale_when_borrowed_apt_dat_missing(install, tmp_path, global_apt):
    patch = _borrowed_patch(install, tmp_path, global_apt)
    global_apt.unlink()
    assert not install.is_current(patch)


def test_stale_when_borrowed_without_the_mtime_key(install, tmp_path,
                                                   global_apt):
    """A patch that borrowed but carries no mtime key rebuilds ONCE
    (fail-safe) — that is how the key is acquired."""
    patch = _borrowed_patch(install, tmp_path, global_apt, with_mtime=False)
    meta = read_patch_source(str(patch))
    assert meta["apt_dat_borrowed"] == str(global_apt)
    assert meta["apt_dat_borrowed_mtime"] is None
    assert not install.is_current(patch)


def test_empty_borrow_stamp_is_unaffected_by_a_global_update(
        install, tmp_path, global_apt):
    """NO MASS INVALIDATION (1): a patch that borrowed NOTHING carries
    ``o4_apt_dat_borrowed=''`` and never stats Global."""
    patch = install.emit_patch(tmp_path / "KFAKE_auto.patch.osm")
    _add_header_attrs(patch, o4_apt_dat_borrowed="")
    assert read_patch_source(str(patch))["apt_dat_borrowed"] == ""
    assert install.is_current(patch)
    _touch_newer(global_apt)
    assert install.is_current(patch)
    global_apt.unlink()
    assert install.is_current(patch)


def test_patch_without_either_borrow_key_stays_current(install, patch_file,
                                                       global_apt):
    """NO MASS INVALIDATION (2): a patch written before §44 carries
    neither key and reads exactly as before."""
    header = patch_file.read_text().splitlines()[1]
    assert "o4_apt_dat_borrowed" not in header
    meta = read_patch_source(str(patch_file))
    assert meta["apt_dat_borrowed"] == ""
    assert meta["apt_dat_borrowed_mtime"] is None
    assert install.is_current(patch_file)
    _touch_newer(global_apt)
    assert install.is_current(patch_file)


def test_borrow_gate_parses_no_apt_dat(install, tmp_path, global_apt,
                                       monkeypatch):
    """STAT ONLY: the gate must not read the borrowed file's CONTENT (no
    Global-block parse, no coverage union)."""
    patch = _borrowed_patch(install, tmp_path, global_apt)
    real_open = open
    target = os.path.realpath(global_apt)

    def _spy(path, *a, **kw):
        assert os.path.realpath(str(path)) != target, \
            "the freshness gate opened the borrowed apt.dat"
        return real_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", _spy)
    assert install.is_current(patch)
