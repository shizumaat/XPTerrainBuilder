"""THE 3D TREES OFFER in the object stage (issue #1360).

Owner (2026-10-26): "When building a tile, if we are also modifying an
airport, identify if the airport uses x-plane 11 style .for resources
that are the old flat planes, and ask the user if they would like to
update their resources to point to the equivalent 3D x-plane 12
resources."

WHERE.  Beside the missing-art check (``object_stage._art_stage``), for
every pack the object stage is about to read: so only a pack the build
modifies, never with "Modify custom airports" off, and a lane build
(measure-only) only reports.  The check itself is
``auto_patch_v2.airport.pack_forests``; the rewrite is
``dsf_write.write_pack(forests=)``, which keeps the pristine DSF as its
``.anchor_bak`` and re-applies the accepted upgrade on every later write.

THE ANSWER IS THE USER'S, PER PACK (:func:`pack_choice`): "Update" and
"Never for this pack" are remembered in the engine's own preferences
folder, never in the pack; "Not now" is not remembered, so the next
build asks again.  A pack the user said Update for is upgraded by later
builds without asking (a new tile, a pack update) and the event says
so; Undo (:func:`forest_choice` ``"undo"``) puts the original
definitions back — the pristine file itself when nothing else of ours
is in the DSF — and forgets the answer.

Nothing here raises into the build: a failed check or write is one log
line and the airport's object stage goes on.
"""
from __future__ import annotations

import json
import os
import shutil
import traceback
import typing as _t

#: the per-pack answers, beside the remembered data-root choice
__all__ = ["ACTIONS", "CHOICES_NAME", "REMEMBERED", "forest_choice", "forest_stage"]

CHOICES_NAME = "pack_forest_choices.json"
#: the answers :func:`set_pack_choice` remembers ("" forgets)
REMEMBERED = ("update", "never")
#: the actions of the ``pack_forests`` command
ACTIONS = ("update", "never", "undo")


def choices_path() -> str:
    import O4_File_Names as FNAMES
    return os.path.join(os.path.dirname(FNAMES.data_root_pointer_file),
                        CHOICES_NAME)


def _pack_key(pack_root: str) -> str:
    return os.path.normcase(os.path.abspath(pack_root or ""))


def _read_choices() -> dict[str, str]:
    try:
        with open(choices_path(), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in doc.items()
            if v in REMEMBERED} if isinstance(doc, dict) else {}


def pack_choice(pack_root: str) -> str:
    """``"update"`` | ``"never"`` | ``""`` (ask)."""
    return _read_choices().get(_pack_key(pack_root), "")


def set_pack_choice(pack_root: str, choice: str) -> None:
    """Remember (or, with ``""``, forget) the user's answer for a pack."""
    doc = _read_choices()
    key = _pack_key(pack_root)
    if choice in REMEMBERED:
        doc[key] = choice
    else:
        doc.pop(key, None)
    path = choices_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


class PackForests(_t.NamedTuple):
    """One pack tile DSF's old forests: what the pristine file declares,
    and the upgrade the live file already carries."""

    pack_name: str
    dsf_path: str
    old: tuple                 # ``pack_forests.OldForest`` rows
    upgraded: dict             # the recorded renames, {} = none

    @property
    def renames(self) -> dict:
        from auto_patch_v2.airport import pack_forests as _pf
        return _pf.renames_of(self.old)

    @property
    def current(self) -> bool:
        """The live DSF already carries exactly this upgrade."""
        return bool(self.upgraded) and self.upgraded == self.renames


def check(pack_root: str, lat: int, lon: int, *,
          read_only: bool) -> PackForests | None:
    """THE CHECK for one pack's tile DSF, or ``None`` when there is
    nothing to judge (``object_stage.pack_dump``, or no library index)."""
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import pack_forests as _pf
    from auto_patch_v2.airport.file_hash import sha256_file

    from . import agp_reader as _agp
    from .object_stage import pack_dump

    pd = pack_dump(pack_root, lat, lon, read_only=read_only)
    if pd is None:
        return None
    old = _pf.old_forests(
        pack_root, pd.dump_path, _agp.get_library_index(pd.xroot),
        os.path.join(pd.xroot, "Resources", "default scenery"),
        lambda: _agp.other_export_names(pd.xroot))
    if old is None:
        return None
    upgraded = {}
    if old and os.path.isfile(pd.pristine) and pd.pristine != pd.dsf_path:
        entry = _bs.dsf_entry(_bs.read_record(pd.dsf_path),
                              os.path.basename(pd.dsf_path))
        upgraded = _pf.recorded(entry, sha256_file(pd.pristine))
    return PackForests(pd.pack_name, pd.dsf_path, tuple(old), upgraded)


def _relative(pack_root: str, path: str) -> str:
    try:
        return os.path.relpath(path, pack_root).replace(os.sep, "/")
    except ValueError:      # Windows: a path on another drive has no relpath
        return path.replace(os.sep, "/")


def _announce(pf: PackForests, pack_root: str, lat: int, lon: int,
              state: str, error: str = "", files: _t.Sequence[str] = ()) -> None:
    """The ``PackOldForests`` event (``UI.pack_old_forests``)."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import pack_forests as _pf
    UI.pack_old_forests(pack=pf.pack_name, pack_root=pack_root, lat=lat,
                        lon=lon, state=state, error=error,
                        can_update=bool(pf.renames), files=list(files),
                        **_pf.summary(pf.old))


def _write(pf: PackForests, pack_root: str, renames: dict) -> None:
    """The pack DSF written with ``renames`` as its forest upgrade and
    everything else of ours as recorded: every airport's placement edits
    and the omission the user accepted (#433)."""
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport import dsf_write as _dw
    from auto_patch_v2.airport import pack_art as _pa
    from auto_patch_v2.airport import pack_journal as _pj
    from auto_patch_v2.airport.file_hash import sha256_file
    from auto_patch_v2.model.placement import BACKUP_SUFFIX, PlacementPlan, Provenance

    from . import dsf_reader as _DSFR
    from .object_stage import _engine_version
    dsf = pf.dsf_path
    backup = dsf + BACKUP_SUFFIX
    omit = (_pa.recorded(_bs.dsf_entry(_bs.read_record(dsf),
                                       os.path.basename(dsf)),
                         sha256_file(backup))
            if os.path.isfile(backup) else ())
    plan = PlacementPlan("", pf.pack_name, pack_root, dsf, backup,
                         Provenance("", _engine_version(), "", {}))
    _pj.snapshot(pack_root, dsf)          # a no-op outside a build (#598)
    _dw.write_pack(pack_root, plan, _DSFR._dsftool_path() or "DSFTool",
                   allow_live_install=True, engine_version=_engine_version(),
                   omit=omit, forests=renames)
    _DSFR.ensure_dsf_text_path(dsf, _dsf2.mod_cache_dir(
        FNAMES.airport_mod_cache_root(), pf.pack_name))
    UI.vprint(0, f"  [pack] {pf.pack_name}: "
                 + (f"{len(renames)} forest definition(s) now point at "
                    f"X-Plane 12 3D trees" if renames else
                    "the original forest definitions are back")
                 + f" — rewrote {_relative(pack_root, dsf)} (the original is "
                   f"kept as {os.path.basename(backup)})")


def _upgrade(pf: PackForests, pack_root: str, lat: int, lon: int) -> str:
    """Write the upgrade and say so; returns the state announced."""
    try:
        _write(pf, pack_root, pf.renames)
    except Exception as exc:
        import O4_UI_Utils as UI
        UI.vprint(0, f"  [pack] {pf.pack_name}: the 3D trees could not be "
                     f"written ({exc}); the pack is as it was")
        UI.vprint(2, traceback.format_exc())
        _announce(pf, pack_root, lat, lon, "failed", str(exc))
        return "failed"
    _announce(pf, pack_root, lat, lon, "upgraded",
              files=[_relative(pack_root, pf.dsf_path)])
    return "upgraded"


def forest_stage(plan_, tile, *, writes: bool) -> str:
    """The 3D trees step of ONE airport's pack, ahead of its placement
    write (which re-applies whatever this step recorded).  Returns what
    happened — ``""`` (nothing to say), ``"found"`` (the user is asked),
    ``"upgraded"``, ``"failed"``, ``"never"``, ``"current"`` — for the
    log and the twins.  Never raises."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import pack_forests as _pf
    pack_root = getattr(plan_, "pack_root", "") or ""
    try:
        pf = check(pack_root, tile.lat, tile.lon, read_only=not writes)
    except Exception as exc:
        UI.vprint(1, f"  [pack] old-forest check skipped ({exc})")
        UI.vprint(2, traceback.format_exc())
        return ""
    if pf is None or not pf.old:
        return ""
    UI.vprint(1, "  " + _pf.log_line(pf.pack_name, pf.old))
    if not pf.renames or pf.current:
        return "current" if pf.renames else ""
    choice = pack_choice(pack_root)
    if choice == "never":
        return "never"
    if writes and choice == "update":
        return _upgrade(pf, pack_root, tile.lat, tile.lon)
    _announce(pf, pack_root, tile.lat, tile.lon, "found")
    return "found"


def forest_choice(pack_root: str, action: str, lat: int | None = None,
                  lon: int | None = None) -> dict:
    """THE USER'S ANSWER, outside a build (the ``pack_forests`` command).

    * ``"update"`` — remember it and upgrade the tile's DSF now;
    * ``"never"`` — remember it; nothing is written;
    * ``"undo"`` — forget the answer and put the original definitions
      back in every DSF of the pack carrying an upgrade (only the tile's
      with ``lat``/``lon``).

    Returns the ``PackOldForests`` fields with ``state`` (``"upgraded"``
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
            set_pack_choice(pack_root, "never")
            out["state"] = "never"
        elif action == "undo":
            set_pack_choice(pack_root, "")
            out["files"] = undo(pack_root, lat, lon)
            out["state"] = "undone" if out["files"] else "none"
        else:
            set_pack_choice(pack_root, "update")
            pf = check(pack_root, int(lat or 0), int(lon or 0),
                       read_only=False)
            if pf is not None and pf.renames:
                out["state"] = ("upgraded" if pf.current else
                                _upgrade(pf, pack_root, int(lat or 0),
                                         int(lon or 0)))
                return out              # _upgrade announced it
    except Exception as exc:
        out["state"], out["error"] = "failed", str(exc)
        UI.vprint(0, f"  [pack] {out['pack']}: 3D trees {action} failed ({exc})")
        UI.vprint(2, traceback.format_exc())
    UI.pack_old_forests(**out)
    return out


def undo(pack_root: str, lat: int | None = None,
         lon: int | None = None) -> list[str]:
    """Put the original forest definitions back in the pack's DSFs that
    carry an upgrade; returns the files rewritten (pack-relative).  A DSF
    holding nothing else of ours gets its pristine file back byte for
    byte and its record entry dropped; one that does is written again
    without the upgrade."""
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import pack_art as _pa
    from auto_patch_v2.airport import pack_forests as _pf

    from . import object_rebake as _OR
    only = None
    if lat is not None and lon is not None:
        only = "%+03d%+04d.dsf" % (int(lat), int(lon))
    done: list[str] = []
    for dsf, entry in _OR.forest_upgraded_dsfs(pack_root):
        if only is not None and os.path.basename(dsf) != only:
            continue
        verdict = _bs.classify_dsf(dsf)
        if verdict.state is not _bs.State.OURS or not verdict.backup:
            continue                    # never a file we cannot prove ours
        bare = not entry.get("airports") and not _pa.recorded(
            entry, entry.get("backup_sha256") or "")
        if bare:
            shutil.copy2(verdict.backup, dsf)
            _bs.invalidate_memo()
            _bs.drop_dsf_entry(dsf)
            import O4_UI_Utils as UI
            UI.vprint(0, f"  [pack] {os.path.basename(os.path.normpath(pack_root))}: "
                         f"{_relative(pack_root, dsf)} is the original again")
        else:
            pf = PackForests(os.path.basename(os.path.normpath(pack_root)),
                             dsf, (), _pf.recorded(entry, entry.get(
                                 "backup_sha256") or ""))
            _write(pf, pack_root, {})
        done.append(_relative(pack_root, dsf))
    return done
