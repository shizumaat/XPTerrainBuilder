"""§45 (18) — THE INSET MANIFEST READER FALLS BACK TO THE INSET'S OWN SIDECAR
(owner RULINGS 2026-09-15bo; defect measured on the KDFW build of 2026-09-15).

Every N32W098 sidecar of 2026-08-15 was minted by a writer that stamped
``native_resolution_m`` only — a key the USGS3DEP fetch never writes (it
writes ``resolution_m``) — so KDFW's composed 1 m 3DEP frame read
``(None, "base_tier")`` in :meth:`ProductionDem.source_pixel_m`,
``_source_class`` said ``coarse`` and ``_lidar_credible`` was False: a 1 m
lidar frame judged coarse by every consumer.

The twins here fix BOTH sides at their one derivation each:

* the READER — ``native_resolution_m``, else the entry's ``resolution_m``,
  else the inset's OWN ``<inset>.json``, else ``None`` as before;
* the WRITER (``O4_Airport_Elevation_Insets._inset_bake_provenance_entry``)
  — both keys stamped on every new entry.

The reader twins drive ``source_pixel_m`` on a hand-built ``_BakedTile``:
no raster, no corpus, no composition.
"""
import json
import types

import pytest

from auto_patch_v2.airport import dem_production as DP


def _dem(entries, icao="KDFW", out=None):
    """A ``ProductionDem`` with ONE baked tile carrying ``entries`` as its
    ``inset_provenance`` — constructed without ``__init__`` so nothing is
    composed and no corpus is touched."""
    dem = object.__new__(DP.ProductionDem)
    dem.icao = icao
    dem._out = out if out is not None else (lambda _m: None)
    dem.frame = types.SimpleNamespace(origin=(32.8968, -97.0380))
    tile = object.__new__(DP._BakedTile)
    tile.inset_provenance = list(entries)
    tile.overlay_provenance = {}
    dem._tiles = {(32, -98): tile}
    dem.tile = lambda lat, lon: dem._tiles.get((lat, lon))
    return dem


def _inset(tmp_path, name="KDFW_usgs3dep", sidecar=None):
    tif = tmp_path / f"{name}.tif"
    tif.write_bytes(b"\x00")
    if sidecar is not None:
        (tmp_path / f"{name}.json").write_text(json.dumps(sidecar))
    return str(tif)


# ── the reader ────────────────────────────────────────────────────────────
def test_the_0815_shaped_manifest_reads_the_insets_own_sidecar(tmp_path):
    """The DEFECT's exact shape: ``native_resolution_m: null``, no
    ``resolution_m`` — and the inset's own sidecar says 1.0."""
    path = _inset(tmp_path, sidecar={"provider": "USGS3DEP",
                                     "resolution_m": 1.0,
                                     "fetch_date": "2026-08-15"})
    lines = []
    dem = _dem([{"icao": "KDFW", "path": path, "provider": "USGS3DEP",
                 "native_resolution_m": None}], out=lines.append)
    assert dem.source_pixel_m() == (1.0, "inset")
    # ONE line, naming the key and the file
    assert len(lines) == 1
    assert "resolution_m" in lines[0] and path[:-4] + ".json" in lines[0]
    # and it is logged once, not once per call
    dem.source_pixel_m()
    assert len(lines) == 1


def test_lidar_credible_follows_from_the_sidecar_fallback(tmp_path):
    """The consequence the defect denied: 1.0 m is the LIDAR class."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import flat_source_class

    path = _inset(tmp_path, sidecar={"resolution_m": 1.0})
    dem = _dem([{"icao": "KDFW", "path": path, "native_resolution_m": None}])
    pixel, whence = dem.source_pixel_m()
    law = Law.for_airport("KDFW")
    assert whence == "inset"
    assert flat_source_class(law, pixel) == "lidar"
    assert pixel <= law.tables.flat_site.detector.lidar_credible_max_m


def test_the_entrys_own_resolution_m_is_preferred_over_the_sidecar(tmp_path):
    path = _inset(tmp_path, sidecar={"resolution_m": 30.0})
    lines = []
    dem = _dem([{"icao": "KDFW", "path": path, "native_resolution_m": None,
                 "resolution_m": 1.0}], out=lines.append)
    assert dem.source_pixel_m() == (1.0, "inset")
    assert len(lines) == 1 and "manifest entry's resolution_m" in lines[0]


def test_a_manifest_with_the_key_is_unchanged_and_silent(tmp_path):
    """A modern entry answers from ``native_resolution_m``: no sidecar is
    opened (the file here says something else) and nothing is logged."""
    path = _inset(tmp_path, sidecar={"resolution_m": 30.0})
    lines = []
    dem = _dem([{"icao": "KDFW", "path": path, "native_resolution_m": 1.0,
                 "resolution_m": 30.0}], out=lines.append)
    assert dem.source_pixel_m() == (1.0, "inset")
    assert lines == []


def test_no_sidecar_stays_none(tmp_path):
    path = _inset(tmp_path)                      # tif, no .json
    dem = _dem([{"icao": "KDFW", "path": path, "native_resolution_m": None}])
    assert dem.source_pixel_m() == (None, "base_tier")


@pytest.mark.parametrize("sidecar", [
    {"resolution_m": None},                      # the key, null
    {"resolution_m": "one metre"},               # unparseable
    {"resolution_m": 0.0},                       # not positive
    [1.0],                                       # not an object
])
def test_an_unusable_sidecar_stays_none(tmp_path, sidecar):
    path = _inset(tmp_path, sidecar=sidecar)
    dem = _dem([{"icao": "KDFW", "path": path, "native_resolution_m": None}])
    assert dem.source_pixel_m() == (None, "base_tier")


def test_a_corrupt_sidecar_does_not_raise(tmp_path):
    path = _inset(tmp_path)
    (tmp_path / "KDFW_usgs3dep.json").write_text("{not json")
    dem = _dem([{"icao": "KDFW", "path": path, "native_resolution_m": None}])
    assert dem.source_pixel_m() == (None, "base_tier")


def test_another_airports_entry_is_not_read(tmp_path):
    """The ICAO filter runs BEFORE the sidecar is opened (v1's
    ``provenance._entries_for_icao``)."""
    other = _inset(tmp_path, name="KDAL_usgs3dep",
                   sidecar={"resolution_m": 1.0})
    dem = _dem([{"icao": "KDAL", "path": other, "native_resolution_m": None}])
    assert dem.source_pixel_m() == (None, "base_tier")


def test_the_finest_of_several_entries_wins(tmp_path):
    fine = _inset(tmp_path, name="KDFW_usgs3dep", sidecar={"resolution_m": 1.0})
    coarse = _inset(tmp_path, name="KDFW_srtm", sidecar={"resolution_m": 30.0})
    dem = _dem([{"icao": "KDFW", "path": coarse, "native_resolution_m": None},
                {"icao": "KDFW", "path": fine, "native_resolution_m": None}])
    assert dem.source_pixel_m() == (1.0, "inset")


def test_the_overlay_still_answers_when_no_inset_does(tmp_path):
    dem = _dem([])
    dem._tiles[(32, -98)].overlay_provenance = {"target_resolution_m": 10.0}
    assert dem.source_pixel_m() == (10.0, "overlay")


# ── the writer ────────────────────────────────────────────────────────────
def test_the_writer_stamps_both_keys_from_resolution_m(tmp_path):
    import O4_Airport_Elevation_Insets as INSETS

    path = _inset(tmp_path, sidecar={"provider": "USGS3DEP",
                                     "resolution_m": 1.0,
                                     "fetch_date": "2026-08-15"})
    entry = INSETS._inset_bake_provenance_entry(path)
    assert entry["native_resolution_m"] == 1.0
    assert entry["resolution_m"] == 1.0
    # and such an entry needs no fallback at all
    dem = _dem([dict(entry, icao="KDFW")])
    assert dem.source_pixel_m() == (1.0, "inset")


def test_the_writer_stamps_both_keys_from_native_resolution_m(tmp_path):
    import O4_Airport_Elevation_Insets as INSETS

    path = _inset(tmp_path, name="CYXY_hrdem",
                  sidecar={"provider": "HRDEM", "native_resolution_m": 1.0})
    entry = INSETS._inset_bake_provenance_entry(path)
    assert entry["native_resolution_m"] == 1.0
    assert entry["resolution_m"] == 1.0


def test_the_writer_keeps_null_when_the_sidecar_states_neither(tmp_path):
    import O4_Airport_Elevation_Insets as INSETS

    path = _inset(tmp_path, name="KBNA_usgs3dep", sidecar={"provider": "X"})
    entry = INSETS._inset_bake_provenance_entry(path)
    assert entry["native_resolution_m"] is None
    assert entry["resolution_m"] is None
