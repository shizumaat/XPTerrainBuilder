"""PLATFORM-EXACT LENGTHS: a plan distance that is the same double on
macOS, Linux and Windows (spec §46 (7); issues #1670, #1673).

``math.hypot``, ``math.dist``, ``np.hypot`` and a float ``**`` are NOT
IEEE-exact operations: ``np.hypot`` and ``**`` call the C library's
``hypot`` / ``pow``, and CPython's ``math.hypot`` / ``math.dist`` use
``fma`` or a Dekker fallback depending on the build.  The three platforms
round them differently in the last bit, and on the release dry runs that
last bit reached 1,900 of CYXY's 68,000 constraint rows.  ``+``, ``*``
and ``sqrt`` are IEEE-754 correctly rounded everywhere, so a length
spelled with them alone is one number on every runner.

The constraint package reads every length through here
(``tests/auto_patch_v2/test_platform_exact_lengths.py`` holds it).
``geom`` imports nothing of v2.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

__all__ = ["sq", "hypot", "dist", "hypot_array"]


def sq(x: _t.Any) -> _t.Any:
    """``x * x`` — never ``x ** 2``, which is the C library's ``pow``."""
    return x * x


def hypot(dx: float, dy: float) -> float:
    """``sqrt(dx² + dy²)`` in correctly rounded operations only."""
    return math.sqrt(dx * dx + dy * dy)


def dist(p: _t.Sequence[float], q: _t.Sequence[float]) -> float:
    """The plan distance between two points (their first two coordinates)."""
    dx, dy = p[0] - q[0], p[1] - q[1]
    return math.sqrt(dx * dx + dy * dy)


def hypot_array(dx: _t.Any, dy: _t.Any) -> np.ndarray:
    """:func:`hypot` elementwise over arrays (``np.hypot`` without libm)."""
    dx = np.asarray(dx, dtype=float)
    dy = np.asarray(dy, dtype=float)
    return np.sqrt(dx * dx + dy * dy)
