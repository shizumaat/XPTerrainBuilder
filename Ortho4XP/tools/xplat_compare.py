"""THE CROSS-PLATFORM COMPARER — the offline half of the stage-digest
instrument (lanes ``xplatdeterminism`` / ``xplatspread``).

The ENGINE writes the dumps (``auto_patch_v2/pipeline/xplat.py``:
``<ICAO>.xplat.json`` — per-stage counts and order-free digests on a
rounding ladder — and ``<ICAO>.xproj.json`` — the exact projection rows),
one per platform, inside the frozen bundle.  THIS module reads two or more
of them and says where they part:

* :func:`compare` — the per-stage AGREE/DIFFER table, naming the FIRST
  divergent stage;
* :func:`compare_projection` — the exact spread of the raw projection and
  how many coordinates straddle each snap grid.

Production never calls either, so they live here and not in the engine
package (RULINGS 2026-10-04c (4)).  The front end is
``scripts/check_frozen_tile.py --compare NAME=PATH …`` (the release
workflow's ``xplat_gate``), which loads this file BY PATH on a bare runner
python3: it is, and must stay, STANDARD-LIBRARY ONLY and import nothing of
the engine.  A library (no CLI of its own).
"""

from __future__ import annotations

import typing as _t

#: Snap grids, in metres.  The first three are the ones owner Q 17d-1
#: names (0.1 mm, 1 mm, 1 cm).  The last two are grids the pipeline
#: ALREADY snaps to today (identity census, main ``2fb0799f``):
#:
#:  * ``0.01`` m — ``classify`` nodes its pavement slices at
#:    ``[cells] snap_grid_m`` (``classify/rules.toml:8``; used at
#:    ``classify/roles.py:473, 938`` and ``classify/neck.py:162, 199,
#:    239``).  It doubles as the owner's 1 cm candidate.
#:  * ``0.5`` m — the planar arrangement is noded at ``grid_size =
#:    emit.identity.min_distinct_spacing_m`` (``planar/overlay.py:360-362,
#:    441, 476``; law ``emit.toml:12``).
#:
#: A coordinate within the platform spread of one of THOSE boundaries
#: already snaps a whole centimetre — or half a metre — apart on two
#: platforms, which is the candidate mechanism for 17d's cells 105/104/105
#: and planar V 4289/4283/4287.  So they are counted on the RAW ``to_xy``
#: output, exactly as the pipeline sees it.
GRIDS = (1e-4, 1e-3, 1e-2, 0.5)


def _engine_writer():
    """The engine's dump writer, loaded BY FILE (it is standard-library
    only at module level, and importing the package would drag shapely
    into a bare runner python3).  Only its snap rule is read: the comparer
    must count a straddle with the SAME tie rule the writer keyed its rows
    by, and one rule has one home."""
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))), "src", "auto_patch_v2", "pipeline", "xplat.py")
    spec = importlib.util.spec_from_file_location("_o4_xplat_writer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_snap = _engine_writer()._snap


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
        key = tuple(row[:nkey])
        other = index.get(key)
        if other is not None:
            yield key, row[nkey:], other


def _axis_report(label: str, joined: list) -> dict:
    """``joined`` is a list of ``(key, (ax, ay), (bx, by))``, the values in
    metres.  Per axis and for the planar distance."""
    import math
    out: dict = {"label": label, "n": len(joined)}
    for k, axis in enumerate(("x", "y")):
        deltas = [abs(p[1][k] - p[2][k]) for p in joined]
        out[axis] = _stats(deltas)
        out[axis]["straddles"] = _straddles([(p[1][k], p[2][k])
                                             for p in joined])
    out["dist"] = _stats([math.hypot(p[1][0] - p[2][0], p[1][1] - p[2][1])
                          for p in joined])
    # A COORDINATE straddles when EITHER axis does — that is the number an
    # identity join would actually lose.
    coord: dict = {}
    witnesses: dict = {}
    for grid in GRIDS:
        hits = [p for p in joined
                if _snap(p[1][0], grid) != _snap(p[2][0], grid)
                or _snap(p[1][1], grid) != _snap(p[2][1], grid)]
        coord["%g" % grid] = len(hits)
        # NAME THE STRADDLING COORDINATES, not just count them: the
        # question the census asks is whether the handful that straddle
        # the grids the pipeline ALREADY snaps to (1 cm in classify,
        # 0.5 m in the planar arrangement) are the places the stage dumps
        # first diverge.  Degrees, because that is what every other
        # instrument in this campaign quotes.
        witnesses["%g" % grid] = [
            {"lon": float.fromhex(p[0][0]), "lat": float.fromhex(p[0][1]),
             "a": list(p[1]), "b": list(p[2]),
             "d": math.hypot(p[1][0] - p[2][0], p[1][1] - p[2][1])}
            for p in hits[:20]]
    out["straddles_coord"] = coord
    out["straddle_witnesses"] = witnesses
    out["bands"] = _bands([(math.hypot(*p[1]),
                            math.hypot(p[1][0] - p[2][0],
                                       p[1][1] - p[2][1]))
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
        joined = [(k, (fh(va[0]), fh(va[1])), (fh(vb[0]), fh(vb[1])))
                  for k, va, vb in _joined(ta, tb, nkey)]
        if key == "probe_inverse":
            # The inverse's outputs are DEGREES; report them in metres so
            # every number in this lane is one unit.  1e-5 deg of latitude
            # is 1.11 m; longitude is scaled by cos(lat) at the origin,
            # which the payload does not carry — the conservative reading
            # is the latitude scale on both axes.
            joined = [(k, (va[0] * _M_PER_DEG, va[1] * _M_PER_DEG),
                       (vb[0] * _M_PER_DEG, vb[1] * _M_PER_DEG))
                      for k, va, vb in joined]
        out[key] = _axis_report(key, joined)
    ca, cb = a.get("constraint_rows") or [], b.get("constraint_rows") or []
    if ca and cb:
        def split(row):
            key, _, values = row.partition("\t")
            return key, values.split()

        # A KEY IS NOT UNIQUE — two faces can put the same generator's row
        # on the same vertex pair with different caps.  Group, and compare
        # the SORTED value vectors: a dict that kept only the last row
        # would pair arbitrary members of a duplicate group and report a
        # 10 m "divergence" between two runs of ONE machine (measured).
        def group(rows):
            out: dict = {}
            for line in rows:
                k, v = split(line)
                out.setdefault(k, []).append(v)
            for v in out.values():
                v.sort()
            return out

        left, right = group(ca), group(cb)
        per_gen: dict = {}
        unmatched = 0
        for row_key, mine in left.items():
            theirs = right.get(row_key)
            if theirs is None or len(theirs) != len(mine):
                unmatched += len(mine)
                continue
            gen = row_key.split("|")[1]
            slot = per_gen.setdefault(gen, {"n": 0, "differ": 0, "max": 0.0,
                                            "worst": None})
            for va_row, vb_row in zip(mine, theirs):
                slot["n"] += 1
                worst = 0.0
                for va, vb in zip(va_row, vb_row):
                    if va == vb:
                        continue
                    if va == "-" or vb == "-":
                        worst = max(worst, float("inf"))
                        continue
                    worst = max(worst, abs(float.fromhex(va)
                                           - float.fromhex(vb)))
                if worst:
                    slot["differ"] += 1
                    if worst > slot["max"]:
                        slot["max"] = worst
                        slot["worst"] = row_key
        out["constraint_rows"] = {
            "n": [len(ca), len(cb)], "unmatched": unmatched,
            "by_generator": per_gen,
        }
    za, zb = a.get("solved_z") or [], b.get("solved_z") or []
    if za and zb:
        pairs = [(fh(va[0]), fh(vb[0])) for _k, va, vb in _joined(za, zb, 2)]
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


#: Airport sizes the expectation is projected onto: CYXY's own N, and a
#: hub at 10x and 50x it (HECA/LEMD are the campaign's large fixtures).
_SCALES = (1, 10, 50)


def _expectation_lines(rep: dict) -> list:
    """WHAT EACH CANDIDATE QUANTUM BUYS, for the spec's grid choice.

    For a quantum ``q`` and a per-axis spread ``s``, a coordinate straddles
    a boundary with probability ~``s/q`` per axis (the offset of a snap
    boundary inside a cell is uniform and independent of the spread at
    these magnitudes), so ``p_coord ~ 2 s / q`` and the expected count is
    ``N p_coord``.  The MEASURED count is printed beside it: the model is
    only there to scale CYXY to a hub, and if the two disagree it is the
    measurement that stands.
    """
    lines = ["  what each quantum buys (s = mean |d| per axis; "
             "p ~ 2s/q; measured count in brackets):"]
    sx = (rep.get("x") or {}).get("mean")
    sy = (rep.get("y") or {}).get("mean")
    n = rep.get("n") or 0
    if sx is None or sy is None or not n:
        return []
    s = 0.5 * (sx + sy)
    for grid in GRIDS:
        p = min(1.0, 2.0 * s / grid)
        counts = "  ".join("N*%-2d=%-7d -> %.2f" % (k, n * k, n * k * p)
                           for k in _SCALES)
        lines.append("    q=%-8g p=%.3e   %s   [measured %d/%d]"
                     % (grid, p, counts,
                        (rep.get("straddles_coord") or {}).get("%g" % grid,
                                                               0), n))
    return lines


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
                for grid, hits in sorted(
                        (rep.get("straddle_witnesses") or {}).items()):
                    for w in hits:
                        lines.append("    straddle @%s m  %.9f,%.9f  "
                                     "|d| %.3e  a (%.6f, %.6f)  "
                                     "b (%.6f, %.6f)"
                                     % (grid, w["lat"], w["lon"], w["d"],
                                        w["a"][0], w["a"][1],
                                        w["b"][0], w["b"][1]))
                lines += _expectation_lines(rep)
                for band in rep["bands"]:
                    lines.append("  r %7.0f..%-7s n %-6d max|d| %.3e  "
                                 "p50 %.3e"
                                 % (band["lo_m"],
                                    ("inf" if band["hi_m"] is None
                                     else "%.0f" % band["hi_m"]),
                                    band["n"], band["max"], band["p50"]))
            cons = pair.get("constraint_rows")
            if cons:
                lines.append("")
                lines.append("== %s vs %s — CONSTRAINT ROW VALUES "
                             "(%s rows, %d unmatched keys) =="
                             % (a, b, cons["n"], cons["unmatched"]))
                for gen, s in sorted(cons["by_generator"].items(),
                                     key=lambda kv: -kv[1]["max"]):
                    lines.append("  %-28s n %-7d differ %-7d max|d| %.3e%s"
                                 % (gen, s["n"], s["differ"], s["max"],
                                    ("  @ " + s["worst"].split("|")[1] + "/"
                                     + s["worst"].split("|")[2])
                                    if s["worst"] else ""))
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
