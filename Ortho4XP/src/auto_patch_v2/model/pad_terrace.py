"""THE DECLARED PAD TERRACES — their record type (owner RULINGS
2026-09-28b, issue #11).

In the ``model`` layer so every consumer may read it (issue #104, the
reds84 pattern of ``model/hard_plane``): ``planar/pad_terrace`` MINTS the
terraces into the map's registries (``PlanarMap.registries.terraces``,
``model.registries``; issue #841 deleted the module global ``TERRACES``),
``planar/build`` declares their joints, ``constraints/pad_fronting`` reads
the lower-pad levels — and ``constraints`` may not import ``planar``
(``tests/auto_patch_v2/test_model.py::test_dependency_direction``).
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["Terrace"]


@_dc.dataclass(frozen=True)
class Terrace:
    """One declared pad terrace: the pad, the apron (or lower pad) split
    from it, the two proxy levels and the weld bound they exceeded."""

    pad_ref: str
    front_ref: str
    other_ref: str
    kind: str                 # "apron" | "pad"
    front_level: float
    other_level: float
    bound_m: float
    gap_m: float
    #: the contact line (frame metres) the strip runs along — the pad's
    #: own ring within the frontage horizon of the other body
    line: tuple[tuple[float, float], ...]
