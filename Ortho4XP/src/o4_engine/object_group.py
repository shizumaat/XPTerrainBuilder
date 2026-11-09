"""The OBJECT GROUP the patch editor selects and moves as one (issue #1970,
owner 2026-11-08: "When selecting and reseating any objects in the editor,
it should select, and only allow movement of entire object groups").

A pack may author one building as many placements — KBZN places each
MATERIAL of its hangars as its own object (``3D/HG/BROWN.obj``,
``3D/HG/kbzn-roof.obj``, …) — and the object stage cuts placements into
bodies.  Re-heighting the one placement under the pointer moved a roof
and left its walls.

The group is read from the placement plan ONLY (canonical identity, never
proximity): the connected component, over the plan's SPLIT rows, of

* every body cut from the same placement (the source object), and
* every body of the same §16g footprint unit (``unit_of``; a body with
  none: its §16f zero-plane family, ``family_of``) — the structure group
  the stage seats together.

A placement the plan did not cut is a group of its own.  Pure functions
over :func:`o4_engine.object_seat._plan_entries` values.
"""
from __future__ import annotations

import typing as _t

__all__ = ["group_rows", "group_zeros", "group_seat"]

Entries = _t.Mapping[int, tuple[str, _t.Mapping]]


def _split_rows(entries: Entries) -> dict[int, _t.Mapping]:
    return {row: rec for row, (kind, rec) in entries.items() if kind == "split"}


def _unit(body: _t.Mapping) -> str:
    return str(body.get("unit_of") or body.get("family_of") or "")


def _keys(rec: _t.Mapping) -> set[str]:
    """What ties a split row to others: its bodies' structure units.  (NOT
    its anchor: at KBZN two shared anchors chain the hangar complex and
    the terminal into one 161-object group.)"""
    return {_unit(b) for b in rec.get("bodies") or () if _unit(b)}


def group_rows(entries: Entries, row: int) -> tuple[int, ...]:
    """The rows of ``row``'s group, sorted: ``(row,)`` when the plan did not
    cut it."""
    splits = _split_rows(entries)
    if int(row) not in splits:
        return (int(row),)
    keys = {r: _keys(rec) for r, rec in splits.items()}
    rows_of: dict[str, set[int]] = {}
    for r, ks in keys.items():
        for k in ks:
            rows_of.setdefault(k, set()).add(r)
    seen, todo = {int(row)}, [int(row)]
    while todo:
        for k in keys[todo.pop()]:
            for other in rows_of[k] - seen:
                seen.add(other)
                todo.append(other)
    return tuple(sorted(seen))


def _group_bodies(entries: Entries, rows: _t.Iterable[int]) -> list[_t.Mapping]:
    """Every body of the group's rows (each row's ``bodies``, in row order)."""
    splits = _split_rows(entries)
    return [b for r in sorted(rows) for b in (splits.get(r, {}).get("bodies") or ())]


def _source_names(entries: Entries, rows: _t.Iterable[int]) -> list[str]:
    """The group's source objects' file names, sorted, once each."""
    names = set()
    for r in rows:
        rec = entries.get(r, ("", {}))[1]
        path = str((rec.get("placement") or {}).get("resource") or rec.get("resource") or "")
        if path:
            names.add(path.replace("\\", "/").rsplit("/", 1)[-1])
    return sorted(names)


def _group_ring(bodies: _t.Iterable[_t.Mapping]) -> list[list[float]]:
    """The convex hull (``[lat, lon]`` corners, counter-clockwise, not
    closed) of the bodies' geometry boxes — the outline the editor draws
    around a selected group; ``[]`` with fewer than three corners."""
    from auto_patch_v2.constraints.geometry import _convex_hull_xy
    pts = []
    for b in bodies:
        box = b.get("geom_box") or b.get("plan_box")
        if box and len(box) == 4:
            s, w, n, e = (float(v) for v in box)
            pts += [(s, w), (s, e), (n, e), (n, w)]
    hull = _convex_hull_xy(pts)
    return [[round(a, 8), round(b, 8)] for a, b in hull] if len(hull) >= 3 else []


def group_zeros(entries: Entries, rows: _t.Iterable[int]) -> list[float]:
    """Where the plan puts each body's authored zero (m MSL), the bodies
    off every graded face left out."""
    from auto_patch_v2.airport.placement_coherence import plan_body_zero
    return [z for z in map(plan_body_zero, _group_bodies(entries, rows)) if z is not None]


def group_seat(entries: Entries, row: int, offset_m: float | None = None,
               built: bool = True) -> dict | None:
    """The object inspector's record (``object_seat``'s fields) for the
    group of SPLIT row ``row``; ``None`` when the plan did not cut it.
    ``offset_m``: the lift the user gave the group (``built``: the pack
    DSF was last written with it).  The group's bottom is its lowest
    part's zero; it has no single top."""
    if entries.get(int(row), ("",))[0] != "split":
        return None
    from .object_seat import _m                 # the inspector's metres
    rows = group_rows(entries, row)
    bodies = _group_bodies(entries, rows)
    off = float(offset_m or 0.0)
    zeros = [z + off for z in group_zeros(entries, rows)]
    names = _source_names(entries, rows)
    shown = ", ".join(names[:3]) + (", …" if len(names) > 3 else "")
    lines = [f"Group of {len(rows)} object{'s' if len(rows) != 1 else ''}, "
             f"{len(bodies)} part{'s' if len(bodies) != 1 else ''}: {shown}"]
    if zeros:
        lines.append(f"Bottom {_m(min(zeros))} MSL")
        if max(zeros) - min(zeros) >= 0.05:
            lines.append(f"Parts seated {_m(min(zeros))} to {_m(max(zeros))} MSL")
    else:
        lines.append("Its elevation is not known here.")
    if offset_m:
        why = f"Moved by hand {offset_m:+.2f} m from the build's seat"
        why += "" if built else "; rebuild the tile to place it there"
    else:
        why = "Its parts move together, as one group"
    return {"seat": "group", "bodies": len(bodies), "pending": False,
            "zero_m": min(zeros) if zeros else None,
            "zero_max_m": max(zeros) if zeros else None,
            "ground_m": None, "height_m": None,
            "bottom_m": round(min(zeros), 3) if zeros else None, "top_m": None,
            "why": why, "lines": lines + [why + "."], "user_offset_m": offset_m,
            "group": {"rows": list(rows), "parts": len(bodies), "sources": names,
                      "ring": _group_ring(bodies)}}
