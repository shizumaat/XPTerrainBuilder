"""Which config files are XPTerrainBuilder's own, and the one-time hand-over
from the names it used to share with Ortho4XP (#1229, owner RULINGS
2026-10-26c, amending 2026-09-18c).

XPTerrainBuilder reads and writes ONLY its own names:

* the global config ``<data root>/XPTerrainBuilder.cfg``;
* each tile's ``<build dir>/XPTerrainBuilder_+XX+YYY.cfg``.

Ortho4XP's own files (``Ortho4XP.cfg``, ``Ortho4XP_+XX+YYY.cfg``) are left
byte-identical: never read for settings, never written, never moved.  A
user who rebuilds a tile an old Ortho4XP made starts from this app's
defaults, and can still open the tile in Ortho4XP with its own config.

THE HAND-OVER, once per file, never overwriting anything:

* :func:`adopt_tile_cfg` — a STAMPED ``Ortho4XP_+XX+YYY.cfg`` (one this
  app wrote between 1.0.352 and the rename; the stamp is
  ``O4_Cfg_Vars.cfg_stamp_key``) is renamed to the new name.  Then the
  oldest ``Ortho4XP_+XX+YYY.cfg.pre352.bak`` — where 2026-09-18c moved the
  user's Ortho4XP file — is renamed back to ``Ortho4XP_+XX+YYY.cfg`` when
  no file holds that name.  Only the exact oldest name is ever restored,
  so a later ``.bak.2`` is never promoted: the restore happens once.
* :func:`adopt_global_cfg` — when the data root has no
  ``XPTerrainBuilder.cfg`` and its ``Ortho4XP.cfg`` was this app's (the
  data root is not an Ortho4XP installation, :func:`is_ortho4xp_install`),
  the file is COPIED to the new name, so a user's own global settings carry
  over.  The original stays where it is.  In an Ortho4XP folder the
  Ortho4XP file is ignored and the app starts from its defaults (owner
  Q97, "Ignore").

Every function here never raises; a step that cannot be taken (a file in
use, a read-only folder) is simply not taken.  The Mac app mirrors
:func:`adopt_global_cfg` in ``SceneryKit/OrthoConfigNames.swift`` because
it reads the global before the engine starts.
"""

from __future__ import annotations

import glob
import os
import shutil

import O4_Cfg_Vars
import O4_File_Names as FNAMES
import O4_Text_Files as TEXT

__all__ = ["GLOBAL_CFG_NAME", "ORTHO4XP_GLOBAL_CFG_NAME", "TILE_CFG_PREFIX",
           "ORTHO4XP_TILE_CFG_PREFIX", "PRE_STAMP_BACKUP_SUFFIX",
           "tile_cfg_name", "ortho4xp_tile_cfg_name", "tile_cfg_path",
           "global_cfg_path", "is_ortho4xp_install", "adopt_global_cfg",
           "adopt_tile_cfg"]

#: This app's global config, in the data root.
GLOBAL_CFG_NAME = "XPTerrainBuilder.cfg"
#: Ortho4XP's global config: never read, written or moved.
ORTHO4XP_GLOBAL_CFG_NAME = "Ortho4XP.cfg"
#: ``XPTerrainBuilder_+XX+YYY.cfg`` — this app's tile config.
TILE_CFG_PREFIX = "XPTerrainBuilder_"
#: ``Ortho4XP_+XX+YYY.cfg`` — Ortho4XP's tile config.
ORTHO4XP_TILE_CFG_PREFIX = "Ortho4XP_"
#: Where 2026-09-18c moved an unstamped Ortho4XP tile config (``.bak.2``,
#: ``.bak.3`` … when that name was taken).  Only this exact, oldest name is
#: restored.
PRE_STAMP_BACKUP_SUFFIX = ".pre352.bak"


def tile_cfg_name(lat: int, lon: int) -> str:
    """``XPTerrainBuilder_+XX+YYY.cfg``."""
    return TILE_CFG_PREFIX + FNAMES.short_latlon(lat, lon) + ".cfg"


def ortho4xp_tile_cfg_name(lat: int, lon: int) -> str:
    """``Ortho4XP_+XX+YYY.cfg`` (Ortho4XP's; only the hand-over reads it)."""
    return ORTHO4XP_TILE_CFG_PREFIX + FNAMES.short_latlon(lat, lon) + ".cfg"


def tile_cfg_path(build_dir: str, lat: int, lon: int) -> str:
    """This app's tile config in *build_dir*."""
    return os.path.join(build_dir, tile_cfg_name(lat, lon))


def global_cfg_path() -> str:
    """This app's global config in the current data root."""
    return FNAMES.data_path(GLOBAL_CFG_NAME)


def _is_stamped_file(path: str) -> bool:
    """Whether the cfg at *path* carries a non-empty stamp line."""
    key = O4_Cfg_Vars.cfg_stamp_key
    try:
        with TEXT.open_supplied(path, legacy_ansi=True) as handle:
            for line in handle:
                name, sep, value = line.strip().partition("=")
                if sep and name.strip() == key and value.strip():
                    return True
    except OSError:
        pass
    return False


def _exclusive_copy(source: str, target: str) -> bool:
    """Copy *source* to *target*, only if *target* does not exist."""
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError:
        return False
    try:
        with open(source, "rb") as src, os.fdopen(fd, "wb") as dst:
            shutil.copyfileobj(src, dst)
    except OSError:
        try:
            os.unlink(target)
        except OSError:
            pass
        return False
    try:
        shutil.copystat(source, target)
    except OSError:
        pass
    return True


def _rename_no_overwrite(source: str, target: str) -> bool:
    """Rename *source* to *target*, never replacing an existing *target*.

    ``os.link`` refuses an existing name, so two parallel tile workers
    cannot both win; a filesystem without hard links falls back to an
    exclusive copy.  The source goes only once the target holds it.
    """
    try:
        os.link(source, target)
    except FileExistsError:
        return False
    except FileNotFoundError:
        return False
    except OSError:
        if not _exclusive_copy(source, target):
            return False
    try:
        os.unlink(source)
    except FileNotFoundError:
        pass
    except OSError:
        return False
    return True


def adopt_tile_cfg(build_dir: str, lat: int, lon: int) -> list[str]:
    """The tile's one-time hand-over (module docstring).

    :returns: INFO lines for the caller to print (empty when nothing
        happened, which is every call after the first).
    """
    infos: list[str] = []
    try:
        if not build_dir or not os.path.isdir(build_dir):
            return infos
        ours = tile_cfg_path(build_dir, lat, lon)
        theirs = os.path.join(build_dir, ortho4xp_tile_cfg_name(lat, lon))
        if (os.path.isfile(theirs) and not os.path.lexists(ours)
                and _is_stamped_file(theirs)
                and _rename_no_overwrite(theirs, ours)):
            infos.append("tile config %s was written by XPTerrainBuilder; "
                         "it is now %s (owner ruling RULINGS 2026-10-26c)"
                         % (os.path.basename(theirs), os.path.basename(ours)))
        backup = theirs + PRE_STAMP_BACKUP_SUFFIX
        if (os.path.isfile(backup) and not os.path.lexists(theirs)
                and _rename_no_overwrite(backup, theirs)):
            infos.append("restored Ortho4XP's tile config %s from %s; "
                         "XPTerrainBuilder leaves it untouched (owner ruling "
                         "RULINGS 2026-10-26c)"
                         % (os.path.basename(theirs), os.path.basename(backup)))
    except Exception:
        pass
    return infos


def is_ortho4xp_install(root: str) -> bool:
    """Whether *root* is an Ortho4XP installation (its launcher beside its
    data) rather than this app's data folder or engine checkout.

    The witness is Ortho4XP's launcher, ``Ortho4XP*.py``, in *root*
    without this engine's ``src/O4_Config_Names.py`` beside it (this
    engine's source checkout carries ``Ortho4XP.py`` too).
    """
    try:
        if not glob.glob(os.path.join(glob.escape(root), "Ortho4XP*.py")):
            return False
        return not os.path.isfile(os.path.join(root, "src",
                                               "O4_Config_Names.py"))
    except Exception:
        return False


def adopt_global_cfg(root: str | None = None) -> list[str]:
    """The global one-time hand-over (module docstring).

    :param root: the data root; defaults to the current one.
    :returns: INFO lines (empty when nothing happened).
    """
    try:
        if root is None:
            root = os.path.dirname(global_cfg_path())
        ours = os.path.join(root, GLOBAL_CFG_NAME)
        theirs = os.path.join(root, ORTHO4XP_GLOBAL_CFG_NAME)
        if os.path.lexists(ours) or not os.path.isfile(theirs):
            return []
        if is_ortho4xp_install(root):
            return []
        if _exclusive_copy(theirs, ours):
            return ["global settings copied from %s to %s; %s is no longer "
                    "read or written (owner ruling RULINGS 2026-10-26c)"
                    % (ORTHO4XP_GLOBAL_CFG_NAME, GLOBAL_CFG_NAME,
                       ORTHO4XP_GLOBAL_CFG_NAME)]
    except Exception:
        pass
    return []
