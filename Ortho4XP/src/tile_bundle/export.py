"""EXPORT LIBRARY BUNDLE (#1699 phase 1): a built tile → one bundle file.

The tile must be exactly what its last build left (every step-reuse
record current, ``O4_Step_Reuse.stale_reason``) and built with the
default mesh settings (owner Q301).  The bundle is a ``tar.xz`` holding
``manifest.json`` (the match key and its parts, the step records, every
file's sha256, the sources and their licences), ``ATTRIBUTION.txt`` and
the files :mod:`.contents` names, every local path tokenised
(:mod:`.paths`).  The members are written with fixed owners, modes and
times, so two exports of the same tile are the same bytes.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import time

from . import FORMAT, BundleRefused, contents
from . import key as _key
from . import paths as _paths

__all__ = ["BUNDLE_SUFFIX", "XZ_PRESET", "export_tile",
           "load_tile"]

#: A tile bundle's file name ends so.
BUNDLE_SUFFIX = ".xptbundle"

#: xz preset: 6 (the default) is a fifth smaller than 1 on a mesh.
XZ_PRESET = 6

_STEP_NOUNS = {"vector": "vector data", "mesh": "mesh", "masks": "water masks"}


def _bundle_name(lat: int, lon: int) -> str:
    import O4_File_Names as FNAMES
    return "XPTerrainBuilder_%s%s" % (FNAMES.short_latlon(lat, lon),
                                     BUNDLE_SUFFIX)


def load_tile(lat: int, lon: int, custom_build_dir: str = ""):
    """The tile as a build reads it: its config over the global one."""
    import O4_Config_Utils as CFG
    tile = CFG.Tile(int(lat), int(lon), custom_build_dir or "")
    tile.read_from_config()
    return tile


def _require_current(tile) -> None:
    import O4_Step_Reuse as REUSE
    for step in REUSE.REUSABLE_STEPS:
        why = REUSE.stale_reason(tile, step)
        if why is not None:
            raise BundleRefused(
                "The tile's %s is not what its last build left (%s). Build "
                "the tile again, then export it." % (_STEP_NOUNS[step], why))


def _inset_providers(path: str) -> list:
    """The elevation providers one cached inset holds: the provider that
    DELIVERED it, from its sidecar (``<stem>.json``), and the surround or
    fill layers assembled into it.  The file name carries the ladder's
    ROOT code (``_usgs3dep.tif``), not the rung that delivered: KPDX's
    inset is Oregon DOGAMI lidar under a ``_usgs3dep`` name.  Only a
    raster with no readable sidecar is named by its file name."""
    try:
        with open(os.path.splitext(path)[0] + ".json",
                  encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, ValueError):
        meta = None
    if not isinstance(meta, dict) or not meta.get("provider"):
        stem = os.path.splitext(os.path.basename(path))[0]
        return [stem.rsplit("_", 1)[1].upper()] if "_" in stem else []
    layers = [meta.get("surround") or {}] + list(
        (meta.get("fills") or {}).get("layers") or ())
    codes = [meta["provider"]] + [layer.get("provider") for layer in layers
                                  if isinstance(layer, dict)]
    return [str(code).upper() for code in codes if code]


def _provider_sources(inset_paths) -> list:
    """The elevation providers of the cached insets, with their licences
    (``Providers/Elevation/<CODE>.elv``)."""
    import O4_Airport_Elevation_Insets as INSETS
    definitions = {code.upper(): definition for code, definition
                   in INSETS.initialize_elevation_providers_dict().items()}
    found = {}
    for path in inset_paths:
        for code in _inset_providers(path):
            definition = definitions.get(code) or {}
            found[code] = {"kind": "elevation", "provider": code,
                           "licence": definition.get("license", ""),
                           "credit": definition.get("attribution", "")}
    return [found[c] for c in sorted(found)]


def _sources(tile) -> list:
    import O4_Airport_Elevation_Insets as INSETS
    base = str(getattr(tile, "base_elevation_source", "") or "auto")
    return ([{"kind": "osm", "provider": "OpenStreetMap",
              "licence": "ODbL-1.0",
              "credit": "© OpenStreetMap contributors"},
             {"kind": "elevation", "provider": "base:" + base,
              "licence": "see the base elevation source", "credit": ""}]
            + _provider_sources(INSETS.list_cached_inset_dems(tile.lat,
                                                               tile.lon)))


def _month(paths) -> str:
    times = [os.path.getmtime(p) for p in paths if os.path.isfile(p)]
    return time.strftime("%Y-%m", time.gmtime(max(times))) if times else ""


def _snapshot(tile) -> dict:
    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES
    folder = FNAMES.osm_dir(tile.lat, tile.lon)
    osm = [os.path.join(folder, n) for n in os.listdir(folder)] \
        if os.path.isdir(folder) else []
    return {"osm": _month(osm),
            "elevation": _month(INSETS.list_cached_inset_dems(tile.lat,
                                                               tile.lon))}


def _attribution(manifest: dict) -> bytes:
    lines = ["Tile %s — XPTerrainBuilder tile bundle %s" % (
        manifest["tile"], manifest["key"]), "",
        "This bundle holds a terrain mesh and airport surfaces derived from:"]
    for source in manifest["sources"]:
        lines.append("- %s (%s)%s" % (
            source["provider"], source["licence"],
            ": " + source["credit"] if source["credit"] else ""))
    lines += ["", "The bundle is offered under the ODbL 1.0, the licence of "
              "the OpenStreetMap data it is built from.", ""]
    return "\n".join(lines).encode("utf-8")


def _info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size, info.mtime, info.mode = size, 0, 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def _sha_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _records(tile, change) -> dict:
    import O4_Step_Reuse as REUSE
    return {step: _paths._walk_strings(REUSE.committed_entry(tile, step), change)
            for step in REUSE.REUSABLE_STEPS}


def export_tile(lat: int, lon: int, out_dir: str,
                custom_build_dir: str = "") -> dict:
    """ENGINE COMMAND ``library_export_bundle``: write the tile's bundle
    into ``out_dir``.

    :returns: ``{"path", "bytes", "key", "files", "seconds"}``
    :raises BundleRefused: the tile is not current, not built with the
        default mesh settings, or a file would carry a local path.
    """
    import O4_Config_Utils as CFG
    t0 = time.time()
    tile = load_tile(lat, lon, custom_build_dir)
    _require_current(tile)
    deviations = _key.profile_deviations(_key.mesh_profile(tile))
    if deviations:
        raise BundleRefused(
            "Tile bundles are made only for the default mesh settings; this "
            "tile was built with other values for: " + ", ".join(deviations))
    parts = _key.key_parts(tile)
    pairs = _paths.roots(tile, CFG.custom_scenery_dir, _key.xplane_root(tile))

    def change(text: str) -> str:
        return _paths.tokenise_text(text, pairs)

    members, files = [], {}
    import O4_DSF_Data_Inputs as DSFDATA
    data = DSFDATA.to_bytes(DSFDATA.compute(tile), _key.bundle_key(parts))
    name = "build/" + os.path.basename(DSFDATA.path(tile))
    members.append((name, data, None))
    files[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    for name, path in contents.files(tile):
        if contents.forbidden(name):
            raise BundleRefused("%s may not go into a bundle" % name)
        if name.endswith((".json", ".osm")):
            with open(path, "rb") as handle:
                data = _paths.transform_file_bytes(name, handle.read(), change)
            members.append((name, data, None))
            files[name] = {"bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}
        else:
            members.append((name, None, path))
            files[name] = {"bytes": os.path.getsize(path),
                           "sha256": _sha_file(path)}
    import O4_Version
    manifest = {"format": FORMAT, "tile": parts["tile"],
                "key": _key.bundle_key(parts), "key_parts": parts,
                "airports": _key.airport_signatures(tile),
                "data_snapshot": _snapshot(tile), "sources": _sources(tile),
                "engine_version": getattr(O4_Version, "version", ""),
                "records": _records(tile, change), "files": files}
    manifest_bytes = (json.dumps(manifest, indent=1, sort_keys=True)
                      + "\n").encode("utf-8")
    home = os.path.expanduser("~")
    for name, data in [("manifest.json", manifest_bytes)] + [
            (n, d) for n, d, _p in members if d is not None]:
        left = _paths.leftovers(data, pairs, (home,))
        if left:
            raise BundleRefused("%s would carry a local path (%s); not "
                                "exported" % (name, left[0]))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, _bundle_name(lat, lon))
    temporary = out_path + ".tmp"
    with tarfile.open(temporary, "w:xz", preset=XZ_PRESET) as tar:
        for name, data in (("manifest.json", manifest_bytes),
                           ("ATTRIBUTION.txt", _attribution(manifest))):
            tar.addfile(_info(name, len(data)), io.BytesIO(data))
        for name, data, path in members:
            if data is not None:
                tar.addfile(_info(name, len(data)), io.BytesIO(data))
            else:
                with open(path, "rb") as handle:
                    tar.addfile(_info(name, files[name]["bytes"]), handle)
    os.replace(temporary, out_path)
    return {"path": out_path, "bytes": os.path.getsize(out_path),
            "key": manifest["key"], "files": len(members),
            "seconds": round(time.time() - t0, 1)}
