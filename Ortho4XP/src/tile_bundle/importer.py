"""IMPORT LIBRARY BUNDLE (#1699 phase 1): a bundle → a tile the next build
finishes with the user's own imagery.

1. The bundle's key is checked against THIS machine's (:mod:`.key`): the
   tile, every graded airport's pack signature from the pristine pack,
   the mesh profile and the code family.  The first difference refuses
   the import, in the user's words — the user's next build is then
   today's normal build.
2. Every member's sha256 is checked against the manifest; a member a
   bundle may not carry refuses it.  The files are spelled with this
   machine's paths (:mod:`.paths`) and laid down in the tile's build,
   patch and mask folders.
3. The vector step's record is adopted from the bundle, its OSM and
   elevation hashes trusted (``O4_Step_Reuse.adopt_bundle_record``).
4. The OBJECT STAGE runs alone (``O4_Object_Stage``) over the mesh just
   laid down: the plans in the bundle applied to the user's own copy of
   each pack, with the build's in-place writes, backups and hash checks.
5. The mesh and masks steps' records are cut as a build cuts them, and
   the object stage's pack writes stand (``O4_Stopped_Build.complete``).

The import never fetches anything.  The tile's next build reuses the
vector, mesh and masks steps and runs imagery and the scenery file.
"""
from __future__ import annotations

import hashlib
import json
import os
import tarfile
import time

import O4_Step_Reuse as REUSE

from . import FORMAT, BundleRefused, contents
from . import key as _key
from . import paths as _paths
from .export import load_tile

__all__ = ["read_manifest", "import_bundle"]


def read_manifest(bundle_path: str) -> dict:
    """The bundle's manifest (only that member is read)."""
    try:
        with tarfile.open(bundle_path, "r:*") as tar:
            member = tar.extractfile("manifest.json")
            doc = json.loads(member.read().decode("utf-8"))
    except (OSError, KeyError, ValueError, tarfile.TarError) as error:
        raise BundleRefused("%s is not a tile bundle (%s)"
                            % (os.path.basename(bundle_path), error)) from error
    if doc.get("format") != FORMAT:
        raise BundleRefused("the bundle is format %r; this app reads %r"
                            % (doc.get("format"), FORMAT))
    return doc


def _tile_of(manifest: dict) -> tuple:
    text = str(manifest.get("tile", ""))
    return int(text[:3]), int(text[3:])


def _renames(theirs: dict, ours: dict) -> dict:
    """Bundle pack folder name -> this machine's, per airport."""
    return {theirs[icao]["pack"]: ours[icao]["pack"] for icao in theirs
            if icao in ours and theirs[icao].get("pack")
            and ours[icao].get("pack")
            and theirs[icao]["pack"] != ours[icao]["pack"]}


def _refuse_user_edits(tile, members) -> None:
    """A patch already on disk that is not the bundle's is the user's own
    work: phase 1 never overwrites it."""
    import O4_File_Names as FNAMES
    folder = FNAMES.patch_dir(tile.lat, tile.lon)
    names = {m.name.partition("/")[2] for m in members
             if m.name.startswith("patches/")}
    try:
        present = os.listdir(folder)
    except OSError:
        return
    own = [n for n in present if n.endswith(".osm") and n not in names]
    if own:
        raise BundleRefused(
            "The tile's patch folder holds patches the bundle does not "
            "(%s): import would set your own airport edits aside. Move "
            "them, or build the tile normally." % ", ".join(sorted(own)[:3]))


def _lay_down(tile, tar, manifest, pairs, renames) -> int:
    """Check and write every member; returns the bytes written."""
    files = manifest.get("files") or {}
    members = [m for m in tar.getmembers()
               if m.name not in ("manifest.json", "ATTRIBUTION.txt")]
    if sorted(m.name for m in members) != sorted(files):
        raise BundleRefused("the bundle's files are not the ones its "
                            "manifest lists")
    _refuse_user_edits(tile, members)

    def change(text: str) -> str:
        return _paths.detokenise_text(text, pairs, renames)

    written = 0
    for member in members:
        if not member.isfile() or contents.forbidden(member.name):
            raise BundleRefused("the bundle holds %s, which no bundle may "
                                "carry" % member.name)
        dest = contents.destination(tile, member.name)
        handle = tar.extractfile(member)
        data = handle.read()
        if hashlib.sha256(data).hexdigest() != files[member.name]["sha256"]:
            raise BundleRefused("%s does not match the bundle's hash: the "
                                "bundle is damaged" % member.name)
        data = _paths.transform_file_bytes(member.name, data, change)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest + ".tmp", "wb") as out:
            out.write(data)
        os.replace(dest + ".tmp", dest)
        written += len(data)
    return written


def import_bundle(bundle_path: str, custom_build_dir: str = "") -> dict:
    """ENGINE COMMAND ``library_import_bundle``: import a tile bundle.

    :returns: ``{"tile", "key", "airports", "bytes", "object_stage",
        "reused", "seconds"}`` — ``reused`` the steps the tile's next build
        reuses (all three when the import took).
    :raises BundleRefused: the key does not match this machine, or the
        bundle is damaged.
    """
    import O4_Config_Utils as CFG
    import O4_Object_Stage as OBJECT_STAGE
    import O4_Stopped_Build as STOPPED
    t0 = time.time()
    manifest = read_manifest(bundle_path)
    lat, lon = _tile_of(manifest)
    tile = load_tile(lat, lon, custom_build_dir)
    ours = _key.key_parts(tile)
    why = _key.first_difference(manifest.get("key_parts") or {}, ours)
    if why:
        raise BundleRefused("This bundle does not match your installation: "
                            + why + ".")
    tile.make_dirs()
    pairs = _paths.roots(tile, CFG.custom_scenery_dir, _key.xplane_root(tile))
    renames = _renames(manifest.get("airports") or {},
                       _key.airport_signatures(tile))
    first = {}
    for name, root in pairs:                 # one root per token
        first.setdefault(name, root)
    with tarfile.open(bundle_path, "r:*") as tar:
        for step in REUSE.REUSABLE_STEPS:
            REUSE.forget_from(tile, step)
        written = _lay_down(tile, tar, manifest, list(first.items()), renames)
    vector = (manifest.get("records") or {}).get("vector") or {}
    trusted = {k: v for k, v in (vector.get("inputs") or {}).items()
               if k in REUSE.BUNDLE_TRUSTED_KEYS}
    REUSE.adopt_bundle_record(tile, "vector", manifest["key"], trusted)
    counts = OBJECT_STAGE.run(tile)
    REUSE.record(tile, "mesh")
    REUSE.record(tile, "masks")
    STOPPED.complete(tile.build_dir, lat, lon)
    return {"tile": manifest["tile"], "key": manifest["key"],
            "airports": sorted(manifest.get("airports") or {}),
            "bytes": written, "object_stage": counts,
            "reused": list(REUSE.predicted_reuse(tile)),
            "stale": {step: REUSE.stale_reason(tile, step)
                      for step in REUSE.REUSABLE_STEPS},
            "seconds": round(time.time() - t0, 1)}
