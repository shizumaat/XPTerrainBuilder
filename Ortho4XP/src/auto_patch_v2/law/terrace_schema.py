"""emit.toml ``[terrace]`` — the SCHEMA of the SHAPES (owner RULINGS
2026-09-08k; ``planar/shapes.py``), split from ``model.py`` by the
1,000-line file law and re-exported there.  A frozen dataclass and the
table's own validation; no numeric value appears here (the values live
in the TOML).  Imports nothing from v2.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Terrace", "check_terrace"]


@_dc.dataclass(frozen=True)
class Terrace:
    """The shapes: the pavement roles whose union forms them, the gap
    under which pavement is one shape, the mouth width under which a
    connection does not join two bodies, the roles whose non-station
    vertices lose their hop-derived reach band."""

    separation_m: float
    narrow_mouth_max_m: float
    shape_roles: tuple[str, ...]
    band_roles: tuple[str, ...]
    #: 08d change 4 (a): the sliver-merge area factor the planar build reads
    #: (``planar/shapes.py``) — moved here from ``[yield]`` with the yielding
    #: machinery's deletion (RULINGS 2026-09-08t); it never was yield law.
    sliver_area_factor: float
    #: 08d change 4 (b): the grade at which the apron edge RAMPS to the
    #: groundside ring across the stand-off (``constraints/groundside.py``).
    groundside_ramp_max: float


def check_terrace(tr: Terrace, roles: _t.Container[str], err: type[Exception]) -> None:
    """Every role registered; a shape role stated; the separation and the
    mouth width positive, the mouth wider than the separation (a gap the
    separation closes cannot also be a mouth)."""
    for r in (*tr.shape_roles, *tr.band_roles):
        if r not in roles:
            raise err(f"emit.terrace: unknown role {r!r}")
    if not tr.shape_roles:
        raise err("emit.terrace.shape_roles: empty")
    if tr.separation_m <= 0.0 or tr.narrow_mouth_max_m <= 0.0:
        raise err("emit.terrace: separation_m and narrow_mouth_max_m must be positive")
    if tr.narrow_mouth_max_m <= tr.separation_m:
        raise err("emit.terrace: narrow_mouth_max_m must exceed separation_m")
    if tr.sliver_area_factor <= 0.0 or not 0.0 < tr.groundside_ramp_max < 1.0:
        raise err("emit.terrace: sliver_area_factor must be positive and "
                  "groundside_ramp_max a grade fraction in (0, 1)")
