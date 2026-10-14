#!/usr/bin/env python3
"""THE MOUTH DEPTH TABLE of an emitted patch — one row per ``tunnel_ramp``
surface: where its floor (lowest vertex) stands, the rim crest at that
mouth (the highest of the nearest ``structure_rim`` / ``tunnel_wall`` /
``retaining_wall`` nodes), the depth between them, the ramp's top, extent
and mean grade — and, with ``--ref``, the same row of a reference patch
beside it (paired by the nearest floor within ``--pair-m``).

Promoted on its SECOND use (RULINGS ``7e90032``) from the scout
``tunneldepth`` scratch ``mouths.py`` by lane ``mouth75`` (owner RULINGS
2026-10-14f: the mouth depth 5.1 -> 7.5 m, measured from the GROUND).  It
READS ONLY: the patch is parsed with ``check_grade``'s own node / way
expressions, and it counts no law family (that is ``harness/census.py``).

    venv/bin/python tools/tunnel_mouth_depths.py NEW.osm [--ref REF.osm] [--json OUT]
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse
import json
import math
import sys
import typing as _t
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_grade import _NODE_ALT_RE, _NODE_RE, _ND_RE, _TAG_RE, _WAY_RE  # noqa: E402

__all__ = ["mouth_rows", "pair_rows", "main"]

#: the refs / features a mouth's crest is read from
RIM_REFS = ("tunnel_wall", "retaining_wall")
RIM_FEATURES = ("structure_rim",)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat0 = math.radians(a[0])
    return math.hypot((a[0] - b[0]) * 111320.0, (a[1] - b[1]) * 111320.0 * math.cos(lat0))


def _parse(path: Path):
    txt = path.read_text(encoding="utf-8")
    ll = {m.group(1): (float(m.group(2)), float(m.group(3))) for m in _NODE_RE.finditer(txt)}
    alt: dict[str, float] = {}
    for m in _NODE_ALT_RE.finditer(txt):
        try:
            alt[m.group(1)] = float(m.group(2))
        except ValueError:
            pass
    ways = [(m.group(1), dict(_TAG_RE.findall(m.group(2))), _ND_RE.findall(m.group(2)))
            for m in _WAY_RE.finditer(txt)]
    return ll, alt, ways


def mouth_rows(path: Path, rim_nodes_n: int = 4) -> list[dict[str, _t.Any]]:
    """One row per ``tunnel_ramp`` way of the patch at ``path``."""
    ll, alt, ways = _parse(Path(path))

    def pts(nds):
        return [(ll[n][0], ll[n][1], alt[n]) for n in nds if n in ll and n in alt]
    ramps = [w for w in ways if "tunnel_ramp" in (w[1].get("role"), w[1].get("ref"))]
    rims = [q for w in ways if w[1].get("ref") in RIM_REFS
            or w[1].get("o4_feature") in RIM_FEATURES for q in pts(w[2])]
    out = []
    for wid, tags, nds in ramps:
        p = pts(nds)
        if not p:
            continue
        lo = min(p, key=lambda q: q[2])
        hi = max(p, key=lambda q: q[2])
        ext = max(_dist(a, b) for a in p for b in p)
        near = sorted(rims, key=lambda q: _dist(q, lo))[:rim_nodes_n]
        rim = max(q[2] for q in near) if near else float("nan")
        out.append({"way": wid, "ref": tags.get("ref", ""), "lat": round(lo[0], 7),
                    "lon": round(lo[1], 7), "floor_z": round(lo[2], 3), "top_z": round(hi[2], 3),
                    "rim_z": round(rim, 3), "rim_off_m": round(_dist(near[0], lo), 1) if near else None,
                    "depth_m": round(rim - lo[2], 3), "extent_m": round(ext, 1),
                    "grade": round((hi[2] - lo[2]) / max(ext, 1.0), 4)})
    return sorted(out, key=lambda r: (r["lat"], r["lon"]))


def pair_rows(new: list[dict], ref: list[dict], pair_m: float) -> list[dict]:
    """Each NEW row with its nearest REF row by floor point (``None``
    beyond ``pair_m``), then every REF row no NEW row took."""
    taken: set[int] = set()
    out = []
    for r in new:
        best = min(((i, _dist((r["lat"], r["lon"]), (q["lat"], q["lon"])))
                    for i, q in enumerate(ref) if i not in taken),
                   key=lambda t: t[1], default=(None, float("inf")))
        if best[0] is not None and best[1] <= pair_m:
            taken.add(best[0])
            out.append({"new": r, "ref": ref[best[0]]})
        else:
            out.append({"new": r, "ref": None})
    out += [{"new": None, "ref": q} for i, q in enumerate(ref) if i not in taken]
    return out


def _fmt(r: dict | None) -> str:
    if r is None:
        return "ABSENT"
    return (f"depth {r['depth_m']:6.2f} (rim {r['rim_z']:.2f} floor {r['floor_z']:.2f}) "
            f"extent {r['extent_m']:5.0f} m grade {r['grade']:.3f}")


def main(argv: _t.Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tunnel_mouth_depths", description=__doc__.split("\n")[0])
    ap.add_argument("patch", type=Path)
    ap.add_argument("--ref", type=Path, help="a reference patch to pair each mouth with")
    ap.add_argument("--pair-m", type=float, default=30.0)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    new = mouth_rows(a.patch)
    rows = pair_rows(new, mouth_rows(a.ref), a.pair_m) if a.ref else [{"new": r} for r in new]
    for row in rows:
        r = row.get("new") or row.get("ref")
        side = f"{_fmt(row.get('ref'))}  ->  " if a.ref else ""
        print(f"{r['lat']:.6f},{r['lon']:.6f} way {r['way']:>8s}  {side}{_fmt(row.get('new'))}")
    if a.json:
        a.json.write_text(json.dumps(rows, indent=1), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
