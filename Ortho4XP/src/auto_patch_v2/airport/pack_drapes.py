"""DRAPED ORTHOPHOTOS A PACK SHIPS INSIDE ITS AIRPORT (issue #1916).

Owner (2026-11-06): "when a package includes draped ortho images in the
airport that would obscure our imagery … let the user choose to hide
draped orthos."  This module owns the WITNESS and the RECORD; the hiding
is ``dsf_write.write_pack(drapes=)``, which leaves the definitions and
every polygon that draws one out of the rewritten DSF
(``pack_art.omit_definitions``, the one omission), the pristine DSF kept
as its backup so a write without them (Undo, Restore originals) puts
them back.

THE WITNESS — a ``POLYGON_DEF`` of the pack's tile DSF is a draped
orthophoto when ALL of these hold, read from the files, never from a
name:

1. it is the PACK'S OWN file (resolved under the pack folder; an
   X-Plane library ``lib/…`` polygon — the stock draped signs, markings
   and pavement — is never one);
2. its header is ``DRAPED_POLYGON`` with ONE NON-WRAPPING IMAGE
   (``TEXTURE_NOWRAP``): a picture laid over its own shape, where
   painted markings and pavement tile a wrapping ``TEXTURE``;
3. it carries NO ``SURFACE`` (pavement the aircraft rolls on, drawn on
   purpose) and is NOT ``WEATHER_TRANSPARENT`` (a translucent overlay —
   dirt, skid marks, cracks — laid over pavement; measured 2026-11-06 on
   the installed packs: every weathering decal carries it, no WED
   orthophoto does);
4. its polygons are IMAGE-MAPPED NORTH-UP: every vertex carries its own
   texture coordinate (``BEGIN_POLYGON i 65535 4``, how WED lays an image
   on the ground) and the image's axes run along the meridians and
   parallels — a georeferenced photo — within :data:`NORTH_UP_DEG` for
   the median polygon (a dirt or skid decal is turned to its runway);
5. at least one of them lies over one of the pack's airports
   (:func:`airport_areas`) and is PHOTO-SIZED: the ``.pol`` carries WED's
   orthophoto ``LOAD_CENTER``, or the polygon spans at least
   :data:`MIN_SPAN_M`;
6. its image is not (nearly) all transparent
   (``image_opacity.opaque_fraction`` at least :data:`MIN_OPAQUE`): a
   weathering overlay laid north-up is still a see-through decal.

MEASURED 2026-11-06 over the 525 packs of the shared mod cache (the
installed packs' cached tile-DSF dumps): of 7,427 definitions passing
(1)-(3), image-mapped and over an airport, 6,651 photo tiles pass and 5
of 247 dirt/skid/tyre/shadow decals do; 529 photo tiles fail — 344 the
see-through "detail" layer one pack lays over its own photo, 178 the
photos of packs that did not lay them north-up, 7 see-through.

A definition that passes is hidden with ALL its polygons (the omission
is per definition).
"""
from __future__ import annotations

import math
import os
import typing as _t

from .pack_art import MissingDef, _lines, decision_key

__all__ = ["RECORD_KEY", "MIN_SPAN_M", "NORTH_UP_DEG", "MIN_OPAQUE",
           "airport_areas", "draped_orthos", "recorded", "summary"]

#: the record key of the hiding the user accepted
RECORD_KEY = "hidden_drapes"
#: the long side, in metres, from which an image-mapped polygon is a photo
MIN_SPAN_M = 100.0
#: how far (degrees) a photo's image axes may turn off north (a GeoTIFF in
#: a projected grid is turned by the grid convergence)
NORTH_UP_DEG = 3.0
#: the share of opaque pixels below which an image is a see-through decal
MIN_OPAQUE = 0.005
#: how much of a ``.pol`` file is read for its header
_HEAD_BYTES = 4096

Box = tuple[float, float, float, float]          # lon0, lat0, lon1, lat1


def pol_header(path: str) -> dict[str, str]:
    """``{directive: rest}`` of a ``.pol`` file's head (first occurrence
    of each; ``{}`` when it cannot be read)."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(_HEAD_BYTES).decode("utf-8", "replace")
    except OSError:
        return {}
    out: dict[str, str] = {}
    for line in head.replace("\r", "\n").split("\n"):
        kw, _sep, rest = line.strip().partition(" ")
        if kw and kw not in out:
            out[kw] = rest.strip()
    return out


def is_ortho_header(header: _t.Mapping[str, str]) -> bool:
    """Witness (2) and (3): a draped polygon with one non-wrapping image,
    no hard surface, and not a weather-transparent overlay."""
    return ("DRAPED_POLYGON" in header and "TEXTURE_NOWRAP" in header
            and "SURFACE" not in header
            and "WEATHER_TRANSPARENT" not in header)


def airport_areas(apt_path: str) -> list[Box]:
    """One lon/lat box per airport of the pack's apt.dat: its boundary
    (row 130) when authored, else its runways, pavement and helipads."""
    from . import apt_dat as _ad
    boxes: list[Box] = []
    if not apt_path:
        return boxes
    for icao in _ad.airports_in(apt_path):
        block = _ad.read_airport_block(apt_path, icao)
        if not block:
            continue
        try:
            apt = _ad.parse_airport_block(block)
        except (ValueError, IndexError):
            continue
        pts = [p for b in apt.boundaries for ring in b.rings[:1] for p in ring]
        if not pts:
            pts = ([(e[2], e[1]) for r in apt.runways for e in r.ends]
                   + [p for pv in apt.pavements for ring in pv.rings[:1]
                      for p in ring]
                   + [(h.lon, h.lat) for h in apt.helipads])
        if pts:
            boxes.append((min(p[0] for p in pts), min(p[1] for p in pts),
                          max(p[0] for p in pts), max(p[1] for p in pts)))
    return boxes


def _overlaps(a: Box, b: Box) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _span_m(box: Box) -> float:
    lat = math.radians((box[1] + box[3]) / 2)
    return max((box[2] - box[0]) * 111_320.0 * math.cos(lat),
               (box[3] - box[1]) * 110_540.0)


class _Use(_t.NamedTuple):
    mapped: bool
    box: Box
    turn_deg: float          # the image's axes off north (90 = unknown)


def _turn_deg(pts: _t.Sequence[tuple[float, float, float]]) -> float:
    """How far (0-45 degrees) the image's u axis is turned off the lon/lat
    axes over one winding's ``(lon, lat, u)`` points: the least-squares
    plane of u over local metres.  90 when it cannot be told."""
    if len(pts) < 3:
        return 90.0
    lat0 = sum(p[1] for p in pts) / len(pts)
    lon0 = sum(p[0] for p in pts) / len(pts)
    k = math.cos(math.radians(lat0)) * 111_320.0
    xs = [(p[0] - lon0) * k for p in pts]
    ys = [(p[1] - lat0) * 110_540.0 for p in pts]
    us = [p[2] for p in pts]
    sxx = sum(x * x for x in xs)
    syy = sum(y * y for y in ys)
    sxy = sum(x * y for x, y in zip(xs, ys, strict=True))
    um = sum(us) / len(us)
    sxu = sum(x * (u - um) for x, u in zip(xs, us, strict=True))
    syu = sum(y * (u - um) for y, u in zip(ys, us, strict=True))
    det = sxx * syy - sxy * sxy
    if abs(det) < 1e-9:
        return 90.0
    a = (sxu * syy - syu * sxy) / det
    b = (syu * sxx - sxu * sxy) / det
    if abs(a) + abs(b) < 1e-12:
        return 90.0
    t = abs(math.degrees(math.atan2(b, a))) % 90.0
    return min(t, 90.0 - t)


def _polygon_uses(lines: _t.Iterable[str]) -> dict[int, list[_Use]]:
    """``{polygon def index: [its polygons]}`` from a dump's rows (the
    first winding of each)."""
    uses: dict[int, list[_Use]] = {}
    cur: tuple[int, bool] | None = None
    pts: list[tuple[float, float, float]] = []
    xs: list[float] = []
    ys: list[float] = []
    windings = 0
    for raw in lines:
        if cur is None:
            if raw.startswith("BEGIN_POLYGON"):
                toks = raw.split()
                try:
                    cur = (int(toks[1]), toks[2] == "65535" and int(toks[3]) >= 4)
                except (IndexError, ValueError):
                    cur = None
                xs, ys, pts, windings = [], [], [], 0
            continue
        if raw.startswith("POLYGON_POINT") and windings == 0:
            toks = raw.split()
            try:
                xs.append(float(toks[1]))
                ys.append(float(toks[2]))
                if cur[1] and len(toks) >= 5:
                    pts.append((xs[-1], ys[-1], float(toks[3])))
            except (IndexError, ValueError):
                pass
        elif raw.startswith("END_WINDING"):
            windings += 1
        elif raw.startswith("END_POLYGON"):
            if xs:
                uses.setdefault(cur[0], []).append(_Use(
                    cur[1], (min(xs), min(ys), max(xs), max(ys)),
                    _turn_deg(pts) if cur[1] else 90.0))
            cur = None
    return uses


def _image_opaque(pol_path: str, header: _t.Mapping[str, str]) -> bool:
    """Witness (6): the ``.pol``'s image is not (nearly) all see-through;
    an image that cannot be read is not held against it."""
    from .image_opacity import image_file, opaque_fraction
    name = (header.get("TEXTURE_NOWRAP", "").split() or [""])[0]
    img = image_file(os.path.dirname(pol_path), name) if name else ""
    frac = opaque_fraction(img) if img else None
    return frac is None or frac >= MIN_OPAQUE


def draped_orthos(pack_root: str, source: str | _t.Sequence[str],
                  areas: _t.Sequence[Box]) -> tuple[MissingDef, ...]:
    """THE WITNESS over one pristine DSF dump (a path or its rows): every
    polygon definition that is a draped orthophoto over one of ``areas``,
    as the ``MissingDef`` rows the omission takes (``uses``: its
    polygons)."""
    from .obj8 import resolve_resource
    lines = list(_lines(source))
    defs = [ln.partition(" ")[2].strip() for ln in lines
            if ln.startswith("POLYGON_DEF ")]
    if not defs or not areas:
        return ()
    uses = _polygon_uses(lines)
    out: list[MissingDef] = []
    for i, path in enumerate(defs):
        if i not in uses or not path.lower().endswith(".pol"):
            continue
        local = resolve_resource(path.replace("\\", "/"), pack_root, {})
        if not local:
            continue                                    # witness (1)
        header = pol_header(local)
        if not is_ortho_header(header):
            continue                                    # (2), (3)
        turns = sorted(u.turn_deg for u in uses[i] if u.mapped)
        if not turns or turns[len(turns) // 2] > NORTH_UP_DEG:
            continue                                    # (4)
        photo = "LOAD_CENTER" in header
        if not any(u.mapped and any(_overlaps(u.box, a) for a in areas)
                   and (photo or _span_m(u.box) >= MIN_SPAN_M)
                   for u in uses[i]):
            continue                                    # (5)
        if _image_opaque(local, header):                # (6)
            out.append(MissingDef("polygon", i, path, len(uses[i])))
    return tuple(out)


def recorded(entry: _t.Mapping[str, _t.Any] | None,
             pristine_sha256: str) -> tuple[MissingDef, ...]:
    """The hiding the user accepted for THIS pristine DSF, from the row
    ``dsf_write`` records with ``pack_art.record`` (the omission's own
    record shape); ``()`` when none is recorded, it belongs to another
    pristine file, or the row no longer reads as written."""
    row = (entry or {}).get(RECORD_KEY)
    if not (isinstance(row, dict) and row.get("accepted") is True
            and row.get("pristine_sha256") == pristine_sha256):
        return ()
    try:
        drapes = tuple(MissingDef(str(d["kind"]), int(d["index"]),
                                  str(d["path"]), int(d.get("uses") or 0))
                       for d in row.get("definitions") or ())
    except (KeyError, TypeError, ValueError):
        return ()
    return drapes if row.get("key") == decision_key(pristine_sha256,
                                                    drapes) else ()


def summary(drapes: _t.Sequence[MissingDef]) -> dict[str, _t.Any]:
    """The counts the adjustment row carries."""
    return {"count": sum(m.uses for m in drapes), "definitions": len(drapes),
            "first_paths": [m.path for m in drapes[:5]]}

