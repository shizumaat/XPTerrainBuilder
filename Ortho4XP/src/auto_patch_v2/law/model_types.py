"""The law tables' LEAF VALUE TYPES — the code-keyed table, the rate and
the role cap.  Kept beside ``model.py`` under the 1,000-line file law
(RULINGS 2026-09-05k-2) and re-exported there, and separate so the sibling
schemas (``eat_schema`` and any other that keys a value by code number or
letter) can name them without importing ``model`` back.  Values live in the
TOML; no numeric value appears here.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["CodeTable", "Rate", "RoleCap"]


@_dc.dataclass(frozen=True)
class CodeTable:
    """A value keyed by aerodrome reference code NUMBER (1-4) or code
    LETTER (A-F).  Exactly one of ``by_code`` / ``by_letter`` is set.  A
    class absent from the table means the authority states no number
    (``value()`` returns ``None`` there only when ``default`` is None)."""

    by_code: _t.Mapping[int, float] | None = None
    by_letter: _t.Mapping[str, float] | None = None
    default: float | None = None

    def value(self, code_number: int | None = None,
              code_letter: str | None = None) -> float | None:
        """The class' value, or ``default`` when the class is unkeyed."""
        if self.by_code is not None:
            if code_number is None:
                return self.default
            return self.by_code.get(int(code_number), self.default)
        if self.by_letter is not None:
            if not code_letter:
                return self.default
            return self.by_letter.get(str(code_letter).upper(), self.default)
        return self.default


@_dc.dataclass(frozen=True)
class Rate:
    """A grade-change rate: ``grade`` per ``per_m`` metres."""

    grade: float
    per_m: float

    @property
    def per_metre(self) -> float:
        """The rate as grade change per metre."""
        return self.grade / self.per_m


@_dc.dataclass(frozen=True)
class RoleCap:
    """A role's HARD caps; ``preferred`` its two-tier preference (2026-09-06w)."""

    longitudinal: float
    transverse: float
    preferred: "RoleCap | None" = None
