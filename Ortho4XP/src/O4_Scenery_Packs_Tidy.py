"""File newly installed scenery packs into ``scenery_packs.ini`` by kind.

X-Plane adds a pack it has not seen at the TOP of its scenery order at
its next launch, so a freshly installed base mesh (an airport's own
terrain, a regional mesh) would be drawn instead of our ortho tiles
(#1729).  Both apps therefore file each pack the ini does not list yet
into its kind's group as soon as they see it — airports above Global
Airports, then overlays, libraries, orthos, and meshes BELOW every ortho
(``O4_Scenery_Packs.insert_new_packs``) — and the tile pane and the
build's closing warnings say when a mesh hides a tile anyway.

The ``tidy_scenery_packs`` command is the Mac app's call after each scan
of Custom Scenery; the Qt window calls :func:`tidy_scenery_packs` after
its own survey.  Existing rows are never moved, disabled or dropped; the
ini's line ending is kept; the user's ini is backed up once
(``scenery_packs.ini.o4bak``) before the first change.
"""

from __future__ import annotations

import os

import O4_Custom_Scenery as PACKS
import O4_DSF_Header as HEADER
import O4_File_Names as FNAMES
import O4_Scenery_Packs as SP

__all__ = ["tidy_scenery_packs"]


def _unlisted_packs(custom_scenery_dir: str, lines: list) -> list:
    """Pack folders on disk (symlinks followed, hidden names skipped) that
    no ``SCENERY_PACK`` / ``SCENERY_PACK_DISABLED`` row names."""
    listed = set()
    for line in lines:
        tokens = line.strip().split(None, 1)
        if len(tokens) == 2 and tokens[0] in ("SCENERY_PACK",
                                              "SCENERY_PACK_DISABLED"):
            name = SP.pack_name_from_ini_path(tokens[1])
            if name:
                listed.add(name)
    try:
        entries = os.listdir(custom_scenery_dir)
    except OSError:
        return []
    return sorted(
        name for name in entries
        if not name.startswith(".") and name not in listed
        and name not in SP.NEVER_FILTERED
        and os.path.isdir(os.path.join(custom_scenery_dir, name)))


def _classify(custom_scenery_dir: str, name: str):
    """A pack's kind read from disk, ``None`` when it is not there.

    :func:`O4_Custom_Scenery.pack_kind`, with one more read the map scan
    skips for speed: a pack of DSFs and no terrain files whose name does
    not say ``mesh`` is a mesh when its first DSF is a base mesh (the Mac
    scanner reads the same flag)."""
    path = os.path.join(custom_scenery_dir, name)
    if not os.path.isdir(path):
        return None
    root = os.path.realpath(path)
    kind = PACKS.pack_kind(name, root)
    if kind == "landmark":
        tiles = sorted(PACKS.pack_tiles(root))
        if tiles and HEADER.dsf_is_overlay(
                FNAMES.dsf_file(root, *tiles[0])) is False:
            return "mesh"
    return kind


def tidy_scenery_packs(custom_scenery_dir: str = "", kinds=None,
                       **_ignored) -> dict:
    """The ``tidy_scenery_packs`` command (protocol 1.25).

    ``kinds`` maps pack names to the kinds the caller's own scan found
    (``O4_Custom_Scenery.PACK_KINDS``); a pack it does not name is read
    from disk (:func:`_classify`), and only when its group is needed.

    :returns: ``{"added": [names filed], "backup": path or ""}`` —
        ``added`` empty when the ini already lists every pack (then it
        is not rewritten).  Raises ``ValueError`` with the user's
        sentence when the ini cannot be written.
    """
    custom_scenery_dir = str(custom_scenery_dir or "")
    reply = {"added": [], "backup": ""}
    if not custom_scenery_dir or not os.path.isdir(custom_scenery_dir):
        return reply
    ini = os.path.join(custom_scenery_dir, SP.INI_FILENAME)
    try:
        lines, newline = SP.read_ini_lines(ini, missing_ok=True)
    except OSError:
        return reply
    new = _unlisted_packs(custom_scenery_dir, lines)
    if not new:
        return reply
    known = {str(key): str(value) for key, value in dict(kinds or {}).items()}

    def kind_of(name):
        if name not in known:
            known[name] = _classify(custom_scenery_dir, name)
        return known[name]

    reply["added"] = SP.insert_new_packs(lines, new, kind_of)
    try:
        SP.write_ini_lines(ini, lines, newline)
    except OSError as exc:
        raise ValueError("scenery_packs.ini could not be written (%s)."
                         % exc.strerror) from None
    backup = ini + SP.BACKUP_SUFFIX
    reply["backup"] = backup if os.path.exists(backup) else ""
    return reply
