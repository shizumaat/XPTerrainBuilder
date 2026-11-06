"""THE "HIDE DRAPED PHOTOS" ADJUSTMENT in the object stage (issue #1916).

Owner (2026-11-06): "when a package includes draped ortho images in the
airport that would obscure our imagery … let the user choose to hide
draped orthos."  The witness is ``auto_patch_v2.airport.pack_drapes``;
the rewrite is ``dsf_write.write_pack(drapes=)``, which keeps the
pristine DSF as its ``.anchor_bak`` and re-applies the accepted hiding on
every later write; the question is one row of the pack's adjustments
(``adjust_stage``), never a box of its own.

The answer is the user's, per pack (``pack_choice.DRAPE_CHOICES``):
"update" (hide them) and "never" are remembered outside the pack.  Undo
(:func:`drape_choice` ``"undo"``) and the pack's Restore originals put
the photos back.  Nothing here raises into the build.
"""
from __future__ import annotations

import os
import traceback
import typing as _t

from . import pack_choice as _PC
from . import pack_rewrite as _PR
from .pack_choice import relative as _relative

__all__ = ["ACTIONS", "STORE", "PackDrapes", "check", "drape_stage",
           "drape_choice", "undo"]

#: the actions of the ``drapes`` row of the ``pack_adjust`` command
ACTIONS = ("update", "never", "undo")
#: the user's answer per pack ("update" | "never" | "" = ask)
STORE = _PC.Store(_PC.DRAPE_CHOICES)


class PackDrapes(_t.NamedTuple):
    """One pack tile DSF's draped photos over its airports, and the
    hiding the live file already carries."""

    pack_name: str
    dsf_path: str
    drapes: tuple              # ``MissingDef`` rows (``pack_drapes``)
    hidden: tuple              # the recorded hiding, () = none

    @property
    def current(self) -> bool:
        """The live DSF already hides exactly these."""
        return bool(self.hidden) and set(self.hidden) == set(self.drapes)


def check(pack_root: str, lat: int, lon: int, *,
          read_only: bool) -> PackDrapes | None:
    """THE CHECK for one pack's tile DSF, or ``None`` when there is
    nothing to judge (``object_stage.pack_dump``)."""
    from auto_patch_v2.airport import apt_flatten as _af
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import pack_drapes as _pd
    from auto_patch_v2.airport.file_hash import sha256_file

    from .object_stage import pack_dump

    pd = pack_dump(pack_root, lat, lon, read_only=read_only)
    if pd is None:
        return None
    drapes = _pd.draped_orthos(pack_root, pd.dump_path,
                               _pd.airport_areas(_af.apt_dat_of(pack_root)))
    hidden: tuple = ()
    if os.path.isfile(pd.pristine) and pd.pristine != pd.dsf_path:
        entry = _bs.dsf_entry(_bs.read_record(pd.dsf_path),
                              os.path.basename(pd.dsf_path))
        hidden = _pd.recorded(entry, sha256_file(pd.pristine))
    return PackDrapes(pd.pack_name, pd.dsf_path, drapes, hidden)


def _write(pd: PackDrapes, pack_root: str, drapes: tuple) -> None:
    import O4_UI_Utils as UI
    backup = _PR.rewrite_dsf(pack_root, pd.pack_name, pd.dsf_path,
                             drapes=drapes)
    UI.vprint(0, f"  [pack] {pd.pack_name}: "
                 + (f"{sum(m.uses for m in drapes)} draped photo polygon(s) "
                    f"hidden" if drapes else "the draped photos are back")
                 + f" — rewrote {_relative(pack_root, pd.dsf_path)} (the "
                   f"original is kept as {os.path.basename(backup)})")


def _hide(pd: PackDrapes, pack_root: str) -> str:
    """Write the hiding and say so; returns ``"hidden"`` or ``"failed"``."""
    try:
        _write(pd, pack_root, pd.drapes)
    except Exception as exc:
        import O4_UI_Utils as UI
        UI.vprint(0, f"  [pack] {pd.pack_name}: the draped photos could not "
                     f"be hidden ({exc}); the pack is as it was")
        UI.vprint(2, traceback.format_exc())
        return "failed"
    return "hidden"


def drape_stage(plan_, tile, *, writes: bool) -> tuple[str, PackDrapes | None]:
    """The draped-photo step of ONE airport's pack, ahead of its placement
    write.  Returns ``(state, check)``: ``""`` (nothing to say),
    ``"found"`` (the adjustments question names it), ``"hidden"``,
    ``"failed"``, ``"never"``, ``"current"``.  Never raises."""
    import O4_UI_Utils as UI
    pack_root = getattr(plan_, "pack_root", "") or ""
    try:
        pd = check(pack_root, tile.lat, tile.lon, read_only=not writes)
    except Exception as exc:
        UI.vprint(1, f"  [pack] draped-photo check skipped ({exc})")
        UI.vprint(2, traceback.format_exc())
        return "", None
    if pd is None or not pd.drapes:
        return "", pd
    UI.vprint(1, f"  [pack] {pd.pack_name}: {len(pd.drapes)} draped photo "
                 f"definition(s) over its airport cover the tile's imagery")
    if pd.current:
        return "current", pd
    choice = STORE.choice(pack_root)
    if choice == "never":
        return "never", pd
    if writes and choice == "update":
        return _hide(pd, pack_root), pd
    return "found", pd


def drape_choice(pack_root: str, action: str, lat: int | None = None,
                 lon: int | None = None) -> tuple[str, list[str]]:
    """THE USER'S ANSWER for the pack's draped photos (the ``drapes`` row
    of ``pack_adjust``): ``"update"`` remembers it and hides them in the
    tile's DSF now, ``"never"`` remembers it, ``"undo"`` forgets the
    answer and puts the photos back in every DSF of the pack (only the
    tile's with ``lat``/``lon``).  Returns ``(state, files)``; raises on a
    bad action (the caller reports it)."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    if action == "never":
        STORE.remember(pack_root, "never")
        return "never", []
    if action == "undo":
        STORE.remember(pack_root, "")
        files = undo(pack_root, lat, lon)
        return ("undone" if files else "none"), files
    STORE.remember(pack_root, "update")
    pd = check(pack_root, int(lat or 0), int(lon or 0), read_only=False)
    if pd is None or not pd.drapes:
        return "none", []
    if pd.current:
        return "hidden", []
    state = _hide(pd, pack_root)
    return state, ([_relative(pack_root, pd.dsf_path)]
                   if state == "hidden" else [])


def undo(pack_root: str, lat: int | None = None,
         lon: int | None = None) -> list[str]:
    """Put the draped photos back in the pack's DSFs that hide them;
    returns the files rewritten (``pack_rewrite.undo_recorded``)."""
    from auto_patch_v2.airport import pack_drapes as _pd
    name = os.path.basename(os.path.normpath(pack_root))
    return _PR.undo_recorded(
        pack_root, lat, lon, _pd.RECORD_KEY,
        lambda dsf: _write(PackDrapes(name, dsf, (), ()), pack_root, ()))
