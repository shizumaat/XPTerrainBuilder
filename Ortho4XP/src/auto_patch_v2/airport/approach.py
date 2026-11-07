"""THE APPROACH WITNESS of one runway END — its approach class and its
Cat II/III status, from the CIFP and the apt.dat row 100 (owner RULINGS
2026-10-15m (2) as amended by 15n; regulation-conformance spec §3.4).

* INSTRUMENT: CIFP lists any approach to the end, OR apt.dat gives it
  precision markings (3 / 5).  Non-precision markings (2 / 4) alone do not
  count (15n: authors paint them on visual runways).
* PRECISION (``pa``): apt.dat precision markings, OR a CIFP ILS / GLS / MLS.
* APV: a CIFP RNAV / RNP approach (vertical guidance) and no precision one.
* Cat II/III: apt.dat ALSF-II (2) or Calvert II/III (4) approach lighting
  WITH touchdown-zone lights, at a precision end.

The CIFP half is ``cifp.read_cifp_approach_runways`` (``{designator:
class}``), joined to the apt.dat end by ``load.join_cifp`` (designator, or
the #119 threshold fallback).  The vocabulary is ``law.reference_code``.

THE DESIGN-LETTER WITNESSES of a whole runway (owner RULINGS 2026-11-07a;
:func:`design_letter`) are read here too: its ends' row-100 markings (no
precision-marked end caps the letter) and the airport's largest row-1301
ramp-start size class (:func:`airport_ramp_class`, which lifts it).
"""
from __future__ import annotations

import typing as _t

from ..law.reference_code import (PA, VISUAL, largest_ramp_class, runway_code_letter,
                                  stronger_class)

if _t.TYPE_CHECKING:  # pragma: no cover
    from ..law import Law

__all__ = ["precision_markings", "cat_ii_iii_lighting", "end_approach",
           "airport_ramp_class", "design_letter"]

#: apt.dat row-100 runway MARKINGS that witness a precision approach.
_PRECISION_MARKINGS = frozenset((3, 5))
#: apt.dat row-100 APPROACH LIGHTING of a Cat II/III system: ALSF-II (2),
#: Calvert ILS Cat II/III (4).
_CAT_II_III_LIGHTS = frozenset((2, 4))


def precision_markings(code: int) -> bool:
    """apt.dat row-100 MARKINGS that witness an approach (15n): precision
    markings only — 3 precision, 5 UK precision."""
    return int(code) in _PRECISION_MARKINGS


def cat_ii_iii_lighting(lights: int, tdz: int) -> bool:
    """A Cat II/III approach-lighting system with touchdown-zone lights
    (15m (2))."""
    return int(lights) in _CAT_II_III_LIGHTS and bool(int(tdz))


def end_approach(cifp_class: str | None, markings: int, lights: int = 0,
                 tdz: int = 0) -> tuple[str, bool]:
    """``(approach class, cat_ii_iii)`` of one end: the CIFP's class for
    it (``None`` = no procedure) strengthened to ``pa`` by precision
    markings; Cat II/III only at a precision end with the lighting."""
    cls = stronger_class(cifp_class or VISUAL,
                         PA if precision_markings(markings) else VISUAL)
    return cls, cls == PA and cat_ii_iii_lighting(lights, tdz)


def airport_ramp_class(apt: _t.Any) -> str | None:
    """The largest 1301 ramp-start ICAO size class of an apt.dat airport
    (``AptAirport.startups``); ``None`` where no start states one."""
    return largest_ramp_class(getattr(s, "width_class", "")
                              for s in getattr(apt, "startups", ()) or ())


def design_letter(law: "Law", rw: _t.Any, ramp_class: str | None) -> str:
    """THE DESIGN LETTER of an apt.dat runway ``rw`` (owner RULINGS
    2026-11-07a; ``reference_code.runway_code_letter``): its width letter,
    capped where no end carries precision markings, lifted by the
    airport's ``ramp_class``.  A runway whose markings are all 0 (none
    authored) at an airport with no 1301 class carries NO witness and reads
    its width letter uncapped."""
    marks = tuple(int(m) for m in getattr(rw, "markings", (0, 0)) or (0, 0))
    if not any(marks) and not ramp_class:
        return runway_code_letter(law, rw.width_m)
    return runway_code_letter(law, rw.width_m,
                              any(precision_markings(m) for m in marks), ramp_class)
