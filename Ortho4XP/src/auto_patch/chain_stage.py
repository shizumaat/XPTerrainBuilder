"""THE OVERLAY PACKS' DECK CHAINS in the object stage (#2144 P1;
``auto_patch_v2.airport.deck_chain``; owner 2026-11-17T19:08Z "any pack
that draws object less than 1km from the airport should be checked and
modified if needed").

WHERE.  Inside ``object_stage._place_objects``, for the airport pack's own
plan only, after the airport pack itself was written: every pack beside it
on the tile that ships objects of its own (``pack_local.tile_candidates``,
``ships_objects``) is read within ``deck_chain.ChainLaw.scope_m`` (and,
for a chain reaching into it, ``reach_m`` beyond) of the airport's
boundary (``sibling_riders.airport_region``); its deck chains are
seated on the surface the airport's own bodies were seated on and written
as ``OBJECT_MSL`` rows (``placement_write.apply_plan``, the pristine DSF
kept as ``.anchor_bak``).  With a pack copy armed (``--pack-copy``) the
write goes into the copy's clone of that pack, never the install.

Nothing here raises into the build: a failed pack is one log line and the
next pack goes on.
"""
from __future__ import annotations

import math
import os
import traceback
import typing as _t

from .sibling_stage import _say

__all__ = ["CHAIN_KEY", "plans", "write"]

#: the placement plan's key beside the patch, per airport and pack
CHAIN_KEY = "{icao}~chain{k}"


def _scope(region: _t.Any, scope_m: float) -> _t.Callable[[float, float], bool]:
    """``(lat, lon) -> within scope_m of the region``."""
    from shapely.geometry import Point
    from shapely.ops import transform
    from shapely.prepared import prep
    c = region.centroid
    la0, lo0 = float(c.y), float(c.x)
    ml, mo = 111132.0, 111320.0 * math.cos(math.radians(la0))
    near = prep(transform(lambda x, y, *_: ((x - lo0) * mo, (y - la0) * ml), region)
                .buffer(scope_m))
    return lambda la, lo: near.contains(Point((lo - lo0) * mo, (la - la0) * ml))


def _placed_in(dump: _t.Any, root: str, inside: _t.Callable[[float, float], bool]) -> list:
    """The pack's on-ground ``OBJECT`` rows of its own ``.obj`` files inside
    the scope, as ``deck_chain.Placed`` (a deck piece read where it is one)."""
    from auto_patch_v2.airport import deck_chain as _dc
    from auto_patch_v2.model.placement import KIND_ON_GROUND
    rows = list(getattr(dump, "placements", ()) or ())
    keep = [(i, p) for i, p in enumerate(rows)
            if p.kind == KIND_ON_GROUND and p.def_path.lower().endswith(".obj")
            and inside(float(p.lat), float(p.lon))]
    if not keep:
        return []
    la0, lo0 = float(keep[0][1].lat), float(keep[0][1].lon)
    ml, mo = 111132.0, 111320.0 * math.cos(math.radians(la0))
    out = []
    for i, p in keep:
        path = os.path.join(root, *p.def_path.split("/"))
        if not os.path.isfile(path):
            continue                      # a library resource: never seated here
        out.append(_dc.Placed(i, p.def_path, float(p.lat), float(p.lon),
                              float(p.heading_deg),
                              ((float(p.lon) - lo0) * mo, (float(p.lat) - la0) * ml),
                              _dc.piece_of(path)))
    return out


def plans(plan: _t.Any, surface_over: _t.Callable, tile: _t.Any,
          installed_root: str = "") -> list:
    """``[PlacementPlan]`` of the overlay packs whose deck chains near the
    airport ``plan`` are seated (module doc).  ``surface_over(box)``: the
    airport's placement surface widened to ``(lon0, lat0, lon1, lat1)``;
    ``installed_root`` the airport pack where it is INSTALLED (its packs
    beside it are the ones scanned -- with a pack copy armed ``plan``'s
    root is the copy, which has no Custom Scenery beside it)."""
    main_root = installed_root or plan.pack_root
    from auto_patch_v2.airport import deck_chain as _dc
    from auto_patch_v2.airport import sibling_riders as _sr
    from auto_patch_v2.airport.pack_local import ships_objects, tile_candidates

    from .sibling_stage import _dump
    law = _dc.ChainLaw()
    try:
        region = _sr.airport_region(main_root, plan.icao)
        if region is None:
            return []
        inside = _scope(region, law.scope_m)
        near = _scope(region, law.scope_m + law.reach_m)
        roots = [r for r in tile_candidates(main_root, tile.lat, tile.lon, plan.icao)
                 if ships_objects(r)]
    except Exception as exc:
        _say(f"  [v2 placement] {plan.icao}: overlay packs not read ({exc})")
        _say(traceback.format_exc(), 2)
        return []
    out = []
    for root in roots:
        sp = _plan_one(plan, root, _dump(plan.icao, root, tile, make=True),
                       (inside, near), surface_over, tile, law)
        if sp is not None:
            out.append(sp)
    return out


def _plan_one(plan, root, dump, inside, surface_over, tile, law):
    """One overlay pack's chain plan, or ``None`` when it seats nothing."""
    from auto_patch_v2.airport import deck_chain as _dc
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.model.placement import MslSeat, PlacementPlan, Provenance

    from . import pack_copy as _copy
    name = os.path.basename(os.path.normpath(root))
    if dump is None:
        return None
    try:
        inside, near = inside
        placed = _placed_in(dump, root, near)
        if not any(p.piece is not None for p in placed):
            return None
        surface = surface_over((min(p.lon for p in placed), min(p.lat for p in placed),
                                max(p.lon for p in placed), max(p.lat for p in placed)))

        def ground(la: float, lo: float) -> "float | None":
            s = surface(la, lo)
            return None if s is None else float(s)
        counts: dict[str, int] = {}
        zero, rep = _dc.chain_seats(placed, ground, law, counts,
                                    admit=lambda p: inside(p.lat, p.lon))
        if not zero:
            return None
        seats = tuple(MslSeat(placed[k].index, placed[k].resource, placed[k].lon,
                              placed[k].lat, placed[k].heading, float(z), _dc.WHY)
                      for k, z in sorted(zero.items()))
        target = _copy.ensure_copy(root) or root
        dsf_path = _dsf.dsf_path_in_pack(target, tile.lat, tile.lon)
        _say(f"  [v2 placement] {plan.icao}: overlay {name}: {counts.get('chain_pieces', 0)} "
             f"deck piece(s) in {counts.get('chain_chains', 0)} chain(s) over "
             f"{counts.get('chain_joints', 0)} joint(s), {counts.get('chain_coanchored', 0)} "
             f"co-anchored, {counts.get('chain_cut_joints', 0)} joint(s) cut; "
             f"{len(seats)} row(s) seated", 0)
        for u, v, d in rep["cut"][:10]:
            _say(f"  [v2 placement] {plan.icao}: overlay {name}: cycle joint "
                 f"{placed[u].index}-{placed[v].index} cut (closes by {d:+.2f} m)", 1)
        return PlacementPlan(
            icao=plan.icao, pack_name=name, pack_root=target, dsf_path=dsf_path,
            dsf_backup_path=dsf_path + ".anchor_bak",
            provenance=Provenance("", plan.provenance.engine_version,
                                  plan.provenance.law_digest, counts),
            conversions=(), splits=(), kept=(), msl_seats=seats)
    except Exception as exc:
        _say(f"  [v2 placement] {plan.icao}: overlay {name} failed ({exc})")
        _say(traceback.format_exc(), 2)
        return None


def write(chains: _t.Sequence, patch_dir: str, tool: str, *,
          engine_version: str = "", law_digest: str = "") -> int:
    """Write every chain plan (``placement_write.apply_plan``); the number
    written."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import placement_write as _pw
    from auto_patch_v2.airport.backup_state import BackupUnproven

    from . import dsf_reader as _DSFR
    from . import pack_copy as _copy
    done = 0
    for k, sp in enumerate(chains, start=1):
        cache = _dsf.mod_cache_dir(FNAMES.airport_mod_cache_root(), sp.pack_name)
        try:
            res = _pw.apply_plan(
                sp, (), tool, patch_dir=patch_dir,
                allow_live_install=_copy.write_guard(sp.pack_root),
                refresh_dump=lambda p, _c=cache: _DSFR.ensure_dsf_text_path(p, _c),
                engine_version=engine_version, law_digest=law_digest,
                plan_key=CHAIN_KEY.format(icao=sp.icao, k=k))
        except BackupUnproven as exc:
            _say(f'  [v2 placement] PACK NOT TOUCHED: "{sp.pack_name}" — {exc}', 0)
            continue
        except Exception as exc:
            _say(f"  [v2 placement] {sp.icao}: overlay {sp.pack_name} not "
                 f"written ({exc})", 0)
            _say(traceback.format_exc(), 2)
            continue
        done += 1
        if res.dsf is not None:
            for note in res.dsf.notes:
                _say(f'  [v2 placement] PACK UPDATED: "{sp.pack_name}" — {note}', 0)
    return done
