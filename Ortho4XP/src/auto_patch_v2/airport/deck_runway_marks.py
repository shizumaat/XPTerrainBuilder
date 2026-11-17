"""THE RUNWAY MARKINGS ON A GENERATED DECK THAT CARRIES A RUNWAY (owner
2026-11-17: the deck surface matches the pavement it carries, runway
markings included where they cross it).

X-Plane paints a row-``100`` runway's markings on the terrain mesh, never
on an object, so a deck over the runway redraws the ones that fall on its
span: the side stripes, the centreline dashes, the threshold bars, the
aiming point and the touchdown-zone bars of each end, laid out as the FAA
draws them (AC 150/5340-1: threshold bars from 20 ft, aiming point from
1,020 ft, touchdown bars at 500 / 1,500 / 2,000 / 2,500 / 3,000 ft,
centreline 120 ft dashes and 80 ft gaps) from the end's displaced
threshold and the end's apt.dat MARKINGS code (1 visual, 2 / 4
non-precision, 3 / 5 precision; the UK codes are drawn as their FAA
twins).  Designators, displaced-threshold arrows and blast-pad chevrons
are not drawn.

THE ART is X-Plane's own: the runway page's ``RUNWAY_MARKINGS`` row (the
page ``deck_pavement.surface_page`` names for the runway's surface) names
the marking atlas (``RWY_markings_1`` / ``_2``: 2048 x 1024, the marks as
a MASK in the red channel) and its tint.  An object cannot read a mask,
so the deck carries the atlas re-cast as an RGBA PNG (the tint, alpha =
the red channel: the paint's wear shows the pavement through), written
into the pack once per atlas -- X-Plane's pixels, never re-drawn.  The
cells each mark reads are the atlas's own (:data:`CELLS`, read
2026-11-17; both atlases share the layout).  An atlas of another size
reads ``None`` and the deck carries no runway markings.  Nothing here
names an airport.

Build-time impact: one 2048 x 1024 DDS decode and PNG encode per atlas
per object-stage write; shapely on a few dozen rectangles per deck.
"""
from __future__ import annotations

import io
import math
import os
import typing as _t

import numpy as np
import shapely
from shapely.geometry import Polygon

from .deck_obj8 import DeckDecal

__all__ = ["CELLS", "read_atlas", "runway_marks", "deck_decals"]

FT = 0.3048
_ATLAS_SIZE = (2048, 1024)
#: ``(x0, y0, x1, y1)`` pixels (top-left origin) of each mark's cell in
#: X-Plane's ``RWY_markings`` atlases: a full-height stripe column (side
#: stripes and centreline dashes repeat along it), a threshold bar, a
#: touchdown-zone bar and the aiming-point block
CELLS: dict[str, tuple[int, int, int, int]] = {
    "stripe": (2014, 0, 2034, 1024),
    "threshold": (1022, 294, 1058, 1018),
    "tdz": (510, 534, 546, 1018),
    "aiming": (1494, 294, 1642, 1018),
}
#: metres along one repeat of the stripe column (its 1024 px at the
#: threshold bar's 724 px per 150 ft)
_STRIPE_REPEAT_M = 1024.0 / 724.0 * 150.0 * FT
_EDGE_INSET_PX = 1.5


class _MarkAtlas(_t.NamedTuple):
    """A runway page's marking art: ``name`` the pack file name and
    ``png`` its bytes (module doc)."""

    name: str
    png: bytes


class _Mark(_t.NamedTuple):
    """One marking rectangle in the runway's frame: ``s0``-``s1`` metres
    along from end 0, ``t0``-``t1`` metres left of end 0 -> end 1, its
    atlas ``cell``; ``repeat_m`` > 0 repeats the cell along every that
    many metres (a stripe), else the cell is stretched over it."""

    s0: float
    s1: float
    t0: float
    t1: float
    cell: str
    repeat_m: float = 0.0


def _markings_row(pol_path: str) -> "tuple[tuple[float, float, float], str] | None":
    """The page's ``RUNWAY_MARKINGS r g b a atlas`` row: tint, atlas name."""
    try:
        with open(pol_path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                r = ln.split()
                if len(r) >= 6 and r[0] == "RUNWAY_MARKINGS":
                    return (float(r[1]), float(r[2]), float(r[3])), r[5]
    except (OSError, ValueError):
        return None
    return None


def _pixels(path: str) -> "np.ndarray | None":
    """RGBA rows (top first) of ``path`` (DDS through the engine's own
    decoder, else Pillow)."""
    try:
        if path.lower().endswith(".dds"):
            import O4_DDS_Decode as _dds
            with open(path, "rb") as fh:
                return _dds.decode_dds(fh.read())[0]
        from PIL import Image
        with Image.open(path) as im:
            return np.asarray(im.convert("RGBA"))
    except (OSError, ValueError, KeyError):
        return None


def read_atlas(pol_path: "str | None") -> "_MarkAtlas | None":
    """The marking art of the runway page at ``pol_path`` (module doc),
    ``None`` when the page names none or the atlas is not the known
    layout."""
    from PIL import Image

    from .deck_skin import texture_file
    row = _markings_row(pol_path) if pol_path else None
    if row is None:
        return None
    tint, name = row
    tex = texture_file(os.path.dirname(pol_path), name)
    px = _pixels(tex) if tex else None
    if px is None or (px.shape[1], px.shape[0]) != _ATLAS_SIZE:
        return None
    out = np.empty(px.shape[:2] + (4,), dtype=np.uint8)
    for k in range(3):
        out[..., k] = int(round(255 * max(0.0, min(1.0, tint[k]))))
    out[..., 3] = px[..., 0]
    buf = io.BytesIO()
    Image.fromarray(out, "RGBA").save(buf, "PNG", optimize=True)
    stem = os.path.splitext(os.path.basename(tex))[0]
    tag = "".join(f"{int(round(255 * max(0.0, min(1.0, c)))):02x}" for c in tint)
    return _MarkAtlas(f"o4_{stem}_{tag}.png", buf.getvalue())


def _pair(s0: float, length: float, inner: float, width: float, gap: float, n: int,
          cell: str) -> list[_Mark]:
    """``n`` bars each side of the centreline, the first ``inner`` metres out."""
    out = []
    for k in range(n):
        a = inner + k * (width + gap)
        out += [_Mark(s0, s0 + length, a, a + width, cell),
                _Mark(s0, s0 + length, -a - width, -a, cell)]
    return out


def _end_marks(thr: float, code: int, w: float, half_len: float) -> list[_Mark]:
    """The marks of one end, ``s`` metres from end 0 with the end's
    displaced threshold at ``thr`` (module doc), out to ``half_len``
    past it; none for a visual or unmarked end."""
    if code < 2:
        return []
    bw = 5.75 * FT                       # FAA: 4 bars at 60 ft wide ... 16 at 200 ft
    out = _pair(thr + 20 * FT, 150 * FT, bw, bw, bw, max(1, round(w / (25 * FT))), "threshold")
    k = min(1.0, w / (150 * FT))         # narrower than 150 ft: scaled in
    inner, aim_w = 36 * FT * k, 30 * FT * k
    if half_len >= 1170 * FT:
        out += _pair(thr + 1020 * FT, 150 * FT, inner, aim_w, 0.0, 1, "aiming")
    if code in (3, 5):
        for at, n in ((500, 3), (1500, 2), (2000, 2), (2500, 1), (3000, 1)):
            if (at + 75) * FT <= half_len:
                out += _pair(thr + at * FT, 75 * FT, inner, 6 * FT, 5 * FT, n, "tdz")
    return out


def runway_marks(width_m: float, length_m: float, displaced: tuple[float, float],
                 codes: tuple[int, int]) -> list[_Mark]:
    """Every mark of a runway ``length_m`` long and ``width_m`` wide in
    its frame (:class:`_Mark`), ``displaced`` / ``codes`` per end."""
    if max(codes) <= 0 or length_m <= 0.0:
        return []
    w, L = float(width_m), float(length_m)
    t0, t1 = float(displaced[0]), L - float(displaced[1])
    half = max(0.0, (t1 - t0) / 2.0)
    out: list[_Mark] = []
    if max(codes) >= 2:
        ew = 3 * FT
        out += [_Mark(0.0, L, w / 2 - ew, w / 2, "stripe", _STRIPE_REPEAT_M),
                _Mark(0.0, L, -w / 2, -w / 2 + ew, "stripe", _STRIPE_REPEAT_M)]
    cw = {3: 36, 5: 36, 2: 18, 4: 18}.get(max(codes), 12) * FT / 12.0
    s, b = t0 + 270 * FT, t1 - 270 * FT
    while s < b:
        out.append(_Mark(s, min(s + 120 * FT, b), -cw / 2, cw / 2, "stripe", _STRIPE_REPEAT_M))
        s += 200 * FT
    out += _end_marks(t0, int(codes[0]), w, half)
    out += [_Mark(L - m.s1, L - m.s0, -m.t1, -m.t0, m.cell, m.repeat_m)
            for m in _end_marks(float(displaced[1]), int(codes[1]), w, half)]
    return out


def _uv(mark: _Mark, s: float, t: float) -> tuple[float, float]:
    """Texture ``(u, v)`` of the runway point ``(s, t)`` on ``mark``: the
    cell's x across (``t1`` side left), its y along (``s0`` at the bottom)
    -- OBJ8 ``v`` counts up from the image's bottom row."""
    x0, y0, x1, y1 = CELLS[mark.cell]
    W, H = _ATLAS_SIZE
    e = _EDGE_INSET_PX
    fu = (mark.t1 - t) / max(mark.t1 - mark.t0, 1e-9)
    u = (x0 + e + fu * (x1 - x0 - 2 * e)) / W
    if mark.repeat_m > 0.0:
        return u, (s - mark.s0) / mark.repeat_m
    fv = (s - mark.s0) / max(mark.s1 - mark.s0, 1e-9)
    vb, vt = 1.0 - (y1 - e) / H, 1.0 - (y0 + e) / H
    return u, vb + fv * (vt - vb)


def deck_decals(marks: _t.Sequence[_Mark], end0: tuple[float, float],
                end1: tuple[float, float], R: Polygon, lift_m: float) -> list[DeckDecal]:
    """The ``marks`` that fall on the deck ``R`` (its frame), clipped to
    it: ``end0`` / ``end1`` the runway's ends in the deck's frame."""
    dx, dz = end1[0] - end0[0], end1[1] - end0[1]
    d = math.hypot(dx, dz)
    if d < 1e-6:
        return []
    ux, uz = dx / d, dz / d
    nx, nz = uz, -ux                     # left of travel (deck_obj8 convention)
    inner = R.buffer(-0.05)

    def at(s: float, t: float) -> tuple[float, float]:
        return (end0[0] + s * ux + t * nx, end0[1] + s * uz + t * nz)
    out = []
    for m in marks:
        rect = Polygon([at(m.s0, m.t0), at(m.s1, m.t0), at(m.s1, m.t1), at(m.s0, m.t1)])
        if not rect.intersects(inner):
            continue
        tris = []
        pieces = [g for g in shapely.get_parts(rect.intersection(inner))
                  if g.geom_type == "Polygon" and g.area > 1e-4]
        for tri in (t for g in pieces
                    for t in shapely.get_parts(shapely.constrained_delaunay_triangles(g))):
            corners = []
            for x, z in list(tri.exterior.coords)[:3]:
                rx, rz = x - end0[0], z - end0[1]
                corners.append((x, z, *_uv(m, rx * ux + rz * uz, rx * nx + rz * nz)))
            tris.append(tuple(corners))
        if tris:
            out.append(DeckDecal(tuple(tris), lift_m))
    return out
