"""terrain_witness.toml — the SCHEMA of THE TERRAIN WITNESS (#1359; owner
RULINGS 2026-10-26q, 26v, 26w, 26x, 26y, 26z, 27a; spec
``docs/specs/multi-source-terrain-spec.md`` §7.2): frozen dataclasses and
the table's own validation.  No numeric value appears here (the values live
in the TOML).  Imports nothing from v2.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["TerrainWitness", "check_terrain_witness"]


@_dc.dataclass(frozen=True)
class WitnessVoteLaw:
    """[vote]: the agreement factor."""

    k: float


@_dc.dataclass(frozen=True)
class WitnessSigma:
    """[sigma]: one-sigma position error per source class, metres."""

    aptdat_xy: float
    cifp_xy: float
    image_registration_m: float
    image_px: float
    lidar_xy: float
    coarse_xy: float


@_dc.dataclass(frozen=True)
class WitnessQ1:
    """[q1]: the landing-threshold position vote."""

    search_before_m: float
    search_after_frac: float
    search_after_max_m: float
    search_past_threshold_m: float
    strip_half_frac: float
    m_per_px: float
    marking_inset_m: float
    marking_sigma_m: float
    min_disagree_m: float


@_dc.dataclass(frozen=True)
class WitnessQ4:
    """[q4]: the graded-edge vote."""

    station_m: float
    band_half_m: float
    along_half_m: float
    slope_change_min_pct: float
    smooth_m: float
    agree_m: float
    edge_agree_frac: float
    max_move_m: float
    m_per_px: float


@_dc.dataclass(frozen=True)
class WitnessQ5:
    """[q5]: the open-cut / portal vote at a mapped mouth."""

    portal_depth_min_m: float
    ring_m: tuple[float, ...]
    core_m: float
    window_half_m: float
    m_per_px: float


@_dc.dataclass(frozen=True)
class WitnessImage:
    """[image]: the image method's registry key."""

    provider: str


@_dc.dataclass(frozen=True)
class TerrainWitness:
    """terrain_witness.toml."""

    vote: WitnessVoteLaw
    sigma: WitnessSigma
    q1: WitnessQ1
    q4: WitnessQ4
    q5: WitnessQ5
    image: WitnessImage


def check_terrain_witness(t: TerrainWitness, error: type[Exception]) -> None:
    """The table's own rules (raised as ``error``): positive k, sigmas,
    steps and pixel sizes; fractions in (0, 1]; a two-value ring, inner <
    outer; a named provider."""
    if not t.vote.k > 0.0:
        raise error(f"terrain_witness.vote.k {t.vote.k!r} <= 0")
    for f in _dc.fields(t.sigma):
        if not getattr(t.sigma, f.name) >= 0.0:
            raise error(f"terrain_witness.sigma.{f.name} < 0")
    for sec, names in (("q1", ("search_before_m", "search_after_max_m", "m_per_px")),
                       ("q4", ("station_m", "band_half_m", "agree_m", "m_per_px",
                               "max_move_m")),
                       ("q5", ("portal_depth_min_m", "core_m", "window_half_m",
                               "m_per_px"))):
        for n in names:
            if not getattr(getattr(t, sec), n) > 0.0:
                raise error(f"terrain_witness.{sec}.{n} must be > 0")
    for sec, n in (("q1", "search_after_frac"), ("q1", "strip_half_frac"),
                   ("q4", "edge_agree_frac")):
        v = getattr(getattr(t, sec), n)
        if not 0.0 < v <= 1.0:
            raise error(f"terrain_witness.{sec}.{n} {v!r} not in (0, 1]")
    r = t.q5.ring_m
    if len(r) != 2 or not 0.0 < r[0] < r[1]:
        raise error(f"terrain_witness.q5.ring_m {r!r}: want [inner, outer], inner < outer")
    if not t.image.provider:
        raise error("terrain_witness.image.provider is empty")
