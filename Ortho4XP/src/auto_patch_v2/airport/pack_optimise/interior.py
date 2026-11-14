"""UNDER THE PACK'S OWN ROOF (issue #1707, "Optimise pack" step ``interior``).

Owner (2026-11-14T21:41Z, "Yes to 1 and 2 for optimizer"):

1. a small prop placed under the pack's own roof is drawn only within
   :data:`LOD_M` (its draw distance ``min(vendor, 150 m)``);
2. nothing under that roof — the props and the interior shells — casts
   a shadow (``GLOBAL_no_shadow``).

"Under the roof" is :mod:`.roof`'s geometric reading.  The changes go
into a COPY of the object, ``<stem>.o4opt_in.obj`` (:data:`COPY_SUFFIX`),
written from the vendor file with the object step's own changes
(``objcopy.copy_text``) and these two (:func:`copy_text`); the vendor
file is never written.  A definition placed only under the roof is
re-pointed at the copy; one placed both under and outside it keeps its
outside rows on the vendor file (or the object step's copy) and its rows
under the roof go to the copy, appended as a new definition
(:func:`apply`) — so an object outside never loses its shadow or its
draw distance.  A large object is changed only when every placement of
it is covered (``roof.covered``), and gets no draw distance.

The plan (:func:`plan_interior`) keeps the roof itself (``roof.encode``)
so each write re-tests its rows exactly as the user accepted them.
"""
from __future__ import annotations

import math
import os
import typing as _t

from . import objcopy as _oc
from . import roof as _rf
from . import shape as _sh

__all__ = ["LOD_M", "COPY_SUFFIX", "plan_interior", "copy_params",
           "copy_text", "apply", "estimate"]

#: owner 2026-11-14: the draw distance of a small prop under the roof
LOD_M = 150
#: the copy of ``<stem>.obj`` carrying the interior changes
COPY_SUFFIX = ".o4opt_in.obj"


def _path(pack_root: str, path: str) -> str:
    return os.path.join(pack_root, *path.replace("\\", "/").split("/"))


def _origin(rows: _t.Sequence[tuple[int, str, _t.Sequence[str]]]) -> tuple[float, float]:
    """The grid's origin: the south-west corner of the rows' 1° tile."""
    toks = rows[0][2]
    return float(math.floor(float(toks[3]))), float(math.floor(float(toks[2])))


def plan_interior(pack_root: str, defs: _t.Sequence[str],
                  rows: _t.Sequence[tuple[int, int, _t.Sequence[str]]],
                  skip: _t.AbstractSet[str]) -> dict[str, _t.Any]:
    """The step's plan for the placements ``rows`` (``placement_rows``)
    of the pack's definitions ``defs``, ``skip`` being the ones another
    step replaces (library swaps): ``{"origin": [lat, lon], "roof":
    runs, "defs": {declared path: {"lod": bool, "split": bool}}}``, or
    ``{}`` when nothing stands under a roof."""
    placed = [(o, defs[int(t[1])], t) for o, _i, t in rows
              if _own(defs[int(t[1])], skip)]
    if not placed:
        return {}
    lat0, lon0 = _origin(placed)
    shapes = {p: _sh.read_shape(_path(pack_root, p)) for p in {p for _o, p, _tk in placed}}
    shapes = {p: s for p, s in shapes.items() if s is not None}
    big = [r for r in placed if r[1] in shapes and max(shapes[r[1]].size) >= _oc.SMALL_M]
    insts = _rf.instances(pack_root, big, shapes, lat0, lon0)
    roof = _rf.read_roof(insts, lat0, lon0)
    cells = _rf.decode(_rf.encode(roof))
    by_def: dict[str, list[bool]] = {}
    small = [(p, t) for _o, p, t in placed
             if p in shapes and max(shapes[p].size) < _oc.SMALL_M]
    for p, t in small:
        by_def.setdefault(p, []).append(_rf.under(cells, lat0, lon0, t))
    out: dict[str, dict[str, bool]] = {}
    for p, flags in sorted(by_def.items()):
        if any(flags):
            out[p] = {"lod": _lod_wanted(pack_root, p, shapes[p]),
                      "split": not all(flags)}
    # the roof a later write re-tests: the cells (and their neighbours,
    # for a row a seat nudged) of the rows of a split definition under it
    keys = {(i + di, j + dj)
            for p, t in small if (out.get(p) or {}).get("split")
            and _rf.under(cells, lat0, lon0, t)
            for i, j in (_rf.cell_of(lat0, lon0, t),)
            for di in (-1, 0, 1) for dj in (-1, 0, 1)}
    runs = _rf.encode(roof, keys)
    rows_of: dict[str, int] = {}
    for _o, p, _tk in big:
        rows_of[p] = rows_of.get(p, 0) + 1
    cover: dict[str, list[bool]] = {}
    for inst in insts:
        cover.setdefault(inst.path, []).append(_rf.covered(roof, inst))
    for p, flags in sorted(cover.items()):
        if len(flags) == rows_of[p] and all(flags):     # every placement
            out[p] = {"lod": False, "split": False}
    if not out:
        return {}
    return {"origin": [lat0, lon0], "roof": runs, "defs": out}


def _own(path: str, skip: _t.AbstractSet[str]) -> bool:
    """A pack object the step may copy: the pack's own ``.obj``, not
    replaced by another step, not one of our body files or copies."""
    return (path not in skip and path.lower().endswith(".obj")
            and "__b" not in os.path.basename(path) and ".o4opt" not in path)


def _lod_wanted(pack_root: str, path: str, s: _sh.Shape) -> bool:
    """Whether the copy draws the prop only within :data:`LOD_M`: its
    vendor draw distance is farther (or it has none) and, without one,
    no light of it is inside an animation (the lights' tail block
    cannot carry it)."""
    if s.lod_far is not None:
        return s.lod_far > LOD_M
    return not _oc.scan(_path(pack_root, path))[3]


def copy_params(path: str, plan_def: _t.Mapping[str, _t.Any],
                objects: _t.Mapping[str, _t.Any] | None) -> dict[str, _t.Any]:
    """What the interior copy of ``path`` is written with: the object
    step's params for it (``objects``), its draw distance capped at
    :data:`LOD_M` and no shadow."""
    params = dict((objects or {}).get(path) or {"specular": None, "lod": None})
    params["interior_lod"] = LOD_M if plan_def.get("lod") else None
    if params["interior_lod"] and params.get("lod"):
        params["lod"] = min(int(params["lod"]), LOD_M)
    params["no_shadow"] = True
    return params


def copy_text(phys: str, params: _t.Mapping[str, _t.Any]) -> str:
    """The interior copy of the vendor file ``phys``: the object step's
    copy (``objcopy.copy_text``), then a draw distance of at most
    ``interior_lod`` (a vendor ``ATTR_LOD`` clamped wherever it stands;
    one inserted without) and ``GLOBAL_no_shadow``."""
    base = dict(params)
    cap = base.get("interior_lod")
    if cap and not base.get("lod") and not _oc.scan(phys)[2]:
        base["lod"] = int(cap)
    text = _oc.copy_text(phys, base)
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    lines[3] = f"# o4opt {_oc.stamp(phys, params)}"     # what it is current for
    if cap:
        lines = clamp_lods(lines, int(cap))
    if params.get("no_shadow") and not any(
            ln.split()[:1] == ["GLOBAL_no_shadow"] for ln in lines):
        pc = next(i for i, ln in enumerate(lines)
                  if ln.split()[:1] == ["POINT_COUNTS"])
        lines.insert(pc, "GLOBAL_no_shadow")
    return eol.join(lines)


def clamp_lods(lines: _t.Sequence[str], cap: int) -> list[str]:
    """Every ``ATTR_LOD near far`` (in the header or the body) drawn no
    farther than ``cap``: a block starting short of ``cap`` ends there; a
    block starting at or past it is dropped when it draws triangles and
    kept when it only carries lights."""
    starts = [i for i, ln in enumerate(lines) if ln.split()[:1] == ["ATTR_LOD"]]
    out = list(lines)
    drop: list[tuple[int, int]] = []
    for n, i in enumerate(starts):
        toks = lines[i].split()
        try:
            near, far = float(toks[1]), float(toks[2])
        except (IndexError, ValueError):
            continue
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        if near < cap:
            if far > cap:
                out[i] = f"ATTR_LOD\t{near:g}\t{cap}"
        elif any(ln.split()[:1] == ["TRIS"] for ln in lines[i:end]):
            drop.append((i, end))
    for i, end in reversed(drop):
        del out[i:end]
    return out


def apply(text: str, plan: _t.Mapping[str, _t.Any]) -> tuple[str, int]:
    """THE ROWS (pure): ``text`` (a DSFTool dump) with each definition of
    ``plan`` placed only under the roof naming its interior copy, and
    each one placed both under and outside it with its rows under the
    roof re-pointed at its copy, appended as a new definition.  Returns
    the text and the rows now drawn from an interior copy."""
    want = (plan or {}).get("defs") or {}
    if not want:
        return text, 0
    lat0, lon0 = (float(v) for v in plan["origin"])
    cells = _rf.decode(plan.get("roof") or ())
    lines = text.splitlines(keepends=True)
    eol = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    defs = [ln[len("OBJECT_DEF "):].strip() for ln in lines if ln.startswith("OBJECT_DEF ")]
    if not defs:
        return text, 0
    split = [p for p in dict.fromkeys(defs) if (want.get(p) or {}).get("split")]
    to_copy = {d: len(defs) + split.index(p) for d, p in enumerate(defs) if p in split}
    out: list[str] = []
    seen = moved = 0
    for raw in lines:
        toks = raw.split()
        kw = toks[0] if toks else ""
        if kw == "OBJECT_DEF":
            p = defs[seen]
            seen += 1
            whole = p in want and not want[p].get("split")
            out.append(f"OBJECT_DEF {_oc.copy_path(p, COPY_SUFFIX)}{eol}" if whole else raw)
            if seen == len(defs):
                out.extend(f"OBJECT_DEF {_oc.copy_path(p, COPY_SUFFIX)}{eol}" for p in split)
            continue
        if kw in ("OBJECT", "OBJECT_AGL", "OBJECT_MSL") and len(toks) >= 4:
            try:
                d = int(toks[1])
            except ValueError:
                d = -1
            if 0 <= d < len(defs) and defs[d] in want:
                if d in to_copy:
                    if _rf.under(cells, lat0, lon0, toks):
                        out.append(" ".join([kw, str(to_copy[d]), *toks[2:]]) + eol)
                        moved += 1
                        continue
                else:
                    moved += 1
        out.append(raw)
    return "".join(out), moved


def estimate(pack_root: str, lines: _t.Sequence[str],
             plan: _t.Mapping[str, _t.Any]) -> tuple[int, int]:
    """``(placements, triangles)``: the placements the plan draws from an
    interior copy, and the triangles those of them with a capped draw
    distance drew past :data:`LOD_M` and no longer do."""
    from ..dsf_rows import placement_rows
    from ..pack_art import declared_definitions
    want = (plan or {}).get("defs") or {}
    if not want:
        return 0, 0
    defs = declared_definitions(lines)["object"]
    lat0, lon0 = (float(v) for v in plan["origin"])
    cells = _rf.decode(plan.get("roof") or ())
    n = tris = 0
    far: dict[str, int] = {}
    for _o, _i, toks in placement_rows(lines):
        p = defs[int(toks[1])]
        w = want.get(p)
        if w is None or (w.get("split") and not _rf.under(cells, lat0, lon0, toks)):
            continue
        n += 1
        if w.get("lod"):
            if p not in far:
                s = _sh.read_shape(_path(pack_root, p))
                far[p] = 0 if s is None else s.tris_at(LOD_M)
            tris += far[p]
    return n, tris
