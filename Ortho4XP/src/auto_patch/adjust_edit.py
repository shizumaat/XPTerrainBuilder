"""THE PACK ROW'S "ADJUST…": change what a modified pack hides or
optimises after the fact, rewriting only what the change needs.

Owner (2026-11-15T13:12Z): "make it so there's an option on any modified
pack to adjust the settings rather than just reset, so the user can
change what's hidden or optimized without saving to rebuild the tile -
should just need to make a new DSF right?"

Two actions of the ``pack_adjust`` command (``adjust_stage.adjust_choice``):

* :func:`report` (``"adjust"``) — every adjustment row that applies to
  the pack's tile DSF, answered or not, each ``checked`` as the pack is
  now (``applied``: the live file carries it), and the "Optimise pack"
  ``steps`` with work on the tile, each ``checked`` when the live recipe
  carries it.  Nothing is written.
* :func:`change` (``"change"``) — the answer: a row (of ``shown``) or a
  step whose tick is the same as :func:`report` says is NOT touched;
  each one that differs goes through its own stage (a tick is that
  stage's ``"update"``; an untick puts an applied change back, its
  ``"undo"``, and is remembered as ``"never"``).  Nothing changed, no
  file is written.

WHAT EACH CHOICE REWRITES (the consumer census of the answers):

* ``trees``, ``drapes``, ``ground``, ``generic`` and the Optimise steps
  — the PACK's tile DSF only, written again from its pristine
  ``.anchor_bak`` with everything else of ours as recorded
  (``pack_rewrite.rewrite_dsf`` / ``undo_recorded``; the Optimise copies
  no DSF names any more are removed, ``optimise_stage._optimise``).  The
  tile's build reads a pack DSF the app wrote by its pristine backup's
  identity (``O4_Step_Reuse._patch_inputs`` →
  ``provenance.pack_dsf_identity_list``), and no step of the tile reads
  these answers: the tile is not rebuilt.
* ``terrain`` (:data:`TILE_ROWS`) — the pack DSF AND THE TILE'S MESH:
  ``terrain_cut_stage.cut_records`` cuts the tile's ``.alt`` raster to
  every terrain model the user has NOT hidden (and lays its plan edge
  into the vector map), and its ids are the vector step's input
  ``terrain_cut`` (``O4_Step_Reuse._inputs``): a hide or a show reruns
  the vector step and every step after it.  The seats
  (``terrain_model.seat_records``, the airport patch's object plan) never
  read the answer.  :func:`tile_state` is what the mesh reads; an answer
  that changes it says ``rebuild`` (``adjust_stage.adjust_choice``), the
  app's button is "Apply and rebuild tile" and it queues the tile's build.

Per tile: the writes are the tile's DSF (``lat``/``lon``), as the
question's "update" is.  A failure raises to ``adjust_choice``, which
reports it.
"""
from __future__ import annotations

import typing as _t

__all__ = ["TILE_ROWS", "tile_state", "report", "change"]

#: the rows whose answer the TILE's mesh reads (the terrain cut)
TILE_ROWS = ("terrain",)


def tile_state(pack_root: str) -> tuple:
    """What the tile's mesh reads of the pack's answers: per row of
    :data:`TILE_ROWS`, whether it is "update" (``terrain_cut_stage.
    _hidden``: a hidden model is not cut), and the terrain objects the
    row hides (#2272: the per-object answers move them; one string, so
    the state stays JSON).  An answer that changes it needs the tile
    rebuilt (``PackAdjust.rebuild``)."""
    from auto_patch_v2.airport import pack_choice as _PC
    from auto_patch_v2.airport import pack_terrain as _pt

    from . import drape_stage as _DS
    kinds = {k.key: k for k in _DS.KINDS}
    return tuple(kinds[key].store.choice(pack_root) == "update"
                 for key in TILE_ROWS) + (_pt.encode(_PC.hidden_terrain(pack_root)),)


def _row(base: dict, applied: bool, choice: str) -> dict:
    """``base`` (the question's row) ticked as the pack is now: applied
    in the live file, or answered "update"."""
    return dict(base, checked=bool(applied or choice == "update"),
                applied=bool(applied), rebuild=base["key"] in TILE_ROWS)


def _rows(pack_root: str, lat: int, lon: int) -> list[dict]:
    """Every adjustment row that applies to the pack's tile DSF, in the
    question's order, ticked as the pack is now."""
    from . import adjust_stage as _AS
    from . import drape_stage as _DS
    from . import forest_stage as _FS
    out: list[dict] = []
    pf = _FS.check(pack_root, lat, lon, read_only=False)
    if pf is not None and pf.renames:
        out.append(_row(_AS._trees_row(pf), pf.current or bool(pf.upgraded),
                        _FS.pack_choice(pack_root)))
    found = _DS.check_all(pack_root, lat, lon, read_only=False)
    for kind in _DS.KINDS:
        pd = found.get(kind.key)
        objects = _DS.terrain_object_rows(pack_root) if kind is _DS.TERRAIN else []
        if pd is not None and (pd.drapes or objects):
            # #2272: the terrain row lists every recognised object, so a
            # pack none of whose objects is offered can still hide one
            out.append(dict(_row(_AS._drapes_row(pd, kind.key),
                                 bool(pd.drapes) and set(pd.drapes) <= set(pd.hidden),
                                 kind.store.choice(pack_root)),
                            **({"objects": objects} if objects else {})))
    if _AS._flatten(pack_root, writes=False):
        out.append(dict(_AS._flatten_row(), applied=True, rebuild=False))
    return out


def _optimise(pack_root: str, lat: int, lon: int):
    """``(weight, steps on now)``: the pack's "Optimise pack" check (the
    whole recipe) and the steps its live recipe carries; ``(None, ())``
    when it has nothing to optimise."""
    from . import optimise_stage as _OS
    pw = _OS.check(pack_root, lat, lon, read_only=False, full=True)
    if pw is None or not (pw.can_optimise or pw.optimised):
        return None, ()
    offered = {r["key"] for r in pw.steps}
    return pw, (tuple(s for s in pw.chosen if s in offered)
                if pw.optimised else ())


def report(pack_root: str, lat: int, lon: int) -> dict:
    """The Adjust… report: ``items`` (each row with ``checked``,
    ``applied``, ``rebuild``), ``steps`` (each Optimise step with
    ``checked``) and ``state`` ``"adjust"``, or ``"none"`` when nothing
    applies."""
    items = _rows(pack_root, lat, lon)
    pw, on = _optimise(pack_root, lat, lon)
    steps = [dict(r, checked=r["key"] in on) for r in (pw.steps if pw else ())]
    choose = [r for r in items if not r.get("automatic")]
    return {"items": items, "steps": steps,
            "state": "adjust" if choose or steps else "none"}


def _set(key: str, on: bool, applied: bool, pack_root: str, lat: int,
         lon: int) -> list[str]:
    """One row changed through its own stage; the files written."""
    from . import adjust_stage as _AS
    if on:
        return _AS._answer(key, pack_root, "update", lat, lon)
    files = _AS._answer(key, pack_root, "undo", lat, lon) if applied else []
    return files + _AS._answer(key, pack_root, "never", lat, lon)


def _set_steps(pack_root: str, lat: int, lon: int,
               steps: _t.Iterable[str]) -> list[str] | None:
    """The Optimise steps changed to ``steps`` when they differ from the
    live recipe's: the files written, or ``None`` when they do not."""
    from auto_patch_v2.airport import pack_optimise as _po
    from auto_patch_v2.airport.pack_choice import relative

    from . import optimise_stage as _OS
    pw, on = _optimise(pack_root, lat, lon)
    if pw is None:
        return None
    offered = {r["key"] for r in pw.steps}
    want = tuple(s for s in _po.chosen_steps(steps) if s in offered)
    if set(want) == set(on):
        return None
    if not want:
        files = (_OS.optimise_choice(pack_root, "undo", lat, lon)["files"]
                 if pw.optimised else [])
        _OS.STORE.remember(pack_root, "never")
        return list(files)
    out = _OS.optimise_choice(pack_root, "update", lat, lon, steps=want)
    return ([relative(pack_root, pw.dsf_path)]
            if out.get("state") == "optimised" else [])


def change(pack_root: str, lat: int, lon: int, *,
           items: _t.Iterable[str] | None,
           shown: _t.Iterable[str] | None,
           steps: _t.Iterable[str] | None,
           objects: _t.Mapping[str, bool] | None = None) -> dict:
    """The Adjust… answer: ``items`` the rows left ticked of ``shown``
    (default: every row :func:`report` lists), ``steps`` the Optimise
    steps left ticked (``None``: Optimise untouched), ``objects`` the
    terrain row's per-object ticks (path -> hidden, #2272; ``None``:
    untouched -- a change to them re-applies a ticked row).  Returns
    ``files`` (pack-relative, written) and ``state`` ``"applied"``
    (something changed) or ``"none"``."""
    from . import drape_stage as _DS
    ticked = set(items or ())
    seen = None if shown is None else set(shown)
    files: list[str] = []
    changed: list[str] = []
    moved = False
    if objects is not None:
        was = _DS.terrain_answers(pack_root)
        moved = _DS.terrain_answers(pack_root, objects) != was
    for row in _rows(pack_root, lat, lon):
        key = row["key"]
        if row.get("automatic") or (seen is not None and key not in seen):
            continue
        if moved and key == _DS.TERRAIN.key and key in ticked and row["checked"]:
            # the set the row hides moved: written again from the pristine
            # DSF with the new set (the old one put back first)
            changed.append(key)
            files += _set(key, False, row["applied"], pack_root, lat, lon)
            files += _set(key, True, False, pack_root, lat, lon)
            continue
        if (key in ticked) == row["checked"]:
            continue
        changed.append(key)
        files += _set(key, key in ticked, row["applied"], pack_root, lat, lon)
    written = None if steps is None else _set_steps(pack_root, lat, lon, steps)
    if written is not None:
        changed.append("optimise")
        files += written
    return {"files": sorted(set(files)),
            "state": "applied" if changed or moved else "none"}
