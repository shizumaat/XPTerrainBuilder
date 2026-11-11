"""APPLY XPTERRAINBUILDER'S OBJECT FIXES INTO MY PACK (RULINGS 2026-11-11m
(3)): the developer's explicit act that makes the object stage's splits
and seats part of their pack's own files, so the pack they ship already
carries them.

The object stage already writes its splits and seats INTO the installed
pack (``auto_patch.object_stage``: the cut ``__b<k>`` bodies under
``objects/``, the rewritten DSF and apt.dat), keeping each original beside
its file as ``<name>.anchor_bak`` and recording its writes
(``.o4_reanchor_provenance.json``, ``Earth nav data/…/
o4_placement_provenance.json``).  Those originals are what makes the
writes reversible and what the pack's SIGNATURE is taken from
(``pack_identity``: the pristine DSF).  Applying moves every one of them,
and the records, out of the way — into ``<pack>/XPTerrainBuilder/backup/
<UTC>/`` at their relative paths, nothing deleted (the existing
convention: originals are kept) — so the live files ARE the pack, its
signature is the one a recipient computes from the shipped copy, and
the pack is marked ``objects: applied`` (:mod:`.pack_dev`): the object
stage leaves it alone from then on, here and at every recipient.

Nothing here runs during a build.  :func:`developer` is the
``package_developer`` command (``o4_engine.library``) both apps' export
window and map airport menu send: read the pack's choice, set "Objects
are final" (the originals the object stage kept are put back first), go
back to the default, or apply.
"""
from __future__ import annotations

import os
import shutil
import time

from . import BundleRefused
from . import pack_dev as _dev

__all__ = ["BACKUP_FOLDER", "RECORD_NAMES", "ACTIONS", "engine_files",
           "apply_into_pack", "developer"]

#: The ``package_developer`` command's actions.
ACTIONS = ("read", "final", "default", "apply")

#: Below the pack's XPTerrainBuilder folder: one folder per apply.
BACKUP_FOLDER = "backup"

#: The object stage's write records in a pack (v1 sidecar, v2 per-DSF).
RECORD_NAMES = (".o4_reanchor_provenance.json", "o4_placement_provenance.json")

#: A file name holding this is an original the object stage kept.
_BACKUP_MARK = ".anchor_bak"


def engine_files(pack_root: str) -> list:
    """The pack's kept originals and write records, relative paths,
    sorted (the pack's own XPTerrainBuilder folder is never walked)."""
    out = []
    for root, dirs, names in os.walk(pack_root):
        dirs[:] = sorted(d for d in dirs if not (
            root == pack_root and d == _dev.FOLDER))
        for name in sorted(names):
            if _BACKUP_MARK in name or name in RECORD_NAMES:
                out.append(os.path.relpath(os.path.join(root, name), pack_root))
    return out


def _refuse_unless_writable(pack_root: str) -> None:
    if not os.path.isdir(os.path.join(pack_root, "Earth nav data")):
        raise BundleRefused("%s is not an airport scenery pack"
                            % os.path.basename(os.path.normpath(pack_root)))
    from auto_patch.post_mesh import _is_protected_scenery_root
    if _is_protected_scenery_root(pack_root):
        raise BundleRefused("%s is part of X-Plane, not your own pack"
                            % os.path.basename(os.path.normpath(pack_root)))


def apply_into_pack(pack_root: str, engine_version: str = "") -> dict:
    """Make the object stage's current splits and seats the pack's own
    (module doc).

    :returns: ``{"pack", "pack_root", "objects": "applied", "moved": n,
        "backup": folder, "files": [relative path, …]}``
    :raises BundleRefused: not a writable airport pack, or one the object
        stage has not changed (nothing to apply).
    """
    _refuse_unless_writable(pack_root)
    files = engine_files(pack_root)
    if not files:
        raise BundleRefused(
            "XPTerrainBuilder has not changed any object of %s yet: build a "
            "tile holding the airport first, then apply."
            % os.path.basename(os.path.normpath(pack_root)))
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup = os.path.join(_dev.folder(pack_root), BACKUP_FOLDER, stamp)
    for rel in files:
        dest = os.path.join(backup, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(os.path.join(pack_root, rel), dest)
    relative = os.path.relpath(backup, pack_root).replace(os.sep, "/")
    _dev.set_objects(pack_root, _dev.APPLIED, applied={
        "utc": stamp, "engine_version": engine_version,
        "backup": relative, "files": len(files)})
    return {"pack": os.path.basename(os.path.normpath(pack_root)),
            "pack_root": pack_root, "objects": _dev.APPLIED,
            "moved": len(files), "backup": relative,
            "files": [f.replace(os.sep, "/") for f in files]}


def _pack_of(icao: str, tiles, custom_build_dir: str) -> str:
    from .export import load_tile
    from .key import pack_root
    for lat, lon in sorted({(int(a), int(b)) for a, b in tiles or ()}):
        root = pack_root(load_tile(lat, lon, custom_build_dir), icao)
        if root:
            return root
    raise BundleRefused("%s is not served by a Custom Scenery pack of yours."
                        % str(icao).upper())


def developer(icao: str, tiles, custom_build_dir: str = "",
              action: str = "read") -> dict:
    """ENGINE COMMAND ``package_developer``: ``icao``'s pack (found from
    ``tiles``) and its author's ``objects`` choice after ``action``
    (:data:`ACTIONS`).

    :returns: ``{"icao", "pack", "pack_root", "objects", "modified",
        "shipped", "restored", "moved"}`` — ``modified``: the object stage
        has changed the pack (what "apply" would make its own);
        ``shipped``: the packages in the pack's folder.
    :raises BundleRefused: no such pack, or an action that cannot be done.
    """
    if action not in ACTIONS:
        raise BundleRefused("unknown action %r (one of %s)" % (action, ", ".join(ACTIONS)))
    icao = str(icao).upper()
    root = _pack_of(icao, tiles, custom_build_dir)
    done = {"restored": 0, "moved": 0}
    if action == "apply":
        import O4_Version
        done["moved"] = apply_into_pack(root, getattr(O4_Version, "version", ""))["moved"]
    elif action == "final":
        _refuse_unless_writable(root)
        if engine_files(root):
            from auto_patch import object_rebake
            done["restored"] = object_rebake.restore_detail(root)["restored"]
        _dev.set_objects(root, _dev.FINAL)
    elif action == "default":
        _refuse_unless_writable(root)
        _dev.set_objects(root, "")
    return {"icao": icao, "pack": os.path.basename(os.path.normpath(root)),
            "pack_root": root, "objects": _dev.objects_mode(root),
            "modified": bool(engine_files(root)),
            "shipped": _dev.shipped_packages(root), **done}
