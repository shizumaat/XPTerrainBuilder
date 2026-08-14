"""WHERE IS AN OBJECT PACK'S RENDER DATUM, and is it in the solve?

The question this answers, for one scenery pack: every terrain-relative
DSF object renders its ``y = 0`` plane at

    mesh(placement.lat, placement.lon) + above_ground_level_metres

(``object_anchor.py:2411-2432``), and its ground-contact base is that
plus the AUTHORED ``base_y``.  So the elevation an object is drawn at is
governed by ONE point — its placement ANCHOR — and by whatever surface
the built mesh carries there.  Two facts about that point decide whether
any pad design can reach it, and neither is guessable from a pack's
name:

  * **Is it SHARED?**  Packs are commonly authored around one datum for
    hundreds of resources (RULINGS / memory "shared-datum pack
    authoring"), so one mesh sample can govern a whole airport's
    objects.  This tool groups placements by ``(lat, lon, AGL)`` and
    reports how many resources, ``.anchor_bak`` BAKED resources and pad
    REQUESTS hang off each datum.
  * **Is it IN THE SOLVE?**  A datum standing inside an emitted patch
    shape has its mesh value authored by our own solved surface; a datum
    in the gap between shapes is draped terrain the patch does not
    author.  The tool answers this against a real emitted patch, per
    datum, with the distance to the nearest emitted shape when the
    answer is no.

With ``--mesh`` (repeatable, a built ``Data+XX+YYY.mesh``) it also reads
the datum's ACTUAL rendered ground, and with ``--tile-lat/--tile-lon``
the auto-patch DEM at the same point — the two numbers whose difference
is the error any PRE-SOLVE design must absorb at that datum.  Several
``--mesh`` arguments give the datum's build-to-build drift, which is the
determinism question asked at the one point that matters.

It measures nothing itself: placements come from
``obj8_reader.read_dsf_object_placements`` through
``dsf_reader._load_dsf_text``, the patch through ``check_grade._parse_osm``
(the harness library), the DEM through ``elevation._load_airport_dem`` /
``_sample_dem`` — production's own readers, so a number here and a number
inside a build mean the same thing.

GUARDED.  Reading the DEM runs production's whole DEM prep, which can
write the shared data repo; the run arms the harness's own composition
(``build_airport.arm_shared_repo_protection``) and reports the guard
frame, exactly as ``tools/object_pad_evidence_report.py`` does.  Without
``--tile-lat/--tile-lon`` nothing is read that could write and the arming
is skipped.

Usage:
    venv/bin/python tools/object_pad_anchor_report.py \\
        --dsf "<pack>/Earth nav data/+30+030/+30+031.dsf" \\
        --patch Patches/+30+030/+30+031/HECA_auto.patch.osm \\
        [--sidecar Patches/+30+030/+30+031/o4_object_foot_pads.json] \\
        [--icao HECA] [--pack-root "<pack>"] \\
        [--tile-lat 30 --tile-lon 31] \\
        [--mesh /path/Data+30+031.mesh]... [--limit 12] [--json PATH]

BUILD-TIME IMPACT: none — a report-only tool, imported by nothing in
``src/``.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "src", _ROOT, _ROOT / "tests", _ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

ARTIFACT_DIR = Path(os.environ.get("O4_ARTIFACT_DIR", "/tmp/harness"))

#: A patch role whose shapes are OBJECT PADS is never a HOST: a pad is
#: what the coupling would place, so a datum standing on one is
#: self-referential rather than hosted.  Prefix-matched, because the pad
#: family spells itself ``object_pad`` / ``object_pad_blend``.
PAD_ROLE_PREFIX = "object_pad"


def role_is_solve_member(role) -> bool:
    """Does this emitted role carry SOLVE VARIABLES?

    Read from ``solver_primitives.PAVEMENT_ROLES`` — the solve's own node
    admission set — never re-listed here.  The distinction matters and is
    not visible in a patch: a datum standing on an APRON stands on solved
    variables, while one standing on a ``graded_strip`` stands on a SOFT
    RECEIVER (``layout.SOFT_RECEIVER_ROLES``), an emitted surface that
    ADOPTS its values post-solve.  Both carry the mesh value the renderer
    reads; only the first offers a node a constraint could be minted
    against.
    """
    from auto_patch.elevation_per_surface.solver_primitives import (
        PAVEMENT_ROLES)
    return role in PAVEMENT_ROLES


def _harness_build_module():
    sys.path.insert(0, str(_ROOT / "tools" / "harness"))
    import build_airport as build_mod  # noqa: E402
    return build_mod


# ── pure readers (the twin's surface) ─────────────────────────────────

def patch_rings(patch_path) -> list:
    """``[(role, ref, Polygon in LON/LAT, per-vertex alts | None)]``.

    Parsed with ``check_grade._parse_osm`` — the harness library, so this
    tool sees exactly the rings the census sees, and the altitudes are
    the census's own per-vertex derivation (``alt_abs`` nodes, the
    ``node_altitudes`` / high-low way forms).  Degenerate rings (fewer
    than 4 node references, unresolvable ids, empty polygons) are
    skipped, never repaired into something the patch does not contain.
    """
    from shapely.geometry import Polygon
    import check_grade as CG
    nodes, ways = CG._parse_osm(Path(patch_path))
    out = []
    for way in ways:
        pts = []
        for nid in way.nids:
            node = nodes.get(nid)
            if node is None:
                pts = []
                break
            pts.append((node[1], node[0]))     # _parse_osm stores (lat, lon)
        if len(pts) < 4:
            continue
        try:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception:
            continue
        if poly.is_empty:
            continue
        alts = list(way.elevs) if getattr(way, "elevs", None) else None
        if alts is not None and len(alts) < len(pts):
            alts = None
        # The RAW ring travels beside the polygon: ``buffer(0)`` repairs
        # a self-touching ring by changing its vertices, and an altitude
        # list paired with repaired coordinates is a silent mis-join.
        out.append((way.role, way.ref, poly, alts, pts))
    return out


def patch_shapes(patch_path) -> list:
    """``[(role, ref, shapely Polygon in LON/LAT)]`` for an emitted patch.

    The elevation-free view of :func:`patch_rings` — one parse, one ring
    derivation, two shapes of answer.
    """
    return [(role, ref, poly) for (role, ref, poly, _alts, _pts)
            in patch_rings(patch_path)]


def _metre_frame(lat0: float, lon0: float):
    """``ll_to_m(lat, lon)`` for a local frame anchored at (lat0, lon0).

    The mesher triangulates in ``(lon * cos(lat0), lat)``
    (``O4_Mesh_Utils``' ``VECT.scalx``) and a Delaunay triangulation is
    invariant under UNIFORM scaling, so this frame — that one times
    ~111320 — triangulates identically.  It is the same frame
    ``PatchGroundField`` gets from a layout in production, which is why
    the tool and the build cannot disagree about a face.
    """
    metres_per_degree = 111320.0
    cos_lat = math.cos(math.radians(lat0))

    def ll_to_m(lat: float, lon: float):
        return ((lon - lon0) * metres_per_degree * cos_lat,
                (lat - lat0) * metres_per_degree)

    return ll_to_m


class _OutermostField:
    """A sensitivity arm: the LARGEST covering shape decides, not the
    smallest.  It wraps a built field rather than rebuilding one, so the
    two arms differ in exactly one decision and nothing else."""

    def __init__(self, field) -> None:
        self._field = field

    def value_at(self, x: float, y: float):
        from shapely.geometry import Point
        rows = self._field._rows
        point = Point(x, y)
        covering = [i for i in range(len(rows)) if rows[i][1].covers(point)]
        if not covering:
            return None, None
        index = max(covering, key=lambda i: rows[i][1].area)
        saved = self._field.host_index
        self._field.host_index = lambda _x, _y: index
        try:
            return self._field.value_at(x, y)
        finally:
            self._field.host_index = saved


def patch_ground_field(shapes, ll_to_m):
    """A :class:`auto_patch.patch_ground.PatchGroundField` over a PATCH.

    Production builds the same field from the live layout
    (``patch_ground.field_from_layout``); this builds it from an emitted
    patch's rings so the two frames can be compared against a built
    mesh.  ONE evaluator, never a second copy of the rule.
    """
    from auto_patch.patch_ground import PatchGroundField
    rows = []
    for role, _ref, _poly, alts, pts in shapes:
        if alts is None:
            continue
        rows.append((role, [ll_to_m(y, x) for (x, y) in pts], alts))
    return PatchGroundField(rows)


def group_by_datum(placements) -> dict:
    """``{(lat, lon, agl): [placement]}`` — the pack's anchor datums.

    Keyed on the SPELLING the DSF carries (9 decimals, the canonical
    identity rule), never proximity-joined: two placements a millimetre
    apart are two datums, and calling them one would invent a sharing
    the pack does not have.
    """
    groups: dict = collections.defaultdict(list)
    for placement in placements:
        key = (round(placement.latitude, 9), round(placement.longitude, 9),
               float(placement.above_ground_level_metres))
        groups[key].append(placement)
    return dict(groups)


def host_index(shapes):
    """``(rows, STRtree)`` over the shapes that can HOST a datum.

    Pads are excluded here rather than at the query, so the index and the
    linear scan can never disagree about what a host is.
    """
    from shapely.strtree import STRtree
    rows = [(role, ref, poly) for (role, ref, poly) in shapes
            if not (role and str(role).startswith(PAD_ROLE_PREFIX))]
    return rows, (STRtree([p for (_r, _f, p) in rows]) if rows else None)


def classify_datum(lat: float, lon: float, shapes, index=None) -> tuple:
    """``(host_role, distance_to_nearest_shape_m)`` for one datum.

    ``host_role`` is the role of a NON-PAD emitted shape covering the
    point — the surface whose solved value the mesh keeps there — or
    ``None``.  The distance is to the nearest non-pad shape (0.0 when
    hosted), converted at the local metres-per-degree.

    ``index`` — an optional :func:`host_index` pair.  It changes the
    SEARCH, never the answer: the covering test and the nearest distance
    are the same two questions either way, and the linear scan stays the
    reference the twins pin.
    """
    from shapely.geometry import Point
    point = Point(lon, lat)
    metres_per_degree = 111320.0
    if index is not None and index[1] is not None:
        rows, tree = index
        for i in tree.query(point):
            if rows[i][2].covers(point):
                return rows[i][0], 0.0
        nearest = rows[tree.nearest(point)][2]
        return None, nearest.distance(point) * metres_per_degree
    best = math.inf
    for role, _ref, poly in shapes:
        if role and str(role).startswith(PAD_ROLE_PREFIX):
            continue
        if poly.covers(point):
            return role, 0.0
        distance = poly.distance(point)
        if distance < best:
            best = distance
    return None, (best * metres_per_degree if best < math.inf else math.inf)


def baked_resources(pack_root) -> set:
    """Pack-relative paths of every resource carrying an ``.anchor_bak``.

    The backup IS the record that the engine's y-bake rewrote that
    ``.obj`` (``object_rebake._rewrite_y_tokens``), so this set is the
    pack-pristine question's own population.
    """
    out = set()
    root = str(pack_root)
    for path in glob.glob(os.path.join(root, "**", "*.anchor_bak"),
                          recursive=True):
        rel = os.path.relpath(path[: -len(".anchor_bak")], root)
        out.add(rel.replace(os.sep, "/"))
    return out


def sidecar_requests(sidecar_path, icao) -> list:
    """The pad requests one airport raised, from the request sidecar."""
    record = json.loads(Path(sidecar_path).read_text())
    for airport in record.get("airports") or ():
        if airport.get("icao") == icao:
            return list(airport.get("requests") or ())
    return []


# ── collection ────────────────────────────────────────────────────────

def collect(dsf_path, patch_path, *, sidecar_path=None, icao=None,
            pack_root=None, tile_lat=None, tile_lon=None, meshes=(),
            xplane_root=None, out_dir=ARTIFACT_DIR, eval_patch=False,
            extra_patches=(), sensitivity=False) -> dict:
    """Read the pack, the patch and (optionally) the DEM + meshes.

    ``eval_patch`` adds each datum's PATCH-EVALUATED ground — what
    ``auto_patch.patch_ground`` says the emitted surface carries there —
    and, when a mesh is also given, the residual against the mesh the
    same patch produced.  That pair is the emission-time design's
    pre-registered premise test.  ``extra_patches`` are the OTHER
    patches of the same tile: the mesher triangulates all of them at
    once, so a datum may be hosted by a neighbouring airport's shape.
    """
    from auto_patch import dsf_reader, obj8_reader

    guard_frame = {"armed": False}
    if tile_lat is not None and tile_lon is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        build_mod = _harness_build_module()
        guard, redirects = build_mod.arm_shared_repo_protection(
            _ROOT, out_dir, f"padanchor_{icao or 'pack'}")
        guard_frame = {"armed": True, "redirects": bool(redirects)}
    else:
        guard = None

    lines = dsf_reader._load_dsf_text(str(dsf_path), None)
    placements = obj8_reader.read_dsf_object_placements(
        lines,
        accept_resource=lambda r: r.lower().endswith(".obj"),
        include_object_msl=True,
    )
    rings = patch_rings(patch_path)
    for extra in (extra_patches or ()):
        rings.extend(patch_rings(extra))
    shapes = [(role, ref, poly) for (role, ref, poly, _a, _p) in rings]
    groups = group_by_datum(placements)

    baked = baked_resources(pack_root) if pack_root else set()
    requests = (sidecar_requests(sidecar_path, icao)
                if (sidecar_path and icao) else [])
    # The anchor a request's resource renders from: object_anchor builds
    # ``{p.resource_path: p for p in pool.placements}``, a comprehension,
    # so the LAST placement of a resource wins.  Spelled the same way
    # here rather than "the nearest placement", which would be a
    # proximity join the identity law forbids.
    anchor_of_resource = {}
    for placement in placements:
        anchor_of_resource[placement.resource_path] = placement
    requests_by_datum: dict = collections.Counter()
    for request in requests:
        placement = anchor_of_resource.get(request.get("resource_path"))
        if placement is None:
            continue
        requests_by_datum[(round(placement.latitude, 9),
                           round(placement.longitude, 9),
                           float(placement.above_ground_level_metres))] += 1

    dem = None
    if guard is not None:
        from auto_patch import elevation
        with guard:
            dem = elevation._load_airport_dem(
                tile_lat + 0.5, tile_lon + 0.5, override_dem=None,
                xplane_root=xplane_root)
        guard_frame["blocked"] = [str(b) for b in guard.blocked]
        guard_frame["lock_churn"] = len(guard.lock_churn)

    samplers = []
    if meshes:
        from mesh_elevation_sampler import MeshElevationSampler
        lats = [k[0] for k in groups]
        lons = [k[1] for k in groups]
        bounds = (min(lons) - 0.01, min(lats) - 0.01,
                  max(lons) + 0.01, max(lats) + 0.01)
        samplers = [MeshElevationSampler(m, bounds) for m in meshes]

    field = ll_to_m = None
    arms: dict = {}
    if eval_patch:
        lat0 = sum(k[0] for k in groups) / max(1, len(groups))
        lon0 = sum(k[1] for k in groups) / max(1, len(groups))
        ll_to_m = _metre_frame(lat0, lon0)
        field = patch_ground_field(rings, ll_to_m)
        if sensitivity:
            # ARM 1 — the FRAME.  Delaunay is invariant under uniform
            # scaling but not under the longitude stretch, so evaluating
            # in raw (lon, lat) is a different triangulation of the same
            # ring.  If the two agree, the frame is not load-bearing at
            # these datums; if they do not, the metre frame is the one
            # that matches the mesher and this arm says by how much.
            arms["raw_lonlat_frame"] = (
                patch_ground_field(rings, lambda la, lo: (lo, la)),
                lambda la, lo: (lo, la))
            # ARM 2 — the HOST CHOICE.  Nested rings make "innermost"
            # a decision; the outermost covering shape is the other
            # answer the same geometry admits.
            arms["outermost_host"] = (
                _OutermostField(patch_ground_field(rings, ll_to_m)),
                ll_to_m)

    index = host_index(shapes)
    rows = []
    for key, members in groups.items():
        lat, lon, agl = key
        host, distance = classify_datum(lat, lon, shapes, index)
        resources = {p.resource_path for p in members}
        dem_value = None
        if dem is not None:
            from auto_patch import elevation
            dem_value = elevation._sample_dem(dem, tile_lat, tile_lon,
                                              lat, lon)
        patch_value = None
        arm_values = {}
        if field is not None:
            x, y = ll_to_m(lat, lon)
            patch_value, _role = field.value_at(x, y)
            for name, (arm_field, arm_frame) in arms.items():
                ax, ay = arm_frame(lat, lon)
                arm_values[name] = arm_field.value_at(ax, ay)[0]
        rows.append({
            "patch_m": patch_value,
            "arm_m": arm_values,
            "lat": lat, "lon": lon, "agl": agl,
            "placements": len(members),
            "resources": len(resources),
            "baked_resources": len(resources & baked),
            "pad_requests": int(requests_by_datum.get(key, 0)),
            "host_role": host,
            "host_is_solve_member": (role_is_solve_member(host)
                                     if host else False),
            "distance_to_patch_m": (None if distance == math.inf
                                    else round(distance, 3)),
            "dem_m": dem_value,
            "mesh_m": [s.elevation_at(lat, lon) for s in samplers],
        })
    rows.sort(key=lambda r: (-r["pad_requests"], -r["baked_resources"],
                             -r["placements"]))
    return {
        "dsf": str(dsf_path), "patch": str(patch_path), "icao": icao,
        "meshes": list(meshes), "guard": guard_frame,
        "n_placements": len(placements), "n_resources": len(
            {p.resource_path for p in placements}),
        "n_baked_resources": len(baked),
        "n_requests": len(requests),
        "n_patch_shapes": len(shapes),
        "rows": rows,
    }


# ── rendering ─────────────────────────────────────────────────────────

def render(record, limit=12) -> None:
    rows = record["rows"]
    print(f"pack {record['dsf']}")
    print(f"patch {record['patch']}  ({record['n_patch_shapes']} shapes)")
    if record["guard"].get("armed"):
        print(f"guard: blocked={len(record['guard'].get('blocked', []))} "
              f"lock_churn={record['guard'].get('lock_churn')}")
    print(f"placements {record['n_placements']} over "
          f"{record['n_resources']} resources and {len(rows)} ANCHOR DATUMS; "
          f"baked resources {record['n_baked_resources']}; "
          f"pad requests {record['n_requests']}")

    n_mesh = len(record["meshes"])
    header = (f"{'datum (lat,lon)':<28}{'AGL':>7}{'place':>7}{'res':>6}"
              f"{'baked':>7}{'reqs':>7}  {'host':<22}{'d(m)':>9}")
    if record.get("rows") and record["rows"][0]["dem_m"] is not None:
        header += f"{'DEM':>10}"
    has_patch = any(r.get("patch_m") is not None for r in rows)
    if has_patch:
        header += f"{'PATCH':>10}"
    header += "".join(f"{'mesh'+str(i+1):>10}" for i in range(n_mesh))
    if n_mesh and record.get("rows") and record["rows"][0]["dem_m"] is not None:
        header += f"{'mesh1-DEM':>11}"
    print(header)
    for row in rows[:limit]:
        line = (f"({row['lat']:.7f},{row['lon']:.7f})"
                f"{row['agl']:>7.2f}{row['placements']:>7}"
                f"{row['resources']:>6}{row['baked_resources']:>7}"
                f"{row['pad_requests']:>7}  "
                f"{((row['host_role'] + (' [solve]' if row.get('host_is_solve_member') else ' [soft]')) if row['host_role'] else '— UNHOSTED'):<28}"
                f"{(row['distance_to_patch_m'] if row['distance_to_patch_m'] is not None else float('nan')):>9.1f}")
        if row["dem_m"] is not None:
            line += f"{row['dem_m']:>10.3f}"
        if has_patch:
            line += (f"{row['patch_m']:>10.3f}"
                     if row.get("patch_m") is not None else f"{'-':>10}")
        for value in row["mesh_m"]:
            line += (f"{value:>10.3f}" if value is not None
                     else f"{'-':>10}")
        if n_mesh and row["dem_m"] is not None and row["mesh_m"][0] is not None:
            line += f"{row['mesh_m'][0] - row['dem_m']:>11.3f}"
        print(line)

    hosted_rows = [r for r in rows if r["host_role"]]
    solve_rows = [r for r in hosted_rows if r.get("host_is_solve_member")]
    total_req = sum(r["pad_requests"] for r in rows)
    total_baked = sum(r["baked_resources"] for r in rows)
    print()
    print("COUPLABLE POPULATION — a coupling needs the datum's ground to be "
          "a SOLVE variable:")
    print(f"  {'':<26}{'hosted (any emitted shape)':>28}"
          f"{'on a SOLVE role':>18}")
    print(f"  {'datums':<26}{len(hosted_rows):>18} /{len(rows):>8}"
          f"{len(solve_rows):>18}")
    print(f"  {'pad requests':<26}"
          f"{sum(r['pad_requests'] for r in hosted_rows):>18} /{total_req:>8}"
          f"{sum(r['pad_requests'] for r in solve_rows):>18}")
    print(f"  {'baked resources':<26}"
          f"{sum(r['baked_resources'] for r in hosted_rows):>18} "
          f"/{total_baked:>8}"
          f"{sum(r['baked_resources'] for r in solve_rows):>18}")
    if n_mesh > 1:
        drift = [max(abs(r["mesh_m"][i] - r["mesh_m"][i - 1])
                     for i in range(1, n_mesh))
                 for r in rows
                 if all(v is not None for v in r["mesh_m"])]
        if drift:
            print(f"  datum build-to-build drift, max over datums: "
                  f"{max(drift):.4f} m")
    render_premise(record)


def _percentile(values, fraction: float) -> float:
    """The ``fraction`` percentile by nearest-rank on a sorted list."""
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    rank = max(0, min(len(ordered) - 1,
                      int(math.ceil(fraction * len(ordered))) - 1))
    return ordered[rank]


def premise_rows(record) -> dict:
    """The PREMISE TEST populations: patch-evaluated vs mesh, by hosting.

    A datum is HOSTED when an emitted non-pad shape covers it; there the
    patch authors the mesh value and the emission-time design can be
    exact.  UNHOSTED datums stand on draped ambient DEM: the patch says
    nothing there and the design's fallback is the y-bake path, so their
    DEM-approximation error is reported separately and never mixed into
    the same percentile.
    """
    hosted, unhosted = [], []
    for row in record.get("rows") or ():
        mesh = (row.get("mesh_m") or [None])[0]
        if mesh is None:
            continue
        weight = int(row.get("pad_requests") or 0)
        if row.get("host_role") and row.get("patch_m") is not None:
            hosted.append((abs(row["patch_m"] - mesh), weight, row))
        elif not row.get("host_role") and row.get("dem_m") is not None:
            unhosted.append((abs(row["dem_m"] - mesh), weight, row))
    return {"hosted": hosted, "unhosted": unhosted}


def render_premise(record) -> None:
    """Print the premise test, or nothing when it was not measured."""
    populations = premise_rows(record)
    hosted, unhosted = populations["hosted"], populations["unhosted"]
    if not hosted and not unhosted:
        return
    print()
    print("PREMISE TEST — |patch-evaluated ground − mesh| at the datum:")
    for label, rows in (("hosted  (patch authors it)", hosted),
                        ("UNHOSTED (DEM read vs mesh)", unhosted)):
        if not rows:
            print(f"  {label:<28} no datums")
            continue
        residuals = [r[0] for r in rows]
        weighted = [r[0] for r in rows for _ in range(r[1])]
        print(f"  {label:<28} datums {len(rows):>6}  "
              f"p50 {_percentile(residuals, 0.50):.4f}  "
              f"p90 {_percentile(residuals, 0.90):.4f}  "
              f"max {max(residuals):.4f}")
        if weighted:
            print(f"  {'  ... weighted by requests':<28} "
                  f"reqs {len(weighted):>7}  "
                  f"p50 {_percentile(weighted, 0.50):.4f}  "
                  f"p90 {_percentile(weighted, 0.90):.4f}  "
                  f"max {max(weighted):.4f}")
    render_sensitivity(record)


def render_sensitivity(record) -> None:
    """How far each sensitivity arm moves the datum evaluation."""
    names = sorted({name for row in (record.get("rows") or ())
                    for name in (row.get("arm_m") or {})})
    if not names:
        return
    print()
    print("SENSITIVITY — |arm − the ruled evaluation| at hosted datums:")
    for name in names:
        deltas, weighted = [], []
        misses = 0
        for row in record["rows"]:
            if row.get("patch_m") is None:
                continue
            value = (row.get("arm_m") or {}).get(name)
            if value is None:
                misses += 1
                continue
            delta = abs(value - row["patch_m"])
            deltas.append(delta)
            weighted.extend([delta] * int(row.get("pad_requests") or 0))
        if not deltas:
            print(f"  {name:<24} no comparable datums")
            continue
        print(f"  {name:<24} datums {len(deltas):>6}  "
              f"p50 {_percentile(deltas, 0.50):.4f}  "
              f"p90 {_percentile(deltas, 0.90):.4f}  "
              f"max {max(deltas):.4f}  arm-miss {misses}")
        if weighted:
            print(f"  {'  ... weighted by requests':<24} "
                  f"reqs {len(weighted):>7}  "
                  f"p90 {_percentile(weighted, 0.90):.4f}  "
                  f"max {max(weighted):.4f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsf", required=True)
    parser.add_argument("--patch", required=True,
                        help="an EMITTED patch .osm — the shapes whose "
                             "solved values the mesh carries")
    parser.add_argument("--sidecar", default=None,
                        help="o4_object_foot_pads.json; with --icao it "
                             "attributes pad REQUESTS to their datum")
    parser.add_argument("--icao", default=None)
    parser.add_argument("--pack-root", default=None,
                        help="counts .anchor_bak BAKED resources per datum")
    parser.add_argument("--tile-lat", type=int, default=None)
    parser.add_argument("--tile-lon", type=int, default=None)
    parser.add_argument("--xplane-root", default=None)
    parser.add_argument("--mesh", action="append", default=[],
                        help="a built Data+XX+YYY.mesh (repeatable): the "
                             "datum's ACTUAL rendered ground, and with "
                             "two or more its build-to-build drift")
    parser.add_argument("--eval-patch", action="store_true",
                        help="also evaluate the PATCH's own ground at "
                             "each datum (auto_patch.patch_ground); with "
                             "--mesh this is the emission-time design's "
                             "premise test")
    parser.add_argument("--also-patch", action="append", default=[],
                        help="another patch of the SAME tile (repeatable) "
                             "— the mesher triangulates them together")
    parser.add_argument("--eval-sensitivity", action="store_true",
                        help="with --eval-patch, also evaluate under the "
                             "raw (lon,lat) frame and the outermost-host "
                             "choice — the design's sensitivity arms")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--json", default=None)
    parser.add_argument("--from-json", default=None,
                        help="render a previous --json dump; reads no "
                             "pack, arms nothing")
    arguments = parser.parse_args()

    if arguments.from_json:
        record = json.loads(Path(arguments.from_json).read_text())
    else:
        if (arguments.tile_lat is None) != (arguments.tile_lon is None):
            parser.error("--tile-lat and --tile-lon go together")
        xplane_root = arguments.xplane_root
        if xplane_root is None and arguments.tile_lat is not None:
            from conftest import xplane_root as _xplane_root
            xplane_root = _xplane_root()
        record = collect(
            arguments.dsf, arguments.patch,
            sidecar_path=arguments.sidecar, icao=arguments.icao,
            pack_root=arguments.pack_root,
            tile_lat=arguments.tile_lat, tile_lon=arguments.tile_lon,
            meshes=tuple(arguments.mesh), xplane_root=xplane_root,
            eval_patch=arguments.eval_patch,
            extra_patches=tuple(arguments.also_patch),
            sensitivity=arguments.eval_sensitivity)
        if arguments.json:
            Path(arguments.json).write_text(json.dumps(record, indent=1))
    render(record, arguments.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
