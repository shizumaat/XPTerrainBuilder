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
* ships NO apt.dat (a pack with one is an airport of its own) -- or one
  that defines only OTHER airports, and then only its rows outside where
  those airports read placements (#2063, below);
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

AN AIRPORT PACK'S OBJECTS AT ANOTHER AIRPORT (#2063, KRNT, the owner's
sim read 2026-11-13 "some floating airplanes").  The Seattle pack's
apt.dat defines KSEA only, yet its ``+47-123`` DSF places dozens of parked
aircraft of its own on KRNT's aprons, each file one aircraft authored up
to 300 m from a shared anchor.  KSEA's window never reads them (they lie
outside its extent), KRNT is served by its own pack, and the rule above
refused the Seattle pack for having an apt.dat -- so nothing re-seated
them, and on KRNT's graded aprons a Cub and a C152 drew +1.6 m over the
ground and other Cubs 1 m under it.  Such a pack is a companion for the
rows inside this airport that NONE of the airports it SERVES reads
(``object_window.own_claim``: their extents grown by the pavement
admission margin, and the load box about each reference point); a row in
doubt stays where its author put it (RULINGS 2026-11-13r).  A pack whose
apt.dat defines this airport is a rival pack of the same airport and is
never a companion.

WHERE THE AIRPORTS THIS PACK SERVES READ IT (#2063 round 2).  The pack's
own apt.dat airports, and every other airport of the tile whose pack
``pack.select_pack`` chooses as this one (#1630's object pack: the Seattle
pack serves KBFI and KPAE without defining them;
``object_window.served_airports``).

A ROW AUTHORED AWAY FROM ITS ANCHOR (``also``): an anchor outside the
airport but within the admission margin is admitted when EVERY
ground-contact foot of its file (the solid vertices within ``[basin]
contact_band_m`` of its lowest, :func:`_feet`) stands inside the airport
-- KRNT's Cub and C152 rows are anchored 300 m off in such atlases.

A ROW X-PLANE NEVER DRAWS IS LEFT ALONE (#2063 round 2).  A pack drawn
ABOVE this one in ``scenery_packs.ini`` whose tile DSF declares a
``sim/exclude_obj`` box removes this pack's objects inside it
(``airport/exclusion``): at KRNT the Renton pack excludes 53 of the
Seattle pack's rows and 3 of Orbx's.  Such a row is never adopted --
rewriting it measures a model the sim does not show (round 1's +7.93 m
"float" was one).  An unreadable header reads as no exclusion.
"""
from __future__ import annotations

import dataclasses as _dc
import glob
import os
import typing as _t

from ..model.airport import DsfObject, SceneryPack
from . import dsf as _dsf
from .obj8 import _to_frame
from .object_window import own_claim, pack_apt_dat, served_airports
from .pack import authored_source
from .pack_local import admitted, ships_objects, tile_candidates

__all__ = ["COMPANION_PLAN", "dump_candidates", "find",
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


def dump_candidates(main_root: str, lat: int, lon: int, icao: str = "") -> list[str]:
    """The candidate packs (``pack_local.tile_candidates``) that ship objects of their
    own: the packs whose tile DSF the pre-build refresh dumps
    (``engine_v2.fresh_pack_dump``) so :func:`find` can read them.  With
    ``icao``, packs of other airports too (#2063)."""
    return [r for r in tile_candidates(main_root, lat, lon, icao) if ships_objects(r)]


def _region(airport):
    """The airport's boundary (apt.dat row 130), else the extent of its
    own runways and pavements; ``None`` with neither."""
    from .load import _own_extent
    if airport.boundaries:
        return _own_extent((), (), airport.boundaries, 0.0)
    return _own_extent(airport.runways, airport.pavements, (), 0.0)


def find(airport, mod_cache_root: str, lat: int, lon: int,
         say: _t.Callable[[str], None] = lambda _m: None, *,
         margin_m: float = 1000.0, radius_deg: float = 0.05,
         band_m: float = 0.0) -> list[Companion]:
    """The airport's companion packs (module doc), each with its admitted
    rows.  A candidate whose pristine dump is not in the mod cache is
    named and skipped (the dump is made before the build, never here).
    ``margin_m`` / ``radius_deg``: how far a pack's OWN airports read its
    placements (``identity.dsf_pavement_admission_m``, the load box);
    ``band_m`` the ground-contact band of a file's feet (``[basin]
    contact_band_m``, :func:`_feet`)."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    from .backup_state import pristine_dsf_path
    main_root = airport.pack.pack_root
    region = _region(airport) if main_root and mod_cache_root else None
    if region is None:
        return []
    region_p = prep(region)
    near_p = prep(region.buffer(float(margin_m)))
    to_xy = airport.frame.transformers()[0]
    ref = airport.frame.origin
    feet_of: dict[str, _t.Any] = {}

    def witnesses(claim, root):
        """``(inside, also)`` for ``pack_local.admitted``: the anchor inside
        the airport, else (#2063) EVERY ground-contact foot of the file
        inside it with the anchor within ``margin_m`` — and never an anchor
        the airports the pack serves read (``claim``)."""
        claim_p = prep(claim) if claim is not None else None

        def own(p) -> bool:
            return bool(claim_p and claim_p.intersects(p))

        def inside(lo: float, la: float) -> bool:
            p = Point(*to_xy(lo, la))
            return region_p.contains(p) and not own(p)

        def also(path: str, pl) -> bool:
            p = Point(*to_xy(pl.lon, pl.lat))
            if own(p) or not near_p.contains(p):
                return False
            fs = feet_of[path] if path in feet_of else feet_of.setdefault(
                path, _feet(authored_source(path, root)[0], band_m))
            if not fs:
                return False
            import shapely
            xy = [_to_frame(p.coords[0], pl.heading_deg, x, z) for x, z in fs]
            return bool(shapely.contains_xy(region, [q[0] for q in xy],
                                            [q[1] for q in xy]).all())
        return inside, also

    out = []
    for root in dump_candidates(main_root, lat, lon, airport.icao):
        name = os.path.basename(root)
        dsf_path = pristine_dsf_path(_dsf.dsf_path_in_pack(root, lat, lon))
        dump_path = _dsf.find_text_dump(mod_cache_root, name, lat, lon, dsf_path=dsf_path)
        if not dump_path:
            say(f"  [companion] {name}: no text dump of {os.path.basename(dsf_path)} "
                "in the mod cache -- not read")
            continue
        claim = own_claim(pack_apt_dat(root), ref, to_xy, margin_m, radius_deg,
                          served=served_airports(root, airport.icao, lat, lon,
                                                 ref, say))
        rows = _drawn(admitted(_dsf.read_dump(dump_path, lambda _p: False), root,
                               *witnesses(claim, root)), root, lat, lon, name, say)
        if rows:
            out.append(Companion(name, root, dump_path, tuple(rows)))
    return out


def _drawn(rows: list, root: str, lat: int, lon: int, name: str,
           say: _t.Callable[[str], None]) -> list:
    """``rows`` less those X-Plane never draws: a row inside a
    ``sim/exclude_obj`` box of a pack drawn ABOVE this one
    (``exclusion.boxes_above``) is left alone, one line per excluding
    pack (#2063 round 2)."""
    from .exclusion import boxes_above, excluder_of
    boxes = boxes_above(root, lat, lon) if rows else []
    if not boxes:
        return rows
    kept, under = [], {}
    for i, pl in rows:
        by = excluder_of(boxes, pl.lon, pl.lat)
        if by is None:
            kept.append((i, pl))
        else:
            under[by] = under.get(by, 0) + 1
    for by, n in sorted(under.items()):
        say(f"  [companion] {name}: {n} row(s) under {by}'s exclusion — "
            "not drawn, left alone")
    return kept


def _feet(path: "str | None", band_m: float) -> "tuple[tuple[float, float], ...]":
    """The authored plan ``(x, z)`` of the file's GROUND-CONTACT FEET: its
    solid vertices within ``band_m`` of its lowest solid vertex (``()``
    when it has none or cannot be read).  Round 2 (#2063) read the file's
    box centre: a 288 m atlas of parked aircraft centred on the airport
    then adopted the aircraft standing outside it."""
    from .obj8 import parse_obj8
    if not path:
        return ()
    try:
        g = parse_obj8(path)
    except (OSError, ValueError):
        return ()
    if g is None or not g.solid.shape[0]:
        return ()
    v = g.vertices[g.solid.reshape(-1)]
    low = v[v[:, 1] <= float(v[:, 1].min()) + float(band_m)]
    return tuple({(round(float(x), 2), round(float(z), 2)) for x, z in low[:, (0, 2)]})


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
        # the stands its airside floor is read at are the AIRPORT's (#1639):
        # a companion ships no apt.dat, and with no stands every foot near
        # an apron voted -- LFPG T1's lower-storey walls floated it 8 m
        out.append(_dc.replace(rebake_plan(site, objs, cache, law, partition=part),
                               apt_dat=str(airport.pack.apt_dat_path or "")))
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
