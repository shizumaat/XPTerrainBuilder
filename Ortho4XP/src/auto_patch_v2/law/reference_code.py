"""THE RUNWAY WITNESSES — the aerodrome reference code of a runway and
the approach class of each of its ends (spec
``docs/specs/regulation-conformance-20261015.md`` §3; owner RULINGS
2026-10-15k/l/m/n).

ONE classifier for the code NUMBER (Annex 14 Table 1-1, runway length as
the reference-field-length proxy) and ONE for the code LETTER (runway width
as the wingspan / AAC-ADG proxy), both read from ``rulesets.toml``
``[common.reference_code]``.  The loader stamps them on ``Runway`` once;
everything else — the generators, verify, the census (from the sidecar) —
reads the stamped value.

The approach-class VOCABULARY lives here too, with the one end filter the
RAOA reads (:func:`raoa_applies`, Annex 14 §3.8.1).  The witness that
assigns an end its class is ``airport/approach.py``.  Values live in the
TOML; no numeric value appears here.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .model_types import CodeTable

if _t.TYPE_CHECKING:  # pragma: no cover
    from .model import Law

__all__ = ["ReferenceCode", "APPROACH_CLASSES", "VISUAL", "NPA", "APV", "PA",
           "runway_code_number", "runway_code_letter", "taxi_code_letter", "is_instrument",
           "is_precision", "stronger_class", "raoa_class", "raoa_applies",
           "NON_INSTRUMENT", "INSTRUMENT", "PRECISION", "status_of_classes",
           "runway_status", "status_by_ref", "ref_status"]

#: An end's APPROACH CLASS, weakest first (spec §3.4; RULINGS 15m (2), 15n):
#: no approach, non-precision, approach with vertical guidance (CIFP
#: RNAV/RNP), precision (ILS/GLS/MLS, or apt.dat precision markings).
VISUAL, NPA, APV, PA = "visual", "npa", "apv", "pa"
APPROACH_CLASSES: tuple[str, ...] = (VISUAL, NPA, APV, PA)
#: The classes the RAOA binds before (Annex 14 §3.8.1: precision approach
#: runways only — audit row 8).
_RAOA_CLASSES = frozenset((PA,))
#: A RUNWAY's INSTRUMENT STATUS, the key of every law table the standard
#: states by status (#811; :func:`status_of_classes`).  ``True`` / ``False``
#: read as 1 / 0, the instrument flag before the precision step.
NON_INSTRUMENT, INSTRUMENT, PRECISION = 0, 1, 2


@_dc.dataclass(frozen=True)
class ReferenceCode:
    """``[common.reference_code]``: the code NUMBER by the runway length it
    starts at (``by_code``), the code LETTER by the widest runway it
    covers (``by_letter``, the unit tolerance included), and the letter of
    a runway wider than every bound."""

    number_min_length_m: CodeTable
    letter_max_width_m: CodeTable
    widest_letter: str
    #: the unit tolerance a measured TAXIWAY width is read with against its
    #: authority's ``taxi.width_m`` table (:func:`taxi_code_letter`) — the
    #: same 0.5 m the runway bounds above carry
    taxi_width_tolerance_m: float = 0.5


def runway_code_number(law: "Law", length_m: float) -> int:
    """The ICAO code NUMBER of a runway ``length_m`` long: the highest code
    whose minimum length it reaches (code 1 below every bound)."""
    table = law.tables.common.reference_code.number_min_length_m.by_code or {}
    code = 1
    for c, lim in sorted(table.items(), key=lambda kv: kv[1]):
        if float(length_m) >= float(lim):
            code = int(c)
    return code


def _first_covering(bounds: _t.Mapping[str, float], width_m: float,
                    tolerance_m: float, widest: str) -> str:
    """THE LETTER-BY-WIDTH READING both classifiers share: the first letter
    (narrowest bound, then alphabetical) whose bound plus ``tolerance_m``
    covers ``width_m``; ``widest`` above every bound."""
    for letter, lim in sorted(bounds.items(), key=lambda kv: (float(kv[1]), kv[0])):
        if float(width_m or 0.0) <= float(lim) + tolerance_m:
            return str(letter)
    return str(widest)


def runway_code_letter(law: "Law", width_m: float) -> str:
    """The code LETTER of a runway ``width_m`` wide: the first letter whose
    bound covers it, the widest letter above every bound."""
    rc = law.tables.common.reference_code
    return _first_covering(rc.letter_max_width_m.by_letter or {}, width_m, 0.0,
                           rc.widest_letter)


def taxi_code_letter(law: "Law", width_m: float) -> str | None:
    """The code LETTER of a TAXIWAY pavement ``width_m`` wide, where the
    apt.dat 1202 route states no width class (master 2026-10-16, regL3
    round 2: a witness, not a default): the first letter whose taxiway
    width under the airport's authority (``rulesets.<authority>.taxi
    .width_m`` — Annex 14 §3.9.3, AC 150/5300-13B by ADG through the letter
    proxy) plus ``taxi_width_tolerance_m`` covers it; the widest letter
    above every bound.  ``None`` where the authority states no width."""
    tbl = law.ruleset.taxi.width_m
    bounds = (tbl.by_letter or {}) if tbl is not None else {}
    if not bounds:
        return None
    widest = max(bounds.items(), key=lambda kv: (float(kv[1]), kv[0]))[0]
    tol = float(law.tables.common.reference_code.taxi_width_tolerance_m)
    return _first_covering(bounds, width_m, tol, widest)


def _rank(cls: str | None) -> int:
    try:
        return APPROACH_CLASSES.index(str(cls or VISUAL))
    except ValueError:
        return 0


def stronger_class(a: str | None, b: str | None) -> str:
    """The stronger of two approach classes (an unknown name reads visual)."""
    return APPROACH_CLASSES[max(_rank(a), _rank(b))]


def is_instrument(cls: str | None) -> bool:
    """An end with any approach (RULINGS 2026-10-15n)."""
    return _rank(cls) > 0


def is_precision(cls: str | None) -> bool:
    """A precision approach end (RULINGS 2026-10-15m (2))."""
    return str(cls) == PA


def status_of_classes(classes: _t.Iterable[str | None], instrument: bool = False) -> int:
    """THE RUNWAY'S INSTRUMENT STATUS from its ends' approach classes
    (#811; owner RULINGS 2026-10-15k): :data:`PRECISION` where an end is
    precision, :data:`INSTRUMENT` where an end has any approach (or the
    caller's ``instrument`` flag says so), else :data:`NON_INSTRUMENT`.
    The law tables stated by status read it (``tables._by_status``); a
    ``bool`` instrument flag is the same number (``True`` = 1)."""
    status = INSTRUMENT if instrument else NON_INSTRUMENT
    for c in classes:
        if is_precision(c):
            return PRECISION
        if is_instrument(c):
            status = INSTRUMENT
    return status


def runway_status(rw) -> int:
    """:func:`status_of_classes` of a ``model.airport.Runway`` — its ends'
    ``approach`` and its stamped ``instrument`` flag."""
    return status_of_classes((getattr(e, "approach", None)
                              for e in getattr(rw, "ends", ()) or ()),
                             bool(getattr(rw, "instrument", False)))


def status_by_ref(runways) -> dict[str, int]:
    """``{runway id: status}`` for a reader that meets a runway by its ref
    (a cell, a face); read it through :func:`ref_status`."""
    return {str(rw.id): runway_status(rw) for rw in runways or ()}


def ref_status(status_of: _t.Mapping[str, int] | None, ref: str | None) -> int:
    """The status of the runway ``ref`` names; a crossing piece (``a+b``)
    is pavement of both runways and reads the stronger.  A ref the map
    does not list reads non-instrument."""
    if not status_of or ref is None:
        return NON_INSTRUMENT
    return max((int(status_of.get(r, NON_INSTRUMENT)) for r in str(ref).split("+")),
               default=NON_INSTRUMENT)


def raoa_class(cls: str | None) -> bool:
    """THE RAOA END FILTER (Annex 14 §3.8.1): the class binds the radio
    altimeter operating area before its threshold.  The engine reads it
    through :func:`raoa_applies`, the census through ``grade_law.
    raoa_applies`` — one predicate."""
    return str(cls) in _RAOA_CLASSES


def raoa_applies(law: "Law", cls: str | None) -> bool:
    """The RAOA binds before an end of class ``cls`` under ``law``: the
    ruleset states one (ICAO) and the end is precision."""
    ra = law.ruleset.raoa
    return bool(ra is not None and ra.length_m and ra.half_width_m
                and raoa_class(cls))
