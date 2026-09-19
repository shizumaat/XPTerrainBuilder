"""THE PRODUCTION DEM FRAME (RULINGS 03j; M1 open question 5).

The surface the mesh drapes on is NOT the authored ``.hgt`` + inset
(``dem.py``'s ``DemSampler``): it is Ortho4XP's tile DEM after the
production prelude — composite assembly, working-grid densification over
inset tiles, tile-overlay bake, ``smooth_raster_over_airports`` (the
per-airport blur at ``apt_smoothing_pix``), the cached-inset bake and the
flat-site substitution — queried BILINEARLY on the baked working grid,
which is exactly what ``Triangle4XP.altitude()`` renders and what
``include_patches`` samples for every patch node (``tile.dem.alt_vec``).
v1 reaches the same surface through its ``elevation._load_airport_
dem`` → ``O4_Vector_Map.compose_tile_dem_from_disk``; v2 calls the core
accessor DIRECTLY (the core is not v1: plan §1 "the core's inset
machinery stays core-side").  Nothing here imports ``auto_patch``.

READ-ONLY.  ``compose_tile_dem_from_disk(write_alt_file=False)`` keeps
the raster in memory; the tile's own ``Tiles/`` directory (lane-local)
is the only thing the core creates.  The shared-repo write guard is
armed by the CLI around the whole build (``pipeline/__main__``), so a
write the prelude attempted into the corpus refuses at the call and the
build reports it — never a private inset cut, never a download.

THE FRAME IS REFUSED WHEN COLD (the harness's ``require_dem_frame``
semantics, ``tools/harness/build_airport.py``): no base raster, no cached
airports OSM layer (no smoothing masks), no ``<tile>_airport_insets``
directory, or a bake that reports NO inset for the airport while its
inset file exists (the swallowed-degradation class of 2026-08-07).  Each
is a :class:`ColdDemFrame` naming the artefact and the ``--refresh-data``
scope; ``allow_degraded=True`` (the CLI's ``--allow-degraded-dem``)
accepts the degraded surface KNOWINGLY and records every problem in the
provenance — it authorises no write.

One baked raster per 1° tile the airport touches, composed lazily: a
straddling airport (SPLP, −13/−77 and −13/−78) samples each point from
ITS tile's raster — the two tiles ballot their working grids identically
(``seam_harmonized_ballot_insets``), so the seam agrees, and the seam
pins v2 mints (``constraints/seams.py``) carry the value the neighbour
tile drapes.
"""
from __future__ import annotations

import json
import math
import math as _m
import os
import sys
import typing as _t
from pathlib import Path

import numpy as np

from auto_patch.selection import DEFAULT_MODE as _MODE_VALUED_KEYS
from auto_patch.selection import normalize_mode

from ..model.frame import Frame
from .dem import hgt_name, resolve_dem_files

__all__ = ["ColdDemFrame", "ProductionDem", "load_production_dem",
           "engine_root", "frame_state", "TileWater"]

#: Posts per axis the inland-body level is sampled on (the median of a
#: body's own DEM cells; a 32x32 grid inside the body is plenty for a
#: level and bounds the cost of a pathological polygon).
_LEVEL_GRID = 32

#: The engine tree this package lives in (``src/auto_patch_v2/airport``).
ENGINE_DIR = Path(__file__).resolve().parents[3]


class ColdDemFrame(RuntimeError):
    """The production frame cannot be composed from cached disk state."""


def engine_root() -> Path:
    return ENGINE_DIR


def frame_state(elevation_root: str, osm_root: str, lat: int, lon: int,
                icao: str, required_box: tuple | None = None,
                expects_inset: bool = True
                ) -> tuple[dict, list[str]]:
    """Filesystem-only cache warmth for one tile (``dem_cache_state``):
    ``(state, problems)`` — pure path inspection, never a fetch.

    ``required_box`` is THIS airport's required inset extent (the
    aerodrome boundary plus ``airport_elevation_inset_margin_m``, from
    ``O4_Airport_Elevation_Insets._airport_bounding_boxes``).  Given it,
    the per-airport check runs too: a present ``_airport_insets``
    directory says nothing about whether THIS airport has an inset in it,
    or whether the one there was cut for a box that still contains what
    the airport needs.  Until 2026-09-17 this function tested only
    ``os.path.isdir`` and took ``icao`` without ever using it for the
    inset, so a MISSING or STALE inset read as a warm frame.

    The predicate is the ENGINE's own
    (``O4_Airport_Elevation_Insets.airport_inset_frame_problem``) —
    imported, never copied — so what the app RE-CUTS and what the harness
    REFUSES cannot drift.  Without ``required_box`` the behaviour is
    exactly as before, and the core is not imported at all.
    """
    hgt, tif, _js = resolve_dem_files(elevation_root, lat + 0.5, lon + 0.5, icao)
    stem = hgt_name(lat, lon)
    block = f"{(lat // 10) * 10:+03d}{(lon // 10) * 10:+04d}"
    short = f"{lat:+03d}{lon:+04d}"
    ins_dir = os.path.join(elevation_root, block, stem + "_airport_insets")
    layer = os.path.join(osm_root, block, short, short + "_airports.osm.bz2")
    state = {"tile": [lat, lon], "tile_stem": stem, "base_raster": hgt,
             "base_raster_present": os.path.isfile(hgt),
             "airport_insets_dir": ins_dir,
             "airport_insets_present": os.path.isdir(ins_dir),
             "airport_inset": tif, "airports_layer": layer,
             "airports_layer_present": os.path.isfile(layer)}
    problems: list[str] = []
    if not state["base_raster_present"]:
        problems.append(f"NO base raster {hgt} — the core would DOWNLOAD it "
                        f"or hand back an all-zero surface (--refresh-data dem)")
    if not state["airports_layer_present"]:
        problems.append(f"NO cached airports OSM layer {layer} — no smoothing "
                        f"masks, the surface stays UNSMOOTHED "
                        f"(--refresh-data osm_layers)")
    if not expects_inset:
        # §A.6 patch∖inset (spec §B row 13): this airport is PATCHED but
        # outside the inset selection, so it solves on the base raster
        # without meter-class data — exactly what every airport with no
        # provider coverage does today.  A missing inset is then not a
        # problem, there is no refusal and nothing is warmed.  An orphan
        # inset that IS on disk is still baked and still recorded (owner
        # Q3, RULINGS 2026-09-18c).
        state["expects_inset"] = False
    elif not state["airport_insets_present"]:
        problems.append(f"NO airport elevation insets dir {ins_dir} — the base "
                        f"surface only, while production bakes insets "
                        f"(--refresh-data dem)")
    elif required_box is not None:
        # THE PER-AIRPORT CHECK.  Only reached with the directory there:
        # a whole-tile miss is already named above, and naming it twice
        # would say the same cold cache in two voices.
        import O4_Airport_Elevation_Insets as INSETS
        state["airport_inset_required_box"] = [float(v) for v in required_box]
        problem = INSETS.airport_inset_frame_problem(lat, lon, icao,
                                                     required_box)
        if problem is not None:
            (state["airport_inset_problem_kind"], text) = problem
            if state["airport_inset_problem_kind"] == "empty":
                # DECLARED EMPTY, not cold (2026-09-18, LSGP/LSGY).  The
                # bake DECLINES a raster under the valid-pixel rule out
                # loud and grades on the base DEM; a declared state is
                # never a silent degrade, so it is recorded and reported
                # and it warms, refuses and degrades NOTHING.  The relic
                # is re-fetched where fetches belong: the tile build's
                # own inset pass, or an explicit --refresh-data dem.
                state["airport_inset_declared_empty"] = text
            elif state["airport_inset_problem_kind"] == "packs":
                # THE PACK SET MOVED (owner ruling 2026-09-17c (1)).  A
                # KNOWN, SELF-HEALING state, never a refusal: the tile's
                # own inset pass re-fetches and re-masks it, out loud
                # ("was masked with a different set of installed scenery
                # packs - refetching").  Refusing the airport for it
                # would take the tile down for a cache the app is about
                # to repair — the 2026-09-18k (3) class exactly.  The
                # HARNESS refuses it instead, because there a re-fetch
                # is a shared-repo write as a build side effect.
                state["airport_inset_pack_set_moved"] = text
            else:
                problems.append(text)
    return state, problems


def _inset_mode_of(tile) -> str:
    """The tile's normalised inset mode, for the provenance record."""
    try:
        from auto_patch.selection import resolved_inset_mode

        return resolved_inset_mode(tile)
    except Exception:                                    # pragma: no cover
        return "?"


class _BakedTile:
    """One tile's baked working raster and the mesh's bilinear query
    (``O4_DEM_Utils.DEM.alt_vec_baked``, reproduced vectorised so the
    array is read once and the core object is released)."""

    def __init__(self, lat: int, lon: int, alt_dem: np.ndarray,
                 x0: float, x1: float, y0: float, y1: float,
                 inset_provenance: list | None = None,
                 flat_site_provenance: list | None = None,
                 overlay_provenance: dict | None = None) -> None:
        self.lat, self.lon = lat, lon
        self.alt = np.asarray(alt_dem, dtype=np.float64)
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        # THE CORE'S OWN RECORDS on the composed raster, kept for the
        # flat-site detector (RULINGS 2026-09-05k-2): the insets that
        # baked (their ``native_resolution_m`` is the source class), the
        # tile-wide overlay, and the core's ``synthetic_flat_site``
        # verdict per airport (compared with v2's, never reconciled).
        self.inset_provenance = list(inset_provenance or [])
        self.flat_site_provenance = list(flat_site_provenance or [])
        self.overlay_provenance = dict(overlay_provenance or {})

    def sample(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        ny, nx = self.alt.shape
        Nx, Ny = nx - 1, ny - 1
        x = np.clip(lon - self.lon, self.x0, self.x1)
        y = np.clip(lat - self.lat, self.y0, self.y1)
        px = (x - self.x0) / (self.x1 - self.x0) * Nx
        py = (self.y1 - y) / (self.y1 - self.y0) * Ny
        ix = np.minimum(px.astype(np.int64), Nx)
        iy = np.minimum(py.astype(np.int64), Ny)
        ixp = np.minimum(ix + 1, Nx)
        iyp = np.minimum(iy + 1, Ny)
        rx, ry = px - ix, py - iy
        a = self.alt
        return (a[iy, ix] * (1 - rx) * (1 - ry) + a[iy, ixp] * rx * (1 - ry)
                + a[iyp, ix] * (1 - rx) * ry + a[iyp, ixp] * rx * ry)


class TileWater:
    """ONE TILE'S WATER WITNESS (owner RULINGS 2026-09-09m; mechanism 09o
    (1)) — the polygons and the LEVEL each one holds.

    The polygons are the core's own, read through
    ``O4_Vector_Map.cached_tile_water``: the coastline partition's SEA
    (``sea_area_from_coastline``, the tree's single SEA/LAND
    implementation) and the tile's cached ``water`` layer — the same
    layers the mesh's masks are built from.  Nothing here re-derives
    them, and nothing here downloads: a tile with no cached layer
    answers "not water" everywhere and says so in :meth:`state`.

    THE LEVEL RULE (spec §1.2):

    * SEA → ``0.0`` — the datum ``sea_smoothing_mode=zero`` levels the
      mesh's own sea triangles to;
    * an INLAND BODY → the MEDIAN of the production DEM over that body,
      one level per polygon, computed on first touch.  The engine's
      inland treatment (``tile.water_smoothing``) iterates a per-triangle
      mean, i.e. it converges a body to ONE level; the body's own DEM
      median is that level, robust to the bank cells the polygon edge
      clips.

    Queries are vectorised through a shapely ``STRtree`` — never a
    per-point containment loop.
    """

    def __init__(self, lat: int, lon: int, sea, inland) -> None:
        from shapely import STRtree
        from shapely.geometry import MultiPolygon, Polygon
        self.lat, self.lon = int(lat), int(lon)
        self.has_data = sea is not None or inland is not None
        polys: list = []
        kinds: list[str] = []

        def _add(geom, kind: str) -> None:
            if geom is None or geom.is_empty:
                return
            parts = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
            for p in parts:
                if isinstance(p, Polygon) and not p.is_empty:
                    polys.append(p)
                    kinds.append(kind)

        _add(sea, "sea")
        _add(inland, "inland")
        self.polys = polys
        self.kinds = kinds
        self.n_sea = kinds.count("sea")
        self.n_inland = kinds.count("inland")
        self._level: list[float | None] = [
            0.0 if k == "sea" else None for k in kinds]
        self._tree = STRtree(polys) if polys else None

    # ── the query ───────────────────────────────────────────────────
    def index_of(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """The covering polygon's index per point, ``-1`` where none."""
        out = np.full(np.shape(lat), -1, dtype=np.int64)
        if self._tree is None or out.size == 0:
            return out
        from shapely import points as _points
        pts = _points(np.asarray(lon, float) - self.lon,
                      np.asarray(lat, float) - self.lat)
        # NOTE the predicate direction: shapely evaluates it as
        # ``input.predicate(tree_geometry)``, so "covers" would ask
        # whether the POINT covers the polygon.  For a point against a
        # polygon "intersects" is exactly "covered by it", boundary
        # included.
        hit_pt, hit_poly = self._tree.query(pts, predicate="intersects")
        # the FIRST hit wins; sea polygons come first, so a body inside
        # the sea's own multipolygon reads as sea (its level is 0.0 too)
        for i, j in zip(hit_pt[::-1], hit_poly[::-1]):
            out.reshape(-1)[int(i)] = int(j)
        return out

    def level_of(self, index: int, sampler) -> float:
        """The water level of polygon ``index`` (module docstring)."""
        lvl = self._level[index]
        if lvl is not None:
            return lvl
        poly = self.polys[index]
        minx, miny, maxx, maxy = poly.bounds
        gx, gy = np.meshgrid(np.linspace(minx, maxx, _LEVEL_GRID),
                             np.linspace(miny, maxy, _LEVEL_GRID))
        gx, gy = gx.ravel(), gy.ravel()
        from shapely import contains_xy
        keep = contains_xy(poly, gx, gy)
        if not keep.any():                       # a sliver: its centroid
            c = poly.representative_point()
            gx, gy = np.array([c.x]), np.array([c.y])
        else:
            gx, gy = gx[keep], gy[keep]
        z = np.asarray(sampler(gy + self.lat, gx + self.lon), float)
        z = z[np.isfinite(z)]
        lvl = float(np.median(z)) if z.size else 0.0
        self._level[index] = lvl
        return lvl

    def state(self) -> dict:
        return {"tile": [self.lat, self.lon], "has_data": self.has_data,
                "sea_polygons": self.n_sea, "inland_polygons": self.n_inland}


def _entered(coords, enter, lon0: float, lat0: float):
    """``(N, 2)`` tile-local ``(lon, lat)`` offsets -> frame metres through
    the §46 ENTRY projection.

    The water mask stores its rings as offsets from the tile's own
    south-west corner, so the absolute lat/lon is rebuilt here and handed
    to ``Frame.entry`` ONE POINT AT A TIME — that callable is the only
    place in the tree that snaps an entering coordinate to
    ``emit.identity.input_quantum_m``, and a numpy re-spelling of its
    arithmetic beside it is exactly the duplicate §46 removed elsewhere.
    An empty ring keeps its shape so ``shapely.transform`` is happy.
    """
    if len(coords) == 0:                        # pragma: no cover - guard
        return np.zeros((0, 2), dtype=np.float64)
    return np.array([enter(float(lo) + lon0, float(la) + lat0)
                     for lo, la in coords], dtype=np.float64)


class ProductionDem:
    """``DemSample`` over the production tile rasters (one per tile,
    composed on first touch)."""

    def __init__(self, frame: Frame, icao: str, elevation_root: str,
                 osm_root: str, xplane_root: str, *, allow_degraded: bool = False,
                 out: _t.Callable[[str], None] = print,
                 seed_tiles: _t.Mapping[tuple[int, int], _t.Any] | None = None,
                 core_hosted: bool = False,
                 declared_tiles: _t.Iterable[tuple[int, int]] | None = None,
                 ) -> None:
        self.frame = frame
        self.icao = icao
        self.elevation_root = elevation_root
        self.osm_root = osm_root
        self.xplane_root = xplane_root
        self.allow_degraded = bool(allow_degraded)
        #: This airport's REQUIRED inset box per tile, kept so the frame
        #: record can state it beside what was requested and delivered.
        self._required_boxes: dict[tuple[int, int], tuple | None] = {}
        self.core_hosted = bool(core_hosted)
        #: The tiles this build OWNS or was told to warm: the airport's own
        #: cell, plus every cell a class-S boundary choice declared (§C.3
        #: ``boundary_policy == "neighbour"``).  A cold tile OUTSIDE this
        #: set is read CONTEXT-ONLY and never refuses (§C.1 class M).
        self.declared_tiles: set = {
            (int(_m.floor(frame.origin[0])), int(_m.floor(frame.origin[1])))}
        for _cell in (declared_tiles or ()):
            self.declared_tiles.add((int(_cell[0]), int(_cell[1])))
        self._out = out
        self.provenance: dict[str, str] = {"frame": "production",
                                           "query": "bilinear on the baked working grid"}
        self._tiles: dict[tuple[int, int], _BakedTile | None] = {}
        self._water: dict[tuple[int, int], TileWater | None] = {}
        #: §39 (i) (owner RULINGS 2026-09-13cg): the SHORE LINEWORK the
        #: mesh constrains, per tile — a different question from
        #: _water ("is this point wet") and a different product.
        self._shore: dict[tuple[int, int], list] = {}
        from pyproj import Transformer  # local: geodesy stays in the loaders
        self._inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)
        #: The EXACT forward projection, for the INTEGER TILE CORNERS
        #: :meth:`bounds` projects — a derived constant, not a coordinate
        #: entering the layout (§46 (9) census row 15).
        self._fwd = Transformer.from_crs("EPSG:4326", frame.crs, always_xy=True)
        #: §46 (9) CENSUS ROW 16, SWITCHED: the tile's WATER-MASK polygons
        #: are foreign lat/lon — water linework we did not compute — so
        #: they ENTER the frame and take the ENTRY projection
        #: (:meth:`water_geometry`).  Built ONCE here: ``Frame.entry()``
        #: constructs its ``pyproj`` transformers on every call.
        self._enter = frame.entry()
        self._check_corpus()
        # THE HOST'S OWN RASTER, REUSED (a tile build's ``tile.dem``): the
        # frame of record for every patch node the mesh will sample, so
        # it is adopted as-is — never re-composed — and its bake
        # provenance is recorded the same way a lazy composition's is.
        for (lat, lon), dem in sorted((seed_tiles or {}).items()):
            self._tiles[(int(lat), int(lon))] = self._adopt(int(lat), int(lon), dem)

    # ── pickling (the synthetic-first capture) ──────────────────────
    def __getstate__(self) -> dict:
        """``Frame.entry()`` returns a CLOSURE (§46 (4) (a)), which pickle
        cannot serialise — so the capture of `tools/v2_solve_replay.py`
        died on every airport.  The closure is a pure function of
        ``self.frame``, so it is dropped here and rebuilt in
        :meth:`__setstate__` from the frame that IS pickled — the derived
        constant is never carried, never re-derived differently.
        """
        st = dict(self.__dict__)
        st.pop("_enter", None)
        return st

    def __setstate__(self, st: dict) -> None:
        self.__dict__.update(st)
        self._enter = self.frame.entry()

    # ── DemSample protocol ──────────────────────────────────────────
    def z(self, x: float, y: float) -> float:
        return float(self.z_many(np.array([x]), np.array([y]))[0])

    def bounds(self) -> tuple[float, float, float, float]:
        lat, lon = self.frame.origin
        t0, t1 = math.floor(lat), math.floor(lon)
        xs, ys = self._fwd.transform([t1, t1 + 1, t1, t1 + 1],
                                     [t0, t0, t0 + 1, t0 + 1])
        return (min(xs), min(ys), max(xs), max(ys))

    # ── the flat-site detector's reads (RULINGS 2026-09-05k-2) ──────
    def posting_m(self) -> float | None:
        """The origin tile's working-grid posting in frame metres (the
        smaller of the two axes) — the step the detector samples the
        raster at, so it reads the DEM's own cells and invents nothing
        between them (v1 ``dem_relief``)."""
        lat, lon = self.frame.origin
        t = self.tile(int(math.floor(lat)), int(math.floor(lon)))
        if t is None:
            return None
        ny, nx = t.alt.shape
        if nx < 2 or ny < 2:
            return None
        xmin, ymin, xmax, ymax = self.bounds()
        return float(min((xmax - xmin) * (t.x1 - t.x0) / (nx - 1),
                         (ymax - ymin) * (t.y1 - t.y0) / (ny - 1)))

    def source_pixel_m(self) -> tuple[float | None, str]:
        """``(pixel_m, whence)`` of the finest source that baked over THIS
        airport, in v1's order (``flat_site.source_class_for_dem``): the
        airport's own inset's ``native_resolution_m`` (``inset``), else
        the tile overlay's ``target_resolution_m`` (``overlay``), else
        ``(None, "base_tier")`` — the base tier's 1- and 3-arcsec postings
        are both coarse; the raster's own posting is NOT consulted (a
        3-arcsec .hgt is upsampled with no record of it).

        §45 (18) (owner RULINGS 2026-09-15bo): the manifest entry is read
        for ``native_resolution_m``, else ``resolution_m``, else the
        INSET'S OWN sidecar (``<inset>.json``, the file the entry's
        ``path`` names) — every N32W098 sidecar of 2026-08-15 was minted
        by a writer that stamped ``native_resolution_m: null``, so KDFW's
        composed 1 m 3DEP frame read ``(None, 'base_tier')`` → ``coarse``
        → ``_lidar_credible`` False.  One line is logged when a fallback
        fires, naming the key and the file."""
        lat, lon = self.frame.origin
        t = self.tile(int(math.floor(lat)), int(math.floor(lon)))
        if t is None:
            return None, "unknown"
        finest: float | None = None
        note: str | None = None
        for e in t.inset_provenance:
            if not isinstance(e, dict):
                continue
            # v1 ``provenance._entries_for_icao``: an entry naming another
            # airport is not this airport's; one naming none counts
            if e.get("icao") and str(e["icao"]).upper() != self.icao.upper():
                continue
            f, whence = self._entry_pixel_m(e)
            if f is None:
                continue
            if finest is None or f < finest:
                finest = f
                note = whence
        if finest is not None:
            if note is not None:
                seen = self.__dict__.setdefault("_pixel_notes", set())
                if note not in seen:
                    seen.add(note)
                    self._out(f"   [inset] {self.icao}: manifest entry carries "
                              f"no native_resolution_m — source pixel "
                              f"{finest:g} m from {note}")
            return finest, "inset"
        try:
            f = float(t.overlay_provenance.get("target_resolution_m"))
        except (TypeError, ValueError):
            f = 0.0
        if f > 0.0:
            return f, "overlay"
        return None, "base_tier"

    @staticmethod
    def _entry_pixel_m(entry: dict) -> tuple[float | None, str | None]:
        """One manifest entry's source pixel, §45 (18)'s precedence:
        ``native_resolution_m``, else the entry's ``resolution_m``, else
        the inset's OWN sidecar (``<path>.json``, keys ``resolution_m`` /
        ``native_resolution_m``).  The second member is ``None`` when the
        primary key answered, and otherwise names the key and the file the
        value came from (the caller logs it once)."""
        def _pos(v) -> float | None:
            try:
                f = float(v)
            except (TypeError, ValueError):
                return None
            return f if f > 0.0 else None

        f = _pos(entry.get("native_resolution_m"))
        if f is not None:
            return f, None
        f = _pos(entry.get("resolution_m"))
        if f is not None:
            return f, "the manifest entry's resolution_m"
        path = entry.get("path")
        if not path or not str(path).endswith(".tif"):
            return None, None
        sidecar = str(path)[:-4] + ".json"
        try:
            with open(sidecar, "r") as handle:
                meta = json.load(handle)
        except (OSError, ValueError):
            return None, None
        if not isinstance(meta, dict):
            return None, None
        for key in ("resolution_m", "native_resolution_m"):
            f = _pos(meta.get(key))
            if f is not None:
                return f, f"{key} in {sidecar}"
        return None, None

    def core_flat_site(self) -> dict | None:
        """The core's own ``synthetic_flat_site`` record for this airport
        on the composed raster (``O4_Airport_Elevation_Insets.
        overlay_flat_site_insets``), or ``None`` when the core substituted
        nothing here."""
        lat, lon = self.frame.origin
        t = self.tile(int(math.floor(lat)), int(math.floor(lon)))
        if t is None:
            return None
        for e in t.flat_site_provenance:
            if isinstance(e, dict) and str(e.get("icao", "")).upper() == self.icao.upper() \
                    and e.get("kind") == "synthetic_flat_site":
                return e
        return None

    def warm_tiles(self) -> frozenset[tuple[int, int]]:
        """The 1° tiles already composed (or seeded) — the rasters a
        caller may sample WITHOUT touching a cold neighbour (the road
        adapter clips the core's tile-wide OSM ways to these)."""
        return frozenset(k for k, t in self._tiles.items() if t is not None)

    def tile_of_many(self, xs: np.ndarray, ys: np.ndarray) -> list[tuple[int, int]]:
        """The 1° tile key of every frame point."""
        lon, lat = self._inv.transform(np.asarray(xs, dtype=np.float64),
                                       np.asarray(ys, dtype=np.float64))
        return list(zip(np.floor(np.asarray(lat)).astype(int).tolist(),
                        np.floor(np.asarray(lon)).astype(int).tolist()))

    def z_many(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        lon, lat = self._inv.transform(np.asarray(xs, dtype=np.float64),
                                       np.asarray(ys, dtype=np.float64))
        lon, lat = np.asarray(lon), np.asarray(lat)
        out = np.full(lat.shape, np.nan)
        tl = np.floor(lat).astype(int)
        tn = np.floor(lon).astype(int)
        for key in sorted(set(zip(tl.tolist(), tn.tolist()))):
            tile = self.tile(*key)
            if tile is None:
                continue
            m = (tl == key[0]) & (tn == key[1])
            out[m] = tile.sample(lat[m], lon[m])
        return out

    # ── THE WATER WITNESS (owner RULINGS 2026-09-09m; 09o (1)) ──────
    def water_many(self, xs: np.ndarray, ys: np.ndarray
                   ) -> tuple[np.ndarray, np.ndarray]:
        """``(is_water, level_m)`` at frame points — ``level_m`` is NaN
        off water.  THE one water read of the v2 engine: the zone rings
        and gap interior (``constraints/water.py``), the flat-site datum
        region (``airport/flat_site.py``) and, next round, the shore
        bank (``emit/bank.py`` — it is already handed this ``dem``) all
        come here.  See :class:`TileWater` for the level rule."""
        lon, lat = self._inv.transform(np.asarray(xs, dtype=np.float64),
                                       np.asarray(ys, dtype=np.float64))
        lon, lat = np.atleast_1d(np.asarray(lon)), np.atleast_1d(np.asarray(lat))
        wet = np.zeros(lat.shape, dtype=bool)
        level = np.full(lat.shape, np.nan)
        if lat.size == 0:
            return wet, level
        tl = np.floor(lat).astype(int)
        tn = np.floor(lon).astype(int)
        for key in sorted(set(zip(tl.tolist(), tn.tolist()))):
            w = self.water(*key)
            if w is None or not w.polys:
                continue
            m = (tl == key[0]) & (tn == key[1])
            idx = w.index_of(lat[m], lon[m])
            hit = idx >= 0
            if not hit.any():
                continue
            sub_w = np.zeros(idx.shape, dtype=bool)
            sub_l = np.full(idx.shape, np.nan)
            sub_w[hit] = True
            baked = self.tile(*key)
            sampler = (baked.sample if baked is not None
                       else (lambda la, lo: np.zeros(np.shape(la))))
            for j in sorted(set(idx[hit].tolist())):
                sub_l[idx == j] = w.level_of(int(j), sampler)
            wet[m] = sub_w
            level[m] = sub_l
        return wet, level

    def sea_geometry(self, bounds: tuple[float, float, float, float] | None = None):
        """§37 (11) (1) / §34 (12) (2) THE SHORE (owner RULINGS 2026-09-15f
        item 2): the SEA polygons alone, as frame geometry — the
        coastline partition's own product (``TileWater.kinds == "sea"``),
        never an inland body.

        The shore law is about THE COAST: its level is the tile's sea
        (``SEAWALL_SEA_LEVEL_M``), its wall is the mesh's Round 7 / R17-3
        seawall breakline, and the owner's words are "a taxiway in the
        water".  An inland canal or retention basin keeps the 09-09m
        WATER DATUM instead — the ground stands over it and is PINNED to
        its own median level — so the two laws never contend for one
        polygon."""
        return self.water_geometry(bounds, sea_only=True)

    def water_geometry(self, bounds: tuple[float, float, float, float] | None = None,
                       sea_only: bool = False):
        """The water polygons AS FRAME GEOMETRY (metres), unioned — for
        the passes that cut a REGION rather than sample points (the
        flat-site datum region, and next round's level rings).  ``None``
        when no water is claimed over ``bounds``."""
        import shapely
        from shapely.geometry import box
        from shapely.ops import unary_union
        lat0, lon0 = self.frame.origin
        keys = sorted(self._tiles) or [(int(math.floor(lat0)), int(math.floor(lon0)))]
        clip = None if bounds is None else box(*bounds)
        out = []
        for key in keys:
            w = self.water(*key)
            if w is None or not w.polys:
                continue
            for p, kind in zip(w.polys, w.kinds):
                if sea_only and kind != "sea":
                    continue
                # §46 (4) (a) / (9) row 16: the ENTRY projection, at the
                # frame's ONE derivation site.  Scalar, because the
                # quantum lives there and a vectorised copy of
                # ``round(x / q) * q`` beside it would be the second
                # spelling §46 exists to remove — the same reason
                # ``airport/load._vector_to_xy`` stopped building its own
                # transformer (RULINGS 2026-09-17d).
                q = shapely.transform(p, lambda c: _entered(c, self._enter,
                                                            w.lon, w.lat))
                if clip is not None:
                    if not q.intersects(clip):
                        continue
                    q = q.intersection(clip)
                if not q.is_empty:
                    out.append(q)
        if not out:
            return None
        u = unary_union(out)
        return None if u.is_empty else u

    def is_water_many(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        return self.water_many(xs, ys)[0]

    def is_water(self, x: float, y: float) -> bool:
        return bool(self.water_many(np.array([x]), np.array([y]))[0][0])

    def water(self, lat: int, lon: int) -> "TileWater | None":
        """This tile's witness, read once (``None`` when the core cannot
        be reached at all — never a download)."""
        key = (int(lat), int(lon))
        if key in self._water:
            return self._water[key]
        w = None
        try:
            if not self.core_hosted:
                self._ensure_core_path()
            import O4_Config_Utils as CFG
            import O4_Vector_Map as VMAP
            t = CFG.Tile(key[0], key[1], "")
            t.read_from_config()
            sea, inland = VMAP.cached_tile_water(t)
            w = TileWater(key[0], key[1], sea, inland)
            self._out(f"  [dem] water witness {hgt_name(*key)}: "
                      f"{w.n_sea} sea + {w.n_inland} inland polygon(s)"
                      + ("" if w.has_data else " — NO cached layer, no water claimed"))
        except Exception as error:                          # pragma: no cover
            self._out(f"  [dem] water witness {hgt_name(*key)} UNAVAILABLE "
                      f"({type(error).__name__}: {error}) — no water claimed")
            w = None
        self._water[key] = w
        return w

    def shore(self, lat: int, lon: int) -> list:
        """§39 (i) THE ONE WITNESS (owner RULINGS 2026-09-13cg): the SHORE
        LINEWORK the mesh will constrain on this tile, in tile-relative
        degrees — ``O4_Vector_Map.cached_constrained_shore``, the same
        products ``include_sea`` / ``include_water`` encode, never a
        second derivation.  Read once; ``[]`` when the core cannot be
        reached or nothing is cached (never a download)."""
        key = (int(lat), int(lon))
        if key in self._shore:
            return self._shore[key]
        lines: list = []
        try:
            if not self.core_hosted:
                self._ensure_core_path()
            import O4_Config_Utils as CFG
            import O4_Vector_Map as VMAP
            t = CFG.Tile(key[0], key[1], "")
            t.read_from_config()
            lines = list(VMAP.cached_constrained_shore(t))
            self._out(f"  [dem] shore witness {hgt_name(*key)}: "
                      f"{len(lines)} constrained chain(s) (§39 (i))")
        except Exception as error:                          # pragma: no cover
            self._out(f"  [dem] shore witness {hgt_name(*key)} UNAVAILABLE "
                      f"({type(error).__name__}: {error}) — no shore claimed")
            lines = []
        self._shore[key] = lines
        return lines

    def water_state(self) -> dict:
        """Provenance: what the witness read, per tile."""
        return {hgt_name(*k): (v.state() if v is not None else None)
                for k, v in sorted(self._water.items())}

    # ── composition ─────────────────────────────────────────────────
    def _check_corpus(self) -> None:
        """The core resolves ``Elevation_data`` from ITS data root; v2's
        ``elevation_root`` must be the same corpus (a private one is a
        second measurement frame — refused, RULINGS ``e9daef5``)."""
        if not self.core_hosted:
            self._ensure_core_path()
        import O4_File_Names as FNAMES
        core = os.path.realpath(FNAMES.Elevation_dir)
        ours = os.path.realpath(self.elevation_root)
        self.provenance["core_elevation_dir"] = core
        if core != ours:
            raise ColdDemFrame(
                f"production frame: the core's Elevation_data ({core}) is not "
                f"the given elevation_root ({ours}) — two corpora, refused")

    @staticmethod
    def _ensure_core_path() -> None:
        """The core on ``sys.path`` with ITS data root = this engine tree
        (the core resolves the root from the cwd; the CLI runs from
        ``src/``).  Set before ``O4_Config_Utils`` captures the paths."""
        if os.path.realpath(os.getcwd()) != os.path.realpath(ENGINE_DIR):
            raise ColdDemFrame(
                f"production frame: the core resolves its bundled resources "
                f"(Providers/, Utils/) from the cwd, which must be the engine "
                f"root {ENGINE_DIR} (cwd is {os.getcwd()}); the v2 CLIs chdir "
                f"there — a library caller must too")
        for d in (str(ENGINE_DIR / "src"), str(ENGINE_DIR / "Providers")):
            if d not in sys.path:
                sys.path.append(d)
        import O4_File_Names as FNAMES
        if os.path.realpath(FNAMES.current_data_root()) != os.path.realpath(ENGINE_DIR):
            if "O4_Config_Utils" in sys.modules:
                raise ColdDemFrame("production frame: the core was imported with "
                                   f"data root {FNAMES.current_data_root()} != "
                                   f"{ENGINE_DIR}; cannot re-point it")
            FNAMES.set_data_root(str(ENGINE_DIR))

    def tile(self, lat: int, lon: int) -> _BakedTile | None:
        key = (lat, lon)
        if key not in self._tiles:
            self._tiles[key] = self._compose(lat, lon)
        return self._tiles[key]

    def _compose(self, lat: int, lon: int) -> _BakedTile | None:
        state, problems = frame_state(self.elevation_root, self.osm_root,
                                      lat, lon, self.icao)
        stem = state["tile_stem"]
        # ``_warm_tile`` / ``_may_warm`` are DELETED (spec §C.6, RULINGS
        # 2026-09-18b): the silent neighbour warm inside the auto-patch POOL
        # CHILD is what spent ~3 h on tile +38-010 fetching 17 never-asked-for
        # insets with no progress reaching the app.  Warming is now an
        # explicit, main-process act after an explicit user choice
        # (``O4_Vector_Map.ensure_tile_frame``, §D).  The owner's 2026-09-10
        # ruling it implemented is honoured there, not here.
        if problems and not self._is_declared(lat, lon):
            # CLASS M FAR SIDE — CONTEXT ONLY (§C.1, owner Q2 answer (a);
            # the coupling this admits is MEASURED and ACCEPTED, RULINGS
            # 2026-09-18h).  This cell carries no emitted airside of ours;
            # it is read for far-field context and for the far edge of a cut
            # seam band.  Never fetched, never a refusal: warm ⇒ compose as
            # usual; cold ⇒ whatever the base raster says; no base raster ⇒
            # None ⇒ ``z_many`` NaN ⇒ ``v.dem_z is None`` ⇒ ``seam_pins``
            # skips the vertex (no pin invented from nothing).
            note = ", ".join(problems)
            self.provenance[f"context_only:{stem}"] = note
            self._out(f"  [dem] production frame {stem} is NOT this build's "
                      f"tile and was not declared by a boundary choice — "
                      f"reading it CONTEXT-ONLY from disk, fetching nothing "
                      f"({note})")
            if not state["base_raster_present"]:
                self.provenance[f"tile:{stem}"] = "ABSENT"
                return None
        elif problems:
            self._degrade(stem, problems)
            if not state["base_raster_present"]:
                self.provenance[f"tile:{stem}"] = "ABSENT"
                return None
        if not self.core_hosted:
            self._ensure_core_path()
        import O4_Config_Utils as CFG
        import O4_OSM_Utils as OSM
        import O4_Vector_Map as VMAP
        tile = CFG.Tile(lat, lon, "")
        tile.read_from_config()
        # The install THIS build was handed: flat-site classification inside
        # the prep reads apt.dat/CIFP from it (a lane cfg ships both empty).
        tile.auto_patch_xplane_root = self.xplane_root
        dico = {}
        if state["airports_layer_present"]:
            layer = OSM.OSM_layer()
            OSM.OSM_queries_to_OSM_layer(VMAP.AIRPORTS_QUERIES, layer, lat, lon,
                                         ["all"], cached_suffix="airports")
            dico = VMAP.build_airports_dico(tile, layer)
        # THE PER-AIRPORT INSET CHECK, which needs the dico the first
        # frame_state call above could not have (the airports layer is
        # one of the things it judges).  A MISSING or STALE inset for
        # THIS airport is a cold frame exactly like a missing directory —
        # on a DECLARED tile.  Since the inset set follows its own
        # selection (spec §A.4), the box is only REQUIRED when the inset
        # mode admits this airport; a patched-but-not-inset airport solves
        # on the base raster and that is lawful, not cold (§A.6).
        expects_inset = self._expects_inset(tile)
        required_box = (self._required_inset_box(tile, dico)
                        if expects_inset else None)
        self.provenance["inset_selection"] = (
            "mode=%s admitted=%s"
            % (_inset_mode_of(tile), expects_inset))
        self._required_boxes[(lat, lon)] = required_box
        if required_box is not None:
            seen = set(problems)
            (state, problems) = frame_state(self.elevation_root, self.osm_root,
                                            lat, lon, self.icao, required_box)
            fresh = [p for p in problems if p not in seen]
            if fresh and not self._is_declared(lat, lon):
                self.provenance[f"context_only:{stem}"] = ", ".join(fresh)
            elif fresh:
                self._degrade(stem, fresh)
        dem = VMAP.compose_tile_dem_from_disk(tile, dico, write_alt_file=False)
        return self._bake(lat, lon, dem, stem, state, tile=tile,
                          airports_smoothed=len(dico), how="composed")

    def _required_inset_box(self, tile: _t.Any, dico: dict) -> tuple | None:
        """This airport's required inset extent, from the ENGINE's own
        arithmetic (``_airport_bounding_boxes``) — boundary bounds plus
        ``airport_elevation_inset_margin_m``.  ``None`` when the airports
        layer gave no boundary for it, which is not a cold frame: there
        is then nothing to require."""
        if not dico:
            return None
        try:
            import O4_Airport_Elevation_Insets as INSETS
            boxes = INSETS._airport_bounding_boxes(tile, dico)
        except Exception:
            return None
        wanted = self.icao.upper()
        for key, box in boxes.items():
            if str(key).upper() == wanted:
                return box
        return None

    def _is_declared(self, lat: int, lon: int) -> bool:
        """Is this cell one this build OWNS or was told to warm?

        The airport's own cell always is.  A neighbour is declared only by
        an explicit boundary choice (§C.3 ``"neighbour"``).  Everything
        else is class-M far side: context-only, never a refusal.
        """
        return (int(lat), int(lon)) in self.declared_tiles

    def _inset_selection_provenance(self, tile: _t.Any) -> str:
        return "mode=%s admitted=%s" % (_inset_mode_of(tile),
                                        self._expects_inset(tile))

    def _expects_inset(self, tile: _t.Any) -> bool:
        """Does the INSET selection admit this airport on this tile?

        §A.6 patch∖inset: an airport that is patched but outside the inset
        selection solves on the base raster WITHOUT meter-class data.  That
        is lawful — it is every no-coverage airport today — so a missing
        inset for it is not a frame problem and must not refuse or warm.
        """
        try:
            from auto_patch.selection import mode_admits, resolved_inset_mode

            return mode_admits(self.icao.upper(), resolved_inset_mode(tile))
        except Exception:                                # pragma: no cover
            return True

    def _adopt(self, lat: int, lon: int, dem: _t.Any) -> _BakedTile | None:
        """A seeded (host-prepared) tile raster: the same checks and the
        same provenance record as a lazy composition, minus the
        composition — the host's cfg values ride on the DEM object where
        it carries them."""
        state, problems = frame_state(self.elevation_root, self.osm_root,
                                      lat, lon, self.icao)
        stem = state["tile_stem"]
        if problems:
            self._degrade(stem, problems)
        return self._bake(lat, lon, dem, stem, state, tile=None,
                          airports_smoothed=None, how="host-seeded")

    def _bake(self, lat: int, lon: int, dem: _t.Any, stem: str, state: dict, *,
              tile: _t.Any, airports_smoothed: int | None, how: str) -> _BakedTile:
        arr = getattr(dem, "alt_dem", None)
        if arr is None or not arr.size or not np.any(arr):
            raise ColdDemFrame(f"production frame for {stem} is IDENTICALLY ZERO "
                               f"or empty — the base raster is missing")
        baked = list(getattr(dem, "airport_inset_provenance", None) or [])
        mine = [b for b in baked if str(b.get("icao", "")).upper() == self.icao.upper()]
        # THE BAKE'S OWN DECLARED DECLINATIONS (2026-09-18, LSGP/LSGY).
        # An inset holding < INSET_MIN_VALID_FRAC valid pixels is not
        # baked; the bake says so in its own line and records it on
        # ``airport_inset_nodata_refusals``.  That is a KNOWN, DECLARED
        # state — the opposite of the 2026-08-07 class this check
        # exists for, which is a bake that dropped a VALID inset and
        # said nothing.  So the check consults the RECORD instead of
        # re-inferring from the file's existence: LSGP's empty
        # swissALTI3D raster took the whole +46+006 tile down in app
        # 1.0.351 while the same build printed the declination.
        declined = [d for d in (getattr(dem, "airport_inset_nodata_refusals",
                                        None) or [])
                    if str(d.get("icao", "")).upper() == self.icao.upper()]
        if state["airport_inset"] and not mine and not declined:
            self._degrade(stem, [f"the bake reports NO inset for {self.icao} while "
                                 f"{state['airport_inset']} exists — the prep "
                                 f"degraded silently (2026-08-07 class)"])
        elif declined and not mine:
            self._out(f"  [dem] {self.icao}: the inset on disk is DECLARED EMPTY "
                      f"and was NOT baked ("
                      + "; ".join(f"{d.get('path') or d.get('provider')} "
                                  f"nodata {float(d.get('nodata_fraction', 1.0)):.4f}"
                                  for d in declined)
                      + f") — this airport solves on the BASE DEM.  Re-fetch it "
                        f"deliberately: --refresh-data dem")
        if state.get("airport_inset_declared_empty"):
            # The frame check's own wording of the same fact, kept on the
            # provenance so an arm can be read back without the log.
            self.provenance[f"inset_declared_empty:{stem}"] = \
                state["airport_inset_declared_empty"]
        self.provenance[f"tile:{stem}"] = (
            f"{how}: grid {dem.nxdem}x{dem.nydem}, baked_query={dem.baked_query_active}, "
            f"airports_smoothed={airports_smoothed if airports_smoothed is not None else '?'}, "
            f"insets=" + ",".join(f"{b.get('icao')}:{b.get('provider')}" for b in baked)
            + (", nodata_refused=" + ",".join(
                f"{d.get('icao')}:{os.path.basename(str(d.get('path', '?')))}"
                for d in declined) if declined else ""))
        self._record_inset_boxes(lat, lon, baked)
        if tile is not None:
            for k in ("apt_smoothing_pix", "apt_smoothing_auto", "working_grid_arc_seconds",
                      "airport_elevation_insets", "airport_elevation_inset_feather_m",
                      "elevation_level", "custom_dem", "fill_nodata"):
                value = getattr(tile, k, "")
                if k in _MODE_VALUED_KEYS:
                    value = normalize_mode(value, k)   # spec §A.5, row 26
                self.provenance[f"cfg:{k}"] = str(value)
        self._out(f"  [dem] production frame {stem}: {self.provenance[f'tile:{stem}']}")
        overlay = getattr(dem, "tile_overlay_provenance", None)
        return _BakedTile(lat, lon, arr, dem.x0, dem.x1, dem.y0, dem.y1,
                          inset_provenance=baked,
                          flat_site_provenance=list(
                              getattr(dem, "synthetic_flat_site_provenance", None) or []),
                          overlay_provenance=overlay if isinstance(overlay, dict) else None)

    @staticmethod
    def _box_text(box) -> str:
        return ",".join(f"{float(v):.6f}" for v in box) if box else "?"

    def _record_inset_boxes(self, lat: int, lon: int, baked: list) -> None:
        """Record, per BAKED inset of THIS airport, the three boxes and the
        scenery packs that served its mask — ADDITIVE frame metadata
        (owner ruling 3, conditional on digest neutrality).

        It buys COMPARABILITY between arms, not the re-cut test: the
        engine consults the manifest, never ``frame.json``.  Written as
        STRING values under ``inset:<ICAO>:<provider>``, the shape every
        other key in this dict already has, so no consumer sees a new
        type.  Proven not to move the artifact-ledger corpus stamp or the
        law-tables digest (``tests/test_harness.py``
        ``..._never_moves_a_frame_identity``): the stamp hashes
        ``dem_cache_before``, ``data_mounts`` and ``dem_frame_effective``,
        and this is none of them.

        Best-effort throughout: the frame record must never be the thing
        that fails a build.
        """
        required = self._required_boxes.get((lat, lon))
        for record in baked:
            icao = str(record.get("icao", ""))
            if icao.upper() != self.icao.upper():
                continue
            provider = str(record.get("provider", "?"))
            try:
                import O4_Airport_Elevation_Insets as INSETS
                import O4_File_Names as FNAMES
                path = FNAMES.airport_inset_dem(lat, lon, icao, provider)
                requested = INSETS.requested_inset_bounding_box(
                    lat, lon, icao, provider)
                delivered = INSETS.delivered_inset_bounding_box(path)
                packs = INSETS.recorded_footprint_packs(
                    lat, lon, icao, provider)
            except Exception:
                continue
            self.provenance[f"inset:{icao}:{provider}"] = (
                f"required={self._box_text(required)} "
                f"requested={self._box_text(requested)} "
                f"delivered={self._box_text(delivered)} "
                f"footprint_packs={'|'.join(packs) if packs else '?'}")

    def _degrade(self, stem: str, problems: list[str]) -> None:
        text = "\n  - ".join(problems)
        if not self.allow_degraded:
            # §C.6: nothing in the pool child warms any more, so the only
            # "we tried" this can report is an attempt ``ensure_tile_frame``
            # (§D, main process, after an explicit boundary choice) recorded
            # on the provenance.
            tried = self.provenance.get(f"warmed:{stem}")
            hint = (f"The build TRIED to warm it ({tried}) — check the "
                    f"network / Overpass and the engine log, then rebuild."
                    if tried else
                    "Warm the shared cache (build_airport.py --refresh-data ...), or pass "
                    "--allow-degraded-dem to measure in the degraded frame KNOWINGLY "
                    "(recorded in the provenance; authorises NO write).")
            raise ColdDemFrame(
                f"REFUSING: the production DEM frame for {stem} is COLD:\n  - {text}\n{hint}")
        prev = self.provenance.get("degraded", "")
        self.provenance["degraded"] = (prev + "; " if prev else "") + f"{stem}: " + \
            " | ".join(problems)
        self._out(f"  [dem] DEGRADED production frame {stem} (accepted by flag): {text}")


def load_production_dem(frame: Frame, icao: str, elevation_root: str,
                        osm_root: str, xplane_root: str, *,
                        allow_degraded: bool = False,
                        out: _t.Callable[[str], None] = print,
                        seed_tiles: _t.Mapping[tuple[int, int], _t.Any] | None = None,
                        core_hosted: bool = False) -> ProductionDem:
    """The production sampler, with the origin tile composed eagerly so a
    cold frame refuses at load time, not mid-planar-build (a seeded
    origin tile is adopted instead — see ``Inputs.production_dem_tiles``)."""
    dem = ProductionDem(frame, icao, elevation_root, osm_root, xplane_root,
                        allow_degraded=allow_degraded, out=out,
                        seed_tiles=seed_tiles, core_hosted=core_hosted)
    lat, lon = frame.origin
    dem.tile(int(math.floor(lat)), int(math.floor(lon)))
    return dem
