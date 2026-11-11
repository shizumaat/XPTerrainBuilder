"""SAVE PACKAGE (#2014): one or several tiles → one ``.xptb`` file anyone
can share however they like, and whose install leaves nothing to download
but imagery.

A package is a ``tar.xz`` holding ``manifest.json``, ``ATTRIBUTION.txt``
and the tiles' downloaded data (:mod:`.inputs`).  The manifest names the
tiles, the airports each grades with the pack each was built against,
every source with its terms (``patch_library.terms``, owner Q319: a held
source refuses the save, a non-commercial one marks the whole package),
the engine and the COMPATIBILITY KEY, every member's sha256, size and
time, and the creator's optional title, name, notes and link (so a
commercial developer can brand it).  Paths of the creator's machine are
replaced by tokens (:mod:`.paths`) and a member that still names one is
refused.  The members are written with fixed owners, modes and times, so
two saves of the same data are the same bytes.

THE COMPATIBILITY KEY.  Data has no engine code in it, so a package does
not expire with an engine release the way a tile bundle (``xptb-1``)
does; what decides whether this engine can use the data is the SCHEMA of
each cache it carries (an OSM layer cache whose ``o4_tag_schema`` the
engine no longer reads is downloaded again; so is a superseded inset
stamp).  :func:`_schemas` lists them; the key is the format and those
schemas, and an install refuses a package whose schemas this engine does
not read.

xz preset 9 (:data:`XZ_PRESET`): on +30+031 the data is 21.1 MB at 9
against 23.3 MB at 6 in the same 7 s (it is mostly compressed already).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import time

import O4_File_Names as FNAMES

from . import PACKAGE_FORMAT, PACKAGE_SUFFIX, BundleRefused, inputs
from . import export as _export
from . import key as _key
from . import paths as _paths

__all__ = ["XZ_PRESET", "BRANDING", "key_parts", "package_name",
           "branding", "destination_path", "write", "save_package",
           "airports_of"]

#: xz preset of a package (module doc: measured).
XZ_PRESET = 9

#: The creator's optional manifest fields, and their longest length.
BRANDING = {"title": 120, "creator": 120, "notes": 2000, "url": 300}


def _schemas(tile) -> dict:
    """``{name: schema}`` of the caches this engine reads for ``tile``:
    each OSM layer's tag schema and the inset completion stamp's."""
    import O4_Airport_Elevation_Insets as INSETS
    import O4_Vector_Map as VMAP
    out = {"osm:" + spec[0]: spec[4]
           for spec in VMAP.osm_layer_warm_specifications(tile)}
    out["insets"] = INSETS.INSET_COMPLETION_SCHEMA
    return out


def airports_of(tiles, custom_build_dir: str = "") -> dict:
    """``{tile key: [icao, …]}``: the airports each tile grades — what the
    export dialog offers for an airport package."""
    out = {}
    for lat, lon in sorted({(int(a), int(b)) for a, b in tiles or ()}):
        tile = _export.load_tile(lat, lon, custom_build_dir)
        out[FNAMES.short_latlon(lat, lon)] = sorted(_key.graded_airports(tile))
    return out


def key_parts(tiles) -> dict:
    """The compatibility key's parts for loaded ``tiles``."""
    merged: dict = {}
    for tile in tiles:
        merged.update(_schemas(tile))
    return {"format": PACKAGE_FORMAT, "schemas": dict(sorted(merged.items()))}


def package_name(keys) -> str:
    """``XPTerrainBuilder_<tile>.xptb``, or ``…_<first>_<n>tiles.xptb``."""
    keys = sorted(keys)
    tail = keys[0] if len(keys) == 1 else "%s_%dtiles" % (keys[0], len(keys))
    return "XPTerrainBuilder_" + tail + PACKAGE_SUFFIX


def destination_path(out: str, keys) -> str:
    """``out`` when it names a ``.xptb`` file, else :func:`package_name` in it."""
    if out.lower().endswith(PACKAGE_SUFFIX):
        return out
    return os.path.join(out, package_name(keys))


def branding(fields: dict) -> dict:
    """The :data:`BRANDING` fields of ``fields``, trimmed."""
    return {name: str(fields.get(name) or "").strip()[:limit]
            for name, limit in BRANDING.items()}


def _tif_sources(paths) -> list:
    """The providers of every carried elevation raster with a sidecar or
    a provider-coded name (rings, bands, overlays, insets)."""
    return _export._provider_sources(
        [p for p in paths if p.lower().endswith((".tif", ".tiff"))])


def _sources(loaded, members) -> tuple:
    """``(sources with terms, licence)`` of the package (the gate)."""
    found: dict = {}
    for tile in loaded:
        for source in _export.sources(tile):
            found.setdefault((source["kind"], source["provider"]), source)
    for source in _tif_sources(path for _n, path in members):
        found.setdefault((source["kind"], source["provider"]), source)
    return _export.gate([found[k] for k in sorted(found)])


def _member_bytes(name: str, path: str, change, airports=None) -> bytes:
    with open(path, "rb") as handle:
        data = handle.read()
    if airports is not None and name.endswith(inputs.INSET_INDEX):
        doc = json.loads(data.decode("utf-8"))
        data = (json.dumps({k: v for k, v in doc.items()
                            if str(k).upper() in airports}, indent=2,
                           sort_keys=True) + "\n").encode("utf-8")
    return _paths.transform_file_bytes(name, data, change)


def _tile_entry(tile, names, airports=None) -> dict:
    graded = _key.airport_signatures(tile)
    return {"tile": FNAMES.short_latlon(tile.lat, tile.lon),
            "airports": {icao: row for icao, row in graded.items()
                         if airports is None or icao in airports},
            "data_snapshot": _export._snapshot(tile),
            "files": len(names)}


def _attribution(manifest: dict) -> bytes:
    from patch_library import terms as _terms
    title = manifest.get("title") or "XPTerrainBuilder package"
    lines = ["%s — tiles %s" % (title, ", ".join(
        t["tile"] for t in manifest["tiles"]))]
    if manifest.get("creator"):
        lines.append("Made by " + manifest["creator"])
    lines += ["", "This package holds map and elevation data from:"]
    lines += [_terms.source_line(s) for s in manifest["sources"]]
    lines += ["", _terms.statement(manifest["licence"], "package"), ""]
    return "\n".join(lines).encode("utf-8")


def _collect(loaded, airports=None) -> tuple:
    """``(members, per-tile names)``: ``[(name, path, tile key)]`` once
    each (neighbour rasters are shared by adjacent tiles)."""
    members, seen, per_tile = [], set(), {}
    for tile in loaded:
        key = FNAMES.short_latlon(tile.lat, tile.lon)
        names = inputs.files(tile.lat, tile.lon, airports)
        if not any(n.startswith("data/OSM_data/") for n, _p in names):
            raise BundleRefused(
                "Tile %s has no downloaded map data on this computer; build "
                "it first, then save its package." % key)
        per_tile[key] = [n for n, _p in names]
        for name, path in names:
            if name not in seen:
                seen.add(name)
                members.append((name, path, key))
    return sorted(members), per_tile


def _airport_tiles(loaded, airports) -> list:
    """The loaded tiles that grade one of ``airports`` (all without)."""
    if airports is None:
        return loaded
    keep = [t for t in loaded if set(_key.airport_signatures(t)) & airports]
    if not keep:
        raise BundleRefused("None of the chosen tiles grades %s."
                            % ", ".join(sorted(airports)))
    return keep


def write(out_path: str, manifest: dict, blobs: dict) -> str:
    """Write the package file: the manifest, the attribution and the
    members ``blobs`` (``{name: bytes}``), fixed metadata, atomically.

    :raises BundleRefused: the manifest would name the home folder."""
    manifest_bytes = (json.dumps(manifest, indent=1, sort_keys=True)
                      + "\n").encode("utf-8")
    if _paths.leftovers(manifest_bytes, (), (os.path.expanduser("~"),)):
        raise BundleRefused("the manifest would name your home folder; the "
                            "package was not saved")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    temporary = out_path + ".tmp"
    with tarfile.open(temporary, "w:xz", preset=XZ_PRESET) as tar:
        for name, data in (("manifest.json", manifest_bytes),
                           ("ATTRIBUTION.txt", _attribution(manifest))):
            tar.addfile(_export._info(name, len(data)), io.BytesIO(data))
        for name in sorted(blobs):
            tar.addfile(_export._info(name, len(blobs[name])),
                        io.BytesIO(blobs[name]))
    os.replace(temporary, out_path)
    return out_path


def save_package(tiles, out: str, custom_build_dir: str = "",
                 airports=None, **fields) -> dict:
    """ENGINE COMMAND ``package_save``: write the package of ``tiles``
    (``[(lat, lon)]``) to ``out`` (a ``.xptb`` path, or a folder it is
    written into under :func:`package_name`).  ``airports`` (ICAOs)
    makes an AIRPORT package (:mod:`.inputs`): only those airports'
    insets and patches, and only the tiles that grade them.
    ``fields``: the optional :data:`BRANDING` fields.

    :returns: ``{"path", "bytes", "data_bytes", "key", "files", "tiles",
        "noncommercial", "seconds"}``
    :raises BundleRefused: no tile, a tile with no downloaded data, a held
        source, or a member that would carry a local path.
    """
    import O4_Config_Utils as CFG
    import O4_Version
    t0 = time.time()
    pairs_in = sorted({(int(a), int(b)) for a, b in tiles or ()})
    if not pairs_in:
        raise BundleRefused("Choose at least one tile to save in a package.")
    chosen = ({str(a).upper() for a in airports} if airports else None)
    loaded = _airport_tiles([_export.load_tile(lat, lon, custom_build_dir)
                             for lat, lon in pairs_in], chosen)
    members, per_tile = _collect(loaded, chosen)
    by_key = dict(zip(sorted(per_tile, key=FNAMES.parse_tile_key), loaded, strict=True))
    found, licence = _sources(loaded, [(n, p) for n, p, _k in members])
    home = os.path.expanduser("~")
    files, blobs = {}, {}
    for name, path, tile_key in members:
        tile = by_key[tile_key]
        pairs = _paths.roots(tile, CFG.custom_scenery_dir, _key.xplane_root(tile))
        data = _member_bytes(name, path,
                             lambda t, p=pairs: _paths.tokenise_text(t, p), chosen)
        if name.endswith((".json", ".osm")):
            left = _paths.leftovers(data, pairs, (home,))
            if left:
                raise BundleRefused("%s would carry a local path (%s); the "
                                    "package was not saved" % (name, left[0]))
        blobs[name] = data
        files[name] = {"bytes": len(data), "tile": tile_key,
                       "sha256": hashlib.sha256(data).hexdigest(),
                       "mtime_ns": os.stat(path).st_mtime_ns}
    parts = key_parts(loaded)
    manifest = {"format": PACKAGE_FORMAT, **branding(fields),
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "engine_version": getattr(O4_Version, "version", ""),
                "key": _key.bundle_key(parts), "key_parts": parts,
                "airports_only": sorted(chosen) if chosen else None,
                "tiles": [_tile_entry(by_key[k], per_tile[k], chosen)
                          for k in sorted(per_tile)],
                "sources": found, "licence": licence,
                "noncommercial": any(s["noncommercial"] for s in found),
                "imagery": "not included", "files": files,
                "data_bytes": sum(f["bytes"] for f in files.values())}
    out_path = write(destination_path(out, per_tile), manifest, blobs)
    return {"path": out_path, "bytes": os.path.getsize(out_path),
            "data_bytes": manifest["data_bytes"], "key": manifest["key"],
            "files": len(files), "tiles": sorted(per_tile),
            "noncommercial": manifest["noncommercial"],
            "seconds": round(time.time() - t0, 1)}
