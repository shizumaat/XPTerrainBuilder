"""A BODY IS WRITTEN IN THE DSF OF THE TILE IT STANDS ON (issue #1884).

A pack that places every object at one shared datum (LOWS: 47.79329,
12.99657, on ``+47+012``) has bodies standing on the NEIGHBOUR tile
(the east GA hangars, past lon 13.0).  ``DSFTool --text2dsf`` refuses a
row off its DSF's tile, so ``split_guard`` undid every such split and the
WHOLE placement was drawn rigidly from the datum: 82 placements (1,492
bodies) of LOWS's ``+47+012`` DSF, ``Terminal_LOWS_15``'s walls 3.8 m
over the ground they stand on.

THE RULE.  The placement's split is decided ONCE, by the build of the
tile whose DSF carries the placement (one decomposition: two builds that
each split it on their own mesh disagree about the bodies — measured on
LOWS, 258 components drawn by neither and 438 by both).  Every body whose
anchor stands on ANOTHER tile of the pack is taken out of this DSF's
split and written as a GUEST row of that tile's DSF
(``PlacementPlan.guests``): an on-ground ``OBJECT`` row at its anchor,
which X-Plane seats on THAT tile's drawn mesh — the seat any body gets
from its own ground.  A placement every body of which went is deleted
from this DSF.  The guest rows are recorded in the neighbour's pack
record under :func:`dsf.guest_key` (``LOWS@+47+012``), beside its own
``LOWS`` row, so each tile's build re-applies the other's rows and
replaces only its own (``dsf_write._sibling_plans``, #25).

THE NEIGHBOUR'S GROUND FOR THE SPLIT.  This tile's mesh ends at its edge,
so a body past it had no ground at all: the split lumped every such body
into one file (all of them "at no ground") and anchored it at its lowest
component — a body of houses kilometres apart, drawn 30 m over the hill
of one of them.  The split now reads the neighbour's ground from the
AIRPORT'S OWN DEM (:func:`airport_ground`: its base tiles and inset, the
DEM the one solve reads; :func:`with_neighbour_ground`), so bodies there
are cut and anchored as on this tile; the row then puts each on the mesh
that tile draws.  ``split_guard.on_tile`` leaves such a body for the
route (:func:`routable`) instead of seating it by an ``OBJECT_MSL`` row
at that DEM's height.

A body is NOT routed — it stays for ``split_guard``'s undo, as before —
when the tile it stands on has no DSF in the pack, or when its anchor is
within :data:`EDGE_MARGIN_DEG` of a tile edge (DSFTool could refuse the
requantised row on either side).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

from ..model.placement import PlacementPlan, Provenance, Split
from . import dsf as _dsf

__all__ = ["Tile", "route", "routable", "guest_plan", "recorded_omit",
           "write_guests", "with_neighbour_ground", "airport_ground",
           "EDGE_MARGIN_DEG"]

Tile = tuple[int, int]

#: an anchor this close to a tile edge is never routed (deg, ~1 m) — the
#: margin ``split_guard`` keeps an anchor inside its tile by
EDGE_MARGIN_DEG = 1e-5


def _tile_of(lat: float, lon: float) -> Tile | None:
    """The ``(lat, lon)`` tile a point stands on, ``None`` within
    :data:`EDGE_MARGIN_DEG` of any of its edges."""
    la, lo = math.floor(lat), math.floor(lon)
    if min(lat - la, la + 1 - lat, lon - lo, lo + 1 - lon) < EDGE_MARGIN_DEG:
        return None
    return int(la), int(lo)


def route(plan: PlacementPlan, here: Tile,
          has_dsf: _t.Callable[[Tile], bool]
          ) -> tuple[PlacementPlan, dict[Tile, tuple[Split, ...]]]:
    """``(plan for this tile's DSF, {tile: guest splits})`` — the module
    rule.  ``has_dsf(tile)`` says whether the pack has a DSF there."""
    here = (int(here[0]), int(here[1]))
    splits: list[Split] = []
    guests: dict[Tile, list[Split]] = {}
    moved = 0
    for sp in plan.splits:
        stay: list = []
        away: dict[Tile, list] = {}
        for b in sp.bodies:
            t = _tile_of(b.anchor.lat, b.anchor.lon)
            if t is None or t == here or not has_dsf(t):
                stay.append(b)
            else:
                away.setdefault(t, []).append(b)
        for t, bodies in away.items():
            guests.setdefault(t, []).append(_dc.replace(sp, bodies=tuple(bodies)))
            moved += len(bodies)
        splits.append(_dc.replace(sp, bodies=tuple(stay)) if away else sp)
    if not guests:
        return plan, {}
    counts = {**dict(plan.provenance.counts),
              "bodies_routed_to_neighbour": moved,
              "placements_routed_whole": sum(1 for s in splits if not s.bodies)}
    plan = _dc.replace(plan, splits=tuple(splits), provenance=_dc.replace(
        plan.provenance, counts=counts))
    return plan, {t: tuple(g) for t, g in sorted(guests.items())}


def routable(pack_root: str, here: "Tile | None"
             ) -> "_t.Callable[[float, float], bool] | None":
    """``(lat, lon) -> bool``: does another DSF of the pack carry a body
    standing there (``split_guard.on_tile``'s ``routable``)?  ``None``
    without a tile (a plan written for no tile is never routed)."""
    if here is None:
        return None
    here = (int(here[0]), int(here[1]))
    has = _pack_has_dsf(pack_root)

    def pred(lat: float, lon: float) -> bool:
        t = _tile_of(lat, lon)
        return t is not None and t != here and has(t)
    return pred


def airport_ground(icao: str, here: Tile, elevation_root: str,
                   feather_m: float = 60.0
                   ) -> _t.Callable[[_t.Any, _t.Any], _t.Any]:
    """``(lats, lons) -> z array`` (NaN where nothing covers) over the
    airport's own DEM (``dem.load_dem``: the base tiles, loaded per 1°
    cell, and its inset).  Loaded on the first point asked — a single-tile
    airport never asks — and all-NaN when its base tile is missing."""
    import numpy as _np
    got: list = []

    def z(lats, lons):
        if not got:
            from ..model.frame import Frame
            from . import dem as _dem
            try:
                frame = Frame(str(icao), (here[0] + 0.5, here[1] + 0.5),
                              identity_dp=9)
                got.append(_dem.load_dem(frame, elevation_root, str(icao),
                                         feather_m).z_many_ll)
            except (OSError, ValueError):
                got.append(lambda la, _lo: _np.full(_np.shape(la), _np.nan))
        return got[0](lats, lons)
    return z


def with_neighbour_ground(mesh_sample: _t.Callable, here: Tile,
                          ground: _t.Callable | None) -> _t.Callable:
    """``mesh_sample`` (``(lat, lon) -> (z, water) | None``, with or
    without ``.many``) answering, OFF this tile only, from ``ground`` —
    the module doc's neighbour ground.  ``ground`` ``None`` changes
    nothing."""
    if ground is None:
        return mesh_sample
    import numpy as _np
    here = (int(here[0]), int(here[1]))

    def off(lat: float, lon: float) -> bool:
        return (math.floor(lat), math.floor(lon)) != here

    def from_ground(lats, lons) -> list:
        zs = ground(_np.asarray(lats, dtype=float), _np.asarray(lons, dtype=float))
        return [None if not _np.isfinite(z) else (float(z), False) for z in zs]

    def sample(lat: float, lon: float):
        if off(lat, lon):
            return from_ground([lat], [lon])[0]
        return mesh_sample(lat, lon)

    batch = getattr(mesh_sample, "many", None)

    def many(lats, lons) -> list:
        lats, lons = list(lats), list(lons)
        out: list = [None] * len(lats)
        on = [i for i in range(len(lats)) if not off(lats[i], lons[i])]
        away = [i for i in range(len(lats)) if off(lats[i], lons[i])]
        if on:
            got = (batch([lats[i] for i in on], [lons[i] for i in on])
                   if batch is not None
                   else [mesh_sample(lats[i], lons[i]) for i in on])
            for i, s in zip(on, got, strict=True):
                out[i] = s
        if away:
            for i, s in zip(away, from_ground([lats[i] for i in away],
                                              [lons[i] for i in away]),
                            strict=True):
                out[i] = s
        return out
    sample.many = many
    for attr in ("bounds", "mesh_path"):
        if hasattr(mesh_sample, attr):
            setattr(sample, attr, getattr(mesh_sample, attr))
    return sample


def guest_plan(plan: PlacementPlan, here: Tile, there: Tile,
               guests: _t.Sequence[Split]) -> PlacementPlan:
    """The write of ``guests`` into ``there``'s DSF of the same pack: no
    edit of its own rows, recorded under ``dsf.guest_key(icao, here)``."""
    dsf_path = _dsf.dsf_path_in_pack(plan.pack_root, there[0], there[1])
    return PlacementPlan(
        icao=_dsf.guest_key(plan.icao, here), pack_name=plan.pack_name,
        pack_root=plan.pack_root, dsf_path=dsf_path,
        dsf_backup_path=dsf_path + ".anchor_bak",
        provenance=Provenance("", plan.provenance.engine_version,
                              plan.provenance.law_digest, {}),
        guests=tuple(guests))


def _pack_has_dsf(pack_root: str) -> _t.Callable[[Tile], bool]:
    """``has_dsf`` for :func:`route`: the pack has its own DSF there."""
    return lambda t: os.path.isfile(_dsf.dsf_path_in_pack(pack_root, t[0], t[1]))


def recorded_omit(dsf_path: str, pack_root: str) -> tuple:
    """The missing art the user accepted to build ``dsf_path`` without, as
    its record holds it (``pack_art.recorded``): a guest write keeps the
    neighbour's decision, never makes one."""
    from . import backup_state as _bs
    from . import pack_art as _pa
    from .file_hash import sha256_file
    backup = dsf_path + ".anchor_bak"
    if not os.path.isfile(backup):
        return ()
    entry = _bs.dsf_entry(_bs.read_record(dsf_path), os.path.basename(dsf_path))
    return tuple(_pa.recorded(entry, sha256_file(backup), pack_root))


def write_guests(plan: PlacementPlan, files: _t.Sequence, here: Tile,
                 apply: _t.Callable[[PlacementPlan, list], _t.Any],
                 say: _t.Callable[[str], None] = lambda _s: None
                 ) -> tuple[PlacementPlan, list, list]:
    """Route ``plan`` (:func:`route`) and write each neighbour's guest rows
    with ``apply(guest plan, its body files)`` — ``placement_write.
    apply_plan`` with the build's own keywords.  Returns ``(plan for this
    tile's DSF, its files, the guest files written)``.

    The guests are written FIRST and this tile's DSF after, by the caller:
    a neighbour whose write fails keeps nothing, and its bodies go back to
    this tile's plan for ``split_guard``'s undo (written whole, as before
    #1884).  The caller writes the guest files once more after its own
    write: a body that was this tile's last build and is a guest now has
    the name the own write's restore removes."""
    has = _pack_has_dsf(plan.pack_root)
    routed, guests = route(plan, here, has)
    if not guests:
        return plan, list(files), []
    by_res = {f.resource.replace("\\", "/"): f for f in files}
    failed: set[Tile] = set()
    written: list = []
    for there, splits in guests.items():
        gp = guest_plan(plan, here, there, splits)
        gfiles = [by_res[r] for r in gp.new_resources() if r in by_res]
        try:
            apply(gp, gfiles)
        except Exception as exc:                 # the bodies stay here
            failed.add(there)
            say(f"{len(gp.new_resources())} body(ies) standing on "
                f"{_dsf.on_tile('', there)[1:]} could not be written in its "
                f"DSF ({exc}); their placements are written whole")
            continue
        written += gfiles
        say(f"{sum(len(s.bodies) for s in splits)} body(ies) of "
            f"{len(splits)} placement(s) stand on "
            f"{_dsf.on_tile('', there)[1:]}: written in its DSF")
    if failed:
        routed, guests = route(plan, here, lambda t: t not in failed and has(t))
    gone = {r for t, sp in guests.items() if t not in failed
            for r in guest_plan(plan, here, t, sp).new_resources()}
    own = [f for f in files if f.resource.replace("\\", "/") not in gone]
    return routed, own, written
