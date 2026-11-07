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

import hashlib
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
    "names_above_global_airports",
    "load_order",
    "EARTH_NAV_DATA",
    "earth_nav_data",
    "INI_HEADER",
    "BACKUP_SUFFIX",
    "KIND_RANKS",
    "read_ini_lines",
    "write_ini_lines",
    "insert_new_packs",
]

INI_FILENAME = "scenery_packs.ini"

#: Names X-Plane's ini never governs for our purposes: the stock global
#: pack (XP11 puts it inside ``Custom Scenery``) is read as a fallback
#: whatever the ini says.
NEVER_FILTERED = frozenset({"Global Airports"})

_ENABLED_TOKEN = "SCENERY_PACK"
_DISABLED_TOKEN = "SCENERY_PACK_DISABLED"

_CUSTOM_SCENERY = "Custom Scenery"

# (ini_path, sha1 of the ini's BYTES) -> (ordered, disabled).  One install
# per process in practice, so a single-entry cache is enough.
#
# The key was ``(path, st_mtime, st_size)`` and served a REORDERED ini
# stale (#141, and #104 before it).  A pure reorder changes neither the
# length nor any name, and ubuntu stamps inode mtimes from a COARSE clock,
# so a rewrite landing in the same tick as the original does not advance
# ``st_mtime`` either -- the key then matched and X-Plane's pack PRIORITY
# was read from the superseded file.  That is a product defect, not only a
# flake: priority decides which pack wins a virtual library path, so the
# wrong pack supplied footprint geometry (reproduced -- the reorder was
# invisible and the old winner kept the path).  No stat tuple can tell a
# same-length rewrite inside one timestamp tick from no rewrite at all, so
# the key is the CONTENT.  The ini is small and the bytes are read anyway
# to parse it, so a hit now costs one read plus one sha1.
_INI_CACHE: dict[tuple, tuple[tuple[str, ...], frozenset, int | None]] = {}


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
    ordered, disabled, _global_at = _read_ini(ini_path)
    return (list(ordered), set(disabled))


def _read_ini(ini_path: str) -> tuple[tuple[str, ...], frozenset, int | None]:
    """``(enabled names in ini order, disabled names, how many enabled
    names precede the Global Airports row)`` — the last ``None`` when the
    ini lists no Global Airports row.  Cached on the ini's BYTES."""
    try:
        with open(ini_path, "rb") as handle:
            raw = handle.read()
    except OSError:
        return ((), frozenset(), None)
    key = (os.path.abspath(ini_path), hashlib.sha1(raw).hexdigest())
    cached = _INI_CACHE.get(key)
    if cached is not None:
        return cached
    ordered: list[str] = []
    disabled: set[str] = set()
    global_at: int | None = None
    for line in raw.decode("utf-8", "replace").splitlines():
        tokens = line.strip().split(None, 1)
        if len(tokens) != 2:
            continue
        if global_at is None and _is_global_airports_row(tokens[1]):
            global_at = len(ordered)
        name = pack_name_from_ini_path(tokens[1])
        if not name:
            continue
        # EXACT token: "SCENERY_PACK_DISABLED".startswith(
        # "SCENERY_PACK") is True, which is the E1 defect.
        if tokens[0] == _DISABLED_TOKEN:
            disabled.add(name)
        elif tokens[0] == _ENABLED_TOKEN and name not in ordered:
            ordered.append(name)
    _INI_CACHE.clear()
    _INI_CACHE[key] = (tuple(ordered), frozenset(disabled), global_at)
    return _INI_CACHE[key]


def _is_global_airports_row(raw: str) -> bool:
    """X-Plane 12's virtual ``*GLOBAL_AIRPORTS*`` row, or an X-Plane 11
    ``Custom Scenery/Global Airports/`` one."""
    parts = _split_components(raw)
    return bool(parts) and parts[-1] in ("*GLOBAL_AIRPORTS*", "Global Airports")


def names_above_global_airports(custom_scenery_dir: str) -> list[str]:
    """The ENABLED packs X-Plane draws ABOVE Global Airports, highest
    priority first (#1630): the packs on disk the ini does not list (X-Plane
    adds a new pack at the top), then the enabled rows listed before the
    Global Airports row.  An ini with no such row (or no ini) puts every
    enabled pack above it — X-Plane 12 draws Custom Scenery over Global
    Scenery."""
    return load_order(custom_scenery_dir, stop_at_global_airports=True)


def load_order(custom_scenery_dir: str,
               stop_at_global_airports: bool = False) -> list[str]:
    """The ENABLED packs on disk in X-Plane's priority order, highest
    first: the packs the ini does not list (X-Plane adds a new pack at the
    top), then the enabled rows in ini order.  With
    ``stop_at_global_airports`` the list ends at the Global Airports row
    (:func:`names_above_global_airports`).  For a tile, the first pack in
    this order that ships a base-mesh DSF is the one X-Plane draws (#1729)."""
    enabled = enabled_pack_names(custom_scenery_dir)
    ordered, _disabled, global_at = _read_ini(
        os.path.join(custom_scenery_dir or "", INI_FILENAME))
    unlisted = sorted(enabled - set(ordered) - NEVER_FILTERED)
    if stop_at_global_airports and global_at is not None:
        ordered = ordered[:global_at]
    return unlisted + [name for name in ordered if name in enabled]


#: The folder of a pack that holds its ``apt.dat`` and DSFs, as X-Plane
#: and most authors spell it.
EARTH_NAV_DATA = "Earth nav data"


def earth_nav_data(pack_root: str) -> str:
    """The pack's ``Earth nav data`` folder, its name matched WITHOUT
    REGARD TO CASE (#1887): X-Plane reads ``earth nav data`` and ``Earth
    Nav Data`` too, and packs in the wild ship them (SBSP GloballArt).
    macOS and Windows volumes answer any spelling; a case-sensitive one
    (Linux) answers only the one on disk, so the directory is LISTED.
    The canonical spelling is returned when nothing matches (the caller's
    ``isfile`` then answers False)."""
    exact = os.path.join(pack_root, EARTH_NAV_DATA)
    if os.path.isdir(exact):
        return exact
    try:
        names = sorted(os.listdir(pack_root))
    except OSError:
        return exact
    want = EARTH_NAV_DATA.casefold()
    for name in names:
        path = os.path.join(pack_root, name)
        if name.casefold() == want and os.path.isdir(path):
            return path
    return exact


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


# ── filing new packs into the ini (#1729 follow-up) ──────────────────────
#: The ini X-Plane writes when there is none yet.
INI_HEADER = "I\n1000 Version\nSCENERY\n\n"

#: The copy of the user's ini kept before this app first changes it.
BACKUP_SUFFIX = ".o4bak"

#: Load-order group per pack kind (``O4_Custom_Scenery.PACK_KINDS``),
#: highest priority first.  Doubled so Global Airports sits at 1, between
#: custom airports and everything below them; a mesh files BELOW every
#: ortho, ours included, so it never hides our tiles.
KIND_RANKS = {"airport": 0, "landmark": 2, "other": 2, "library": 4,
              "ortho": 6, "mesh": 8}
_GLOBAL_AIRPORTS_RANK = 1


def read_ini_lines(ini_path: str, missing_ok: bool = False):
    """``(lines, newline)`` of the ini, split on its
    own line ending (CRLF kept when the file has it).  A missing ini is
    :data:`INI_HEADER` when ``missing_ok``; otherwise ``OSError``."""
    try:
        with open(ini_path, encoding="utf-8", newline="") as handle:
            text = handle.read()
    except FileNotFoundError:
        if not missing_ok:
            raise
        text = INI_HEADER
    newline = "\r\n" if "\r\n" in text else "\n"
    return text.split(newline), newline


def write_ini_lines(ini_path: str, lines: list, newline: str) -> None:
    """Replace the ini atomically.  The first time this app changes it,
    the user's file is kept beside it as ``scenery_packs.ini.o4bak``."""
    backup = ini_path + BACKUP_SUFFIX
    if os.path.isfile(ini_path) and not os.path.exists(backup):
        with open(ini_path, "rb") as source, open(backup, "wb") as copy:
            copy.write(source.read())
    temporary = ini_path + ".o4tmp"
    with open(temporary, "w", encoding="utf-8", newline="") as handle:
        handle.write(newline.join(lines))
    os.replace(temporary, ini_path)


def _row_pack(line: str):
    """``(is_pack_row, pack name or None)`` for one ini line."""
    tokens = line.strip().split(None, 1)
    if len(tokens) != 2 or tokens[0] not in (_ENABLED_TOKEN, _DISABLED_TOKEN):
        return False, None
    return True, pack_name_from_ini_path(tokens[1])


def insert_new_packs(lines: list, new_names, kind_of) -> list:
    """File each pack in ``new_names`` into ``lines`` (edited in place)
    as an enabled row, in its kind's group (:data:`KIND_RANKS`).

    A new pack goes just before the first row of a LATER group — for an
    airport that is the Global Airports row — or at the end of the file.
    Additions go in (rank, lower-case name) order.  Existing rows are
    never moved or dropped.  ``kind_of(name)`` is a pack's kind, or
    ``None`` for a row that takes no group (not on disk, unknown).

    :returns: the names added, in the order they were filed.
    """
    rank_of: dict = {}

    def line_rank(line: str):
        is_row, name = _row_pack(line)
        if not is_row:
            return None
        if _is_global_airports_row(line.strip().split(None, 1)[1]):
            return _GLOBAL_AIRPORTS_RANK
        if not name:
            return None
        if name not in rank_of:
            rank_of[name] = KIND_RANKS.get(kind_of(name) or "")
        return rank_of[name]

    additions = sorted(
        ((KIND_RANKS.get(kind_of(name) or "other", 2), name)
         for name in new_names),
        key=lambda item: (item[0], item[1].lower()))
    # A file ending in a line break ends in an empty piece: the end of the
    # file is before it, so the ini keeps its last line break.
    added = []
    for rank, name in additions:
        end = len(lines) - 1 if lines and lines[-1] == "" else len(lines)
        at = end
        if rank < max(KIND_RANKS.values()):
            for index in range(end):
                other = line_rank(lines[index])
                if other is not None and other > rank:
                    at = index
                    break
        lines.insert(at, "SCENERY_PACK Custom Scenery/%s/" % name)
        added.append(name)
    return added
