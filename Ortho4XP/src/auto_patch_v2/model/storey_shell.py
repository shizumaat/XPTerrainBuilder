"""A STOREY SHELL (#2062, owner RULINGS 2026-11-13w; spec
``docs/specs/2062-storey-shell-spec.md`` §1, Amendment A1): a split-level
building (``airport/split_level``) laid on ONE held pad with one rigid level
per storey -- the record ``planar/storey_pad`` mints, the platform planner
splits the pad by (``planar/low_level``), the sidecar publishes
(``storey_shells``) and the object stage seats the building's frame from.

Frame metres; ``levels`` are FRAME heights (authored y plus each row's own
AGL lift): the building's zero is ``z0 = D_block - levels[block]``,
``D_block`` the solved datum of the block pad."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["StoreyShell", "StoreyRun", "SHELL_VERDICT"]

#: the held verdict of a storey shell's pad (``planar/platform``)
SHELL_VERDICT = "storey_shell"


@_dc.dataclass(frozen=True)
class StoreyRun:
    """One run of the building's outline: its frame segment (the building
    on its RIGHT), the foot of the walls facing out of it (``None``: no
    wall), the level it stands at (``None``: no foot) and whether it is
    MINOR (its own foot's level did not count; spec A1 (2)), and whether it
    faces AIRSIDE pavement (its bar: 0.05 m airside, 0.5 m groundside)."""

    xy: tuple[tuple[float, float], ...]
    foot: "float | None"
    level: "int | None"
    minor: bool = False
    airside: bool = False
    #: THE BACK CUT outside a groundside run at the lowest level (spec A2
    #: (3)): its mean depth (metres; ``None``: no back cut is asked here)
    #: and what clipped it (``"road"`` -- a mapped road keeps its profile,
    #: ``"airside"``, ``"structure"``, ``"pad"``, ``"pit"``)
    back_cut_m: "float | None" = None
    clipped_by: tuple[str, ...] = ()


@_dc.dataclass(frozen=True)
class StoreyShell:
    """One split-level building on its storey pad (module docstring)."""

    #: the split-level record's id (its witness placement) and its family
    id: str
    member_ids: tuple[str, ...]
    #: the family's resources (the drawn rows a check reads)
    paths: tuple[str, ...]
    #: the held pad (``Registries.held``) the shell stands on
    pad_ref: str
    #: the storey heights, ascending, and the BLOCK's index (the level the
    #: airside meets: the pad's own face, at the pad's datum)
    levels: tuple[float, ...]
    block: int
    #: the face ref of each level: the pad's for the block, ``<pad>/p<k>``
    #: for every other
    level_refs: tuple[str, ...]
    #: each level's region of the pad (frame polygons; empty: no region)
    level_regions: tuple[_t.Any, ...]
    runs: tuple[StoreyRun, ...]
    #: the plan the building covers and the pad (frame rings)
    plan: tuple[tuple[float, float], ...]
    pad: tuple[tuple[float, float], ...]
    anchor_xy: tuple[float, float]
    #: THE BACK CUT ``T`` (at the block's level) and THE KERB ``R`` (the
    #: declared riser between it and the higher lot, spec A2 (3)), frame
    #: polygons (empty: none), and the kerb's wall records in
    #: ``planar/foot_kerb``'s shape (``ring``, ``upper`` -- the lot's side,
    #: high -- ``height_m``)
    back_cut: _t.Any = None
    kerb: _t.Any = None
    kerbs: tuple[dict, ...] = ()
    #: the scope that laid it on its pad (spec A2 (4)): ``"airside"`` (its
    #: block the airside's level) or ``"floor"`` (its lowest level on a
    #: structure floor)
    scope: str = "airside"

    def y_of(self, k: int) -> float:
        """Level ``k``'s height over the block (its landing's ``y``)."""
        return float(self.levels[k]) - float(self.levels[self.block])
