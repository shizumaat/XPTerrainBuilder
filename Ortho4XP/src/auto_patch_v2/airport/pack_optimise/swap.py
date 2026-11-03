"""D2 — HEAVY VEHICLES SWAPPED FOR X-PLANE'S LIBRARY ONES (issue #1707).

Measured on one heavy airport pack (the frame-rate finding of
2026-10-30): its road cars drew 181.7 M of its 275.5 M triangles (22,042
to 45,702 triangles a car; X-Plane's library sedan is 164), and its
ground equipment most of the rest.  The owner's hand swap of 14 props
took the close-range triangles from 89.6 M to 50.7 M and the frame rate
from 15 to 26-30 fps.

THE MATCH (:func:`plan_swaps`, when the user accepts) — a pack object is
swapped when

* it is the pack's own file, placed by the DSF, and nothing in it moves;
* its file name carries a class's words (``swap_map.CLASSES``) and one of
  that class's library objects has its FOOTPRINT: length, width and
  height each within :data:`SIZE_RATIO` (or :data:`SIZE_SLACK_M`) of the
  pack object's — the best fit is the equivalent;
* X-Plane can draw that library object, through every library of the
  install whose region holds the tile, only from files that exist, draw
  something, and none of which is a blank placeholder (owner
  2026-10-30: "never point at an export that can resolve to
  blank.obj");
* the swap saves at least :data:`MIN_SAVING` triangles across the tile,
  counting the heaviest file X-Plane may draw for the equivalent (a
  better-fitting but heavy equivalent is never traded for a lighter,
  worse-fitting one).

THE TURN.  The long axes are lined up; of the two (or, for a square
footprint, four) turns that do so, the FRONT decides: the pack object's
head lights (``shape``) against X-Plane's convention (a library object
faces north, -z), else the profile along the long axis that fits best
when one clearly does, else the smallest turn (owner 2026-11-03: swap
"even when its front cannot be proven").

THE ROW (:func:`apply`, on every write).  The library object stands on
the pack object's footprint centre, turned, at the same base height;
an object whose lights can be copied keeps them in a lights-only copy
``<stem>.o4opt-lights.obj`` placed on the same row (owner 2026-11-03:
the parked cars' spill lights stay).  The match is recorded in the
recipe, so every later write re-applies the same table.
"""
from __future__ import annotations

import math
import os
import re
import typing as _t

import numpy as np

from . import shape as _sh
from .swap_map import CLASSES

__all__ = ["SIZE_RATIO", "MIN_SAVING", "LIGHTS_SUFFIX", "plan_swaps",
           "apply", "name_words", "lights_text"]

#: each footprint dimension within this ratio of the pack object's...
SIZE_RATIO = 1.5
#: ...or within this many metres of it
SIZE_SLACK_M = 0.5
#: the smallest saving a swap is made for (triangles x placements)
MIN_SAVING = 100_000
#: the lights-only copy of a swapped object
LIGHTS_SUFFIX = ".o4opt-lights.obj"
#: a footprint whose sides are closer than this is square: four turns
SQUARE = 1.15
#: one profile fits "clearly" better when its misfit is at most this
#: share of the other's
PROFILE_DECISIVE = 0.8
#: metres per degree on the sphere ``dsf_write``'s duplicate test reads
_M_DEG = math.radians(1.0) * 6371008.8

_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+")


def name_words(path: str) -> set[str]:
    """The lower-case words of a file's stem: ``BaggageCar1`` -> ``baggage
    car``, ``T1BusRed`` -> ``t bus red``."""
    stem = os.path.splitext(os.path.basename(path.replace("\\", "/")))[0]
    return {w.lower() for w in _WORD.findall(stem)}


def _class_of(path: str) -> tuple[str, tuple[str, ...]] | None:
    words = name_words(path)
    for name, sets, targets in CLASSES:
        if any(s <= words for s in sets):
            return name, targets
    return None


# ── the library side ────────────────────────────────────────────────────

def _library_shapes(virtual: str, exports_of: _t.Callable[[str], _t.Sequence[str]]
                    ) -> list[_sh.Shape] | None:
    """The shapes of every file X-Plane may draw for a library object,
    the one nearest the median size first; ``None`` when any of them is
    missing, blank, draws nothing or moves."""
    files = list(exports_of(virtual))
    if not files or any("blank" in os.path.basename(f).lower()
                        or not os.path.isfile(f) for f in files):
        return None
    shapes = [_sh.read_shape(f) for f in sorted(set(files))]
    if any(s is None or s.animated for s in shapes):
        return None
    med = np.median([s.size for s in shapes], axis=0)
    return sorted(shapes, key=lambda s: float(
        np.abs(np.log(np.asarray(s.size) / med)).sum()))


# ── the turn ────────────────────────────────────────────────────────────

def _turned(size: tuple[float, float, float], turn: int) -> tuple[float, float, float]:
    return (size[1], size[0], size[2]) if turn % 180 else size


def _misfit(a: tuple[float, float, float], b: tuple[float, float, float]
            ) -> float | None:
    """Sum of the log size ratios, ``None`` when a dimension is past
    :data:`SIZE_RATIO` and more than :data:`SIZE_SLACK_M` apart (a flat
    dolly 0.2 m tall is a 0.6 m one's equal)."""
    if any(not (x > 0 and y > 0) for x, y in zip(a, b)):
        return None
    if any(not (1 / SIZE_RATIO <= x / y <= SIZE_RATIO) and abs(x - y) > SIZE_SLACK_M
           for x, y in zip(a, b)):
        return None
    return float(sum(abs(math.log(x / y)) for x, y in zip(a, b)))


def _rotate(points: np.ndarray, turn: int) -> np.ndarray:
    """``points`` (x, y, z) of an object turned ``turn`` degrees clockwise,
    in the frame of the unturned one."""
    t = math.radians(turn)
    c, s = math.cos(t), math.sin(t)
    x, z = points[:, 0], points[:, 2]
    return np.column_stack([x * c - z * s, points[:, 1], x * s + z * c])


def _azimuth(v: tuple[float, float]) -> float:
    """Clockwise from north of a local (x, z) direction (z is south)."""
    return math.degrees(math.atan2(v[0], -v[1])) % 360.0


def _pick_turn(pack: _sh.Shape, lib: _sh.Shape, turns: _t.Sequence[int]) -> tuple[int, str]:
    """The turn among ``turns`` and what decided it."""
    if pack.front is not None:
        want = _azimuth(pack.front) - (_azimuth(lib.front) if lib.front else 0.0)
        best = min(turns, key=lambda t: abs((want - t + 180.0) % 360.0 - 180.0))
        return best, "lights"
    sx, sz, _ = pack.size
    axis = 0 if sx >= sz else 2
    mine = _sh.profile(pack.points, axis)
    miss = {}
    for t in turns:
        theirs = _sh.profile(_rotate(lib.points, t), axis)
        ok = ~(np.isnan(mine) | np.isnan(theirs))
        miss[t] = float(np.abs(mine[ok] - theirs[ok]).mean()) if ok.any() else math.inf
    ranked = sorted(turns, key=lambda t: miss[t])
    if len(ranked) > 1 and miss[ranked[0]] <= PROFILE_DECISIVE * miss[ranked[1]]:
        return ranked[0], "profile"
    return min(turns, key=lambda t: (min(t, 360 - t), t)), "default"


def _turns(pack: _sh.Shape, lib: _sh.Shape) -> tuple[list[int], float] | None:
    fits = {t: _misfit(pack.size, _turned(lib.size, t)) for t in (0, 90, 180, 270)}
    fits = {t: m for t, m in fits.items() if m is not None}
    if not fits:
        return None
    sx, sz, _ = pack.size
    square = max(sx, sz) / max(min(sx, sz), 1e-6) < SQUARE
    best = min(fits.values())
    return [t for t, m in sorted(fits.items()) if square or m <= best + 1e-9], best


# ── the match ───────────────────────────────────────────────────────────

def plan_swaps(pack_root: str, defs: _t.Sequence[str], uses: _t.Mapping[int, int],
               exports_of: _t.Callable[[str], _t.Sequence[str]]
               ) -> dict[str, dict[str, _t.Any]]:
    """THE MATCH.  ``{declared path: swap}`` for the object definitions
    ``defs`` (``uses`` = placements per definition index) that the rules
    above swap; ``exports_of(virtual)`` lists every file the install's
    libraries export a virtual path as."""
    out: dict[str, dict[str, _t.Any]] = {}
    for d, n in sorted(uses.items()):
        path = defs[d]
        if path in out or not path.lower().endswith(".obj"):
            continue
        cls = _class_of(path)
        phys = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
        if cls is None or not os.path.isfile(phys):
            continue
        pack = _sh.read_shape(phys)
        if pack is None or pack.animated or pack.uncopyable_lights:
            continue
        best = None
        for target in cls[1]:
            libs = _library_shapes(target, exports_of)
            fit = _turns(pack, libs[0]) if libs else None
            if not fit or any(_misfit(pack.size, _turned(v.size, fit[0][0])) is None
                              for v in libs):
                continue                # every variant must fit the footprint
            if best is None or fit[1] < best[0]:
                best = (fit[1], target, max(libs, key=lambda v: v.tris), fit[0], libs[0])
        if best is None or (pack.tris - best[2].tris) * n < MIN_SAVING:
            continue                   # the clear equivalent is not lighter
        _m, target, _heaviest, turns, lib = best
        turn, why = _pick_turn(pack, lib, turns)
        out[path] = {"to": target, "class": cls[0], "turn": int(turn),
                     "why": why, "from_c": [round(v, 4) for v in pack.centre],
                     "to_c": [round(v, 4) for v in lib.centre],
                     "dy": round(pack.box[2] - lib.box[2], 4),
                     "tris": [pack.tris, _heaviest.tris],
                     "far": lib.lod_far,
                     "lights": (_lights_path(path) if pack.lights else "")}
    return out


def _lights_path(path: str) -> str:
    stem, _ext = os.path.splitext(path)
    return stem + LIGHTS_SUFFIX


def lights_text(phys: str) -> str | None:
    """The lights-only copy of a pack object: its texture rows and its
    copyable light rows (``shape.LIGHT_ROWS``), nothing drawn."""
    s = _sh.read_shape(phys)
    if s is None or not s.lights:
        return None
    rows = ["I", "800", "OBJ", "", *s.header,
            "POINT_COUNTS 0 0 0 0", "", *s.lights, ""]
    return "\n".join(rows)


# ── the row ─────────────────────────────────────────────────────────────

def _offset(c: _t.Sequence[float], heading: float) -> tuple[float, float]:
    """East, north metres of the local point ``c`` (x, z) at ``heading``."""
    h = math.radians(heading)
    return (c[0] * math.cos(h) - c[1] * math.sin(h),
            -(c[0] * math.sin(h) + c[1] * math.cos(h)))


def _num(x: float, places: int) -> str:
    return f"{x:.{places}f}"


def apply(text: str, swaps: _t.Mapping[str, _t.Mapping[str, _t.Any]]
          ) -> tuple[str, dict[str, int]]:
    """THE ROW (pure): ``text`` (a DSFTool dump) with each swapped
    definition pointing at its library object and each of its rows moved
    and turned onto it; a lights copy's definition is appended and placed
    on the same row.  Returns the text and ``{declared path: rows}``."""
    if not swaps:
        return text, {}
    lines = text.splitlines(keepends=True)
    eol = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    defs: list[str] = []
    last_def = -1
    for i, raw in enumerate(lines):
        if raw.startswith("OBJECT_DEF "):
            defs.append(raw[len("OBJECT_DEF "):].strip())
            last_def = i
    if last_def < 0:
        return text, {}
    extra: list[str] = []
    lights_of: dict[int, int] = {}
    for d, p in enumerate(defs):
        lp = (swaps.get(p) or {}).get("lights") or ""
        if lp:
            if lp not in extra:
                extra.append(lp)
            lights_of[d] = len(defs) + extra.index(lp)
    counts: dict[str, int] = {}
    out: list[str] = []
    d_seen = 0
    for i, raw in enumerate(lines):
        toks = raw.split()
        kw = toks[0] if toks else ""
        if kw == "OBJECT_DEF":
            p = defs[d_seen]
            d_seen += 1
            sw = swaps.get(p)
            out.append(f"OBJECT_DEF {sw['to']}{eol}" if sw else raw)
            if i == last_def:
                out.extend(f"OBJECT_DEF {lp}{eol}" for lp in extra)
            continue
        if kw in ("OBJECT", "OBJECT_AGL", "OBJECT_MSL") and len(toks) >= 4:
            try:
                d = int(toks[1])
            except ValueError:
                d = -1
            sw = swaps.get(defs[d]) if 0 <= d < len(defs) else None
            if sw:
                out.append(_moved(toks, sw) + eol)
                if d in lights_of:
                    out.append(" ".join([toks[0], str(lights_of[d]), *toks[2:]]) + eol)
                counts[defs[d]] = counts.get(defs[d], 0) + 1
                continue
        out.append(raw)
    return "".join(out), counts


def _moved(toks: _t.Sequence[str], sw: _t.Mapping[str, _t.Any]) -> str:
    """One swapped row: the library object on the pack object's footprint
    centre, turned, at the pack object's base height."""
    on_ground = toks[0] == "OBJECT"
    hi = 4 if on_ground else 5
    lon, lat = float(toks[2]), float(toks[3])
    heading = float(toks[hi]) if len(toks) > hi else 0.0
    new_h = (heading + float(sw["turn"])) % 360.0
    ea, na = _offset(sw["from_c"], heading)
    el, nl = _offset(sw["to_c"], new_h)
    lat2 = lat + (na - nl) / _M_DEG
    lon2 = lon + (ea - el) / (_M_DEG * math.cos(math.radians(lat)))
    row = [toks[0], toks[1], _num(lon2, 9), _num(lat2, 9)]
    if not on_ground:
        row.append(_num(float(toks[4]) + float(sw.get("dy", 0.0)), 4))
    row.append(_num(new_h, 6))
    return " ".join(row)
