"""THE "OPTIMISE PACK" OFFER in the object stage (issue #1707).

Owner (2026-10-30): an opt-in "optimise pack" option for an airport pack
too heavy to fly, applied only to the rebaked copy, per pack, reversible
from the pristine backup.  And (2026-10-31): "the optimisations must be
applied inside ``write_pack``, re-applied on every write from the
pristine file, the same way an accepted #1360 forest upgrade is."

WHERE.  Right after the 3D trees step (``forest_stage``), for every pack
the object stage is about to read: so only a pack the build modifies,
never with "Modify custom airports" off, and a lane build (measure-only)
only reports.  The recipe is ``auto_patch_v2.airport.pack_optimise``; the
rewrite is ``dsf_write.write_pack(optimise=)``, which keeps the pristine
DSF as its ``.anchor_bak`` and re-applies the accepted recipe on every
later write.

THE OFFER: a pack whose own objects draw more than
``pack_optimise.weight.OFFER_TRIANGLES`` on the tile, and that the recipe
can lighten (duplicate placements D1, library swaps D2, lighter object
copies O1/O2).  The answer is the
user's, per pack (``pack_choice``): "Optimise" and "Never for this pack"
are remembered outside the pack, "Not now" is not.  The pack's row under
Modified airports optimises at any weight, and undoes it.

Nothing here raises into the build: a failed check or write is one log
line and the airport's object stage goes on.
"""
from __future__ import annotations

import os
import traceback
import typing as _t

from . import pack_choice as _PC
from . import pack_rewrite as _PR
from .pack_choice import relative as _relative

__all__ = ["ACTIONS", "CHOICES_NAME", "STORE", "optimise_choice", "optimise_stage",
           "recorded_key"]

#: the per-pack answers, beside the remembered data-root choice
CHOICES_NAME = _PC.OPTIMISE_CHOICES
#: the actions of the ``pack_optimise`` command
ACTIONS = ("update", "never", "undo")


#: the user's answer per pack ("update" | "never" | "" = ask)
STORE = _PC.Store(CHOICES_NAME)


class PackWeight(_t.NamedTuple):
    """One pack tile DSF's weight: what its pristine file's own objects
    draw, what the recipe would drop, and the recipe the live file
    already carries."""

    pack_name: str
    dsf_path: str
    tris_before: int
    tris_after: int
    dedupe: int                # duplicate placements the recipe drops
    optimised: dict            # the recorded recipe, {} = none
    recipe: dict = {}          # the recipe "Optimise" writes today
    swapped: int = 0           # placements swapped for library objects

    @property
    def heavy(self) -> bool:
        from auto_patch_v2.airport.pack_optimise.weight import OFFER_TRIANGLES
        return self.tris_before > OFFER_TRIANGLES

    @property
    def can_optimise(self) -> bool:
        return (self.dedupe > 0 or self.swapped > 0
                or bool((self.recipe or {}).get("objects")))

    @property
    def wanted(self) -> dict:
        """The recipe "Optimise" writes: the check's, else the rules that
        need no match."""
        from auto_patch_v2.airport import pack_optimise as _po
        return self.recipe or _po.default_recipe()

    @property
    def current(self) -> bool:
        """The live DSF already carries today's recipe."""
        return bool(self.optimised) and self.optimised == self.wanted


def check(pack_root: str, lat: int, lon: int, *,
          read_only: bool, full: bool = False) -> PackWeight | None:
    """THE CHECK for one pack's tile DSF, or ``None`` when there is
    nothing to judge (``object_stage.pack_dump``).  The whole recipe (the
    library swaps, the object and texture copies: every placed object
    file read) is made only for a pack heavy enough to be offered, or
    with ``full`` (the user said Optimise); any other pack is weighed on
    its duplicates alone, from the OBJ headers."""
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import pack_optimise as _po
    from auto_patch_v2.airport.file_hash import sha256_file
    from auto_patch_v2.airport.pack_optimise import weight as _w

    from . import agp_reader as _agp
    from .object_stage import pack_dump

    pd = pack_dump(pack_root, lat, lon, read_only=read_only)
    if pd is None:
        return None
    with open(pd.dump_path, encoding="utf-8", errors="surrogateescape") as fh:
        lines = fh.read().splitlines(keepends=True)
    recipe = _po.default_recipe()
    drop, counts = _po.drop_ordinals(lines, recipe, frozenset())
    est = _w.estimate(pack_root, lines, drop)
    if full or est["tris_before"] > _w.OFFER_TRIANGLES:
        exports = _agp.export_files(pd.xroot) if pd.xroot else None
        recipe = _po.build_recipe(
            pack_root, lines,
            (lambda v: _agp.files_at(exports.get(v.lower(), ()), lat, lon))
            if exports else None)
        est = _w.estimate(pack_root, lines, drop, swaps=recipe.get("swap"))
    optimised = {}
    if os.path.isfile(pd.pristine) and pd.pristine != pd.dsf_path:
        entry = _bs.dsf_entry(_bs.read_record(pd.dsf_path),
                              os.path.basename(pd.dsf_path))
        optimised = _po.recorded(entry, sha256_file(pd.pristine))
    return PackWeight(pd.pack_name, pd.dsf_path, est["tris_before"],
                      est["tris_after"], int(counts.get("dropped", 0)),
                      optimised, recipe, int(est["swapped"]))


def recorded_key(pack_root: str, lat: int, lon: int) -> str:
    """The key of the recipe the tile DSF's record holds, ``""`` for none
    — the object stage reuse's input (#879): an optimise or its Undo
    re-runs the airport."""
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport import pack_optimise as _po
    dsf = _dsf2.dsf_path_in_pack(pack_root, lat, lon)
    row = _bs.dsf_entry(_bs.read_record(dsf), os.path.basename(dsf)).get(
        _po.RECORD_KEY)
    return str(row.get("key") or "") if isinstance(row, dict) else ""


def _millions(n: int) -> str:
    return f"{n / 1e6:.1f} M"


def log_line(pw: PackWeight) -> str:
    """The engine log line for a pack the recipe can lighten."""
    return (f"[pack] {pw.pack_name}: its own objects draw "
            f"{_millions(pw.tris_before)} triangles on this tile; "
            f"{pw.dedupe} placement(s) are duplicates and {pw.swapped} "
            f"vehicle(s) have a lighter X-Plane library equivalent "
            f"(Optimise pack: {_millions(pw.tris_after)})")


def _announce(pw: PackWeight, pack_root: str, lat: int, lon: int,
              state: str, error: str = "", files: _t.Sequence[str] = ()) -> None:
    """The ``PackOptimise`` event (``UI.pack_optimise``)."""
    import O4_UI_Utils as UI
    UI.pack_optimise(pack=pw.pack_name, pack_root=pack_root, lat=lat, lon=lon,
                     state=state, error=error, dedupe=pw.dedupe,
                     swapped=pw.swapped,
                     est_tris_before=pw.tris_before,
                     est_tris_after=pw.tris_after,
                     can_optimise=pw.can_optimise, files=list(files))


def _write(pw: PackWeight, pack_root: str, recipe: dict) -> None:
    """The pack DSF written with ``recipe`` as its optimisation and
    everything else of ours as recorded."""
    import O4_UI_Utils as UI
    dsf = pw.dsf_path
    backup = _PR.rewrite_dsf(pack_root, pw.pack_name, dsf, optimise=recipe)
    UI.vprint(0, f"  [pack] {pw.pack_name}: "
                 + (f"optimised — {pw.dedupe} duplicate placement(s) dropped, "
                    f"{pw.swapped} swapped for X-Plane library objects"
                    if recipe else "the original placements are back")
                 + f" — rewrote {_relative(pack_root, dsf)} (the original is "
                   f"kept as {os.path.basename(backup)})")


def _optimise(pw: PackWeight, pack_root: str, lat: int, lon: int) -> str:
    """Write the recipe and say so; returns the state announced."""
    try:
        _write(pw, pack_root, pw.wanted)
    except Exception as exc:
        import O4_UI_Utils as UI
        UI.vprint(0, f"  [pack] {pw.pack_name}: the pack could not be "
                     f"optimised ({exc}); it is as it was")
        UI.vprint(2, traceback.format_exc())
        _announce(pw, pack_root, lat, lon, "failed", str(exc))
        return "failed"
    _announce(pw, pack_root, lat, lon, "optimised",
              files=[_relative(pack_root, pw.dsf_path)])
    return "optimised"


def optimise_stage(plan_, tile, *, writes: bool) -> str:
    """The "Optimise pack" step of ONE airport's pack, ahead of its
    placement write (which re-applies whatever this step recorded).
    Returns what happened — ``""`` (nothing to say), ``"found"`` (the
    user is asked), ``"optimised"``, ``"failed"``, ``"never"``,
    ``"current"`` — for the log and the twins.  Never raises."""
    import O4_UI_Utils as UI
    pack_root = getattr(plan_, "pack_root", "") or ""
    choice = STORE.choice(pack_root)
    try:
        pw = check(pack_root, tile.lat, tile.lon, read_only=not writes,
                   full=writes and choice == "update")
    except Exception as exc:
        UI.vprint(1, f"  [pack] optimise check skipped ({exc})")
        UI.vprint(2, traceback.format_exc())
        return ""
    if pw is None or not pw.can_optimise:
        return ""
    if pw.current:
        return "current"
    if choice == "never":
        return "never"
    if writes and choice == "update":
        return _optimise(pw, pack_root, tile.lat, tile.lon)
    if not pw.heavy:
        return ""
    UI.vprint(1, "  " + log_line(pw))
    _announce(pw, pack_root, tile.lat, tile.lon, "found")
    return "found"


def optimise_choice(pack_root: str, action: str, lat: int | None = None,
                    lon: int | None = None) -> dict:
    """THE USER'S ANSWER, outside a build (the ``pack_optimise`` command).

    * ``"update"`` — remember it and optimise the tile's DSF now;
    * ``"never"`` — remember it; nothing is written;
    * ``"undo"`` — forget the answer and put the original placements
      back in every optimised DSF of the pack (only the tile's with
      ``lat``/``lon``).

    Returns the ``PackOptimise`` fields with ``state`` (``"optimised"``
    | ``"never"`` | ``"undone"`` | ``"none"`` | ``"failed"``).  Never
    raises."""
    import O4_UI_Utils as UI
    out = {"pack": os.path.basename(os.path.normpath(pack_root or "")),
           "pack_root": pack_root, "lat": int(lat or 0), "lon": int(lon or 0),
           "state": "none", "error": "", "files": []}
    try:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        if not os.path.isdir(pack_root or ""):
            raise ValueError(f"not a scenery pack folder: {pack_root!r}")
        if action == "never":
            STORE.remember(pack_root, "never")
            out["state"] = "never"
        elif action == "undo":
            STORE.remember(pack_root, "")
            out["files"] = undo(pack_root, lat, lon)
            out["state"] = "undone" if out["files"] else "none"
        else:
            STORE.remember(pack_root, "update")
            pw = check(pack_root, int(lat or 0), int(lon or 0),
                       read_only=False, full=True)
            if pw is not None and pw.can_optimise and not pw.current:
                out["state"] = _optimise(pw, pack_root, int(lat or 0),
                                         int(lon or 0))
                return out              # _optimise announced it
            if pw is not None and pw.current:
                out["state"] = "optimised"
    except Exception as exc:
        out["state"], out["error"] = "failed", str(exc)
        UI.vprint(0, f"  [pack] {out['pack']}: optimise {action} failed ({exc})")
        UI.vprint(2, traceback.format_exc())
    UI.pack_optimise(**out)
    return out


def undo(pack_root: str, lat: int | None = None,
         lon: int | None = None) -> list[str]:
    """Put the original placements back in the pack's optimised DSFs;
    returns the files rewritten (pack-relative) — byte for byte when
    nothing else of ours is in a DSF (``pack_rewrite.undo_recorded``)."""
    from auto_patch_v2.airport import pack_optimise as _po
    name = os.path.basename(os.path.normpath(pack_root))
    before = _generated(pack_root)
    done = _PR.undo_recorded(
        pack_root, lat, lon, _po.RECORD_KEY,
        lambda dsf: _write(PackWeight(name, dsf, 0, 0, 0, {}), pack_root, {}))
    # a file the recipe wrote goes once no optimised DSF names it
    _po.remove_generated(pack_root, before - _generated(pack_root))
    return done


def _generated(pack_root: str) -> set[str]:
    """Every file the pack's optimised DSFs' records say the recipe wrote."""
    from auto_patch_v2.airport import pack_optimise as _po

    from . import object_rebake as _OR
    return {f for _dsf, entry in _OR.recorded_dsfs(pack_root, _po.RECORD_KEY)
            for f in _po.generated_of(entry)}
