"""The ONE derivation site for "is this Custom Scenery pack enabled?".

Owner ruling RULINGS 2026-09-17b: **a scenery pack DISABLED in
``Custom Scenery/scenery_packs.ini`` is IGNORED by the build.**  What the
simulator does not draw is not evidence about the ground, so a disabled
pack must not supply an ``apt.dat``, a DSF, an object library entry or an
elevation-mask footprint — and must never be REWRITTEN by the object
re-anchor.

Before this module four independent ini parsers lived in
``auto_patch/driver.py``, ``O4_Custom_Scenery.py``,
``O4_Airport_Elevation_Insets.py`` and ``auto_patch/agp_reader.py``, and
the readers that mattered most (the apt.dat selector) had none at all.
They now all delegate here.

Import constraints — this module is imported from BOTH engines and from a
module that must stay importable with no Ortho4XP package on
``sys.path``, so it uses the standard library ONLY and imports no ``O4_*``
and no ``auto_patch*`` module.  (``auto_patch_v2`` imports zero v1 modules
by law; ``auto_patch/agp_reader.py`` is unit-testable standalone.)

The edge rules (the Swift scanner, ``Sources/SceneryKit/
InstallationScanner.swift``, is the cross-language reference and
``tests/test_qt_mac_parity.py`` asserts the agreement):

* ini ABSENT or unreadable  -> every pack on disk is enabled.
* ``SCENERY_PACK`` enabled, ``SCENERY_PACK_DISABLED`` excluded, matched as
  the EXACT first whitespace-delimited token — never ``startswith``, which
  admits ``SCENERY_PACK_DISABLED`` into a ``SCENERY_PACK`` test.
* On disk but NOT LISTED -> enabled (X-Plane appends new packs enabled at
  its next launch).
* Listed but absent from disk, or a DANGLING SYMLINK -> simply not in the
  enabled SET, never an error (``os.path.isdir`` semantics; thousands of
  the owner's entries are symlinks onto a removable volume and all of them
  dangle while it is unmounted).
* ``*GLOBAL_AIRPORTS*`` (X-Plane 12's virtual entry) and any listed path
  that is not under ``Custom Scenery/`` are not pack names at all.
  ``Global Airports``, ``Global Scenery/`` and ``Resources/default
  scenery/`` are never filtered by this module.
"""

from __future__ import annotations

import os
from typing import Iterable

__all__ = [
    "INI_FILENAME",
    "NEVER_FILTERED",
    "pack_name_from_ini_path",
    "parse_ini",
    "disabled_pack_names",
    "enabled_pack_names",
    "pack_enabled",
    "custom_scenery_dir_for",
    "pack_state",
    "filter_enabled",
]

INI_FILENAME = "scenery_packs.ini"

#: Names X-Plane's ini never governs for our purposes: the stock global
#: pack (XP11 puts it inside ``Custom Scenery``) is read as a fallback
#: whatever the ini says.
NEVER_FILTERED = frozenset({"Global Airports"})

_ENABLED_TOKEN = "SCENERY_PACK"
_DISABLED_TOKEN = "SCENERY_PACK_DISABLED"

_CUSTOM_SCENERY = "Custom Scenery"

# (ini_path, mtime, size) -> (ordered, disabled).  One install per process
# in practice, so a single-entry cache is enough and keeps a toggled ini
# from ever being served stale (mtime/size are part of the key).
_INI_CACHE: dict[tuple, tuple[tuple[str, ...], frozenset]] = {}


def _split_components(raw: str) -> list[str]:
    """Path components of an ini entry, separator-agnostic.

    The ini is written by X-Plane on the platform it runs on, and an ini
    authored on Windows carries backslashes that ``os.path`` on POSIX
    would treat as part of the name.
    """
    text = raw.strip().replace("\\", "/")
    return [part for part in text.split("/") if part not in ("", ".")]


def pack_name_from_ini_path(raw: str) -> str | None:
    """The Custom Scenery pack directory name an ini entry names.

    ``None`` when the entry does not name a pack: X-Plane 12's virtual
    ``*GLOBAL_AIRPORTS*`` row, or a path outside ``Custom Scenery/``
    (``Global Scenery/…``, ``Resources/default scenery/…``).  A bare name
    with no separators is accepted as a pack name — that is the shorthand
    the older parsers' ``os.path.basename`` accepted and several fixtures
    use.
    """
    parts = _split_components(raw)
    if not parts:
        return None
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == _CUSTOM_SCENERY:
            return parts[index + 1] if index + 1 < len(parts) else None
    if len(parts) == 1:
        name = parts[0]
        # "*GLOBAL_AIRPORTS*" and friends are not directories.
        return None if name.startswith("*") and name.endswith("*") else name
    return None


def parse_ini(ini_path: str) -> tuple[list[str], set[str]]:
    """``(enabled pack names in ini order, names marked disabled)``.

    Both are empty when the ini is missing or unreadable — which the
    callers read as "the ini governs nothing", i.e. every pack on disk is
    enabled.  Duplicate enabled rows keep their first position.
    """
    try:
        stat = os.stat(ini_path)
        key = (os.path.abspath(ini_path), stat.st_mtime, stat.st_size)
    except OSError:
        return ([], set())
    cached = _INI_CACHE.get(key)
    if cached is not None:
        return (list(cached[0]), set(cached[1]))
    ordered: list[str] = []
    disabled: set[str] = set()
    try:
        with open(ini_path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                tokens = line.strip().split(None, 1)
                if len(tokens) != 2:
                    continue
                name = pack_name_from_ini_path(tokens[1])
                if not name:
                    continue
                # EXACT token: "SCENERY_PACK_DISABLED".startswith(
                # "SCENERY_PACK") is True, which is the E1 defect.
                if tokens[0] == _DISABLED_TOKEN:
                    disabled.add(name)
                elif tokens[0] == _ENABLED_TOKEN and name not in ordered:
                    ordered.append(name)
    except OSError:
        return ([], set())
    _INI_CACHE.clear()
    _INI_CACHE[key] = (tuple(ordered), frozenset(disabled))
    return (list(ordered), set(disabled))


def disabled_pack_names(custom_scenery_dir: str) -> set[str]:
    """Pack directory names marked ``SCENERY_PACK_DISABLED``.

    Names only — a disabled pack that is not on disk is still named here,
    which is what the UI readers want (they LIST disabled packs, dimmed,
    so a user can re-enable one).
    """
    _ordered, disabled = parse_ini(
        os.path.join(custom_scenery_dir or "", INI_FILENAME))
    return disabled


def enabled_pack_names(custom_scenery_dir: str) -> set[str]:
    """Every pack directory ON DISK under ``custom_scenery_dir`` that
    X-Plane loads: listed-and-enabled, plus everything unlisted.

    An entry listed but missing from disk (a removed pack, a dangling
    symlink onto an unmounted volume) simply is not in the set.
    """
    if not custom_scenery_dir or not os.path.isdir(custom_scenery_dir):
        return set()
    disabled = disabled_pack_names(custom_scenery_dir)
    on_disk = {
        name for name in os.listdir(custom_scenery_dir)
        if os.path.isdir(os.path.join(custom_scenery_dir, name))
    }
    return {name for name in on_disk
            if name not in disabled or name in NEVER_FILTERED}


def custom_scenery_dir_for(path: str | None) -> str | None:
    """The ``Custom Scenery`` directory a pack path lives under.

    Accepts anything inside the pack — the pack root, its ``Earth nav
    data/apt.dat``, an object file.  ``None`` when the path is not under a
    ``Custom Scenery`` directory at all (Global Airports on XP12, the
    stock default scenery): X-Plane's ini does not govern those.
    """
    if not path:
        return None
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    try:
        index = len(parts) - 1 - parts[::-1].index(_CUSTOM_SCENERY)
    except ValueError:
        return None
    if index + 1 >= len(parts):
        return None
    return os.sep.join(parts[:index + 1]) or os.sep


def _pack_name_for(path: str) -> str | None:
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    try:
        index = len(parts) - 1 - parts[::-1].index(_CUSTOM_SCENERY)
    except ValueError:
        return None
    return parts[index + 1] if index + 1 < len(parts) else None


def pack_enabled(pack_path_or_name: str,
                 custom_scenery_dir: str | None = None) -> bool:
    """Does X-Plane load this pack?

    ``pack_path_or_name`` is either a bare pack directory name (then
    ``custom_scenery_dir`` is required) or any path inside the pack, in
    which case the ``Custom Scenery`` directory is found by walking up and
    ``custom_scenery_dir`` may be omitted.

    True for anything the ini does not govern: a path outside ``Custom
    Scenery`` (Global Airports on XP12, default scenery), an absent or
    unreadable ini, an unlisted pack, ``Global Airports`` itself.
    """
    if not pack_path_or_name:
        return True
    bare = (os.sep not in pack_path_or_name
            and "/" not in pack_path_or_name)
    if bare:
        name = pack_path_or_name
    else:
        name = _pack_name_for(pack_path_or_name)
        if name is None:
            # A path, but not under Custom Scenery: not governed.
            return True
        custom_scenery_dir = (custom_scenery_dir
                              or custom_scenery_dir_for(pack_path_or_name))
    if not name or name in NEVER_FILTERED:
        return True
    if not custom_scenery_dir:
        return True
    return name not in disabled_pack_names(custom_scenery_dir)


def pack_state(path: str | None) -> tuple[str, str]:
    """``(pack_name, "enabled"|"disabled")`` for a path inside a pack.

    ``("", "external")`` when the ini does not govern the path (Global
    Airports on XP12, the stock default scenery), ``("", "unknown")`` for
    a falsy path.  This is the freshness stamp in ``auto_patch/driver.py``
    split into its two parts.
    """
    if not path:
        return ("", "unknown")
    custom = custom_scenery_dir_for(path)
    name = _pack_name_for(path)
    if not custom or not name:
        return ("", "external")
    return (name, "disabled" if name in disabled_pack_names(custom)
            else "enabled")


def filter_enabled(pack_names: Iterable[str],
                   custom_scenery_dir: str) -> list[str]:
    """``pack_names`` minus the disabled ones, order preserved."""
    disabled = disabled_pack_names(custom_scenery_dir)
    return [name for name in pack_names
            if name not in disabled or name in NEVER_FILTERED]
