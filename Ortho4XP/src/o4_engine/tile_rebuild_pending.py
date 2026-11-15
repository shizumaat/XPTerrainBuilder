"""THE TILE REBUILDS A PACK ANSWER STILL OWES.

"Hide terrain objects" opens ticked (owner 2026-11-15T13:12Z), and its
answer is the one the tile's MESH reads (``auto_patch.adjust_edit.
TILE_ROWS``: ``terrain_cut_stage`` cuts the ground under every model the
user has not hidden, in the vector step).  The question arrives in the
object stage, after the vector step, so an answer given during a build
leaves the pack hiding the object over ground still cut to it.  This
module is the engine's record of that debt, so both apps read the same
state:

* :func:`mark` — a ``pack_adjust`` answer changed what the tile's mesh
  reads (``PackAdjust.rebuild``; ``EngineSession.pack_adjust``).  A later
  answer that puts the pack back as the mesh was built drops the debt.
* :func:`_pending` — the debts still open, announced after every run that
  was not cancelled as ``PackAdjust(state="pending")``
  (:func:`announcement`): each app rebuilds those tiles.
* :func:`resolve` — at a built tile's ``BuildDone``: when the tile's
  vector step was last run on the answers as they are now (its step
  record's ``terrain_cut`` input, ``O4_Step_Reuse``, equals the live
  ``terrain_cut_stage.cut_records``), the debt is paid and the tile's
  ``BuildDone.notes`` says so (:func:`note`, "Tile X was built to
  match: terrain objects hidden in …").

One JSON file beside the remembered data-root choice
(``auto_patch.pack_choice.store_path``), keyed by tile and pack.  Never
raises.
"""
from __future__ import annotations

import json
import os
import time
import typing as _t

__all__ = ["FILE", "mark", "resolve", "note", "announcement"]

#: the debts file
FILE = "tile_rebuild_pending.json"


def _path() -> str:
    from auto_patch import pack_choice as _PC
    return _PC.store_path(FILE)


def _read() -> dict:
    try:
        with open(_path(), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(doc: dict) -> None:
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def _tile_key(lat: int, lon: int) -> str:
    import O4_File_Names as FNAMES
    return FNAMES.short_latlon(int(lat), int(lon))


def mark(lat: int, lon: int, pack_root: str, pack: str,
         was: _t.Sequence[bool], now: _t.Sequence[bool]) -> None:
    """A pack's answer changed what tile ``lat``/``lon``'s mesh reads from
    ``was`` to ``now`` (``adjust_edit.tile_state``).  The first ``was``
    is kept: an answer back to it drops the debt."""
    try:
        doc = _read()
        key = _tile_key(lat, lon)
        packs = doc.setdefault(key, {})
        root = os.path.normcase(os.path.abspath(pack_root or ""))
        first = list((packs.get(root) or {}).get("was", list(was)))
        if list(now) == first:
            packs.pop(root, None)
        else:
            packs[root] = {"lat": int(lat), "lon": int(lon), "pack": pack,
                           "change": "hidden" if any(now) else "shown",
                           "was": first, "id": "%s@%.3f" % (key, time.time())}
        if not packs:
            doc.pop(key, None)
        _write(doc)
    except Exception:
        pass


def _pending() -> list[dict]:
    """Every open debt: ``{"lat", "lon", "tile", "pack", "change", "id"}``."""
    return [dict({k: v for k, v in row.items() if k != "was"}, tile=key)
            for key, packs in sorted(_read().items())
            if isinstance(packs, dict)
            for _root, row in sorted(packs.items()) if isinstance(row, dict)]


def _mesh_matches(tile) -> bool:
    """The tile's vector step last ran on the terrain answers as they are."""
    import O4_File_Names as FNAMES
    import O4_Step_Reuse as SR
    from auto_patch import terrain_cut_stage as _TC
    recorded = (SR.committed_entry(tile, "vector").get("inputs") or {})
    if "terrain_cut" not in recorded:
        return False
    live = sorted(str(r.get("id")) for r in _TC.cut_records(
        FNAMES.patch_dir(tile.lat, tile.lon)))
    return recorded["terrain_cut"] == live


def resolve(tile) -> list[dict]:
    """The debts of ``tile`` its build has paid (removed from the file)."""
    try:
        doc = _read()
        key = _tile_key(tile.lat, tile.lon)
        if not doc.get(key) or not _mesh_matches(tile):
            return []
        rows = [dict(r, tile=key) for r in doc.pop(key).values()
                if isinstance(r, dict)]
        _write(doc)
        return rows
    except Exception:
        return []


def note(row: _t.Mapping[str, _t.Any]) -> dict:
    """A paid debt as a ``BuildDone.notes`` entry (the folded shape of
    ``O4_Tile_Failures.fold``, severity ``info``)."""
    change = row.get("change", "hidden")
    pack = row.get("pack", "")
    return {"code": "rebuilt_to_match", "severity": "info",
            "what": "Tile %s was built to match: terrain objects %s in “%s”."
                    % (row.get("tile", ""), change, pack),
            "why": ("Its terrain objects were %s in the package’s "
                    "adjustments after the tile was last built; the ground "
                    "under them now matches." % change),
            "remedy": "Nothing to do.", "cells": [], "airports": [],
            "link": "", "detail": "", "log_path": ""}


def announcement() -> dict | None:
    """The ``PackAdjust(state="pending")`` fields for the open debts, or
    ``None`` with none."""
    rows = _pending()
    if not rows:
        return None
    return {"state": "pending", "items": rows,
            "lat": int(rows[0]["lat"]), "lon": int(rows[0]["lon"]),
            "rebuild": True}
