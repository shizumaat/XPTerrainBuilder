"""THE PLACEMENT WINDOW: WHICH PACK OBJECTS ARE THIS AIRPORT'S (#1653).

THE DEFECT.  ``load`` read a pack's ``.obj`` / ``.agp`` placements only
inside a fixed 0.05 deg box about the airport's reference point.  A large
airport overflowed it (KDEN, LFPG, KABQ: 400–1,300 placements unread) and
EDDF's ``Tunnel_1`` and ``Bridge_2_hard`` lay just past it: nothing graded
the terrain to them (#1640 point 2).  The owner: "I expect us to take into
account every object in the scenery pack."

THE RULE.  A placement is read when it lies inside the airport's OWN
extent — the extent the pavement pages are admitted by
(``load._own_extent``: runways, 110 pavements, 130 boundaries, grown by
``identity.dsf_pavement_admission_m``) — never a degree box.

A PACK OF SEVERAL AIRPORTS (one DSF, several apt.dat blocks: a regional
pack, a city pack) gives each placement to ONE airport: the one whose
region (``object_pack.region_in``: row 130, else runways and pavements)
is nearest.  A placement nearer another airport of the same pack stays
with that airport; an exact tie goes to the lower ICAO, so two builds of
the same pack never both seat one placement.
"""
from __future__ import annotations

import functools
import os
import typing as _t

import numpy as np

from . import apt_dat as _apt
from .apt_dat import airports_in
from .object_pack import region_in

__all__ = ["Window", "pack_apt_dat", "rivals"]

#: neighbours whose reference point is farther than this (deg) cannot reach
#: this airport's extent and are not projected (a pre-filter only)
_RIVAL_PREFILTER_DEG = 0.5


class Window:
    """``extent`` (this airport's grown extent, metres), ``own`` (its
    region, the distance origin) and ``rivals`` ``((icao, region), ...)``
    of the same pack."""

    def __init__(self, icao: str, extent, own, rivals=()):
        self.icao, self.extent, self.own = icao.upper(), extent, own
        self.rivals = tuple(rivals)
        self.n_outside = self.n_rival = 0

    def admits(self, xy: _t.Sequence[tuple[float, float]]) -> np.ndarray:
        """One bool per point: inside the extent and nearest this airport.
        Counts the refusals on ``n_outside`` / ``n_rival``."""
        import shapely
        if not len(xy):
            return np.zeros(0, dtype=bool)
        pts = np.asarray(xy, dtype=float)
        if self.extent is None:
            return np.ones(len(pts), dtype=bool)
        keep = shapely.contains_xy(self.extent, pts[:, 0], pts[:, 1])
        self.n_outside += int((~keep).sum())
        if self.rivals and keep.any() and self.own is not None:
            idx = np.flatnonzero(keep)
            geoms = shapely.points(pts[idx])
            d_own = shapely.distance(self.own, geoms)
            for icao, region in self.rivals:
                d = shapely.distance(region, geoms)
                lost = (d < d_own) | ((d == d_own) & (icao < self.icao))
                keep[idx[lost]] = False
            self.n_rival += int(len(idx) - keep[idx].sum())
        return keep


def pack_apt_dat(pack_root: str) -> str | None:
    """The pack's own apt.dat (``Earth nav data/apt.dat``), or ``None``."""
    p = os.path.join(pack_root, "Earth nav data", "apt.dat")
    return p if os.path.isfile(p) else None


def rivals(apt_dat_path: str | None, icao: str, ref: tuple[float, float],
           to_xy, extent) -> tuple:
    """``((icao, region), ...)``: the OTHER airports of the pack's apt.dat
    whose region reaches ``extent``, in this airport's ``to_xy`` frame."""
    if not apt_dat_path or extent is None:
        return ()
    try:
        st = os.stat(apt_dat_path)
    except OSError:
        return ()
    out = []
    lat0, lon0 = ref
    for other, apt in _parsed(apt_dat_path, st.st_mtime_ns, st.st_size):
        if other == icao.upper():
            continue
        la, lo = apt.reference_point()
        if abs(la - lat0) > _RIVAL_PREFILTER_DEG or abs(lo - lon0) > _RIVAL_PREFILTER_DEG:
            continue
        region = region_in(apt, to_xy)
        if region is not None and region.distance(extent) == 0.0:
            out.append((other, region))
    return tuple(sorted(out, key=lambda r: r[0]))


@functools.lru_cache(maxsize=8)
def _parsed(path: str, _mtime_ns: int, _size: int) -> tuple:
    """Every airport block of ``path``, parsed: ``((icao, AptAirport), ...)``."""
    out = []
    for other in airports_in(path):
        block = _apt.read_airport_block(path, other)
        if block:
            try:
                out.append((other, _apt.parse_airport_block(block)))
            except Exception:       # an unparsable neighbour claims nothing
                continue
    return tuple(out)
