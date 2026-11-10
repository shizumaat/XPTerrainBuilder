"""The ortho budget of imagery on demand (#1992, RULINGS 2026-11-10c (2)):
one budget holds every installed on-demand tile's imagery, favorites
included.

The budget is GENERIC on purpose -- a cap, the bytes in it nothing can
free, and an ordered list of tiers of what to clear first -- so the sweep
(``o4_engine.imagery_downgrade.sweep``) reads a :class:`Budget` and never
a setting or a store of its own.

* :data:`CLEAR_TIERS` -- what is made low-res first: ordinary sharp
  imagery, then airport cores (spec §6.1), then favorites.
* :func:`tier_of` -- an index row's tier (its position in
  :data:`CLEAR_TIERS`).
* :func:`placeholder_bytes` / :func:`build_dirs` / :func:`dsf_bytes` --
  the parts of the floor (the total disk budget, ``o4_engine.storage_budget``,
  reads them too).
* :func:`floor_bytes` -- the bytes the on-demand tiles hold even at
  placeholder resolution: every row's kept placeholder (counted once) and
  each tile's scenery files (``Earth nav data/*/*.dsf``).
* :class:`Budget` -- ``cap`` and ``fixed`` (the floor); its
  :meth:`Budget.total` of the sharp bytes and :attr:`Budget.over_at_floor`
  (the built tiles do not fit even low-res: the apps warn).
* :func:`measure` -- the :class:`Budget` of an index for a cap.

Pure but for ``os.stat``; no tile or airport is named here.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

__all__ = ["CLEAR_TIERS", "Budget", "build_dirs", "dsf_bytes", "floor_bytes",
           "measure", "placeholder_bytes", "tier_of"]

#: Made low-res first to last (favorites last, airport cores just before).
CLEAR_TIERS = ("sharp", "airport", "favorite")


def tier_of(row: dict) -> int:
    """The row's position in :data:`CLEAR_TIERS`."""
    if row.get("pinned"):
        return CLEAR_TIERS.index("favorite")
    return CLEAR_TIERS.index("airport" if row.get("core") else "sharp")


def _size(path: str) -> int:
    try:
        return os.stat(path).st_size
    except OSError:
        return 0


def placeholder_bytes(conn) -> int:
    """The kept placeholders of the index, one per distinct file."""
    return sum(_size(path) for path in {
        os.path.normcase(os.path.abspath(path)) for (path,) in conn.execute(
            "SELECT placeholder_path FROM textures") if path})


def build_dirs(conn) -> "set[str]":
    """The build folders of the index's tiles."""
    return {os.path.abspath(folder) for (folder,) in conn.execute(
        "SELECT DISTINCT build_dir FROM textures") if folder}


def dsf_bytes(folders) -> int:
    """The scenery files (``Earth nav data/*/*.dsf``) of ``folders``, each
    real folder once."""
    total = 0
    for folder in {os.path.realpath(f) for f in folders}:
        pattern = os.path.join(glob.escape(folder), "Earth nav data", "*", "*.dsf")
        total += sum(_size(path) for path in glob.glob(pattern))
    return total


def floor_bytes(conn) -> int:
    """Placeholders plus each on-demand tile's DSF files: what the tiles
    use at their lowest resolution."""
    return placeholder_bytes(conn) + dsf_bytes(build_dirs(conn))


@dataclass(frozen=True)
class Budget:
    """``cap`` bytes, of which ``fixed`` nothing can free."""

    cap: int
    fixed: int = 0

    def total(self, clearable: int) -> int:
        """The budget's use with ``clearable`` sharp bytes on top."""
        return int(self.fixed) + int(clearable)

    @property
    def over_at_floor(self) -> bool:
        """The installed tiles exceed the budget even low-res."""
        return self.fixed > self.cap


def measure(conn, cap: int) -> Budget:
    """The :class:`Budget` of the index ``conn`` for ``cap`` bytes."""
    return Budget(int(cap), floor_bytes(conn))
