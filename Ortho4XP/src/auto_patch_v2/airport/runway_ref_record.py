"""The record every runway-end cross-check provider returns (owner RULINGS
2026-10-25a, 26a; ``airport/runway_refs`` is the registry that reads
them).  Its own module so the providers and the registry both import it
and neither imports the other's module."""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["RefEnd", "REFS_DIR"]

#: The cache directory under the airport mod cache root.
REFS_DIR = "_runway_refs"


@_dc.dataclass(frozen=True)
class RefEnd:
    """One runway end as a cross-check source states it: the bare
    designator, the END elevation (metres), the end's coordinate and its
    displaced-threshold length (metres; 0 when the source states none)."""

    designator: str
    elevation_m: float
    lat: float | None
    lon: float | None
    displaced_m: float
    source: str
