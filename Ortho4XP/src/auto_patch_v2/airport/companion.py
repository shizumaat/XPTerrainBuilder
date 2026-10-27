"""OBJECTS-ONLY COMPANION PACKS (owner RULINGS 2026-10-28p (5), Q244 a;
#1301 / #1279).

An airport can ship in two packs: the one carrying the apt.dat (the pack
``pack.select_pack`` serves) and a second that carries only objects -- at
LFPG ``1_LFPG_PARIS_T1_2_3_XP12`` places the T1/T2/T3 terminals, with no
apt.dat of its own.  The engine re-seated only the first, so the second's
plain ``OBJECT`` rows draped y = 0 at an anchor 360 m from the buildings
and 45 of its 149 objects floated more than 1 m.  The ruling: such a
COMPANION is re-seated together with the main pack; OVERLAY packs (AEP
Overlays, simHeaven, Ortho4XP overlays, forests) are left alone.

THE WITNESS IS THE PACK'S OWN CONTENT, never its name.  A companion is a
Custom Scenery pack that

* is not the serving pack and is enabled in ``scenery_packs.ini``;
* ships NO apt.dat (a pack with one is an airport of its own);
* has a DSF for the airport's tile whose ``OBJECT`` rows place at least
  one PACK-LOCAL object -- a file the pack itself ships, resolved inside
  its own folder -- INSIDE the airport's boundary (apt.dat row 130, else
  the runways and pavements of the airport's own block).

An overlay places library objects (``lib/...`` and other virtual paths
another pack exports): measured on the owner's install at LFPG, AEP
Overlays 0 pack-local of 81 object definitions, every simHeaven layer 0,
yOrtho4XP_Overlays and Global_Forests_v2 no object rows at all; the
companion 225 of 225.  Only the admitted rows are adopted -- a library row
of a companion stays as authored, as the main pack's partition already
skips stock and outside-pack resources.

WHAT ADOPTION IS HERE: the admitted rows are read and partitioned by the
main pack's own machinery (``basin_witness.read_objects``,
``pack_partition.partition_pack``, ``rebake_plan.plan``) against the
airport's frame and DEM, and the plan is written beside the main plan
(``o4_v2_rebake_<ICAO>~<k>.json``).  The object stage places it like any
plan: split, seat on the built mesh, write the companion's own DSF with
its ``.anchor_bak``.  The patch mints no pads for the companion's objects
(their ground is what the main layout grades there), and the main pack's
planar facts (basins, plates, below-grade regions) are not carried over:
their ids name the main pack's rows.
"""
from __future__ import annotations

import dataclasses as _dc
import glob
import os
import typing as _t

from ..model.airport import DsfObject, SceneryPack
from . import dsf as _dsf
from .pack import authored_source

__all__ = ["COMPANION_PLAN", "Companion", "dump_candidates", "find", "admitted",
           "plans", "place"]

#: ``<patch dir>/o4_v2_rebake_<ICAO>~<k>.json`` -- the object stage's plan
#: glob reads it beside the main plan (``object_stage._PLAN_NAME_RE``).
COMPANION_PLAN = "o4_v2_rebake_{icao}~{k}.json"


@_dc.dataclass(frozen=True)
class Companion:
    """One adopted pack: its folder, its tile DSF's PRISTINE text dump and
    the rows admitted from it (``(row index, placement)``)."""

    name: str
    root: str
    dump_path: str
    rows: tuple[tuple[int, _t.Any], ...]


def _inside(path: str, root: str) -> bool:
    real = os.path.realpath(root)
    try:
        return os.path.commonpath([os.path.realpath(path), real]) == real
    except ValueError:
        return False


def _candidates(main_root: str, lat: int, lon: int) -> list[str]:
    """The Custom Scenery packs beside ``main_root`` that could be a
    companion: enabled, not the serving pack, no apt.dat, a DSF for the
    tile.  In folder-name order."""
    import O4_Scenery_Packs as _SP
    scenery = os.path.dirname(os.path.normpath(main_root))
    if os.path.basename(scenery) != "Custom Scenery" or not os.path.isdir(scenery):
        return []
    main = os.path.realpath(main_root)
    out = []
    for name in sorted(os.listdir(scenery)):
        root = os.path.join(scenery, name)
        if not os.path.isdir(root) or os.path.realpath(root) == main:
            continue
        if os.path.isfile(os.path.join(root, "Earth nav data", "apt.dat")):
            continue
        if not os.path.isfile(_dsf.dsf_path_in_pack(root, lat, lon)):
            continue
        if _SP.pack_enabled(root):
            out.append(root)
    return out


def _ships_objects(root: str) -> bool:
    """Does the pack ship any ``.obj`` of its own (outside its DSFs)?  The
    cheap gate before a DSF is dumped: an overlay that places only
    library objects ships none and is never dumped."""
    for here, dirs, files in os.walk(root):
        if os.path.basename(here) == "Earth nav data":
            dirs[:] = []
            continue
        if any(f.lower().endswith(".obj") for f in files):
            return True
    return False


def dump_candidates(main_root: str, lat: int, lon: int) -> list[str]:
    """The candidate packs (``_candidates``) that ship objects of their
    own: the packs whose tile DSF the pre-build refresh dumps
    (``engine_v2.fresh_pack_dump``) so :func:`find` can read them."""
    return [r for r in _candidates(main_root, lat, lon) if _ships_objects(r)]


def admitted(dump, root: str, inside: _t.Callable[[float, float], bool]
             ) -> list[tuple[int, _t.Any]]:
    """The rows of ``dump`` a companion adopts: ``.obj`` placements whose
    resource is a file ``root`` ships and whose anchor ``(lon, lat)`` is
    ``inside`` the airport."""
    rows = []
    for i, pl in enumerate(dump.placements):
        if not pl.def_path.lower().endswith(".obj"):
            continue
        path = os.path.join(root, pl.def_path)
        if not (os.path.isfile(path) and _inside(path, root)):
            continue
        if inside(pl.lon, pl.lat):
            rows.append((i, pl))
    return rows


def _region(airport):
    """The airport's boundary (apt.dat row 130), else the extent of its
    own runways and pavements; ``None`` with neither."""
    from .load import _own_extent
    if airport.boundaries:
        return _own_extent((), (), airport.boundaries, 0.0)
    return _own_extent(airport.runways, airport.pavements, (), 0.0)


def find(airport, mod_cache_root: str, lat: int, lon: int,
         say: _t.Callable[[str], None] = lambda _m: None) -> list[Companion]:
    """The airport's companion packs (module doc), each with its admitted
    rows.  A candidate whose pristine dump is not in the mod cache is
    named and skipped (the dump is made before the build, never here)."""
    from shapely.geometry import Point
    from shapely.prepared import prep
    from .dsf_write import pristine_dsf_path
    main_root = os.path.dirname(os.path.dirname(airport.pack.apt_dat_path or ""))
    region = _region(airport) if main_root and mod_cache_root else None
    if region is None:
        return []
    region_p = prep(region)
    to_xy = airport.frame.transformers()[0]

    def inside(lo: float, la: float) -> bool:
        return region_p.contains(Point(*to_xy(lo, la)))

    out = []
    for root in dump_candidates(main_root, lat, lon):
        name = os.path.basename(root)
        dsf_path = pristine_dsf_path(_dsf.dsf_path_in_pack(root, lat, lon))
        dump_path = _dsf.find_text_dump(mod_cache_root, name, lat, lon, dsf_path=dsf_path)
        if not dump_path:
            say(f"  [companion] {name}: no text dump of {os.path.basename(dsf_path)} "
                "in the mod cache -- not read")
            continue
        rows = admitted(_dsf.read_dump(dump_path, lambda _p: False), root, inside)
        if rows:
            out.append(Companion(name, root, dump_path, tuple(rows)))
    return out


def _objects(c: Companion, to_xy) -> tuple[DsfObject, ...]:
    """The admitted rows as the loader mints them (``load``: ``dsf:obj<i>``
    is row ``i`` of the companion's own dump; the AUTHORED file read)."""
    objs = []
    for i, pl in c.rows:
        resolved, _restored = authored_source(os.path.join(c.root, pl.def_path), c.root)
        agl = float(pl.elevation) if pl.kind in ("OBJECT_AGL", "OBJECT_MSL") \
            and pl.elevation is not None else 0.0
        objs.append(DsfObject(f"dsf:obj{i}", pl.def_path, to_xy(pl.lon, pl.lat),
                              pl.heading_deg, None, False, None, agl, resolved, pl.kind))
    return tuple(objs)


def plans(airport, law, companions: _t.Sequence[Companion]) -> list:
    """One :class:`~auto_patch_v2.model.rebake.RebakePlan` per companion,
    read and partitioned exactly as the main pack is (module doc)."""
    from .basin_witness import read_objects
    from .frame_entry import quantum
    from .obj8 import ResourceCache
    from .pack_partition import partition_pack
    from .rebake_plan import plan as rebake_plan
    to_xy = airport.frame.transformers()[0]
    out = []
    for c in companions:
        site = _dc.replace(airport, dsf_objects=_objects(c, to_xy),
                           pack=SceneryPack(c.name, "", "", (), (), root=c.root))
        cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m,
                              quantum(law))
        objs, _rep = read_objects(site, law, cache)
        part = partition_pack(site, objs, cache, law)
        out.append(rebake_plan(site, objs, cache, law, partition=part))
    return out


def place(patch_dir: str, icao: str, plan_paths: _t.Sequence[str]) -> list[str]:
    """Copy the build's companion plans beside the patch as
    :data:`COMPANION_PLAN`, removing every earlier build's first (a pack
    the user removed leaves no plan behind)."""
    import shutil
    for stale in glob.glob(os.path.join(glob.escape(patch_dir), COMPANION_PLAN.format(
            icao=glob.escape(icao), k="*"))):
        os.remove(stale)
    placed = []
    for k, src in enumerate(plan_paths, start=1):
        dest = os.path.join(patch_dir, COMPANION_PLAN.format(icao=icao, k=k))
        shutil.copyfile(str(src), dest + ".tmp")
        os.replace(dest + ".tmp", dest)
        placed.append(dest)
    return placed
