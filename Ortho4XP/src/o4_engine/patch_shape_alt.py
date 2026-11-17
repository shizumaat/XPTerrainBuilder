"""A patch shape's own elevation tags: what they say, and how an edit
rewrites them (issue #2137).

Ortho4XP reads a patch way's elevation from ITS TAGS before it looks at the
nodes (``O4_Vector_Map`` — the patch reader — in this order; the first key
present wins):

* ``cst_alt_abs`` — one elevation (metres MSL) for every node;
* ``cst_alt_rel`` — the mean ground under the shape plus this offset;
* ``var_alt_rel`` — the ground at each node plus this offset;
* ``altitude`` — the deprecated spelling of ``cst_alt_abs``;
* ``node_altitudes`` — one value per node (not a whole-shape value: this
  module reports nothing for it);
* ``altitude_high`` / ``altitude_low`` — the SLOPING RECTANGLE: a closed
  way of exactly four corners (five refs).  Its HIGH side is the edge
  from the fourth corner back to the first (refs ``[3]``–``[0]``), its LOW
  side the edge between the second and third (refs ``[1]``–``[2]``); the
  surface runs between them along the ``profile`` (``plane`` unless told).
  If either value is not a number the build takes BOTH from the mesh.

On the first four a node's own ``alt_abs`` / ``alt_rel`` still wins over the
shape value; on a sloping rectangle the nodes' elevations are not read.

This module only names what the tags say and writes new values back with the
same key (a legacy ``altitude`` stays ``altitude``); the reader in
``O4_Vector_Map`` is untouched.  Both editors use it — the Qt app directly,
the Mac app through its twin ``SceneryKit/PatchShapeAltitude.swift`` — and
both run ``tests/fixtures/patch_shape_alt.json``, so they cannot drift.
:func:`slope_marks` is the map drawing both apps share (owner 2026-11-17
15:58Z): an outlined arrow from the high side to the low side, a label at
each end carrying its value, the high edge drawn thicker.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["ABSOLUTE", "MEAN_OFFSET", "GROUND_OFFSET", "SLOPE", "HIGH_KEY", "LOW_KEY",
           "shape_alt", "level_tags", "slope_tags", "slope_label",
           "slope_marks"]

#: The whole-shape forms.
ABSOLUTE = "absolute"            # cst_alt_abs (or the legacy ``altitude``)
MEAN_OFFSET = "mean_offset"      # cst_alt_rel
GROUND_OFFSET = "ground_offset"  # var_alt_rel
SLOPE = "slope"                  # altitude_high / altitude_low

HIGH_KEY = "altitude_high"
LOW_KEY = "altitude_low"

#: The reader's order (``O4_Vector_Map``): key -> form; ``None`` = a form
#: this module does not edit, which still hides every key after it.
_PRECEDENCE: tuple[tuple[str, str | None], ...] = (
    ("cst_alt_abs", ABSOLUTE),
    ("cst_alt_rel", MEAN_OFFSET),
    ("var_alt_rel", GROUND_OFFSET),
    ("altitude", ABSOLUTE),
    ("node_altitudes", None),
    (HIGH_KEY, SLOPE),
)

#: Where the arrow and the labels sit along the high -> low axis
#: (fractions of the distance between the two edge midpoints).
ARROW_FROM, ARROW_TO = 0.25, 0.75
LABEL_HIGH_AT, LABEL_LOW_AT = 0.10, 0.90
#: The arrow's widths, fractions of the rectangle's mean width; the head's
#: length is the smaller of a fraction of the arrow and of the width.
SHAFT_HALF, HEAD_HALF = 0.12, 0.30
HEAD_OF_ARROW, HEAD_OF_WIDTH = 0.40, 0.60


def _number(text: _t.Any) -> float | None:
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def shape_alt(tags: _t.Mapping[str, str], refs: _t.Sequence[int] = ()) -> dict | None:
    """What the way's tags say about its elevation, or ``None``.

    ``{"form", "key", "value"}`` for a whole-shape value (``value`` None
    when the tag is not a number), or ``{"form": "slope", "high", "low",
    "valid"}`` (``valid``: the way is a closed four-corner ring, which the
    build needs — it skips any other).  ``refs`` are the way's refs."""
    for key, form in _PRECEDENCE:
        if key not in tags:
            continue
        if form is None:
            return None
        if form == SLOPE:
            valid = len(refs) == 5 and refs[0] == refs[-1]
            return {"form": SLOPE, "high": _number(tags.get(HIGH_KEY)),
                    "low": _number(tags.get(LOW_KEY)), "valid": valid}
        return {"form": form, "key": key, "value": _number(tags[key])}
    return None


def _format_alt(value: float) -> str:
    """A value as the tags carry it: metres, two decimals."""
    return "%.2f" % float(value)


def level_tags(tags: _t.Mapping[str, str], value: float) -> dict:
    """The tags with the whole-shape value set to ``value`` under the key
    the shape already uses (``cst_alt_abs`` when it has none)."""
    found = shape_alt(tags)
    key = found["key"] if found and found["form"] != SLOPE else "cst_alt_abs"
    out = dict(tags)
    out[key] = _format_alt(value)
    return out


def slope_tags(tags: _t.Mapping[str, str], high: float | None = None,
               low: float | None = None) -> dict:
    """The tags with the sloping rectangle's high and/or low value set;
    every other tag (``profile``, ``steepness``, ``cell_size``) kept."""
    out = dict(tags)
    if high is not None:
        out[HIGH_KEY] = _format_alt(high)
    if low is not None:
        out[LOW_KEY] = _format_alt(low)
    return out


def slope_label(side: str, value: float | None) -> str:
    """The map label at one end of the arrow: ``High 172.4 m`` /
    ``Low 170.9 m`` (``High: mesh`` when the value is not a number)."""
    word = "High" if side == "high" else "Low"
    return "%s %.1f m" % (word, value) if value is not None else "%s: mesh" % word


def slope_marks(corners: _t.Sequence[_t.Sequence[float]]) -> dict | None:
    """The drawing of a sloping rectangle from its four corners ``(lat,
    lon)`` in ring order (refs ``[0]``..``[3]``), all in degrees:
    ``high_edge`` / ``low_edge`` (two points each), ``arrow`` (seven points,
    an outlined arrow pointing high -> low), ``high_label`` /
    ``low_label`` (where each end's label is centred).  ``None`` when the
    two sides coincide.  Computed in a plane scaled by cos(mean latitude)."""
    if len(corners) != 4:
        return None
    k = max(math.cos(math.radians(sum(c[0] for c in corners) / 4)), 1e-6)
    p = [(float(c[1]) * k, float(c[0])) for c in corners]   # (x, y)

    def mid(a, b):
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    hi, lo = mid(p[3], p[0]), mid(p[1], p[2])
    dx, dy = lo[0] - hi[0], lo[1] - hi[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return None
    ux, uy = dx / length, dy / length
    vx, vy = -uy, ux
    width = (math.dist(p[3], p[0]) + math.dist(p[1], p[2])) / 2

    def at(t, s=0.0):
        return (hi[0] + ux * t + vx * s, hi[1] + uy * t + vy * s)

    t0, t1 = ARROW_FROM * length, ARROW_TO * length
    head = min(HEAD_OF_ARROW * (t1 - t0), HEAD_OF_WIDTH * width)
    base = t1 - head
    shaft, wing = SHAFT_HALF * width, HEAD_HALF * width
    arrow = [at(t0, shaft), at(base, shaft), at(base, wing), at(t1),
             at(base, -wing), at(base, -shaft), at(t0, -shaft)]

    def ll(q):
        return [q[1], q[0] / k]

    return {"high_edge": [ll(p[3]), ll(p[0])], "low_edge": [ll(p[1]), ll(p[2])],
            "arrow": [ll(q) for q in arrow],
            "high_label": ll(at(LABEL_HIGH_AT * length)),
            "low_label": ll(at(LABEL_LOW_AT * length))}
