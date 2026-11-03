"""Cache files nothing needs any more (#1725 items 3 and 4): what the
Storage automatic cleanup removes after every build, whatever its two
settings say, because each one only duplicates or outlives its source.

* :func:`dds_held_by_tiles` -- texture-cache entries every tile that used
  them now holds itself (``O4_DDS_Cache.held_by_built_tiles``);
* :func:`airport_pack_leftovers` -- ``Airport_mod_cache/<pack>/`` folders
  of packs that are no longer in Custom Scenery, and text dumps of a pack
  DSF superseded by its current bytes.  The dumps are content-keyed
  (``<name>.dsf.<tag>.text``, ``auto_patch.dsf_reader.dsf_content_tag``),
  so a pack update leaves the old dump behind for ever.

Measured 2026-11-02 on the shared data repo (allocated bytes; every file
of that cache is an APFS clone there, so its private bytes are 0):
``Airport_mod_cache`` 40.3 GB in 553 pack folders, 47 of them (5.6 GB)
for packs not in Custom Scenery, 655 older dumps (2.7 GB).

SAFETY.  This module only NAMES files; ``o4_engine.storage`` deletes
them under its own rules (log line, in-flight age, protected names, never
during a build).  A pack counts as installed when ANY entry of its name
is in Custom Scenery or Global Scenery -- a disabled pack, and a symlink
onto a volume that is not mounted, included.  With no Custom Scenery
folder configured or readable, or when more than half of the pack folders
would go (the setting names another X-Plane), no pack folder is named.
A dump is named only when its DSF has another dump beside it, was read,
and its tag differs.
"""
from __future__ import annotations

import glob
import os
import re

import O4_DDS_Cache as DDSC
import O4_File_Names as FNAMES

__all__ = ["dds_held_by_tiles", "airport_pack_leftovers",
           "MAX_PACK_SHARE"]

#: Above this share of pack folders to remove, the configured Custom
#: Scenery is taken for another install and no folder is named.
MAX_PACK_SHARE = 0.5

_DUMP = re.compile(r"^(?P<source>.+\.dsf(?:\.anchor_bak)?)\."
                   r"(?P<tag>[0-9a-f]{8})\.text$")


def dds_held_by_tiles() -> list:
    """Texture-cache entries their tiles already hold (paths)."""
    return DDSC.held_by_built_tiles()


def _custom_scenery_dir() -> str:
    try:
        import O4_Settings_Model as SM
        return SM.read_global_raw().get("custom_scenery_dir", "") or ""
    except Exception:
        return ""


def _pack_roots(name: str, custom_scenery: str) -> list:
    """Where a pack of that folder name may be: Custom Scenery, then the
    sibling Global Scenery (X-Plane 12 keeps Global Airports there)."""
    return [os.path.join(custom_scenery, name),
            os.path.join(os.path.dirname(custom_scenery.rstrip("/\\")),
                         "Global Scenery", name)]


def _installed(name: str, custom_scenery: str) -> bool:
    return any(os.path.lexists(p) for p in _pack_roots(name, custom_scenery))


def _superseded_dumps(cache_dir: str, pack_roots: list) -> list:
    """Dumps in ``cache_dir`` whose source file, found in the pack's
    ``Earth nav data``, now has another content tag.  Only a source with
    two or more dumps is read (a full hash of its DSF), so a cleanup
    never hashes every pack."""
    from auto_patch.dsf_reader import dsf_content_tag
    stale = []
    try:
        names = os.listdir(cache_dir)
    except OSError:
        return stale
    dumps: dict = {}
    for name in names:
        match = _DUMP.match(name)
        if match is not None:
            dumps.setdefault(match.group("source"), []).append(name)
    tags: dict = {}
    for name in sorted(names):
        match = _DUMP.match(name)
        if match is None or len(dumps[match.group("source")]) < 2:
            continue                # one dump: never hash the pack for it
        source = match.group("source")
        if source not in tags:
            tags[source] = None
            for root in pack_roots:
                found = glob.glob(os.path.join(
                    glob.escape(root), "Earth nav data", "*",
                    glob.escape(source)))
                if found and os.path.isfile(found[0]):
                    tags[source] = dsf_content_tag(found[0])
                    break
        if tags[source] is not None and tags[source] != match.group("tag"):
            stale.append(os.path.join(cache_dir, name))
    return stale


def airport_pack_leftovers(custom_scenery: str | None = None) -> list:
    """Files of ``Airport_mod_cache`` no installed pack needs (paths)."""
    custom_scenery = (_custom_scenery_dir() if custom_scenery is None
                      else custom_scenery)
    root = FNAMES.airport_mod_cache_root()
    if not custom_scenery or not os.path.isdir(custom_scenery):
        return []
    try:
        packs = sorted(n for n in os.listdir(root)
                       if os.path.isdir(os.path.join(root, n)))
    except OSError:
        return []
    gone = [n for n in packs if not _installed(n, custom_scenery)]
    if packs and len(gone) > MAX_PACK_SHARE * len(packs):
        gone = []
    out = []
    for name in packs:
        folder = os.path.join(root, name)
        if name in gone:
            for parent, _dirs, files in os.walk(folder):
                out.extend(os.path.join(parent, f) for f in files)
        else:
            out.extend(_superseded_dumps(
                folder, _pack_roots(name, custom_scenery)))
    return out
