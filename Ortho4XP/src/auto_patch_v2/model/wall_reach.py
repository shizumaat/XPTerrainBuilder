"""HOW FAR A RETAINING WALL READS ITS GROUND — the numbers the adjacent
ground (``constraints/wall_zone``) and the band set-back
(``planar/zones``, ``airport/wall_sides``; #1633 round 3) share, in one
place because neither layer may read the other's."""
from __future__ import annotations

__all__ = ["BEHIND_SHARE", "wall_reach_m", "wall_smear_m"]

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
