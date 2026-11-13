"""A GRADED FACADE STANDS ON ITS DRAWN GROUND (#2042; owner 2026-11-13,
KOAK's shoreline embankment: "we don't want any visible edge to be
floating").

HOW X-PLANE SEATS ONE (X-Plane facade file format specification): "in a
graded facade, the center of the first wall is placed on the terrain and
the facade is then kept in a flat plane".  ONE ground height, read at ONE
point, carries the whole polygon — KOAK's ``Objects/see.fac`` is a 6 km
shoreline chain whose first wall stands on the graded shore at 1.76 m
while its water-side foot runs over 0.0-0.5 m of drawn water: the whole
embankment hangs up to 1.6 m over the bay.  The DSF row carries no height
(a facade node is ``lon lat [wall] [ctrl]``), so neither the row nor the
ground can lower it without moving something else.

THE RULE, general to every graded facade a pack authors as MESH segments:

* its AUTHORED BASE is every mesh vertex at or below the file's own
  ground line ``y = 0`` — the feet, footings and buried column ends the
  author drew to stand in the ground (an elevated deck's underside, at
  ``y > 0``, is not base and is never pulled down);
* the plane it stands on is lowered — never raised — until every base
  vertex, swept along every wall at its outward offset ``x``, sits at or
  below the drawn ground under it: ``plane <= min(ground - y)``;
* the lowering is the FILE's: a copy of the ``.fac`` beside it with every
  ``VERTEX`` and ``ATTACH_GRADED`` height moved by the drop (a new
  ``POLYGON_DEF`` the polygon is pointed at, like a split body's
  ``OBJECT_DEF``; the authored file is never opened for writing).

What it does NOT lower: a facade drawn by wall quads (v800, or a v1000
segment without a ``MESH``) or one with a roof — X-Plane builds those from
the height parameter, so no file edit moves them; a library facade (its
textures resolve beside the library's file, not the pack's); a facade with
no vertex at or below its ground line (drawn to hang).
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import math
import os
import typing as _t

from ..model.placement import CUT_MARK, FacadeSeat

__all__ = ["FLOAT_TOL_M", "STEP_M", "station_floats", "candidates",
           "candidates_box", "plan_seats"]

#: A foot this far over its ground is not lowered (the owner's pavement
#: visibility bar, ``tools/drawn_site.PAVEMENT_BAR_M``): mesh noise under
#: a fence on graded ground never re-writes its file.
FLOAT_TOL_M = 0.05
#: Stations along each wall (metres): the base is swept, not spot-read.
STEP_M = 2.0
#: Base vertices whose outward offsets fall in one bucket this wide are
#: read at one offset — the shallowest of them, which binds.
X_BUCKET_M = 0.5


@_dc.dataclass(frozen=True)
class _FacadeBase:
    """The authored base of one graded mesh facade: ``feet`` are ``(x out,
    y up)`` of its vertices at or below ``y = 0``, one per ``x`` bucket
    (the highest ``y`` there).  ``ring`` is the file's ``RING``."""

    ring: bool
    feet: tuple[tuple[float, float], ...]


@_dc.dataclass(frozen=True)
class _FacadeFile:
    """A lowered copy: pack-relative ``resource`` and its whole ``text``
    (the shape ``placement_write.write_files`` writes)."""

    resource: str
    text: str


@_dc.dataclass(frozen=True)
class _Seat:
    """What one polygon's base asks of its plane."""

    anchor: tuple[float, float]       # (lon, lat) of the first wall's centre
    anchor_z: float                   # the drawn ground there (X-Plane's plane)
    need_z: float                     # the highest plane every foot allows
    worst: tuple[float, float]        # (lon, lat) of the binding foot station

    @property
    def drop_m(self) -> float:
        """How far the plane must come down (``<= 0``)."""
        return min(0.0, self.need_z - self.anchor_z)


# ── the file ─────────────────────────────────────────────────────────────

def _segments_meshed(lines: _t.Sequence[str]) -> bool:
    """Whether every ``SEGMENT`` / ``SEGMENT_CURVED`` carries a ``MESH``."""
    open_seg, meshed = False, True
    for raw in lines:
        t = raw.split()
        k = t[0] if t else ""
        if k in ("SEGMENT", "SEGMENT_CURVED", "WALL", "FLOOR"):
            if open_seg and not meshed:
                return False
            open_seg, meshed = k.startswith("SEGMENT"), False
        elif k == "MESH":
            meshed = True
    return not (open_seg and not meshed)


def _facade_base(text: str) -> _FacadeBase | None:
    """The authored base of a ``.fac``'s text, or ``None`` when no file edit
    can lower it (module doc): not a v1000 ``GRADED`` facade, a segment
    with no ``MESH``, a roof (``ROOF_HEIGHT`` > 0, ``ROOF_OBJ``), or no
    vertex at or below the ground line."""
    lines = text.splitlines()
    try:
        if int(lines[1].split()[0]) < 1000 or lines[2].split()[0] != "FACADE":
            return None
    except (IndexError, ValueError):
        return None
    if not _segments_meshed(lines[3:]):
        return None
    graded, ring = False, True
    best: dict[int, tuple[float, float]] = {}
    for raw in lines[3:]:
        t = raw.split()
        k = t[0] if t else ""
        if k in ("GRADED", "DRAPED"):
            graded = k == "GRADED"
        elif k == "RING" and len(t) > 1:
            ring = t[1] != "0"
        elif k.startswith("ROOF_OBJ") or (k == "ROOF_HEIGHT" and len(t) > 1
                                          and float(t[1]) > 0.0):
            return None
        elif k == "VERTEX" and len(t) >= 4 and float(t[2]) <= 1e-6:
            x, y = float(t[1]), float(t[2])
            b = int(math.floor(x / X_BUCKET_M))
            if b not in best or y > best[b][1]:
                best[b] = (x, y)
    if not graded or not best:
        return None
    return _FacadeBase(ring, tuple(best[b] for b in sorted(best)))


def _lowered_text(text: str, drop_m: float, resource: str) -> str:
    """``text`` with every ``VERTEX`` and ``ATTACH_GRADED`` height moved by
    ``drop_m`` and this writer's ``CUT_MARK`` after the header (a ``#``
    comment line, as shipped packs carry them)."""
    eol = "\r\n" if "\r\n" in text else "\n"
    out: list[str] = []
    for n, raw in enumerate(text.splitlines()):
        t = raw.split()
        if t and t[0] == "VERTEX" and len(t) >= 4:
            t[2] = f"{float(t[2]) + drop_m:.6f}"
            raw = "VERTEX\t" + " ".join(t[1:])
        elif t and t[0] == "ATTACH_GRADED" and len(t) >= 5:
            t[3] = f"{float(t[3]) + drop_m:.6f}"
            raw = " ".join(t)
        out.append(raw)
        if n == 2:
            out.append(f"{CUT_MARK}{resource}: graded facade lowered "
                       f"{drop_m:+.2f} m onto its drawn ground (#2042)")
    return eol.join(out) + eol


def _variant_resource(resource: str, text: str, drop_m: float) -> str:
    """``<dir>/<stem>__g_<hash>.fac`` beside the original: one name per
    (file, drop), so polygons asking the same drop share one copy."""
    stem, _ext = os.path.splitext(resource.replace("\\", "/"))
    h = hashlib.sha256(f"{text}\0{drop_m:.2f}".encode("utf-8", "surrogateescape"))
    return f"{stem}__g_{h.hexdigest()[:8]}.fac"


# ── one placed polygon ───────────────────────────────────────────────────

def _stations(nodes: _t.Sequence[tuple[float, float]], base: _FacadeBase
              ) -> list[tuple[float, float, float, float]]:
    """``(lon, lat, foot y, metres along)`` of every foot at every station
    of every wall.  The wall frame: ``x`` is outward, to the RIGHT of the
    node order (a counter-clockwise ring's outside)."""
    from .anchor_rule import _m_per_deg
    ml, mo = _m_per_deg(nodes[0][1])
    pts: list[tuple[float, float, float, float]] = []
    n, along = len(nodes), 0.0
    for i in range(n if base.ring else n - 1):
        a, b = nodes[i], nodes[(i + 1) % n]
        dx, dy = (b[0] - a[0]) * mo, (b[1] - a[1]) * ml
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        rx, ry = dy / length, -dx / length
        k = max(1, int(math.ceil(length / STEP_M)))
        for j in range(k + 1):
            lon = a[0] + (b[0] - a[0]) * j / k
            lat = a[1] + (b[1] - a[1]) * j / k
            pts.extend((lon + x * rx / mo, lat + x * ry / ml, y,
                        along + length * j / k) for x, y in base.feet)
        along += length
    return pts


def station_floats(nodes: _t.Sequence[tuple[float, float]], base: _FacadeBase,
                   surface: _t.Callable):
    """How far each foot station of one placed polygon floats over the
    ground under it: ``(anchor (lon, lat), anchor z, [(lon, lat, metres
    along, float)])`` — float ``= anchor z + foot y - ground`` (positive:
    the foot hangs over the ground).  The plane is X-Plane's: the ground
    at the first wall's centre.  ``nodes`` are the DSF nodes ``(lon,
    lat)``; ``surface(lat, lon) -> z | None`` (``.many`` when it has one).
    ``None`` when the anchor is off the surface; a station off it is
    left out."""
    if len(nodes) < 2:
        return None
    anchor = ((nodes[0][0] + nodes[1][0]) / 2.0, (nodes[0][1] + nodes[1][1]) / 2.0)
    pts = _stations(nodes, base)
    lats = [anchor[1]] + [p[1] for p in pts]
    lons = [anchor[0]] + [p[0] for p in pts]
    many = getattr(surface, "many", None)
    zs = (many(lats, lons) if many is not None
          else [surface(la, lo) for la, lo in zip(lats, lons, strict=True)])
    if zs[0] is None:
        return None
    az = float(zs[0])
    return anchor, az, [(lon, lat, s, az + y - float(z))
                        for (lon, lat, y, s), z in zip(pts, zs[1:], strict=True)
                        if z is not None]


def _seat_polygon(nodes: _t.Sequence[tuple[float, float]], base: _FacadeBase,
                 surface: _t.Callable) -> _Seat | None:
    """The plane one placed polygon stands on and the highest its base
    allows (:func:`station_floats`); ``None`` when the anchor or every
    foot station is off the surface."""
    got = station_floats(nodes, base, surface)
    if got is None or not got[2]:
        return None
    anchor, az, rows = got
    worst = max(rows, key=lambda r: r[3])
    return _Seat(anchor, az, az - worst[3], (worst[0], worst[1]))


# ── the pack ─────────────────────────────────────────────────────────────

def _read_base(path: str) -> tuple[str, _FacadeBase] | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="latin-1") as fh:
            text = fh.read()
        base = _facade_base(text)
    except (OSError, ValueError):
        return None
    return None if base is None else (text, base)


def candidates(dump: _t.Any, pack_root: str
               ) -> list[tuple[_t.Any, str, _FacadeBase]]:
    """``(polygon, file text, base)`` for every polygon of ``dump`` whose
    definition is a PACK-LOCAL graded mesh facade (module doc)."""
    read: dict[str, tuple[str, _FacadeBase] | None] = {}
    out = []
    for poly in getattr(dump, "polygons", ()):
        d = poly.def_path
        if not d.lower().endswith(".fac") or not poly.nodes \
                or getattr(poly, "index", -1) < 0:
            continue
        if d not in read:
            read[d] = _read_base(os.path.join(
                pack_root, *d.replace("\\", "/").split("/")))
        if read[d] is not None:
            out.append((poly, read[d][0], read[d][1]))
    return out


def candidates_box(cands: _t.Sequence) -> tuple[float, float, float, float] | None:
    """``(min_lon, min_lat, max_lon, max_lat)`` over the candidates' nodes
    widened by their widest foot, or ``None`` with none."""
    from .anchor_rule import _m_per_deg
    lons = [n[0] for poly, _t2, _b in cands for n in poly.nodes[0]]
    lats = [n[1] for poly, _t2, _b in cands for n in poly.nodes[0]]
    if not lons:
        return None
    reach = STEP_M + max(abs(x) for _p, _t2, b in cands for x, _y in b.feet)
    ml, mo = _m_per_deg(lats[0])
    return (min(lons) - reach / mo, min(lats) - reach / ml,
            max(lons) + reach / mo, max(lats) + reach / ml)


def plan_seats(dump: _t.Any, pack_root: str, surface: _t.Callable,
               cands: _t.Sequence | None = None
               ) -> tuple[tuple[FacadeSeat, ...], tuple[_FacadeFile, ...],
                          dict[str, _t.Any]]:
    """``(seats, lowered files, counts)`` for the pack's graded mesh
    facades standing on ``surface`` (the built mesh)."""
    cands = candidates(dump, pack_root) if cands is None else cands
    seats: list[FacadeSeat] = []
    files: dict[str, _FacadeFile] = {}
    deepest = 0.0
    for poly, text, base in cands:
        s = _seat_polygon([(n[0], n[1]) for n in poly.nodes[0]], base, surface)
        if s is None or s.drop_m > -FLOAT_TOL_M:
            continue
        drop = math.floor(s.drop_m * 100.0) / 100.0
        res = _variant_resource(poly.def_path, text, drop)
        if res not in files:
            files[res] = _FacadeFile(res, _lowered_text(text, drop, poly.def_path))
        seats.append(FacadeSeat(int(poly.index), poly.def_path, res, drop,
                                s.anchor[0], s.anchor[1], round(s.anchor_z, 3),
                                round(s.need_z, 3)))
        deepest = min(deepest, drop)
    counts = {"graded_facades": len(cands), "graded_facades_lowered": len(seats),
              "graded_facade_drop_max_m": deepest}
    return tuple(seats), tuple(files.values()), counts
