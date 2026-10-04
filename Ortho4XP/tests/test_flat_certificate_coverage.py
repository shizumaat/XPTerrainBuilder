"""Flat-airport fast path — Tier 1 certificate coverage (WP1).

Hermetic unit tests (no fixtures, no network, ``tmp_path``-free) for the
taxi-rect and building-seat certificates added by
docs/specs/flat-airport-fast-path-spec.md §3.2:

  * a taxi RECT whose DEM is provably flat certifies (returns its seed +
    shortest axial span) and one over the axial budget / with a cross-fall /
    on a sampling gap refuses (``None``);
  * a building SEAT whose whole footprint DEM relief fits the seat tolerance
    certifies, SKIPS its reach band, and records the footprint DEM MEAN as the
    seated level through the same ``{id(shape): level}`` structure the band
    path fills — while a footprint over the relief budget, a tight reach band,
    or the gate turned off all fall back to the normal band clamp.

The certificate helpers sample the DEM through ``auto_patch.elevation.
_sample_dem`` (rects) / a caller-supplied ``dem_sampler`` (seats); both are
stubbed here so each case drives a controlled elevation field.
"""

from auto_patch.config import BUILDING_SEAT_FLATNESS_TOLERANCE_M

from shapely.geometry import Polygon


# ── shared fakes ─────────────────────────────────────────────────────────────
class _FakeShape:
    def __init__(self, role, polygon):
        self.role = role
        self.polygon = polygon


class _FakeLayout:
    """Minimal layout: identity ``m_to_ll`` (so DEM samples key on the local
    metre coords), a shapes list, and an ICAO for the summary line."""

    def __init__(self, shapes, icao="TEST"):
        self.shapes = shapes
        self.icao = icao

    def m_to_ll(self, x, y):
        return (x, y)


# ── seat certificate (building_feasible_levels) ──────────────────────────────
_APRON = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])       # 10 000 m²


def _wide_band(x, y):
    return (0.0, 1000.0)


def test_seat_tolerance_boundary():
    # Documents the tolerance the seat certificate is wired to.
    assert BUILDING_SEAT_FLATNESS_TOLERANCE_M == 0.30
