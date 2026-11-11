"""THE DEVELOPER'S CHOICE FOR THEIR AIRPORT PACK (RULINGS 2026-11-11m (3)),
kept IN the pack: ``<pack>/XPTerrainBuilder/xptb.json``.

Owner, verbatim (16:54Z): "For a developer creating a new airport and
making a patch for it, they will most likely not want XPTerrainBuilder to
modify their objects, or if they do, they will then want to save that as
part of their actual airport package they ship".  Per pack, objects are:

* ``""`` — the default: the object stage splits and reseats them;
* :data:`FINAL` — "Objects are final": the object stage never splits or
  reseats them (the terrain is still graded to the patch);
* :data:`APPLIED` — "Apply XPTerrainBuilder's object fixes into my pack"
  was done (:mod:`.pack_apply`): the splits and seats ARE the pack's own
  now, so the stage leaves them as final ones.

WHY IN THE PACK, not in the app's preferences (``auto_patch.pack_choice``
keeps the user's answers there): this is the AUTHOR'S statement about
their pack, and it ships with it.  A recipient who installs the pack gets
the same file and their object stage leaves the pack alone without being
told; a package saved from it records the choice too (``objects`` per
airport in the manifest).  The same folder holds the pack's shipped
``<ICAO>.xptb`` packages (:func:`package_path`, :mod:`.pack_shipped`) and
the backups an apply makes.
"""
from __future__ import annotations

import json
import os
import time

__all__ = ["FOLDER", "CHOICE_FILE", "FINAL", "APPLIED", "MODES", "REGISTRY",
           "folder", "read", "objects_mode", "objects_frozen", "frozen_reason",
           "set_objects", "package_path", "shipped_packages"]

#: The pack's own XPTerrainBuilder folder.
FOLDER = "XPTerrainBuilder"
#: The choice file in it.
CHOICE_FILE = "xptb.json"

FINAL = "final"
APPLIED = "applied"
#: What ``objects`` may say ("" is the default: the stage may split).
MODES = ("", FINAL, APPLIED)

#: Per tile, in its patch folder: which package installed which patch,
#: and (``objects``/``signature``) an airport whose package's pack carries
#: the object fixes already (``install``; read here without importing it:
#: the object stage reads it on every build).
REGISTRY = "o4_installed_packages.json"


def folder(pack_root: str) -> str:
    """``<pack>/XPTerrainBuilder``."""
    return os.path.join(pack_root, FOLDER)


def _choice_path(pack_root: str) -> str:
    return os.path.join(folder(pack_root), CHOICE_FILE)


def read(pack_root: str) -> dict:
    """The pack's choice file, ``{}`` when absent or unreadable."""
    try:
        with open(_choice_path(pack_root), encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def objects_mode(pack_root: str) -> str:
    """``""``, :data:`FINAL` or :data:`APPLIED` (an unknown word reads ``""``)."""
    mode = str(read(pack_root).get("objects") or "") if pack_root else ""
    return mode if mode in MODES else ""


def objects_frozen(pack_root: str) -> bool:
    """True when the object stage must not split or reseat the pack."""
    return objects_mode(pack_root) in (FINAL, APPLIED)


def _package_frozen(tile, icao: str) -> bool:
    """A package installed for ``icao`` on ``tile`` says its pack's objects
    are final or carry the fixes, and the pack installed here is that one
    (same signature): splitting an applied pack would split the splits."""
    import O4_File_Names as FNAMES
    path = os.path.join(FNAMES.patch_dir(tile.lat, tile.lon), REGISTRY)
    entry = FNAMES.read_json_dict(path).get(str(icao).upper()) or {}
    if entry.get("objects") not in (FINAL, APPLIED) or not entry.get("signature"):
        return False
    from .key import pack_signature, xplane_root
    root = xplane_root(tile)
    return bool(root) and pack_signature(
        root, icao, tile.lat, tile.lon).get("signature") == entry["signature"]


def frozen_reason(tile, icao: str, pack_root: str) -> str:
    """Why the object stage leaves ``icao``'s pack alone on ``tile``, in a
    log's words, or ``""`` (it may split and reseat)."""
    mode = objects_mode(pack_root)
    if mode == FINAL:
        return "the pack's author marked its objects final"
    if mode == APPLIED:
        return "the pack already carries XPTerrainBuilder's object fixes"
    try:
        if _package_frozen(tile, icao):
            return ("the package installed for it says the pack's objects "
                    "are final")
    except Exception:                       # unreadable: the stage runs
        return ""
    return ""


def set_objects(pack_root: str, mode: str, **fields) -> dict:
    """Write the pack's ``objects`` choice (``fields`` join it, e.g. an
    apply's record); returns the file's new content.

    :raises ValueError: an unknown mode."""
    if mode not in MODES:
        raise ValueError("objects must be one of %s" % ", ".join(repr(m) for m in MODES))
    doc = read(pack_root)
    doc.update(fields, objects=mode,
               changed=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    if mode != APPLIED:
        doc.pop("applied", None)
    os.makedirs(folder(pack_root), exist_ok=True)
    path = _choice_path(pack_root)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(path + ".tmp", path)
    return doc


def package_path(pack_root: str, icao: str) -> str:
    """Where Export saves an airport's package into its pack:
    ``<pack>/XPTerrainBuilder/<ICAO>.xptb``."""
    from . import PACKAGE_SUFFIX
    return os.path.join(folder(pack_root), str(icao).upper() + PACKAGE_SUFFIX)


def shipped_packages(pack_root: str) -> list:
    """The ``.xptb`` files the pack ships in its folder, sorted."""
    from . import PACKAGE_SUFFIX
    try:
        names = sorted(os.listdir(folder(pack_root)))
    except OSError:
        return []
    return [os.path.join(folder(pack_root), n) for n in names
            if n.lower().endswith(PACKAGE_SUFFIX) and not n.startswith(".")]
