"""How each airport uses its custom patch: "As made" or "Our auto patch"
(#2179; owner RULINGS 2026-11-23d, 2026-11-23f).

A CUSTOM patch is a manual ``*.patch.osm`` in a tile's
``Patches/<10°>/<1°>/`` folder other than the patch editor's own
``<ICAO>_edited.patch.osm`` (RULINGS 2026-11-18k).  For 1.0 each airport
that has one uses it one of two ways:

* :data:`AS_MADE` (the default, 23f): the patch is meshed unchanged, on the
  elevation it was made for (``O4_Custom_Patch_Ground`` leaves the
  airport's own insets out when that is the base raster), and the
  airport's pack is used unmodified (18k);
* :data:`AUTO_PATCH`: the custom file stays where it is but is NOT a patch
  of this build -- the airport is auto-patched on our high-resolution
  elevation like any other.

The choice is per airport, stored beside the patches it governs in
``Patches/<10°>/<1°>/custom_patch_use.json`` = ``{ICAO: mode}`` (an
airport not listed takes :data:`DEFAULT`), so every reader that is handed
only a patch folder decides the same way.  THIS module is the one place
that says which manual patch files a build applies
(:func:`applied_manual_files`): the mesh's ``include_patches``, the
selector's manual set, the admission test, the object stage and the
elevation choice all ask it, so they cannot disagree.  The file is never
renamed (the old "Use auto patch" rename is retired).

Imported by build steps (in the patch code key): standard library only,
no wording beyond the mode names.
"""

from __future__ import annotations

import json
import os

import O4_File_Names as FNAMES

__all__ = ["AS_MADE", "AUTO_PATCH", "MODES", "DEFAULT", "RECORD",
           "read", "set_use", "use_of", "custom_files", "as_made_files", "uses",
           "applied_manual_files"]

#: The patch unchanged, on the elevation it was made for.
AS_MADE = "as_made"
#: Our auto patch on the high-resolution elevation; the file is kept.
AUTO_PATCH = "auto_patch"
MODES = (AS_MADE, AUTO_PATCH)
#: An installed custom patch is used as made (owner RULINGS 2026-11-23f).
DEFAULT = AS_MADE
#: The per-airport record, in the tile's Patches folder.
RECORD = "custom_patch_use.json"


def read(patch_dir: str) -> dict:
    """``{ICAO: mode}`` of the airports with a choice of their own (an
    unreadable record or an unknown mode counts as no choice)."""
    try:
        with open(os.path.join(patch_dir, RECORD), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).upper(): v for (k, v) in data.items() if v in MODES}


def set_use(patch_dir: str, icao: str, mode: str) -> dict:
    """Give *icao* the mode *mode* (``"default"`` removes its own choice);
    returns the record written.

    :raises ValueError: for a mode that is not one of :data:`MODES` (the
        user's sentence)."""
    icao = str(icao).strip().upper()
    if mode not in MODES + ("default",) or not icao:
        raise ValueError("a custom patch is used %s, not %r"
                         % (" or ".join(repr(m) for m in MODES), mode))
    record = read(patch_dir)
    if mode == "default":
        record.pop(icao, None)
    else:
        record[icao] = mode
    os.makedirs(patch_dir, exist_ok=True)
    path = os.path.join(patch_dir, RECORD)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="") as handle:
        json.dump(record, handle, sort_keys=True)
    os.replace(temporary, path)
    return record


def use_of(patch_dir: str, icao: str) -> tuple[str, bool]:
    """``(mode, chosen)`` for *icao*: its own choice (``chosen`` True), else
    :data:`DEFAULT`."""
    own = read(patch_dir).get(str(icao).upper())
    return (own, True) if own else (DEFAULT, False)


def _manual_names(patch_dir: str) -> list[str]:
    try:
        names = os.listdir(patch_dir)
    except OSError:
        return []
    return sorted(n for n in names if FNAMES.is_manual_patch_name(n)
                  and os.path.isfile(os.path.join(patch_dir, n)))


def _is_custom(name: str) -> bool:
    icao = FNAMES.patch_file_icao(name)
    return bool(icao) and name != FNAMES.edited_patch_name(icao)


def custom_files(patch_dir: str) -> dict:
    """``{ICAO: [file names]}`` of every custom patch in *patch_dir*,
    whichever way it is used."""
    out: dict = {}
    for name in _manual_names(patch_dir):
        if _is_custom(name):
            out.setdefault(FNAMES.patch_file_icao(name), []).append(name)
    return out


def as_made_files(patch_dir: str) -> dict:
    """``{ICAO: [file names]}`` of the custom patches used :data:`AS_MADE`
    -- the airports whose pack is used unmodified (RULINGS 2026-11-18k)
    and whose ground is the elevation the patch was made for."""
    record = read(patch_dir)
    return {icao: files for (icao, files) in custom_files(patch_dir).items()
            if record.get(icao, DEFAULT) == AS_MADE}


def uses(patch_dir: str) -> dict:
    """``{ICAO: (mode, chosen)}`` for every airport with a custom patch in
    *patch_dir*."""
    record = read(patch_dir)
    return {icao: ((record[icao], True) if icao in record
                   else (DEFAULT, False))
            for icao in custom_files(patch_dir)}


def applied_manual_files(patch_dir: str) -> list[str]:
    """The manual patch file names the build APPLIES, sorted: every
    manual patch but a custom one whose airport uses :data:`AUTO_PATCH`.
    The patch editor's ``_edited`` patch is always applied."""
    record = read(patch_dir)
    return [name for name in _manual_names(patch_dir)
            if not (_is_custom(name) and record.get(
                FNAMES.patch_file_icao(name)) == AUTO_PATCH)]
