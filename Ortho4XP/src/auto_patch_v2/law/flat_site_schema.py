"""flat_site.toml — the SCHEMA of the flat-site datum law (RULINGS
2026-09-05k-2; spec ``docs/specs/auto-patch-v2/flat-site-datum-spec.md``
§2), split from ``model.py`` by the 1,000-line file law and re-exported
there.  Frozen dataclasses + the table's own validation; no numeric value
appears here (the values live in the TOML).  Imports nothing from v2.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["ReliefFloor", "FlatDetector", "FlatDatum", "Declared", "FlatSite",
           "FLAT_SOURCES", "DECLARED_SOURCES", "check_flat_site"]


#: The datum's measured sources, and the declared register's (``metres``
#: = the declared number IS the datum).
FLAT_SOURCES = ("cifp", "pack_seats")
DECLARED_SOURCES = FLAT_SOURCES + ("metres",)


@_dc.dataclass(frozen=True)
class ReliefFloor:
    """S2's p95−p5 noise floor by DEM source class: ``coarse`` (≥ 1
    arcsec) and ``fine`` (sub-10 m); a lidar-class pixel short-circuits
    (``FlatDetector.lidar_credible_max_m``)."""

    coarse: float
    fine: float


@_dc.dataclass(frozen=True)
class FlatDetector:
    """The flat-site detector's constants (v1 flat-site-detector-spec v3,
    ``config.FLAT_SITE_*`` by name; spec §2)."""

    threshold_spread_max_m: float
    relief_floor_m: ReliefFloor
    fine_source_max_m: float
    lidar_credible_max_m: float
    plane_slope_max: float
    sea_band_max_m: float
    sea_band_min_z0_m: float
    dsm_trim_over_median_m: float
    seat_consensus_max_m: float
    seat_spread_max_m: float
    below_grade_base_y_m: float
    margin_m: float


@_dc.dataclass(frozen=True)
class FlatDatum:
    """How the datum is priced: its ``source`` (``cifp`` | ``pack_seats``),
    the ``Weights.preference`` group it rides in, that group's weight,
    and whether the runway family keeps its CIFP pins (08-25)."""

    source: str
    preference: str
    runway_pins_hard: bool


@_dc.dataclass(frozen=True)
class Declared:
    """One owner-declared flat site: ``source`` ``cifp`` | ``pack_seats``
    | ``metres`` (``z0`` IS the datum, required then)."""

    source: str
    z0: float | None = None


@_dc.dataclass(frozen=True)
class FlatSite:
    """flat_site.toml."""

    detector: FlatDetector
    datum: FlatDatum
    declared: _t.Mapping[str, Declared] = _dc.field(default_factory=dict)



def check_flat_site(fs: FlatSite, error: type[Exception]) -> None:
    """flat_site.toml's own rules (raised as ``error``, the loader's
    ``LawError``): the datum source is measured, the preference group is one prefix (no ``:``), every declared key is a
    four-character ICAO identifier, a declared source is known and a
    ``metres`` declaration carries its number."""
    if fs.datum.source not in FLAT_SOURCES:
        raise error(f"flat_site.datum.source {fs.datum.source!r} not in "
                    f"{FLAT_SOURCES}")
    g = fs.datum.preference
    if not g or ":" in g or not g.replace("_", "").isalnum():
        raise error(f"flat_site.datum.preference {g!r}: one identifier, "
                    "no ':' (the Weights.preference prefix)")
    for icao, d in fs.declared.items():
        if len(icao) != 4 or not icao.isalnum() or icao != icao.upper():
            raise error(f"flat_site.declared.{icao}: not a 4-character "
                           "upper-case ICAO identifier")
        if d.source not in DECLARED_SOURCES:
            raise error(f"flat_site.declared.{icao}.source {d.source!r} "
                           f"not in {DECLARED_SOURCES}")
        if d.source == "metres" and d.z0 is None:
            raise error(f"flat_site.declared.{icao}: source = \"metres\" "
                           "needs z0 (the number IS the datum)")


