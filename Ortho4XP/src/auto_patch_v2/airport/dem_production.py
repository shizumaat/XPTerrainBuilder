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

import math
import os
import sys
import typing as _t
from pathlib import Path

import numpy as np

from ..model.frame import Frame
from .dem import hgt_name, resolve_dem_files

__all__ = ["ColdDemFrame", "ProductionDem", "load_production_dem",
           "engine_root", "frame_state"]

#: The engine tree this package lives in (``src/auto_patch_v2/airport``).
ENGINE_DIR = Path(__file__).resolve().parents[3]


class ColdDemFrame(RuntimeError):
    """The production frame cannot be composed from cached disk state."""


def engine_root() -> Path:
    return ENGINE_DIR


def frame_state(elevation_root: str, osm_root: str, lat: int, lon: int,
                icao: str) -> tuple[dict, list[str]]:
    """Filesystem-only cache warmth for one tile (``dem_cache_state``):
    ``(state, problems)`` — pure path inspection, never a fetch."""
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
    if not state["airport_insets_present"]:
        problems.append(f"NO airport elevation insets dir {ins_dir} — the base "
                        f"surface only, while production bakes insets "
                        f"(--refresh-data dem)")
    return state, problems


class _BakedTile:
    """One tile's baked working raster and the mesh's bilinear query
    (``O4_DEM_Utils.DEM.alt_vec_baked``, reproduced vectorised so the
    array is read once and the core object is released)."""

    def __init__(self, lat: int, lon: int, alt_dem: np.ndarray,
                 x0: float, x1: float, y0: float, y1: float) -> None:
        self.lat, self.lon = lat, lon
        self.alt = np.asarray(alt_dem, dtype=np.float64)
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1

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


class ProductionDem:
    """``DemSample`` over the production tile rasters (one per tile,
    composed on first touch)."""

    def __init__(self, frame: Frame, icao: str, elevation_root: str,
                 osm_root: str, xplane_root: str, *, allow_degraded: bool = False,
                 out: _t.Callable[[str], None] = print,
                 seed_tiles: _t.Mapping[tuple[int, int], _t.Any] | None = None,
                 core_hosted: bool = False) -> None:
        self.frame = frame
        self.icao = icao
        self.elevation_root = elevation_root
        self.osm_root = osm_root
        self.xplane_root = xplane_root
        self.allow_degraded = bool(allow_degraded)
        self.core_hosted = bool(core_hosted)
        self._out = out
        self.provenance: dict[str, str] = {"frame": "production",
                                           "query": "bilinear on the baked working grid"}
        self._tiles: dict[tuple[int, int], _BakedTile | None] = {}
        from pyproj import Transformer  # local: geodesy stays in the loaders
        self._inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)
        self._fwd = Transformer.from_crs("EPSG:4326", frame.crs, always_xy=True)
        self._check_corpus()
        # THE HOST'S OWN RASTER, REUSED (a tile build's ``tile.dem``): the
        # frame of record for every patch node the mesh will sample, so
        # it is adopted as-is — never re-composed — and its bake
        # provenance is recorded the same way a lazy composition's is.
        for (lat, lon), dem in sorted((seed_tiles or {}).items()):
            self._tiles[(int(lat), int(lon))] = self._adopt(int(lat), int(lon), dem)

    # ── DemSample protocol ──────────────────────────────────────────
    def z(self, x: float, y: float) -> float:
        return float(self.z_many(np.array([x]), np.array([y]))[0])

    def bounds(self) -> tuple[float, float, float, float]:
        lat, lon = self.frame.origin
        t0, t1 = math.floor(lat), math.floor(lon)
        xs, ys = self._fwd.transform([t1, t1 + 1, t1, t1 + 1],
                                     [t0, t0, t0 + 1, t0 + 1])
        return (min(xs), min(ys), max(xs), max(ys))

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
        if problems:
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
        dem = VMAP.compose_tile_dem_from_disk(tile, dico, write_alt_file=False)
        return self._bake(lat, lon, dem, stem, state, tile=tile,
                          airports_smoothed=len(dico), how="composed")

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
        if state["airport_inset"] and not mine:
            self._degrade(stem, [f"the bake reports NO inset for {self.icao} while "
                                 f"{state['airport_inset']} exists — the prep "
                                 f"degraded silently (2026-08-07 class)"])
        self.provenance[f"tile:{stem}"] = (
            f"{how}: grid {dem.nxdem}x{dem.nydem}, baked_query={dem.baked_query_active}, "
            f"airports_smoothed={airports_smoothed if airports_smoothed is not None else '?'}, "
            f"insets=" + ",".join(f"{b.get('icao')}:{b.get('provider')}" for b in baked))
        if tile is not None:
            for k in ("apt_smoothing_pix", "apt_smoothing_auto", "working_grid_arc_seconds",
                      "airport_elevation_insets", "airport_elevation_inset_feather_m",
                      "elevation_level", "custom_dem", "fill_nodata"):
                self.provenance[f"cfg:{k}"] = str(getattr(tile, k, ""))
        self._out(f"  [dem] production frame {stem}: {self.provenance[f'tile:{stem}']}")
        return _BakedTile(lat, lon, arr, dem.x0, dem.x1, dem.y0, dem.y1)

    def _degrade(self, stem: str, problems: list[str]) -> None:
        text = "\n  - ".join(problems)
        if not self.allow_degraded:
            raise ColdDemFrame(
                f"REFUSING: the production DEM frame for {stem} is COLD:\n  - {text}\n"
                f"Warm the shared cache (build_airport.py --refresh-data ...), or pass "
                f"--allow-degraded-dem to measure in the degraded frame KNOWINGLY "
                f"(recorded in the provenance; authorises NO write).")
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
