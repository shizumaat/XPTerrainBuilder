"""CROSS-PLATFORM STAGE DIGESTS (lane ``xplatdeterminism``).

The frozen release check (``scripts/check_frozen_tile.py --pass airport``)
solves CYXY inside each platform's bundle.  On run 35262948212 every
platform came back ``optimal`` and NONE of them agreed: the LP was
17151x1922 on Linux, 17128x1933 on macOS, 17039x1934 on Windows.  Rows and
columns differ BEFORE HiGHS is entered, so the divergence is upstream of
the solver and the release check could see only its shadow.

This module is the instrument that names WHICH STAGE first disagrees.  It
is a READ: it computes counts and canonical, order-free geometry digests
over the stage products ``pipeline/build.build`` already holds, and writes
them beside the v2 report as ``<ICAO>.xplat.json``.  It prices no law,
counts no defects and changes no geometry.

Two things make it usable across machines:

* **Order-free.**  Every digest is a sha256 over a SORTED list of
  canonical lines, so a different enumeration order alone cannot move it.
* **A ROUNDING LADDER.**  Every coordinate digest is taken at several
  decimal places (9, 6, 4, 2, 1 for the frame's metres).  A pair that
  differs at 9 dp but agrees at 4 dp is a last-ulp/libm difference; one
  that differs at every rounding is different topology.  Distinguishing
  those two is the whole point.

ARMED, NEVER DEFAULT: ``build`` calls :func:`stage_digests` only when
``pipeline/build.Config.xplat_dump`` is set — a SCHEMA, never an env gate
(``tests/auto_patch_v2/test_model.py`` forbids an environment read
anywhere in this package, and rightly: a gate the engine reads out of the air is a
second configuration nobody can see).  The v1 wrapper
``auto_patch/engine_v2.py`` is where the release check's
``O4_V2_XPLAT_DIGEST`` is read and turned into that flag.  Off by default
because the digests walk every vertex of every stage and a release check
is the only caller that wants that per build.
"""

from __future__ import annotations

import hashlib as _hash
import platform as _platform
import sys as _sys
import typing as _t

#: Decimal places the FRAME's metre coordinates are digested at.
METRE_DP = (9, 6, 4, 2, 1)

# ---------------------------------------------------------------- digests

def _fmt(value: _t.Any, dp: int) -> str:
    if isinstance(value, float):
        # ``%.*f`` of -0.0 is "-0.000"; normalise so a sign that only a
        # rounding produced cannot move a digest.
        rounded = round(value, dp)
        if rounded == 0:
            rounded = 0.0
        return "%.*f" % (dp, rounded)
    return str(value)


def _line(item: _t.Sequence[_t.Any], dp: int) -> str:
    return "|".join(_fmt(part, dp) for part in item)


def digest(items: _t.Iterable[_t.Sequence[_t.Any]],
           dps: _t.Sequence[int] = METRE_DP) -> dict:
    """A sorted-line sha256 per rounding, plus the line count.

    ``items`` is an iterable of flat sequences (numbers and strings).  The
    lines are SORTED before hashing, so the caller's enumeration order is
    not part of the answer.
    """
    materialised = [tuple(item) for item in items]
    out: dict = {"n": len(materialised)}
    for dp in dps:
        lines = sorted(_line(item, dp) for item in materialised)
        sha = _hash.sha256()
        for line in lines:
            sha.update(line.encode("utf-8"))
            sha.update(b"\n")
        out["dp%d" % dp] = sha.hexdigest()[:16]
    return out


def _ring_items(tag: str, ident: _t.Any, ring: _t.Iterable) -> list:
    """One line per ring VERTEX, carrying the ring's identity and the
    vertex's position in it — a reversed or rotated ring is a different
    set of lines, which is what we want to see."""
    out = []
    for k, point in enumerate(ring or ()):
        try:
            x, y = float(point[0]), float(point[1])
        except (TypeError, ValueError, IndexError):
            continue
        out.append((tag, ident, k, x, y))
    return out


# ------------------------------------------------------------ the stages

def _load_items(airport) -> list:
    items: list = []
    for rw in getattr(airport, "runways", ()) or ():
        for end in rw.ends:
            items.append(("rw_end", rw.id, end.name, float(end.xy[0]),
                          float(end.xy[1]), float(end.displaced_m),
                          float(end.overrun_m)))
        items.append(("rw", rw.id, float(rw.width_m), int(rw.surface),
                      str(rw.code_number), str(rw.code_letter)))
    for pv in getattr(airport, "pavements", ()) or ():
        items += _ring_items("pav", pv.id, pv.outer)
        for h, hole in enumerate(pv.holes or ()):
            items += _ring_items("pav_hole:%d" % h, pv.id, hole)
    for bd in getattr(airport, "boundaries", ()) or ():
        items += _ring_items("bnd", bd.id, bd.outer)
    for lf in getattr(airport, "linear_features", ()) or ():
        items += _ring_items("lin:%d" % lf.line_type, lf.id, lf.points)
    for nd in (getattr(airport, "taxi_nodes", None) or {}).values():
        items.append(("tnode", nd.id, float(nd.xy[0]), float(nd.xy[1]),
                      nd.usage))
    for ed in getattr(airport, "taxi_edges", ()) or ():
        items.append(("tedge", min(ed.a, ed.b), max(ed.a, ed.b), ed.name,
                      int(bool(ed.is_runway))))
    for bg in getattr(airport, "buildings", ()) or ():
        items += _ring_items("bldg:%s" % bg.source, bg.id, bg.outer)
    for wy in getattr(airport, "osm_ways", ()) or ():
        items += _ring_items("osm:%s" % wy.kind, wy.id, wy.points)
    return items


def _classify_items(cl) -> list:
    items: list = []
    for cell in getattr(cl, "cells", ()) or ():
        items += _ring_items("cell:%s" % cell.role, cell.ref, cell.ring)
        for h, hole in enumerate(cell.holes or ()):
            items += _ring_items("cell_hole:%s:%d" % (cell.role, h),
                                 cell.ref, hole)
    return items


def _planar_items(pm):
    """(vertices, edges, faces) as order-free lines keyed by GEOMETRY."""
    vertices = getattr(pm, "vertices", {}) or {}
    # xy ALONE and xy+DEM separately: a divergence that shows only in
    # ``dem`` is the DEM sampler's own (its forward transform and its
    # bilinear arithmetic), not the planar build's, and one combined
    # digest could never say which.
    verts = [("v", float(v.xy[0]), float(v.xy[1]))
             for v in vertices.values()]
    verts_dem = [("v", float(v.xy[0]), float(v.xy[1]),
                  "-" if v.dem_z is None else float(v.dem_z))
                 for v in vertices.values()]
    edges = []
    for e in (getattr(pm, "edges", {}) or {}).values():
        a, b = vertices.get(e.a), vertices.get(e.b)
        if a is None or b is None:
            continue
        pa = (float(a.xy[0]), float(a.xy[1]))
        pb = (float(b.xy[0]), float(b.xy[1]))
        lo, hi = (pa, pb) if pa <= pb else (pb, pa)
        edges.append(("e", str(e.kind), lo[0], lo[1], hi[0], hi[1]))
    faces = []
    for f in (getattr(pm, "faces", {}) or {}).values():
        ring = [vertices.get(i) for i in f.ring]
        pts = sorted((float(v.xy[0]), float(v.xy[1]))
                     for v in ring if v is not None)
        faces.append(("f", f.role, f.ref, f.side, len(f.ring),
                      len(f.holes or ())) + tuple(c for p in pts for c in p))
    return verts, verts_dem, edges, faces


def _constraint_items(cs, pm) -> list:
    """Every row, keyed by its vertices' GEOMETRY, not their ids."""
    vertices = getattr(pm, "vertices", {}) or {}

    def at(i):
        v = vertices.get(i)
        return ("-", "-") if v is None else (float(v.xy[0]), float(v.xy[1]))

    items: list = []
    for p in getattr(cs, "pins", ()) or ():
        items.append(("pin", p.source.generator, p.source.ruling)
                     + at(p.v) + (float(p.z),))
    for d in getattr(cs, "diffs", ()) or ():
        items.append(("diff", d.source.generator, d.source.ruling)
                     + at(d.a) + at(d.b) + (float(d.cap), float(d.d)))
    for fl in getattr(cs, "flats", ()) or ():
        pts = sorted(at(i) for i in fl.group)
        items.append(("flat", fl.source.generator, fl.source.ruling,
                      len(fl.group)) + tuple(c for p in pts for c in p))
    for b in getattr(cs, "bands", ()) or ():
        items.append(("band", b.source.generator, b.source.ruling) + at(b.v)
                     + ("-" if b.lo is None else float(b.lo),
                        "-" if b.hi is None else float(b.hi)))
    for o in getattr(cs, "offsets", ()) or ():
        items.append(("offset", o.source.generator, o.source.ruling)
                     + at(o.a) + at(o.b) + (float(o.min_delta),))
    for ln in getattr(cs, "linears", ()) or ():
        terms = sorted((at(i), float(c)) for i, c in ln.terms)
        items.append(("linear", ln.source.generator, ln.source.ruling,
                      len(ln.terms),
                      "-" if ln.lo is None else float(ln.lo),
                      "-" if ln.hi is None else float(ln.hi))
                     + tuple(part for pt, c in terms
                             for part in (pt[0], pt[1], c)))
    return items


# --------------------------------------------------------------- the dump

def environment() -> dict:
    """The libraries whose BUILD is the first suspect, read from the
    running interpreter — never assumed from ``requirements.txt``."""
    env: dict = {
        "python": _sys.version.split()[0],
        "platform": _sys.platform,
        "machine": _platform.machine(),
        "processor": _platform.processor(),
        "frozen": bool(getattr(_sys, "frozen", False)),
        # Read off the INTERPRETER, not the environment: what PYTHONHASHSEED
        # was asked for and what the process actually did can differ.
        "hash_randomization": _sys.flags.hash_randomization,
        "maxsize": _sys.maxsize,
        "float_repr_style": _sys.float_repr_style,
    }
    try:
        import shapely
        env["shapely"] = shapely.__version__
        env["geos_version"] = ".".join(str(p) for p in shapely.geos_version)
        env["geos_capi_version"] = ".".join(
            str(p) for p in shapely.geos_capi_version)
    except Exception as error:                       # pragma: no cover
        env["shapely_error"] = repr(error)
    try:
        import pyproj
        env["pyproj"] = pyproj.__version__
        env["proj_version_str"] = pyproj.proj_version_str
    except Exception as error:                       # pragma: no cover
        env["pyproj_error"] = repr(error)
    try:
        import numpy
        env["numpy"] = numpy.__version__
        try:
            build = numpy.__config__.show(mode="dicts")
            blas = (build.get("Build Dependencies") or {}).get("blas") or {}
            env["numpy_blas"] = "%s %s" % (blas.get("name"),
                                           blas.get("version"))
        except Exception:
            env["numpy_blas"] = "(unavailable)"
    except Exception as error:                       # pragma: no cover
        env["numpy_error"] = repr(error)
    try:
        import scipy
        env["scipy"] = scipy.__version__
    except Exception as error:                       # pragma: no cover
        env["scipy_error"] = repr(error)
    return env


def stage_digests(icao: str, airport=None, classification=None, pm=None,
                  stage=None, constraints=None, lp=None, solved=None,
                  final_pm=None) -> dict:
    """The per-stage table.  Every argument is optional: a caller passes
    what it holds, and a stage it does not pass is simply absent.

    ``pm`` is the map the PLANAR stage produced; ``final_pm`` the one the
    constraints and the solution are keyed against (the shape stage and
    the trend channels replace it).  Looking a constraint's vertex up in
    the planar-stage map would silently mis-key every row.
    """
    stages: dict = {}
    if final_pm is None:
        final_pm = pm
    if airport is not None:
        items = _load_items(airport)
        stages["load"] = {
            "counts": {
                "runways": len(getattr(airport, "runways", ()) or ()),
                "pavements": len(getattr(airport, "pavements", ()) or ()),
                "boundaries": len(getattr(airport, "boundaries", ()) or ()),
                "linear_features": len(getattr(airport, "linear_features",
                                                ()) or ()),
                "taxi_nodes": len(getattr(airport, "taxi_nodes", None) or {}),
                "taxi_edges": len(getattr(airport, "taxi_edges", ()) or ()),
                "buildings": len(getattr(airport, "buildings", ()) or ()),
                "osm_ways": len(getattr(airport, "osm_ways", ()) or ()),
            },
            "geometry": digest(items),
        }
        part = getattr(airport, "partition", None)
        groups = getattr(airport, "groups", None)
        stages["partition"] = {
            "counts": dict(getattr(part, "counts", {}) or {},
                           **{"group.%s" % k: v for k, v in
                              (getattr(groups, "counts", {}) or {}).items()}),
        }
    if classification is not None:
        items = _classify_items(classification)
        cells = list(getattr(classification, "cells", ()) or ())
        by_role: dict = {}
        for cell in cells:
            by_role[cell.role] = by_role.get(cell.role, 0) + 1
        stages["classify"] = {
            "counts": dict(sorted(by_role.items()), cells=len(cells)),
            "geometry": digest(items),
        }
    if pm is not None:
        verts, verts_dem, edges, faces = _planar_items(pm)
        by_role = {}
        for f in (getattr(pm, "faces", {}) or {}).values():
            by_role[f.role] = by_role.get(f.role, 0) + 1
        stages["planar"] = {
            "counts": {
                "vertices": len(getattr(pm, "vertices", {}) or {}),
                "edges": len(getattr(pm, "edges", {}) or {}),
                "faces": len(getattr(pm, "faces", {}) or {}),
                "breaklines": len(getattr(pm, "breaklines", {}) or {}),
                "faces_by_role": dict(sorted(by_role.items())),
            },
            "vertices": digest(verts),
            "vertices_dem": digest(verts_dem),
            "edges": digest(edges),
            "faces": digest(faces),
        }
    if stage is not None:
        # ``ShapeStage.as_dict`` is the stage's OWN census (shapes, joints,
        # gap joints, road ramps, the withdraw set) — imported, never
        # re-spelled here.
        counts = dict(stage.as_dict())
        counts.pop("wall_s", None)
        counts.pop("dropped_by_generator", None)
        joints = getattr(stage.pm, "shape_joints", ()) or ()
        stages["shapes"] = {
            "counts": counts,
            "joints": digest([("j", j.length_m, len(j.points))
                              + tuple(c for p in sorted(
                                  (float(a), float(b)) for a, b in j.points)
                                  for c in p)
                              for j in joints]),
        }
    if constraints is not None and final_pm is not None:
        items = _constraint_items(constraints, final_pm)
        stages["constraints"] = {
            "counts": dict(constraints.counts()),
            "rows": digest(items),
        }
    if lp is not None:
        stages["lp"] = {"counts": {k: v for k, v in sorted(lp.items())
                                   if isinstance(v, int)}}
    if solved is not None and final_pm is not None:
        # ``Solution.z`` is a DENSE TUPLE in vertex-id order (solve/api.py);
        # a mapping is accepted too so a caller holding one can pass it.
        vertices = getattr(final_pm, "vertices", {}) or {}
        pairs = (solved.items() if hasattr(solved, "items")
                 else enumerate(solved))
        items = []
        for i, z in pairs:
            v = vertices.get(i)
            if v is None:
                continue
            items.append(("z", float(v.xy[0]), float(v.xy[1]), float(z)))
        stages["solved"] = {"counts": {"z": len(items)},
                            "z": digest(items)}
    return {"icao": icao, "env": environment(), "stages": stages}


def write(path: str, payload: dict) -> str:
    import json
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
    return path


# ===================================================================
# THE RAW PROJECTION DUMP (lane ``xplatspread``)
# ===================================================================
#
# The digests above name WHICH STAGE first disagrees; they cannot say BY
# HOW MUCH.  RULINGS 2026-09-17d could only BRACKET the platform spread of
# ``Frame.to_xy`` as "(5e-7, 5e-5) m" — inferred from a digest agreeing at
# 4 dp and differing at 6 dp.  Owner Q 17d-1 (option A: the canonical
# vertex identity moves into the METRE domain, "can we simply standardize
# everything to the nearest 1 mm?") has to be decided against the real
# distribution, because a coordinate within the spread of a snap boundary
# rounds differently on two platforms — a STRADDLE.
#
# So this section records the projection EXACTLY: ``float.hex()`` of the
# input ``(lon, lat)`` and of the output ``(x, y)``, no rounding anywhere.
# The join across platforms is the INPUT pair, which is identical on every
# platform by construction (the same apt.dat bytes, IEEE-correct parsing),
# so the comparison is exact rather than nearest-neighbour.
#
# ARMED, NEVER DEFAULT, and byte-neutral when off: the one hook
# (``airport/load._vector_to_xy``) returns the frame's own function
# UNCHANGED unless :func:`arm_projection` has been called, which only
# ``pipeline/build.build`` does, only under ``Config.xplat_dump``.

#: The armed recorder: ``{(lon_hex, lat_hex): (x, y)}``.  ``None`` = off.
_PROJ: dict | None = None
#: Metre quantum applied to the RECORDED projection in the dump arm only
#: (``Config.xplat_quantise_m``).  0.0 = record, never alter.  This is the
#: interventional arm of 17d (commit ``8615f4f9``, reverted ``e885d4d0``)
#: re-armed behind the dump switch: it makes the pipeline's inputs
#: IDENTICAL on every platform so what still differs downstream can be
#: attributed to something other than the projection.
_PROJ_Q: float = 0.0


def arm_projection(quantise_m: float = 0.0) -> None:
    """Start recording (and, with ``quantise_m``, snapping) the load
    stage's projection.  Resets any previous recording."""
    global _PROJ, _PROJ_Q
    _PROJ = {}
    _PROJ_Q = float(quantise_m or 0.0)


def disarm_projection() -> None:
    global _PROJ, _PROJ_Q
    _PROJ = None
    _PROJ_Q = 0.0


def projection_armed() -> bool:
    return _PROJ is not None


def projection_quantum() -> float:
    return _PROJ_Q


def record_projection(lon: float, lat: float, x: float, y: float) -> None:
    """One ``to_xy`` evaluation, keyed by its exact input."""
    if _PROJ is None:
        return
    _PROJ[(float(lon).hex(), float(lat).hex())] = (float(x).hex(),
                                                   float(y).hex())


# ---------------------------------------------------------- the probes

#: Degree offsets from the frame origin for the synthetic LATTICE probe.
#: Every value is an exact binary fraction, so the probe's INPUTS are
#: bit-identical on every platform without relying on decimal parsing.
#: 1/1024 deg is ~108.7 m in latitude, so the ladder reaches ~13.9 km —
#: past a large hub's half-extent (CYXY's own is ~1 km).
_LATTICE_DEG = tuple(s * (2 ** -10) * (2 ** k)
                     for k in range(8) for s in (-1, 1)) + (0.0,)

#: Metre offsets for the INVERSE probe.  Exact binary metres, so the
#: ``to_ll`` input is bit-identical everywhere (the forward probe's output
#: is not — that is the thing being measured).
_LATTICE_M = tuple(float(s * (2 ** k))
                   for k in range(7, 15) for s in (-1, 1)) + (0.0,)


def probe_projection(frame) -> dict:
    """Project a deterministic lattice through ``frame`` both ways.

    The recorded airport coordinates answer "what is the spread on the
    points this airport actually has"; the lattice answers "how does the
    spread GROW with distance from the origin", which is how a CYXY
    measurement is scaled to a hub.  Both are exact hex.
    """
    to_xy, to_ll = frame.transformers()
    lat0, lon0 = frame.origin
    forward = []
    for dlat in sorted(_LATTICE_DEG):
        for dlon in sorted(_LATTICE_DEG):
            lat, lon = lat0 + dlat, lon0 + dlon
            x, y = to_xy(lon, lat)
            forward.append([float(lon).hex(), float(lat).hex(),
                            float(x).hex(), float(y).hex()])
    inverse = []
    for x in sorted(_LATTICE_M):
        for y in sorted(_LATTICE_M):
            lat, lon = to_ll(x, y)
            inverse.append([float(x).hex(), float(y).hex(),
                            float(lat).hex(), float(lon).hex()])
    return {"forward": forward, "inverse": inverse}


def projection_payload(icao: str, frame=None, solved=None,
                       final_pm=None) -> dict:
    """The exact-projection dump: what was recorded, the lattice probes,
    and (when the inputs were made identical by ``quantise_m``) the
    SOLVED z keyed by its vertex's xy, so the vertical axis can be
    straddle-counted the same way."""
    recorded = [[k[0], k[1], v[0], v[1]]
                for k, v in sorted((_PROJ or {}).items())]
    out: dict = {
        "icao": icao,
        "env": environment(),
        "quantise_m": _PROJ_Q,
        "recorded": recorded,
        "counts": {"recorded": len(recorded)},
    }
    if frame is not None:
        lat0, lon0 = frame.origin
        out["origin"] = [float(lat0).hex(), float(lon0).hex()]
        out["crs"] = getattr(frame, "crs", "")
        try:
            probe = probe_projection(frame)
        except Exception as error:                     # pragma: no cover
            out["probe_error"] = repr(error)
        else:
            out["probe"] = probe
            out["counts"]["probe_forward"] = len(probe["forward"])
            out["counts"]["probe_inverse"] = len(probe["inverse"])
    if solved is not None and final_pm is not None:
        vertices = getattr(final_pm, "vertices", {}) or {}
        pairs = (solved.items() if hasattr(solved, "items")
                 else enumerate(solved))
        rows = []
        for i, z in pairs:
            v = vertices.get(i)
            if v is None:
                continue
            rows.append([float(v.xy[0]).hex(), float(v.xy[1]).hex(),
                         float(z).hex()])
        rows.sort()
        out["solved_z"] = rows
        out["counts"]["solved_z"] = len(rows)
    return out


# ------------------------------------------------- the offline comparer

#: Snap grids the owner's question names, in metres (0.1 mm, 1 mm, 1 cm).
GRIDS = (1e-4, 1e-3, 1e-2)


def _snap(value: float, grid: float) -> int:
    """The snap a metre-domain identity would take.  ``floor(v/g + 0.5)``
    and not ``round``: round() is banker's, and a tie landing on an even
    multiple would be reported as agreement on one platform and not the
    other for a reason that has nothing to do with the spread."""
    import math
    return math.floor(value / grid + 0.5)


def _stats(deltas: list) -> dict:
    """max / p99 / median / mean of |Δ|, and the decade histogram."""
    import math
    n = len(deltas)
    out: dict = {"n": n}
    if not n:
        return out
    ordered = sorted(deltas)
    out["max"] = ordered[-1]
    out["p99"] = ordered[min(n - 1, int(0.99 * (n - 1)))]
    out["p50"] = ordered[n // 2]
    out["mean"] = sum(ordered) / n
    out["exact"] = sum(1 for d in ordered if d == 0.0)
    hist: dict = {}
    for d in ordered:
        if d == 0.0:
            key = "0"
        else:
            key = "1e%d" % int(math.floor(math.log10(d)))
        hist[key] = hist.get(key, 0) + 1
    out["hist"] = hist
    return out


def _straddles(pairs: list) -> dict:
    """For each grid: how many of ``pairs`` ((a, b) values in metres) snap
    to DIFFERENT multiples."""
    out = {}
    for grid in GRIDS:
        out["%g" % grid] = sum(1 for a, b in pairs
                               if _snap(a, grid) != _snap(b, grid))
    return out


def _bands(rows: list) -> list:
    """|Δ| against distance from the frame origin.  ``rows`` are
    ``(r_m, d_m)``; the bands double, because the question is whether the
    spread scales with the coordinate's magnitude (it would, if it is a
    last-ulp effect of a double whose exponent grows)."""
    import math
    edges = [0.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0,
             float("inf")]
    out = []
    for lo, hi in zip(edges, edges[1:]):
        here = [d for r, d in rows if lo <= r < hi]
        if not here:
            continue
        out.append({"lo_m": lo, "hi_m": None if math.isinf(hi) else hi,
                    "n": len(here), "max": max(here),
                    "p50": sorted(here)[len(here) // 2],
                    "rel_max": (max(here) / hi if not math.isinf(hi)
                                and hi else None)})
    return out


def _joined(a: list, b: list, nkey: int):
    """Inner join two hex tables on their first ``nkey`` columns."""
    index = {tuple(row[:nkey]): row[nkey:] for row in b}
    for row in a:
        other = index.get(tuple(row[:nkey]))
        if other is not None:
            yield row[nkey:], other


def _axis_report(label: str, joined: list) -> dict:
    """``joined`` is a list of ``((ax, ay), (bx, by))`` value pairs in
    metres.  Per axis and for the planar distance."""
    import math
    out: dict = {"label": label, "n": len(joined)}
    for k, axis in enumerate(("x", "y")):
        deltas = [abs(p[0][k] - p[1][k]) for p in joined]
        out[axis] = _stats(deltas)
        out[axis]["straddles"] = _straddles([(p[0][k], p[1][k])
                                             for p in joined])
    out["dist"] = _stats([math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1])
                          for p in joined])
    # A COORDINATE straddles when EITHER axis does — that is the number an
    # identity join would actually lose.
    coord = {}
    for grid in GRIDS:
        coord["%g" % grid] = sum(
            1 for p in joined
            if _snap(p[0][0], grid) != _snap(p[1][0], grid)
            or _snap(p[0][1], grid) != _snap(p[1][1], grid))
    out["straddles_coord"] = coord
    out["bands"] = _bands([(math.hypot(*p[0]),
                            math.hypot(p[0][0] - p[1][0],
                                       p[0][1] - p[1][1]))
                           for p in joined])
    return out


def _pair_projection(a: dict, b: dict) -> dict:
    """Everything one platform PAIR has to say."""
    fh = float.fromhex
    out: dict = {}
    for key, table_key, nkey in (("recorded", None, 2),
                                 ("probe_forward", "forward", 2),
                                 ("probe_inverse", "inverse", 2)):
        if table_key is None:
            ta, tb = a.get("recorded") or [], b.get("recorded") or []
        else:
            ta = ((a.get("probe") or {}).get(table_key)) or []
            tb = ((b.get("probe") or {}).get(table_key)) or []
        if not ta or not tb:
            continue
        joined = [((fh(va[0]), fh(va[1])), (fh(vb[0]), fh(vb[1])))
                  for va, vb in _joined(ta, tb, nkey)]
        if key == "probe_inverse":
            # The inverse's outputs are DEGREES; report them in metres so
            # every number in this lane is one unit.  1e-5 deg of latitude
            # is 1.11 m; longitude is scaled by cos(lat) at the origin,
            # which the payload does not carry — the conservative reading
            # is the latitude scale on both axes.
            joined = [((va[0] * _M_PER_DEG, va[1] * _M_PER_DEG),
                       (vb[0] * _M_PER_DEG, vb[1] * _M_PER_DEG))
                      for va, vb in joined]
        out[key] = _axis_report(key, joined)
    za, zb = a.get("solved_z") or [], b.get("solved_z") or []
    if za and zb:
        pairs = [(fh(va[0]), fh(vb[0])) for va, vb in _joined(za, zb, 2)]
        out["solved_z"] = {
            "n": len(pairs),
            "joined_of": [len(za), len(zb)],
            "delta": _stats([abs(p[0] - p[1]) for p in pairs]),
            "straddles": _straddles(pairs),
        }
    return out


#: Metres per degree of latitude on the WGS84 ellipsoid, mid-latitudes —
#: only ever used to put the INVERSE probe's degrees on the same axis as
#: everything else in the report.
_M_PER_DEG = 111320.0


def compare_projection(dumps: _t.Mapping[str, dict]) -> list:
    """Printable lines: per platform PAIR, the exact spread of the
    projection, its growth with distance from the origin, and the straddle
    count at each candidate snap grid."""
    names = list(dumps)
    lines: list = []
    for name in names:
        d = dumps[name]
        env = d.get("env") or {}
        lines.append("dump %-10s q=%-8g %s  (%s %s, pyproj %s / PROJ %s)"
                     % (name, d.get("quantise_m") or 0.0,
                        d.get("counts"), env.get("platform"),
                        env.get("machine"), env.get("pyproj"),
                        env.get("proj_version_str")))
    qs = {float(dumps[n].get("quantise_m") or 0.0) for n in names}
    if len(qs) > 1:
        lines.append("WARNING: dumps were taken at DIFFERENT quanta %s — "
                     "they are not one arm." % sorted(qs))
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pair = _pair_projection(dumps[a], dumps[b])
            for key in ("recorded", "probe_forward", "probe_inverse"):
                rep = pair.get(key)
                if not rep:
                    continue
                lines.append("")
                lines.append("== %s vs %s — %s (n=%d joined) =="
                             % (a, b, key, rep["n"]))
                for axis in ("x", "y", "dist"):
                    s = rep[axis]
                    if not s.get("n"):
                        continue
                    lines.append("  %-4s max %.3e  p99 %.3e  p50 %.3e  "
                                 "mean %.3e  exact %d/%d"
                                 % (axis, s["max"], s["p99"], s["p50"],
                                    s["mean"], s["exact"], s["n"]))
                    lines.append("       hist %s"
                                 % " ".join("%s:%d" % kv for kv in
                                            sorted(s["hist"].items())))
                for axis in ("x", "y"):
                    lines.append("  straddles %-2s %s" % (
                        axis, " ".join("%s m:%d" % (g, n) for g, n in
                                       sorted(rep[axis]["straddles"].items()))))
                lines.append("  straddles COORD %s of %d"
                             % (" ".join("%s m:%d" % (g, n) for g, n in
                                         sorted(rep["straddles_coord"].items())),
                                rep["n"]))
                for band in rep["bands"]:
                    lines.append("  r %7.0f..%-7s n %-6d max|d| %.3e  "
                                 "p50 %.3e"
                                 % (band["lo_m"],
                                    ("inf" if band["hi_m"] is None
                                     else "%.0f" % band["hi_m"]),
                                    band["n"], band["max"], band["p50"]))
            z = pair.get("solved_z")
            if z:
                s = z["delta"]
                lines.append("")
                lines.append("== %s vs %s — SOLVED z (n=%d joined of %s) =="
                             % (a, b, z["n"], z["joined_of"]))
                if s.get("n"):
                    lines.append("  z    max %.3e  p99 %.3e  p50 %.3e  "
                                 "exact %d/%d"
                                 % (s["max"], s["p99"], s["p50"],
                                    s["exact"], s["n"]))
                    lines.append("       hist %s"
                                 % " ".join("%s:%d" % kv for kv in
                                            sorted(s["hist"].items())))
                lines.append("  straddles z  %s of %d"
                             % (" ".join("%s m:%d" % (g, n) for g, n in
                                         sorted(z["straddles"].items())),
                                z["n"]))
    return lines


def compare(dumps: _t.Mapping[str, dict]) -> list:
    """The three-platform table as printable lines: per stage, per key,
    the value on each platform and whether they AGREE.  The FIRST stage
    with a disagreement is what the lane is after, so stages are reported
    in pipeline order and each line says AGREE or DIFFER."""
    order = ["load", "partition", "classify", "planar", "shapes",
             "constraints", "lp", "solved"]
    names = list(dumps)
    lines = []
    env_keys: list = []
    for name in names:
        for key in (dumps[name].get("env") or {}):
            if key not in env_keys:
                env_keys.append(key)
    for key in env_keys:
        values = [str((dumps[n].get("env") or {}).get(key)) for n in names]
        flag = "AGREE" if len(set(values)) == 1 else "DIFFER"
        lines.append("env %-22s %-6s %s" % (key, flag, " | ".join(values)))
    for stage in order:
        present = [n for n in names if stage in (dumps[n].get("stages") or {})]
        if not present:
            continue
        keys: list = []
        for n in present:
            block = dumps[n]["stages"][stage]
            for group, value in sorted(block.items()):
                if isinstance(value, dict):
                    for sub in sorted(value):
                        key = "%s.%s" % (group, sub)
                        if key not in keys:
                            keys.append(key)
        for key in keys:
            group, sub = key.split(".", 1)
            values = []
            for n in present:
                block = (dumps[n]["stages"][stage].get(group) or {})
                values.append(str(block.get(sub)))
            flag = "AGREE" if len(set(values)) == 1 else "DIFFER"
            lines.append("%-12s %-28s %-6s %s"
                         % (stage, key, flag, " | ".join(values)))
    return lines
