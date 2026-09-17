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
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
    return path


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
