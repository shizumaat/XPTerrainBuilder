"""THE UNIT-PAD PLATFORM VERDICTS — their record type and the last
arrangement's registry (unit-platform spec, owner RULINGS 2026-09-28a).

ONE registry, in the ``model`` layer so every consumer may read it (issue
#104, the reds84 pattern of ``model/hard_plane``): ``planar/platform``
MINTS the verdicts (and re-exports these names), ``pipeline/publication``
publishes them, ``constraints/platform`` reads the refused ones — and
``constraints`` may not import ``planar`` (``tests/auto_patch_v2/
test_model.py::test_dependency_direction``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Platform", "PLATFORMS"]


@_dc.dataclass(frozen=True)
class Platform:
    """One unit pad's platform verdict at the arrangement."""

    ref: str
    collar_m: float
    pad_m2: float
    platform_m2: float
    welded_samples: int
    #: the welded rim's relief at the mint (DEM, against the tilt-bounded
    #: frontage plane) that set C; ``None`` without a DEM
    relief_m: "float | None" = None
    #: ``""`` when minted, else why not (``"eroded_away"``,
    #: ``"under_min_area"``)
    refused: str = ""

    def to_dict(self) -> dict[str, _t.Any]:
        return _dc.asdict(self)


#: The last arrangement's platform verdicts (the ``pad_terrace.TERRACES``
#: pattern: read back by the publication and the census).
PLATFORMS: list[Platform] = []
