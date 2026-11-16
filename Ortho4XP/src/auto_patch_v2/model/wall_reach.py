"""HOW FAR A RETAINING WALL READS ITS GROUND — the numbers the adjacent
ground (``constraints/wall_zone``), the band set-back (``planar/zones``,
``airport/wall_sides``; #1633 round 3) and the wall slope (``planar/
wall_slope``, #1661) share, in one
place because neither layer may read the other's."""
from __future__ import annotations

__all__ = ["BEHIND_SHARE", "wall_reach_m", "wall_smear_m", "WALL_SLOPE_REF_PREFIX",
           "is_wall_slope_ref", "FILL_SLOT_M", "WALL_FILL_MARK", "is_wall_fill_ref",
           "wall_slot"]

#: the face ref of a wall-slope piece (``planar/wall_slope``, #1661):
#: ``adjacent_ground:wall:<resource>#<k>``
WALL_SLOPE_REF_PREFIX = "adjacent_ground:wall:"

#: THE WALL'S FILL (#1600): the strip along a retaining wall's LOWER face
#: its footprint's fill (``planar/wall_slope``) leaves to the mesh, where
#: the step from the wall's top down to its foot is made; the rest of the
#: footprint is held at the top (``constraints/wall_zone.fill_top``).  Wider
#: than the zones' weld spacing to an airside rim (``emit.identity.
#: weld_spacing_m`` 1.0 m and the snap's half-diagonal): a narrower slot's
#: edge beside an airside pad at the wall's foot is that rim's own line work
#: (``planar/zone_pass``), and the fill would close on the pad at its level
FILL_SLOT_M = 1.5

#: how far behind a pavement edge a wall still stands "at" that edge: the
#: share of the wall's own reach (``max(4 h, 20 m)``) — 5 m for a short wall
BEHIND_SHARE = 0.25


def wall_reach_m(height_m: float) -> float:
    """How far a wall of ``height_m`` reads ground and pavement."""
    return max(4.0 * float(height_m), 20.0)


def wall_smear_m(height_m: float) -> float:
    """How far a lidar DEM smears its step on either side: the witness's
    ring (``airport/wall_class._retains_its_height``), at least 3 m, the
    wall's height out."""
    return max(3.0, float(height_m))


def is_wall_slope_ref(ref: str) -> bool:
    """A wall-slope piece's face ref (:data:`WALL_SLOPE_REF_PREFIX`)."""
    return str(ref or "").startswith(WALL_SLOPE_REF_PREFIX)


#: the mark of a wall's FILL piece in its wall-slope ref (#1600):
#: ``adjacent_ground:wall:<resource>#fill<k>``
WALL_FILL_MARK = "#fill"


def is_wall_fill_ref(ref: str) -> bool:
    """A wall's fill piece (:data:`WALL_FILL_MARK`): held at the wall's top
    and narrower than a zone strip by construction, so never a sliver zone
    (``planar/overlay.dissolve_sliver_zones``)."""
    return is_wall_slope_ref(ref) and WALL_FILL_MARK in str(ref)


def wall_slot(walls, grid_m: float):
    """THE WALL'S SLOT (#1934 R3; RULINGS 2026-11-16d, 2026-11-13x (1)):
    the retaining walls' footprints (``Airport.wall_shade``) grown one
    identity-grid step -- where the step between a wall's two levels is
    drawn.  Nothing on one level is welded, dissolved or banded across it
    (``planar/ribbons``, ``planar/overlay.dissolve_sliver_zones``).
    MEASURED KLAX ``Fence_Terminal_1.obj`` (0.5 m
    thick, the apron rim on its upper face, ``big_roads:-1143`` 1 m off):
    the road was welded and dissolved across it to the apron rim, 34.8-35.1 m
    beside 33.6 m.
    ``None`` without walls."""
    if walls is None or walls.is_empty:
        return None
    return walls.buffer(float(grid_m), join_style="mitre", mitre_limit=2.0)
