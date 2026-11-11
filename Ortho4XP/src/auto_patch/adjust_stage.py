"""THE PACKAGE ADJUSTMENTS of an airport pack the app modifies (#1916).

Owner (2026-11-06): "Similar to the optimize UI, identify if more than one
thing should be adjusted for the package and present the user with the
items checked by default: e.g. Update trees, hide draped orthos included
with the package.  The flatten line should be removed whenever found …
don't ask the user, just include it as an undoable part of the airport
modifications."

ONE QUESTION PER PACK, one row per adjustment that applies
(:data:`CHOICES` the user ticks, each row's ``checked`` its state when
the question opens; ``flatten`` listed as automatic):

* ``trees`` — the X-Plane 12 3D trees (#1360, ``forest_stage``);
* ``drapes`` — hide the pack's draped photos over its airport
  (``drape_stage.PHOTOS``);
* ``ground`` — hide the pack's large draped ground textures over its
  airport (``drape_stage.GROUND``, #1962): the one row that is UNCHECKED
  when the question opens (``checked``), never hidden without the user's
  tick (RULINGS 2026-11-09a (3));
* ``flatten`` — the apt.dat's ``1302 flatten 1`` rows, removed on every
  write with no question (RULINGS 2026-10-20ac;
  ``auto_patch_v2.airport.apt_flatten``), undone by Restore originals.

:func:`adjust_stage` runs in the object stage ahead of the placement
write (which re-applies every accepted choice) and announces a
``PackAdjust`` event when a row still needs the user's answer;
:func:`tile_stage` runs once per tile after it and asks the drape rows of
every other pack on the tile — each airport pack the build did not place
and each companion overlay (RULINGS 2026-11-09a (9), #1968,
``drape_stage.scanned``).  A pack is asked ONCE per tile build (the
``asked`` set they share), however many of its airports were built;
:func:`adjust_choice` is the ``pack_adjust`` command: the answer (a row
ticked is "update", a row shown and left unticked is "never"), Never for
this pack, Undo, and ``"ask"`` — the report of the rows that apply now.
Nothing here raises into the build.
"""
from __future__ import annotations

import os
import traceback
import typing as _t

__all__ = ["CHOICES", "ACTIONS", "adjust_stage", "tile_stage",
           "adjust_choice"]

#: the rows the user chooses, in the question's order
CHOICES = ("trees", "drapes", "ground")
#: the rows left unticked when the question opens
UNCHECKED = ("ground",)
#: the actions of the ``pack_adjust`` command
ACTIONS = ("update", "never", "undo", "ask")


def _trees_row(pf) -> dict:
    from auto_patch_v2.airport import pack_forests as _pf
    s = _pf.summary(pf.old)
    return {"key": "trees", "count": int(s["mapped"]), "uses": int(s["uses"]),
            "automatic": False, "checked": True,
            "first_paths": list(s["first_paths"])}


def _drapes_row(pd, key: str = "drapes") -> dict:
    from auto_patch_v2.airport import pack_drapes as _pdr
    s = _pdr.summary(pd.drapes)
    return {"key": key, "count": int(s["definitions"]),
            "uses": int(s["count"]), "automatic": False,
            "checked": key not in UNCHECKED,
            "first_paths": list(s["first_paths"])}


def _flatten_row() -> dict:
    return {"key": "flatten", "count": 1, "uses": 0, "automatic": True,
            "checked": True, "first_paths": []}


def _writable(pack_root: str) -> bool:
    """A pack the object stage may write: present, enabled, not X-Plane's
    own (``object_stage.pack_dump``'s guards)."""
    import O4_Scenery_Packs as _SP

    from .post_mesh import _is_protected_scenery_root
    return (bool(pack_root) and os.path.isdir(pack_root)
            and not _is_protected_scenery_root(pack_root)
            and _SP.pack_enabled(pack_root))


def _flatten(pack_root: str, *, writes: bool) -> str:
    """The pack's flatten state (``apt_flatten.pack_flatten``), the strip
    written when ``writes``; ``""`` on any failure (one log line)."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import apt_flatten as _af
    if not _writable(pack_root):
        return ""
    name = os.path.basename(os.path.normpath(pack_root))
    try:
        state = _af.pack_flatten(pack_root, write=writes)
    except Exception as exc:
        UI.vprint(0, f"  [pack] {name}: the apt.dat's flatten flag could not "
                     f"be removed ({exc}); it is as it was")
        UI.vprint(2, traceback.format_exc())
        return ""
    if state == "removed":
        UI.vprint(0, f"  [pack] {name}: removed '1302 flatten 1' from its "
                     f"apt.dat (the app's terrain mesh replaces X-Plane's "
                     f"flattening; the original is kept as apt.dat.anchor_bak "
                     f"and Restore originals puts it back)")
    return state


def _announce(pack: str, pack_root: str, lat: int, lon: int, state: str,
              items: _t.Sequence[dict] = (), error: str = "",
              files: _t.Sequence[str] = ()) -> None:
    import O4_UI_Utils as UI
    UI.pack_adjust(pack=pack, pack_root=pack_root, lat=lat, lon=lon,
                   state=state, items=[dict(r) for r in items], error=error,
                   files=list(files))


def _first_ask(pack_root: str, asked: set[str] | None) -> bool:
    """The pack is not yet in ``asked`` (now it is).  ``asked`` keeps the
    path as written (its folder names the pack and is scanned again by
    :func:`tile_stage`); the comparison folds case where the file system
    does (Windows)."""
    if asked is None:
        return True
    root = os.path.normpath(pack_root)
    key = os.path.normcase(root)
    if any(os.path.normcase(a) == key for a in asked):
        return False
    asked.add(root)
    return True


def adjust_stage(plan_, tile, *, writes: bool,
                 asked: set[str] | None = None) -> dict[str, str]:
    """The adjustments of ONE airport's pack, ahead of its placement
    write.  Returns each row's state (``{"flatten": …, "trees": …,
    "drapes": …, "ground": …}``, the stages' own words) for the log and
    the twins, and announces ``PackAdjust(state="found")`` when a row
    asks.  ``asked``: the packs this tile build already adjusted (a pack
    in it returns ``{}``; this one is added).  Never raises."""
    from . import forest_stage as _FS
    pack_root = getattr(plan_, "pack_root", "") or ""
    if not _first_ask(pack_root, asked):
        return {}
    out = {"flatten": _flatten(pack_root, writes=writes)}
    asked: list = []
    out["trees"] = _FS.forest_stage(plan_, tile, writes=writes,
                                    found=asked.append)
    items = [_trees_row(pf) for pf in asked[:1]]
    name = asked[0].pack_name if asked else ""
    for key, (state, pd) in _drape_stages(plan_, tile, writes).items():
        out[key] = state
        if state == "found" and pd is not None:
            items.append(_drapes_row(pd, key))
            name = name or pd.pack_name
    if items:
        if out["flatten"]:
            items.append(_flatten_row())
        _announce(name, pack_root, tile.lat, tile.lon, "found", items)
    return out


def _drape_stages(plan_, tile, writes: bool) -> dict[str, tuple]:
    """Every drape kind's step for one pack, its DSF read once."""
    import O4_UI_Utils as UI

    from . import drape_stage as _DS
    pack_root = getattr(plan_, "pack_root", "") or ""
    try:
        found = _DS.check_all(pack_root, tile.lat, tile.lon,
                              read_only=not writes)
    except Exception as exc:
        UI.vprint(1, f"  [pack] draped-polygon check skipped ({exc})")
        UI.vprint(2, traceback.format_exc())
        return {k.key: ("", None) for k in _DS.KINDS}
    return {k.key: _DS.drape_stage(plan_, tile, writes=writes, kind=k,
                                   found=found) for k in _DS.KINDS}


def _configured_dirs() -> list[str]:
    """The user's Custom Scenery folder (the suite points this at none:
    a test never scans the owner's install, ``tests/conftest.py``)."""
    import O4_Config_Utils as CFG
    return [getattr(CFG, "custom_scenery_dir", "") or ""]


#: where :func:`tile_stage` finds the configured folder (replaceable)
configured_dirs = _configured_dirs


def tile_stage(tile, *, writes: bool, asked: set[str] | None = None,
               scenery_dirs: _t.Iterable[str] | None = None) -> None:
    """THE TILE'S SCAN, once per tile build after the placements
    (RULINGS 2026-11-09a (9)): the drape rows of every pack on the tile
    not in ``asked`` (``drape_stage.scanned`` — an airport pack this build
    did not place, a companion overlay), each asked as that pack's own
    question.  ``scenery_dirs``: the Custom Scenery folders to scan
    (default: the configured one and those of the packs in ``asked``).
    Never raises."""
    import types

    import O4_UI_Utils as UI

    from . import drape_stage as _DS
    asked = set() if asked is None else asked
    try:
        if scenery_dirs is None:
            scenery_dirs = (configured_dirs()
                            + [os.path.dirname(p) for p in sorted(asked)])
        dirs: dict[str, str] = {}
        for d in scenery_dirs:
            if d:
                dirs.setdefault(os.path.normcase(os.path.normpath(d)), d)
        roots = [r for d in dirs.values() if os.path.isdir(d)
                 for r in _DS.scanned(d, tile.lat, tile.lon)]
    except Exception as exc:
        UI.vprint(1, f"  [pack] tile pack scan skipped ({exc})")
        UI.vprint(2, traceback.format_exc())
        return
    from tile_bundle import pack_dev as _dev
    for root in roots:
        if _dev.objects_frozen(root) or not _first_ask(root, asked):
            continue                        # RULINGS 11m (3): the author's
        plan_ = types.SimpleNamespace(pack_root=root)
        items = [_drapes_row(pd, key) for key, (state, pd)
                 in _drape_stages(plan_, tile, writes).items()
                 if state == "found" and pd is not None]
        if items:
            _announce(os.path.basename(os.path.normpath(root)), root,
                      tile.lat, tile.lon, "found", items)


def rows(pack_root: str, lat: int, lon: int) -> list[dict]:
    """THE REPORT: every adjustment that applies to the pack's tile DSF
    now — a row the user already answered "never" for, or that the live
    file already carries, is not listed."""
    from . import drape_stage as _DS
    from . import forest_stage as _FS
    out: list[dict] = []
    pf = _FS.check(pack_root, lat, lon, read_only=False)
    if (pf is not None and pf.renames and not pf.current
            and _FS.pack_choice(pack_root) != "never"):
        out.append(_trees_row(pf))
    found = _DS.check_all(pack_root, lat, lon, read_only=False)
    for kind in _DS.KINDS:
        pd = found.get(kind.key)
        if (pd is not None and pd.drapes and not pd.current
                and kind.store.choice(pack_root) != "never"):
            out.append(_drapes_row(pd, kind.key))
    if _flatten(pack_root, writes=False):
        out.append(_flatten_row())
    return out


def _answer(key: str, pack_root: str, action: str, lat, lon) -> list[str]:
    """One row's answer through its own stage; returns the files written."""
    from . import drape_stage as _DS
    from . import forest_stage as _FS
    if key == "trees":
        return list(_FS.forest_choice(pack_root, action, lat, lon)
                    .get("files") or [])
    kind = next(k for k in _DS.KINDS if k.key == key)
    return _DS.drape_choice(pack_root, action, lat, lon, kind)[1]


def adjust_choice(pack_root: str, action: str, lat: int | None = None,
                  lon: int | None = None,
                  items: _t.Iterable[str] | None = None,
                  shown: _t.Iterable[str] | None = None) -> dict:
    """THE USER'S ANSWER, outside a build (the ``pack_adjust`` command).

    * ``"update"`` — every row in ``items`` (default: every row) is
      applied and remembered; a row in ``shown`` (default: the rows of
      :data:`CHOICES`) left out of ``items`` is remembered as "never";
    * ``"never"`` — every row in ``shown`` is remembered as "never";
    * ``"undo"`` — every row of ``items`` (default: all) is forgotten and
      undone in every DSF of the pack (only the tile's with ``lat``/
      ``lon``);
    * ``"ask"`` — nothing is written: the report (:func:`rows`), announced
      as ``state="ask"``.

    Returns the ``PackAdjust`` fields; ``state`` is ``"applied"`` |
    ``"never"`` | ``"undone"`` | ``"ask"`` | ``"none"`` | ``"failed"``.
    Never raises."""
    import O4_UI_Utils as UI
    out = {"pack": os.path.basename(os.path.normpath(pack_root or "")),
           "pack_root": pack_root, "lat": int(lat or 0), "lon": int(lon or 0),
           "state": "none", "error": "", "files": [], "items": []}
    try:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        if not os.path.isdir(pack_root or ""):
            raise ValueError(f"not a scenery pack folder: {pack_root!r}")
        picked = [k for k in CHOICES if items is None or k in set(items)]
        seen = [k for k in CHOICES if shown is None or k in set(shown)]
        files: list[str] = []
        if action == "ask":
            out["items"] = rows(pack_root, int(lat or 0), int(lon or 0))
            out["state"] = "ask" if out["items"] else "none"
        elif action == "never":
            for key in seen:
                files += _answer(key, pack_root, "never", lat, lon)
            out["state"] = "never"
        elif action == "undo":
            for key in picked:
                files += _answer(key, pack_root, "undo", lat, lon)
            out["state"] = "undone" if files else "none"
        else:
            for key in seen:
                files += _answer(key, pack_root,
                                 "update" if key in picked else "never",
                                 lat, lon)
            out["state"] = "applied"
        out["files"] = sorted(set(files))
    except Exception as exc:
        out["state"], out["error"] = "failed", str(exc)
        UI.vprint(0, f"  [pack] {out['pack']}: package adjustments {action} "
                     f"failed ({exc})")
        UI.vprint(2, traceback.format_exc())
    UI.pack_adjust(**out)
    return out
