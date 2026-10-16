"""THE CORE'S CAP-LIPSCHITZ CLAMP, for v2 — the one adapter to
``O4_Vector_Utils.cap_lipschitz_profile`` (the minimum-intervention
profile that holds a longitudinal cap: identity wherever the input is
already cap-lawful).

Lives in ``geom`` because two layers call it — ``airport/road_profile``
(the road clamp, spec §2-SUPPLEMENT S.2) and ``constraints/taxi_trend``
(the taxi trend made lawful, owner RULINGS 2026-10-15e follow-up) — and a
helper two packages need goes DOWN.  The clamp itself is the core's; this
module only imports it, never re-spells it.
"""
from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["core_vector_utils", "ENGINE_DIR"]

#: ``Ortho4XP/`` — the engine root whose ``src/`` holds the core modules.
ENGINE_DIR = Path(__file__).resolve().parents[3]


def core_vector_utils():
    """``O4_Vector_Utils`` — the core's clamp.  The ONLY core import v2
    makes for profiles, and it is made here."""
    d = str(ENGINE_DIR / "src")
    if d not in sys.path:
        sys.path.append(d)
    import O4_Vector_Utils as VECT  # noqa: WPS433 (core adapter)
    return VECT
