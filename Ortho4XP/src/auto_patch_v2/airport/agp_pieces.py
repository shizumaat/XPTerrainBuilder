"""AN ``.agp``'s PLACED PIECES — the OBJ8s an ``.agp`` stands up, where
X-Plane stands them (#2090).

THE FILE (X-Plane AGP spec, v1000): ``TEXTURE_SCALE`` / ``TEXTURE_WIDTH``
/ ``TEXTURE_HEIGHT`` turn texture units into metres; ``ANCHOR_PT s t`` is
the point placed at the DSF row; ``GROUND_PT s t`` the ONE point whose
drawn ground height becomes the datum of the whole rigid group (the
anchor when absent); ``ROTATION`` turns the tile; ``OBJECT <file>`` lists
the pieces (relative to the ``.agp``'s folder) and ``OBJ_DELTA x y rot
height index`` stands piece ``index`` at texture point ``(x, y)``, turned
``rot`` degrees clockwise and ``height`` metres over the datum.

KDEN's ``Jeppesen_Concourse.agp`` is one such group of 110 pieces — the
terminal, both garages and the Westin — drawn on the ground under one
point.  Every reader that measures what X-Plane draws (the AGP seat,
``tools/drawn_site.py``) places the pieces through HERE, so the two never
disagree about where a piece stands.

Plan coordinates are metres east / north of the DSF row, the row heading
applied clockwise, as ``riders.agp_footprint_xy``.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os

__all__ = ["AgpFile", "read_agp", "placed_pieces", "ground_point",
           "lifted_text", "MOVABLE", "FIXED_ON_GROUND"]

#: the placement keyword a datum lift moves (its 4th field is the height)
MOVABLE = "OBJ_DELTA"
#: placements X-Plane lays ON the terrain whatever the datum: a lift
#: leaves them where they are and is still the group's lift
FIXED_ON_GROUND = frozenset({"OBJ_DRAPED", "TREE", "TREE_LINE"})
#: every other AGP placement keyword a lift could not move by a height
_OTHER = frozenset({"FAC", "FACADE", "OBJ_GRADED", "OBJ_SCRAPER", "AUTOGEN",
                    "AUTOGEN_STRING", "SPELLING"})


@_dc.dataclass(frozen=True)
class AgpFile:
    """One parsed ``.agp``: ``objects`` its ``OBJECT`` paths (absolute),
    ``deltas`` its ``OBJ_DELTA`` rows ``(s, t, rot, height, index)``,
    metres per texture unit ``mpp``, ``anchor`` / ``ground`` in texture
    units, ``rotation`` in degrees, and ``other`` the placement keywords
    a height lift cannot move (``FAC`` …)."""

    path: str
    objects: tuple[str, ...]
    deltas: tuple[tuple[float, float, float, float, int], ...]
    mpp: tuple[float, float]
    anchor: tuple[float, float]
    ground: tuple[float, float]
    rotation: float
    other: tuple[str, ...]


@_dc.dataclass(frozen=True)
class _Piece:
    """One placed piece: the OBJ8 ``obj`` (absolute path), its origin
    ``(lon, lat)``, heading (degrees clockwise) and ``height`` over the
    group's datum."""

    obj: str
    lon: float
    lat: float
    heading_deg: float
    height: float


def read_agp(path: str) -> AgpFile | None:
    """The ``.agp`` at ``path``, or ``None`` when it is unreadable or has
    no scale (no metres to place a piece by)."""
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    base = os.path.dirname(path)
    objects: list[str] = []
    deltas: list[tuple[float, float, float, float, int]] = []
    other: set[str] = set()
    anchor = ground = None
    sc_s = sc_t = width = height = None
    rotation = 0.0
    for ln in lines:
        t = ln.split()
        if not t:
            continue
        k = t[0]
        try:
            if k == "OBJECT" and len(t) >= 2:
                objects.append(os.path.join(base, *ln.split(None, 1)[1].strip()
                                            .replace("\\", "/").split("/")))
            elif k == MOVABLE and len(t) >= 6:
                deltas.append((float(t[1]), float(t[2]), float(t[3]),
                               float(t[4]), int(t[5])))
            elif k == "ANCHOR_PT" and len(t) >= 3:
                anchor = (float(t[1]), float(t[2]))
            elif k == "GROUND_PT" and len(t) >= 3:
                ground = (float(t[1]), float(t[2]))
            elif k == "ROTATION" and len(t) >= 2:
                rotation = float(t[1])
            elif k == "TEXTURE_SCALE" and len(t) >= 2:
                sc_s = float(t[1])
                sc_t = float(t[2]) if len(t) >= 3 else None
            elif k == "TEXTURE_WIDTH" and len(t) >= 2:
                width = float(t[1])
            elif k == "TEXTURE_HEIGHT" and len(t) >= 2:
                height = float(t[1])
            elif k in _OTHER:
                other.add(k)
        except ValueError:
            continue
    if not sc_s or width is None:
        return None
    if height is None:
        height = width
    mpp = (width / sc_s, height / (sc_t or sc_s))
    anchor = anchor or (0.0, 0.0)
    return AgpFile(path, tuple(objects), tuple(deltas), mpp, anchor,
                   ground or anchor, rotation, tuple(sorted(other)))


def _to_ll(lon: float, lat: float, heading_deg: float, e: float, n: float
           ) -> tuple[float, float]:
    """``(lon, lat)`` of the AGP-frame point ``(e, n)`` of a row at
    ``(lon, lat)`` turned ``heading_deg`` clockwise."""
    from .anchor_rule import _m_per_deg
    ml, mo = _m_per_deg(lat)
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    return lon + (e * c + n * s) / mo, lat + (-e * s + n * c) / ml


def _local(agp: AgpFile, st: tuple[float, float]) -> tuple[float, float]:
    return ((st[0] - agp.anchor[0]) * agp.mpp[0],
            (st[1] - agp.anchor[1]) * agp.mpp[1])


def placed_pieces(agp: AgpFile, lon: float, lat: float, heading_deg: float
                  ) -> tuple[_Piece, ...]:
    """Every ``OBJ_DELTA`` piece of ``agp`` placed by a row at ``(lon,
    lat)`` heading ``heading_deg`` (an index past the ``OBJECT`` list
    places nothing)."""
    hdg = heading_deg + agp.rotation
    out = []
    for s, t, rot, h, i in agp.deltas:
        if not 0 <= i < len(agp.objects):
            continue
        e, n = _local(agp, (s, t))
        plon, plat = _to_ll(lon, lat, hdg, e, n)
        out.append(_Piece(agp.objects[i], plon, plat, hdg + rot, h))
    return tuple(out)


def ground_point(agp: AgpFile, lon: float, lat: float, heading_deg: float
                 ) -> tuple[float, float]:
    """``(lon, lat)`` of the ``GROUND_PT`` — where X-Plane reads the
    datum of every piece."""
    e, n = _local(agp, agp.ground)
    return _to_ll(lon, lat, heading_deg + agp.rotation, e, n)


def lifted_text(text: str, lift_m: float, note: str) -> str:
    """``text`` with every ``OBJ_DELTA`` height moved by ``lift_m`` and
    ``note`` (a ``#`` comment, the writer's ``CUT_MARK`` line) after the
    third line (the ``A`` / ``1000`` / ``AG_POINT`` header).  Every other
    byte is kept."""
    eol = "\r\n" if "\r\n" in text else "\n"
    out: list[str] = []
    for n, raw in enumerate(text.splitlines()):
        t = raw.split()
        if t and t[0] == MOVABLE and len(t) >= 6:
            t[4] = f"{float(t[4]) + lift_m:.8f}"
            raw = " ".join(t)
        out.append(raw)
        if n == 2:
            out.append(note)
    return eol.join(out) + eol
