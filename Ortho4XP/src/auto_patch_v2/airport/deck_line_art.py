"""THE PAINT ON A GENERATED DECK IN X-PLANE'S OWN LINE ART (#2141 items
1 and 3; owner 2026-11-17: "drape them the same way as the tire overlay
... use X-Plane line types if possible").

X-Plane drapes apt.dat ``120`` lines on the terrain mesh, never on an
object, so the deck redraws each dropped line as strips of its OWN line
page: ``lib/airport/lines/<type>_*.lin`` read from the user's install --
its ``TEXTURE`` (one atlas, ``taxilines``, for every line type), its
``TEX_WIDTH`` and ``SCALE`` (metres across the atlas, along one repeat)
and its ``S_OFFSET`` layers (left / centre / right pixel of each stripe,
layer 0 under layer 1).  A strip spans its layer's pixels across the
line (left of the line's direction of travel at the left pixel) and
repeats the atlas every ``SCALE`` along metres along it: the dashes, the
wear and the black ``_b`` border are X-Plane's, never re-drawn.

The pages are found by the folder of :data:`[deck_gen] line_lib`
(the first line page), each ``<n>_*.lin`` there re-resolved through the
library (an override in the user's install wins); a page on another
texture than the first is left out (one texture per object).  An install
that resolves none leaves the deck on the generated atlas
(``deck_paint``).  Nothing here names an airport.

Build-time impact: a directory listing and a few small text reads per
object-stage write.
"""
from __future__ import annotations

import os
import typing as _t

from .deck_skin import Resolver, texture_file

__all__ = ["LinePage", "line_pages"]


class LinePage(_t.NamedTuple):
    """A line page's art: ``texture`` / ``normal`` absolute paths
    (``normal`` ``""`` for none), ``tex_width`` pixels across, ``scale_m``
    ``(across, along)`` metres, ``layers`` the ``(left, centre, right)``
    pixels of each ``S_OFFSET`` in layer order, and the page's material
    rows ``decal_lib`` (verbatim) and ``weather_transparent``."""

    texture: str
    normal: str
    tex_width: float
    scale_m: tuple[float, float]
    layers: tuple[tuple[float, float, float], ...]
    decal_lib: str = ""
    weather_transparent: bool = False

    def span_m(self, layer: tuple[float, float, float]) -> tuple[float, float]:
        """``(left, right)`` metres of a layer's stripe from the line."""
        k = self.scale_m[0] / self.tex_width
        return ((layer[1] - layer[0]) * k, (layer[2] - layer[1]) * k)


def _read_page(path: str) -> "LinePage | None":
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            rows = [ln.split() for ln in fh if ln.strip()]
    except OSError:
        return None
    first: dict[str, list[str]] = {}
    layers: list[tuple[int, tuple[float, float, float]]] = []
    for r in rows:
        first.setdefault(r[0], r)
        if r[0] == "S_OFFSET" and len(r) >= 5:
            try:
                layers.append((int(r[1]), (float(r[2]), float(r[3]), float(r[4]))))
            except ValueError:
                continue
    tex, nrm, tw, sc = (first.get(k) for k in ("TEXTURE", "TEXTURE_NORMAL", "TEX_WIDTH", "SCALE"))
    folder = os.path.dirname(path)
    texture = texture_file(folder, tex[1]) if tex and len(tex) >= 2 else None
    if texture is None or not tw or not sc or len(sc) < 3 or not layers:
        return None
    try:
        width, across, along = float(tw[1]), float(sc[1]), float(sc[2])
    except ValueError:
        return None
    if width <= 0 or across <= 0 or along <= 0:
        return None
    normal = texture_file(folder, nrm[-1]) if nrm and len(nrm) >= 2 else None
    dcl = first.get("DECAL_LIB")
    return LinePage(texture, normal or "", width, (across, along),
                    tuple(lay for _k, lay in sorted(layers, key=lambda t: t[0])),
                    dcl[1] if dcl and len(dcl) >= 2 else "", "WEATHER_TRANSPARENT" in first)


def line_pages(line_lib: str, xplane_root: "str | None", resolve: "Resolver | None"
               ) -> dict[int, LinePage]:
    """``{apt.dat line type: LinePage}`` of the install's line pages on
    one texture (module doc); ``{}`` when nothing resolves."""
    if not line_lib or not xplane_root or resolve is None:
        return {}
    try:
        base = resolve(line_lib, xplane_root)
    except (OSError, ValueError):
        return {}
    if not base:
        return {}
    lib_dir, folder = line_lib.rsplit("/", 1)[0], os.path.dirname(base)
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".lin"))
    except OSError:
        return {}
    out: dict[int, LinePage] = {}
    for name in names:
        head = name.split("_", 1)[0]
        if not head.isdigit():
            continue
        try:
            path = resolve(f"{lib_dir}/{name}", xplane_root) or os.path.join(folder, name)
        except (OSError, ValueError):
            path = os.path.join(folder, name)
        page = _read_page(path)
        if page is not None:
            out[int(head)] = page
    if not out:
        return {}
    tex = out[min(out)].texture
    return {k: p for k, p in out.items() if p.texture == tex}

