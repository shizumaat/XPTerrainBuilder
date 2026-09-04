"""The classification rule table (``rules.toml``) as a typed record.

Loaded with ``tomllib`` and checked strictly — an unknown key, a missing
key or a non-numeric threshold refuses, the same discipline as
``law/model.py`` (owner 2026-09-03e: data files that fail loudly).
"""
from __future__ import annotations

import dataclasses as _dc
import tomllib
import typing as _t
from pathlib import Path

__all__ = ["Rules", "RulesError", "load_rules", "DEFAULT_RULES_PATH"]

DEFAULT_RULES_PATH: Path = Path(__file__).resolve().parent / "rules.toml"


class RulesError(ValueError):
    """A rules table failed validation; the message names the key."""


@_dc.dataclass(frozen=True)
class Cells:
    snap_grid_m: float
    min_area_m2: float
    on_tol_m: float
    min_shared_m: float


@_dc.dataclass(frozen=True)
class Keyhole:
    deadend_boundary_tol_m: float
    join_tol_m: float
    max_spur_m: float


@_dc.dataclass(frozen=True)
class Corridor:
    max_width_m: float


@_dc.dataclass(frozen=True)
class Junction:
    max_area_m2: float
    route_territory_half_width_m: float
    route_territory_min_fraction: float


@_dc.dataclass(frozen=True)
class Apron:
    route_proximity_m: float
    through_join_tol_m: float
    through_min_len_m: float


@_dc.dataclass(frozen=True)
class OsmTaxiways:
    enabled: bool
    dedup_m: float
    min_len_m: float


@_dc.dataclass(frozen=True)
class Service:
    road_width_m: float
    free_max_width_m: float
    sample_step_m: float
    min_run_m: float


@_dc.dataclass(frozen=True)
class OsmRoads:
    enabled: bool
    highways: tuple[str, ...]
    dedup_m: float
    min_len_m: float


@_dc.dataclass(frozen=True)
class Lot:
    min_road_fraction: float
    narrow_road_width_m: float
    max_road_pieces_per_100m: float
    apron_name_tokens: tuple[str, ...]
    through_min_fraction: float
    parking_cover_fraction: float


@_dc.dataclass(frozen=True)
class Groundside:
    touch_tol_m: float
    requires_terminal: bool


@_dc.dataclass(frozen=True)
class TaxiSubrole:
    parallel_max_angle_deg: float
    parallel_min_overlap_frac: float
    primary_max_offset_m: float
    runway_touch_m: float


@_dc.dataclass(frozen=True)
class Leadin:
    ramp_start_trim_m: float
    max_len_m: float


@_dc.dataclass(frozen=True)
class DsfPavement:
    boundary_buffer_m: float
    overlay_fraction: float
    remainder_min_m2: float
    min_area_m2: float


@_dc.dataclass(frozen=True)
class Surfaces:
    graded_codes: tuple[int, ...]


@_dc.dataclass(frozen=True)
class Buildings:
    sources: tuple[str, ...]


@_dc.dataclass(frozen=True)
class Rules:
    """Every threshold the scorer reads."""

    cells: Cells
    keyhole: Keyhole
    corridor: Corridor
    junction: Junction
    apron: Apron
    osm_taxiways: OsmTaxiways
    service: Service
    osm_roads: OsmRoads
    lot: Lot
    groundside: Groundside
    taxi_subrole: TaxiSubrole
    leadin: Leadin
    dsf_pavement: DsfPavement
    surfaces: Surfaces
    buildings: Buildings


def _build(cls: type, data: _t.Mapping[str, _t.Any], where: str) -> _t.Any:
    fields = {f.name: f for f in _dc.fields(cls)}
    unknown = set(data) - set(fields)
    if unknown:
        raise RulesError(f"{where}: unknown key(s) {sorted(unknown)}")
    kw: dict[str, _t.Any] = {}
    for name, f in fields.items():
        if name not in data:
            raise RulesError(f"{where}.{name}: missing")
        v = data[name]
        t = f.type
        if t == "float" or t is float:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise RulesError(f"{where}.{name}: not a number ({v!r})")
            if v < 0:
                raise RulesError(f"{where}.{name}: negative")
            kw[name] = float(v)
        elif t == "int" or t is int:
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise RulesError(f"{where}.{name}: not a non-negative int ({v!r})")
            kw[name] = v
        elif t == "bool" or t is bool:
            if not isinstance(v, bool):
                raise RulesError(f"{where}.{name}: not a bool ({v!r})")
            kw[name] = v
        elif t.startswith("tuple[int") if isinstance(t, str) else False:
            if not isinstance(v, list) or not all(isinstance(i, int) for i in v):
                raise RulesError(f"{where}.{name}: not a list of ints")
            kw[name] = tuple(v)
        elif t.startswith("tuple[str") if isinstance(t, str) else False:
            if not isinstance(v, list) or not all(isinstance(i, str) for i in v):
                raise RulesError(f"{where}.{name}: not a list of strings")
            kw[name] = tuple(v)
        else:
            kw[name] = v
    return cls(**kw)


def load_rules(path: str | Path | None = None) -> Rules:
    """Read and validate the table (default: the checked-in one)."""
    p = Path(path) if path else DEFAULT_RULES_PATH
    with open(p, "rb") as fh:
        data = tomllib.load(fh)
    sections = {f.name: f.type for f in _dc.fields(Rules)}
    unknown = set(data) - set(sections)
    if unknown:
        raise RulesError(f"rules.toml: unknown section(s) {sorted(unknown)}")
    kw = {}
    types = {"cells": Cells, "keyhole": Keyhole, "corridor": Corridor,
             "junction": Junction, "apron": Apron,
             "osm_taxiways": OsmTaxiways, "service": Service,
             "osm_roads": OsmRoads, "lot": Lot, "groundside": Groundside, "taxi_subrole": TaxiSubrole,
             "leadin": Leadin, "dsf_pavement": DsfPavement,
             "surfaces": Surfaces, "buildings": Buildings}
    for name, cls in types.items():
        if name not in data:
            raise RulesError(f"rules.toml: missing section [{name}]")
        kw[name] = _build(cls, data[name], name)
    return Rules(**kw)
