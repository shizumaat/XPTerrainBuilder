"""WHAT EACH STEP OF "OPTIMISE PACK" WOULD DO (issue #1707): the
estimate the question shows beside each step's checkbox.

Owner (2026-11-03): "The optimization dialog should present the user
with the options, all defaulted on with an explanation and estimated
impact, but provide check boxes so they can choose to disable some if
they prefer."  Each row is read from the recipe of every step
(``build_recipe``), one step at a time on top of the previous ones:

* ``dedupe`` — the duplicate placements and the triangles they drew;
* ``swap`` — the placements swapped and the triangles saved from
  ``swap.NEAR_M``;
* ``objects`` — the lighter copies and the triangles no longer drawn
  past ``objcopy.LOD_MAX_M`` (the farthest draw distance a copy gets);
* ``textures`` — the textures rewritten and the video memory saved
  (``textures.estimate_vram``).

A step with nothing to do on the tile is not listed.
"""
from __future__ import annotations

import typing as _t

from . import objcopy as _oc
from . import textures as _tx
from . import weight as _w

__all__ = ["steps"]


def steps(pack_root: str, lines: _t.Sequence[str],
          recipe: _t.Mapping[str, _t.Any]) -> list[dict[str, _t.Any]]:
    """``[{"key", "count", "tris", "mb"}]`` of the steps ``recipe`` (every
    step's) has work for, in ``STEPS`` order."""
    from . import drop_ordinals
    out: list[dict[str, _t.Any]] = []
    drop, counts = drop_ordinals(lines, recipe, frozenset())
    bare = _w.estimate(pack_root, lines, frozenset())
    deduped = _w.estimate(pack_root, lines, drop)
    if counts.get("dropped"):
        out.append(_row("dedupe", counts["dropped"],
                        bare["tris_before"] - deduped["tris_after"]))
    swaps = recipe.get("swap") or {}
    if swaps:
        swapped = _w.estimate(pack_root, lines, drop, swaps=swaps)
        out.append(_row("swap", swapped["swapped"],
                        deduped["tris_after"] - swapped["tris_after"]))
    copies = {p: c for p, c in (recipe.get("objects") or {}).items()
              if c.get("specular") is not None or c.get("lod")}
    if copies:
        plain = _w.estimate(pack_root, lines, drop, swaps=swaps, far_m=_oc.LOD_MAX_M)
        far = _w.estimate(pack_root, lines, drop, swaps=swaps,
                          far_m=_oc.LOD_MAX_M, copies=copies)
        out.append(_row("objects", len(copies),
                        plain["far_after"] - far["far_after"]))
    textures = recipe.get("textures") or {}
    if textures:
        placed = sorted({p for p in (recipe.get("objects") or {})})
        before, after = _tx.estimate_vram(pack_root, placed, placed, textures)
        out.append(_row("textures", len(textures), 0, (before - after) / 1e6))
    return out


def _row(key: str, count: int, tris: int, mb: float = 0.0) -> dict[str, _t.Any]:
    return {"key": key, "count": int(count), "tris": max(0, int(tris)),
            "mb": round(max(0.0, mb), 1)}
