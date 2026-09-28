"""THE airport-selection predicates: ONE spelling of the mode filter.

Spec: ``docs/specs/insets-follow-patch-set-spec.md`` §A (rev 2), ruled by
``docs/RULINGS.md`` 2026-09-18b (insets entry) as amended by 18c and 18e.

Two independent settings select two independent populations, and both use
the SAME three-valued mode vocabulary:

* ``auto_patch``               → which airports get an auto-patch
* ``airport_elevation_insets`` → which airports get a lidar elevation inset

Before this module the mode filter was spelled inline in three places
(``driver.generate_auto_patches``, ``O4_Vector_Map.include_patches``) and
the inset set consulted nothing at all — which is how tile +38-010 spent
~3 h fetching ~190 MB insets for 17 name-keyed private strips of a tile
nobody was building (RULINGS 2026-09-18b).

PURITY: module level imports stdlib only.  Core modules
(``O4_Settings_Model``, ``O4_Cfg_Vars`` consumers, the insets module) import
the normalisers, so nothing here may drag the auto-patch pipeline in;
``auto_patch/__init__`` resolves ``generate_auto_patches`` lazily so that
``import auto_patch.selection`` does not import ``driver``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# THE MODE PREDICATES live in the CORE (``O4_Airport_Modes``, #59): the v2
# engine reads them too and may import nothing of ``auto_patch`` (v1).  They
# are re-exported here so every ``auto_patch.selection.<name>`` reader — and
# every test that monkeypatches one on this module — is unchanged.
from O4_Airport_Modes import (DEFAULT_MODE, LEGACY_FALSE, LEGACY_TRUE,  # noqa: F401
                              MODE_RANK, MODES, _ui_warn, inset_keys,
                              mode_admits, normalize_mode,
                              resolved_auto_patch_mode, resolved_inset_mode)


# ══════════════════════════════════════════════════════════════════════
# SELECTION 1 — the PATCH set (spec §A.3)
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class PatchCandidate:
    """One CIFP airport and what this tile build will do with it.

    ``disposition``:

    ``"patch"``
        this build will BUILD or REUSE an auto-patch (which of the two is
        the driver's up-to-date gate, not this selector's business);
    ``"manual"``
        a hand-written patch already covers the airport;
    ``"no_apt_dat"``
        CIFP lists it, no ENABLED apt.dat in the install defines it —
        skipped, never queued, never expected by the manifest (H1);
    ``"no_xplane_root"``
        the X-Plane root cannot be resolved from the CIFP path;
    ``"boundary_skipped"``
        its patch reaches into a 1° tile this build is not building and
        the boundary policy is "skip" (spec §C.3).

    Airports the MODE does not admit are not candidates at all.
    """

    icao: str
    cifp_file: str
    runways: dict = field(default_factory=dict)
    disposition: str = "patch"
    reason: str = ""
    #: The apt.dat this build WOULD read, resolved once here so the driver
    #: and its freshness gate never re-run the (apt.dat-scanning) selector.
    #: ADDITIVE to the spec's field list; nothing outside the engine sees it.
    apt_dat: str = ""


def select_patch_airports(tile, cifp_path: str, mode: str, *,
                          manual_icaos=(), boundary=None) -> list:
    """THE patch set for this tile: the driver loop's head, lifted whole.

    Same ORDER and same RESULT as the inline filter chain that lived in
    ``driver.generate_auto_patches`` (mode → manual → CIFP parse →
    in-tile → runway pairing → X-Plane root → apt.dat selection); the
    up-to-date REUSE decision deliberately stays in the driver, because
    reuse is about what is on disk in *this* tile's Patches dir, not about
    which airports this tile owns.

    ``mode == "None"`` returns ``[]`` WITHOUT touching the CIFP directory.

    *boundary*, when given, is ``callable(icao, runways) -> str | None``
    returning a reason when the airport's patch reaches a tile this build
    is not building (spec §C.3); the candidate is then
    ``"boundary_skipped"``.

    Pure apart from reading the CIFP files and the install's apt.dat: it
    downloads nothing, writes nothing and logs nothing (the driver owns
    the user-facing lines, so running the selector twice — the preflight
    and the build — never doubles the log).
    """
    mode = normalize_mode(mode, "auto_patch", warn=_ui_warn)
    if mode == "None":
        return []

    from . import build_support as _bs
    from . import cifp_reader as _cifp

    (airport_in_tile, discover_cifp_airports, parse_cifp_file,
     xplane_root_from_cifp_path) = (
        _cifp.airport_in_tile, _cifp.discover_cifp_airports,
        _cifp.parse_cifp_file, _cifp.xplane_root_from_cifp_path)
    pair_runways = _bs.pair_runways

    manual = {str(code).upper() for code in (manual_icaos or ())}
    tile_lat = int(getattr(tile, "lat"))
    tile_lon = int(getattr(tile, "lon"))

    out: list = []
    for (icao, filepath) in sorted(discover_cifp_airports(cifp_path).items()):
        if not mode_admits(icao, mode):
            continue
        if icao in manual:
            out.append(PatchCandidate(icao, filepath, {}, "manual",
                                      "a manual patch covers this airport"))
            continue
        runways = parse_cifp_file(filepath)
        if not runways:
            continue
        if not airport_in_tile(runways, tile_lat, tile_lon):
            continue
        if not pair_runways(runways):
            continue
        xp_root = xplane_root_from_cifp_path(cifp_path)
        if xp_root is None:
            out.append(PatchCandidate(
                icao, filepath, runways, "no_xplane_root",
                "cannot resolve X-Plane root from CIFP path"))
            continue
        apt_dat = _bs._pick_best_apt_dat_against_osm(xp_root, icao)
        if apt_dat is None:
            out.append(PatchCandidate(
                icao, filepath, runways, "no_apt_dat",
                "no enabled scenery pack defines this airport"))
            continue
        candidate = PatchCandidate(icao, filepath, runways, "patch", "",
                                   apt_dat)
        reason = _ask_boundary(boundary, icao, runways, candidate)
        if reason:
            out.append(PatchCandidate(icao, filepath, runways,
                                      "boundary_skipped", reason,
                                      apt_dat))
            continue
        out.append(candidate)
    return out


def _ask_boundary(boundary, icao, runways, candidate):
    """Call a ``boundary=`` callback, tolerating the 2-argument form.

    The decider the engine installs (:func:`boundary_skipper`) needs the
    CANDIDATE, because the ask geometry is read from its ``apt_dat``; a
    lab/test callback that only wants ``(icao, runways)`` still works.
    """
    if boundary is None:
        return None
    try:
        return boundary(icao, runways, candidate)
    except TypeError:
        return boundary(icao, runways)


def patch_set(selection) -> set:
    """The ICAOs a selection says this build patches (builds OR reuses)."""
    return {c.icao for c in (selection or []) if c.disposition == "patch"}


# ══════════════════════════════════════════════════════════════════════
# THE AIRSIDE CLAIM and the class S / M decision (spec §C.1, rev 3;
# RULINGS 2026-09-18h ruled the far-side leak ACCEPTED for class M,
# 2026-09-18i confirmed class S ALWAYS prompts)
# ══════════════════════════════════════════════════════════════════════
#: Default reach when no law table is at hand (tools, unit fixtures).  The
#: LAW value is ``law.tables.emit.seam.ask_reach_m`` and wins wherever a
#: Law object exists; this constant exists so the geometry helpers stay
#: pure and importable without the law tables.
ASK_REACH_M_DEFAULT = 150.0


def ask_reach_m(law=None) -> float:
    """The law's ``emit.seam.ask_reach_m``, else the module default."""
    if law is None:
        try:
            from auto_patch_v2.law import tables as _tables

            law = _tables.load_default()
        except Exception:                                # pragma: no cover
            return ASK_REACH_M_DEFAULT
    try:
        return float(law.tables.emit.seam.ask_reach_m)
    except Exception:                                    # pragma: no cover
        return ASK_REACH_M_DEFAULT


def airside_claim(apt_dat: str, icao: str):
    """THE ask geometry: the airport's OWN AIRSIDE, in ``(lon, lat)``.

    Union of apt.dat **row 100** runway rectangles and **row 110** airside
    pavement outer rings, read through v2's own apt.dat reader (never a
    second parser — spec §C.2).  ``None`` when the file carries no such
    geometry.

    DELIBERATELY EXCLUDED, and this is the whole point of rev 3:

    * **row 130 boundary** — a fence line around grass is not "the
      airport crossing"; with no pavement across the line there is no
      half-built airside.
    * **all OSM geometry** — it is absent on exactly the never-built
      tiles where the question matters, and it would make the preflight
      and the build-time check disagree.
    * the **groundside tail** (service roads, parking, access roads,
      tunnel ramps) — measured at 1,110-1,494 m past the airport at CYXY
      and HECA, with no meaningful bound.  It is what refuted rev 2's
      single scalar ``R_patch``.

    UNBUFFERED: callers buffer by :func:`ask_reach_m` (``R_air``).
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from auto_patch_v2.airport.apt_dat import (parse_airport_block,
                                               read_airport_block)

    block = read_airport_block(apt_dat, icao)
    if not block:
        return None
    parsed = parse_airport_block(block)
    parts = []
    for runway in parsed.runways:
        ((_da, lat_a, lon_a, _xa, _oa), (_db, lat_b, lon_b, _xb, _ob)) = \
            runway.ends
        half = float(runway.width_m or 60.0) / 2.0
        # Rectangle in DEGREES, widened by the runway half-width converted
        # at this runway's own latitude — the claim is compared against
        # integer lat/lon lines, so degrees are the natural space.
        (dlat, dlon) = _degrees_per_metre(0.5 * (lat_a + lat_b))
        (dx, dy) = (lon_b - lon_a, lat_b - lat_a)
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        (nx, ny) = (-dy / length * half * dlon, dx / length * half * dlat)
        parts.append(Polygon([
            (lon_a + nx, lat_a + ny), (lon_b + nx, lat_b + ny),
            (lon_b - nx, lat_b - ny), (lon_a - nx, lat_a - ny)]))
    for pavement in parsed.pavements:
        if not pavement.rings or len(pavement.rings[0]) < 3:
            continue
        polygon = Polygon(list(pavement.rings[0]))       # already (lon, lat)
        parts.append(polygon if polygon.is_valid else polygon.buffer(0))
    if not parts:
        return None
    claim = unary_union(parts)
    return claim if not claim.is_empty else None


def _degrees_per_metre(latitude: float):
    """``(degrees of latitude, degrees of longitude)`` per metre."""
    import math

    lat_m = 111132.0
    lon_m = max(111320.0 * math.cos(math.radians(latitude)), 1.0)
    return (1.0 / lat_m, 1.0 / lon_m)


def crossing_cells(claim, home_lat: int, home_lon: int,
                   reach_m: float = ASK_REACH_M_DEFAULT) -> list:
    """Which OTHER 1° cells the claim, buffered by *reach_m*, touches.

    Returns ``[((lat, lon), crossing_m), …]`` sorted, where ``crossing_m``
    is how far past the shared graticule line the buffered claim reaches,
    in metres.

    The cell edges are straight lines at integer lat/lon, so "does the
    buffered claim reach past this line" is decided EXACTLY by the claim's
    bounds — no polygon buffering, and no projection, is needed.
    """
    if claim is None or claim.is_empty:
        return []
    (west, south, east, north) = claim.bounds
    (dlat, dlon) = _degrees_per_metre(0.5 * (south + north))
    (margin_lat, margin_lon) = (reach_m * dlat, reach_m * dlon)
    (west, south) = (west - margin_lon, south - margin_lat)
    (east, north) = (east + margin_lon, north + margin_lat)
    import math

    out = {}
    for lat in range(int(math.floor(south)), int(math.floor(north)) + 1):
        for lon in range(int(math.floor(west)), int(math.floor(east)) + 1):
            if (lat, lon) == (home_lat, home_lon):
                continue
            # How far past the line shared with the home cell this cell is
            # reached into: the overlap of the buffered box with the cell.
            over_lat = min(north, lat + 1.0) - max(south, float(lat))
            over_lon = min(east, lon + 1.0) - max(west, float(lon))
            if over_lat <= 0.0 or over_lon <= 0.0:
                continue
            metres = max(
                0.0 if lat == home_lat else over_lat / dlat,
                0.0 if lon == home_lon else over_lon / dlon,
            )
            out[(lat, lon)] = round(metres, 1)
    return sorted(out.items())


def airport_boundary_class(candidate, home_lat: int, home_lon: int, *,
                           reach_m: float = ASK_REACH_M_DEFAULT) -> tuple:
    """``(cls, [(lat, lon), …], crossing_m)`` for ONE patch candidate.

    ``cls`` is ``"S"`` when the buffered airside claim touches another 1°
    cell (spec §C.1) and ``"M"`` otherwise — including an airport whose
    groundside roads, parking, inset box or DEM window cross the line.

    THE ONE FUNCTION the preflight (§C.2) and the build-time check (§C.3)
    both call, on the SAME apt.dat (``PatchCandidate.apt_dat``, chosen by
    the 17a selector), so they agree by construction.  A candidate with no
    apt.dat gets no patch and therefore never asks.
    """
    if not getattr(candidate, "apt_dat", ""):
        return ("M", [], 0.0)
    claim = airside_claim(candidate.apt_dat, candidate.icao)
    if claim is None:
        return ("M", [], 0.0)
    crossings = crossing_cells(claim, home_lat, home_lon, reach_m)
    if not crossings:
        return ("M", [], 0.0)
    return ("S", [cell for (cell, _m) in crossings],
            max(m for (_cell, m) in crossings))


def boundary_skipper(home_lat: int, home_lon: int, *, is_cold,
                     reach_m: float = ASK_REACH_M_DEFAULT,
                     record=None):
    """The ``boundary=`` callback :func:`select_patch_airports` takes.

    Returns a reason (⇒ disposition ``"boundary_skipped"``) for a CLASS S
    airport at least one of whose neighbour cells is COLD; ``None``
    otherwise.  *is_cold* is ``callable((lat, lon)) -> bool`` — an
    already-built neighbour asks nothing.  *record*, when given, is
    appended ``(icao, cls, cold_neighbours, crossing_m)`` per candidate,
    which is how the preflight reuses this same pass to BUILD the dialog's
    list instead of skipping anything.
    """
    def decide(icao, runways, candidate=None):
        if candidate is None:
            return None
        (cls, cells, crossing_m) = airport_boundary_class(
            candidate, home_lat, home_lon, reach_m=reach_m)
        cold = [cell for cell in cells if is_cold(cell)] if cls == "S" else []
        if record is not None:
            record.append((icao, cls, list(cold), crossing_m))
        if not cold:
            return None
        names = ", ".join("%+03d%+04d" % cell for cell in cold)
        return ("crosses into tile %s (not built) — patch SKIPPED by your "
                "boundary choice; build %s with this tile to patch it"
                % (names, names))

    return decide
