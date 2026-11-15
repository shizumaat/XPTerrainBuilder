"""THE PACK'S DENSE GRASS DRAWN AS X-PLANE 12 GRASS (issue #1937, "Optimise
pack" step ``grass``; refs #1707, #1920).

Owner (2026-11-07): "EGLL is a good example that places very dense grass
all around the runways that's very hard on frame rates. Ideally we would
swap it out for an XP12 resource and optimize density for better
performance."  And (2026-11-15) on the density: "You pick a balanced
amount".

WHAT.  A pack's own grass forest (``pack_trees.low_class`` reads it as
``grass``: its name, or nothing taller than ground cover) is re-pointed
at X-Plane 12's grass planter :data:`PLANTER`, and each of its area
polygons drawn at the pack's plant count (``pack_trees_density``'s rule:
``planter cell / pack cell``, never more plants than the pack drew) and
at most :data:`PLANTS_PER_M2` — THE density budget.

THE BUDGET (measured on the owner's packs, ``forest_model``'s triangles
and the side-on cover of the plants; the lane report of 2026-11-15 has
the table): X-Plane 12's grass plant is a 3D mesh of 36-272 triangles
within 100-500 m and a billboard to 2 km, where a pack's grass is one
card.  Seen from a cockpit the grass layer closes at a low count — the
cover at taxi distance is 90 % or more of the pack's from about one
plant per m² — while its triangles go on rising with every plant.
:data:`PLANTS_PER_M2` is that knee.

WHICH.  Only a definition the swap makes lighter: every polygon of it an
area (a line or point forest's plants are its edges'), and its plants
times what one costs every camera around it (``ForestModel.view_weight``)
less than the pack's.  A pack's sparse, short-range grass is left as it
is.  The match is made once, when the user accepts (:func:`plan_grass`),
with the planter's model in the recipe, so every later write re-applies
it (:func:`apply`) without the install.  Undo is the pristine DSF; no
file is written beside the vendor's.
"""
from __future__ import annotations

import math
import os
import typing as _t

import numpy as np

from ..obj8 import resolve_resource
from ..pack_art import declared_definitions
from ..pack_trees import for_top_m, low_class
from ..pack_trees_clear import metre_frame, polygon_blocks
from .forest_model import ForestModel, read_forest

__all__ = ["PLANTER", "PLANTS_PER_M2", "LINE_FOREST", "plan_grass",
           "planter_model", "new_param", "apply", "drawn", "estimate"]

#: X-Plane 12's ground grass (``pack_trees_map.PLANTERS``)
PLANTER = "lib/vegetation/planters/ground/grass_green_1.for"
#: THE DENSITY BUDGET: the most plants per m² the planter draws (module doc)
PLANTS_PER_M2 = 1.0
#: a forest polygon parameter at or above this draws along edges / at vertices
LINE_FOREST = 256
#: the side of the ground cell :func:`drawn` samples a polygon on (m)
STEP_M = 5.0


def planter_model(exports_of: _t.Callable[[str], _t.Sequence[_t.Any]]
                  ) -> ForestModel | None:
    """The heaviest of the files the install draws :data:`PLANTER` as
    (its seasons); ``None`` when it exports none that reads."""
    files = [e if isinstance(e, str) else str(e[0]) for e in exports_of(PLANTER)]
    models = [m for m in (read_forest(f) for f in files) if m is not None]
    return max(models, key=lambda m: m.view_weight(), default=None)


def _models(phys: _t.Sequence[str]) -> ForestModel | None:
    """The heaviest of the grass-class ``.for`` files ``phys`` (one
    definition's seasons); ``None`` when any is not grass or none reads."""
    out = []
    for f in phys:
        top = for_top_m(f)
        if top is None or low_class(f, top, 0.0) != "grass":
            return None
        out.append(read_forest(f))
    models = [m for m in out if m is not None]
    return max(models, key=lambda m: m.view_weight(), default=None)


def _grass(pack_root: str, path: str,
           exports_of: _t.Callable[[str], _t.Sequence[_t.Any]] | None
           ) -> ForestModel | None:
    """The model of a grass-class ``.for`` the pack declares as ``path``
    (its own file, else every file a library exports it as); X-Plane's
    own (``lib/``) is never one."""
    if not path.lower().endswith(".for") or path.startswith("lib/"):
        return None
    rel = path.replace("\\", "/").replace(":", "/")
    phys = resolve_resource(rel, pack_root, None)
    if phys and os.path.isfile(phys):
        return _models([phys])
    files = [e if isinstance(e, str) else str(e[0])
             for e in (exports_of(path) if exports_of else ())]
    return _models(files) if files else None


def _rings(windings, to_m) -> list[list[tuple[float, float]]]:
    return [[to_m(x, y) for x, y, _r in w] for w in windings if len(w) >= 3]


def _area(rings) -> float:
    """Area (m²) of an outer ring less its holes."""
    def shoelace(r):
        return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1)
                       in zip(r, r[1:] + r[:1], strict=True))) / 2.0
    return max(0.0, shoelace(rings[0]) - sum(shoelace(r) for r in rings[1:])) if rings else 0.0


def new_param(param: int, keep: float, cap: int) -> int:
    """A polygon's planter parameter: the pack's plant count (``keep`` =
    planter cell / pack cell) within the budget ``cap``, never below 1."""
    return max(1, min(255, cap, round(param * keep)))


def _cap(planter: ForestModel) -> int:
    return max(1, min(255, round(255 * planter.cell_m2 * PLANTS_PER_M2)))


def plan_grass(pack_root: str, lines: _t.Sequence[str],
               planter: ForestModel | None,
               exports_of: _t.Callable[[str], _t.Sequence[_t.Any]] | None = None
               ) -> dict[str, _t.Any]:
    """The step's plan for the pristine dump ``lines``: ``{"to":
    PLANTER, "planter": model, "cap": parameter, "defs": {declared path:
    {"keep": factor, "from": the pack file's model}}}``, or ``{}`` when no grass of the pack is made
    lighter (module doc)."""
    if planter is None:
        return {}
    defs = declared_definitions(lines)["polygon"]
    models = {i: m for i, p in enumerate(defs)
              if (m := _grass(pack_root, p, exports_of))}
    if not models:
        return {}
    cap, w_after = _cap(planter), planter.view_weight()
    cost: dict[int, list[float]] = {}
    for _s, _e, idx, param, _tail, windings in polygon_blocks(lines):
        if idx not in models:
            continue
        c = cost.setdefault(idx, [0.0, 0.0])
        if param >= LINE_FOREST or not windings:
            c[0] = math.inf                     # an edge or point forest
            continue
        to_m, _d = metre_frame(windings[0][0][1])
        a = _area(_rings(windings, to_m))
        m = models[idx]
        keep = planter.cell_m2 / m.cell_m2
        c[0] += a * (param / 255.0 / m.cell_m2) * m.view_weight()
        c[1] += a * (new_param(param, keep, cap) / 255.0 / planter.cell_m2) * w_after
    chosen = {defs[i]: {"keep": round(planter.cell_m2 / models[i].cell_m2, 6),
                        "from": models[i].to_dict()}
              for i, (before, after) in sorted(cost.items())
              if math.isfinite(before) and after < before}
    if not chosen:
        return {}
    return {"to": PLANTER, "planter": planter.to_dict(), "cap": cap,
            "defs": chosen}


def apply(text: str, plan: _t.Mapping[str, _t.Any]) -> tuple[str, int]:
    """THE ROWS (pure): ``text`` (a DSFTool dump) with each definition of
    ``plan`` naming :data:`PLANTER` and its area polygons at
    :func:`new_param`.  Returns the text and the polygons changed."""
    want = (plan or {}).get("defs") or {}
    if not want:
        return text, 0
    cap = int(plan["cap"])
    out: list[str] = []
    seen, keep, n = 0, {}, 0
    for raw in text.splitlines(keepends=True):
        tok = raw.split()
        end = raw[len(raw.rstrip("\r\n")):]
        if tok[:1] == ["POLYGON_DEF"] and len(tok) >= 2:
            path = raw[len("POLYGON_DEF "):].strip()
            if path in want:
                keep[seen] = float(want[path]["keep"])
                raw = f"POLYGON_DEF {plan['to']}{end}"
            seen += 1
        elif tok[:1] == ["BEGIN_POLYGON"] and len(tok) >= 3:
            try:
                idx, param = int(tok[1]), int(tok[2])
            except ValueError:
                idx, param = -1, LINE_FOREST
            if idx in keep and param < LINE_FOREST:
                raw = " ".join(["BEGIN_POLYGON", tok[1],
                                str(new_param(param, keep[idx], cap)), *tok[3:]]) + end
                n += 1
        out.append(raw)
    return "".join(out), n


def _samples(windings, to_m) -> tuple[np.ndarray, np.ndarray]:
    """Cell centres (m) of the :data:`STEP_M` grid inside a polygon."""
    from shapely import contains_xy
    from shapely.geometry import Polygon
    rings = _rings(windings, to_m)
    if not rings:
        return np.empty(0), np.empty(0)
    poly = Polygon(rings[0], rings[1:])
    x0, y0, x1, y1 = poly.bounds
    xs = np.arange(x0 + STEP_M / 2, x1, STEP_M)
    ys = np.arange(y0 + STEP_M / 2, y1, STEP_M)
    if not len(xs) or not len(ys):
        c = poly.representative_point()
        return np.array([c.x]), np.array([c.y])
    gx, gy = (g.ravel() for g in np.meshgrid(xs, ys))
    inside = contains_xy(poly, gx, gy)
    return gx[inside], gy[inside]


def drawn(lines: _t.Sequence[str], plan: _t.Mapping[str, _t.Any],
          camera: tuple[float, float], after: bool) -> dict[str, float]:
    """What the grass of ``plan`` draws seen from ``camera`` (lat, lon),
    as the pack has it or (``after``) as the step writes it: ``{"polygons",
    "plants", "tris", "runs"}`` — the plants within the forest's ``LOD``,
    their triangles and the draw runs (``ForestModel.runs_in`` per
    polygon)."""
    want = (plan or {}).get("defs") or {}
    defs = declared_definitions(lines)["polygon"]
    planter = ForestModel.from_dict(plan["planter"]) if want else None
    to_m, _d = metre_frame(camera[0])
    cx, cy = to_m(camera[1], camera[0])
    out = {"polygons": 0, "plants": 0.0, "tris": 0.0, "runs": 0}
    pack = {p: ForestModel.from_dict(w["from"]) for p, w in want.items()}
    for _s, _e, idx, param, _tail, windings in polygon_blocks(lines):
        path = defs[idx] if 0 <= idx < len(defs) else ""
        if path not in want or param >= LINE_FOREST:
            continue
        model = planter if after else pack[path]
        n = (new_param(param, float(want[path]["keep"]), int(plan["cap"])) if after
             else param) / 255.0 / model.cell_m2
        xs, ys = _samples(windings, to_m)
        d = np.hypot(xs - cx, ys - cy)
        seen = d < model.lod
        if not seen.any():
            continue
        plants = n * STEP_M * STEP_M
        out["polygons"] += 1
        out["plants"] += plants * float(seen.sum())
        out["tris"] += plants * float(model.tris_of(d).sum())
        out["runs"] += model.runs_in(float(d.min()), float(d.max()))
    return out


def estimate(lines: _t.Sequence[str], plan: _t.Mapping[str, _t.Any]) -> tuple[int, int]:
    """``(polygons, triangles)``: the grass polygons the plan re-points
    and the triangles it saves seen from the middle of them (their
    area-weighted centre)."""
    want = (plan or {}).get("defs") or {}
    if not want:
        return 0, 0
    defs = declared_definitions(lines)["polygon"]
    sx = sy = sw = 0.0
    n = 0
    for _s, _e, idx, param, _tail, windings in polygon_blocks(lines):
        if not (0 <= idx < len(defs) and defs[idx] in want) or param >= LINE_FOREST:
            continue
        n += 1
        pts = [(x, y) for w in windings[:1] for x, y, _r in w]
        to_m, _d = metre_frame(pts[0][1])
        a = _area(_rings(windings[:1], to_m))
        sx += a * sum(p[1] for p in pts) / len(pts)
        sy += a * sum(p[0] for p in pts) / len(pts)
        sw += a
    if not sw:
        return n, 0
    cam = (sx / sw, sy / sw)
    before = drawn(lines, plan, cam, after=False)["tris"]
    after = drawn(lines, plan, cam, after=True)["tris"]
    return n, int(before - after)
