#!/usr/bin/env python3
"""THE PAD GROUND SURVEY (owner RULINGS 2026-11-19l) -- what the ground-
contact trim (``classify/pad_ground.trim_to_ground``) takes out of an
airport's building pads, read DRY off a ``v2_solve_replay --capture``.

    cd Ortho4XP && venv/bin/python tools/pad_ground_survey.py CAP.pkl [...] [--json OUT.json]
        [--site LAT,LON[,R]] [--top N]

Per capture: the clusters are re-derived under the current tree (as
``--replay --from classify`` does), the facade reads are refreshed for a
capture older than ``FacadeRead.base_m``, and the classify EVIDENCE stage
(``classify/evidence.build_evidence``, the one pad derivation) runs twice:
with the trim disarmed (the base) and as shipped (the arm).  Printed: the
pad count and area each way, every base pad that SHRINKS (its area lost,
what remains, its representative point) worst first, and the trim's own
counters and passage notes (clearance under each lifted piece).  ``--site``
lists the pads within R m (default 60) of a point both ways.

A DRY READ: it re-runs no planar build, no solve and no emit, so it
prices no law and counts no movers (``--replay --from classify`` pairs do).
Promoted on its second use by lane ``lpadfeet`` (RULINGS ``7e90032``).
"""
from __future__ import annotations

import os as _o4os
import sys as _o4sys

_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

import argparse  # noqa: E402
import dataclasses as _dc  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _refresh_facades(airport, inputs):
    """A capture older than ``FacadeRead.base_m``: each roofed facade's base,
    read from its file (every floor's base over the ground band reads as
    lifted only when all of them are -- the capture holds no height)."""
    from auto_patch_v2.airport import facade as _fac
    from auto_patch_v2.airport import obj8 as _obj8
    if not any(getattr(b, "facade", None) is not None for b in airport.buildings):
        return airport, 0
    if any(getattr(b.facade, "base_m", None) is not None for b in airport.buildings
           if getattr(b, "facade", None) is not None):
        return airport, 0
    import os
    xp = getattr(inputs, "xplane_root", "") or ""
    index = None
    # the capture's own mod cache, else this checkout's (a capture taken in
    # another lane's worktree names a cache that is gone)
    for root in (getattr(inputs, "mod_cache_root", "") or "", str(ROOT / "Airport_mod_cache")):
        lib = _obj8.library_index_path(root, xp) if root and xp else ""
        if lib and os.path.isfile(lib):
            index = _obj8.read_library_index(lib)
            break
    root = airport.pack.pack_root if airport.pack is not None else None
    out, n = [], 0
    for b in airport.buildings:
        fr = getattr(b, "facade", None)
        if fr is not None:
            fac = _fac.read_facade(fr.def_path, root, index)
            bases = [f.base_y for f in fac.floors] if fac is not None else []
            if bases and all(x is not None for x in bases):
                b = _dc.replace(b, facade=_dc.replace(fr, base_m=min(bases)))
                n += 1
        out.append(b)
    return _dc.replace(airport, buildings=tuple(out)), n


def _pads(airport, law, rules, armed: bool):
    from auto_patch_v2.airport import frame_entry as _fe
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.classify import pad_ground
    from auto_patch_v2.classify.evidence import build_evidence
    keep = pad_ground.trim_to_ground
    if not armed:
        pad_ground.trim_to_ground = lambda parts, *_a, **_k: parts
    try:
        cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m,
                              _fe.quantum(law))
        ev = build_evidence(airport, rules, law.tables.structures.building_pad.min_area_m2,
                            law, cache)
    finally:
        pad_ground.trim_to_ground = keep
    return ev.pads, dict(pad_ground.GROUND_TRIMMED), list(pad_ground.PASSAGE_NOTES)


def survey(pkl: Path, site=None, top: int = 15) -> dict:
    from auto_patch_v2.classify import load_rules
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.cluster import clusters as derive_clusters
    from shapely.geometry import Point
    from shapely.ops import unary_union
    with pkl.open("rb") as fh:
        cap = pickle.load(fh)
    icao, airport = cap["icao"], cap["airport"]
    law, rules = Law.for_airport(icao), load_rules()
    airport = _dc.replace(airport, clusters=derive_clusters(airport, law))
    airport, nfac = _refresh_facades(airport, cap.get("inputs"))
    base, _c0, _n0 = _pads(airport, law, rules, False)
    arm, counts, notes = _pads(airport, law, rules, True)
    to_ll = airport.frame.transformers()[1]
    au = unary_union([p for _r, p in arm]) if arm else None
    shrink = []
    for ref, p in base:
        kept = p.intersection(au).area if au is not None else 0.0
        if p.area - kept > 1.0:
            lat, lon = to_ll(*p.representative_point().coords[0])
            shrink.append({"ref": ref, "area_m2": round(p.area, 1),
                           "lost_m2": round(p.area - kept, 1), "kept_m2": round(kept, 1),
                           "lat": round(lat, 6), "lon": round(lon, 6)})
    shrink.sort(key=lambda r: -r["lost_m2"])
    rec = {"icao": icao, "capture": str(pkl), "facades_refreshed": nfac,
           "base": {"pads": len(base), "m2": round(sum(p.area for _r, p in base), 1)},
           "arm": {"pads": len(arm), "m2": round(sum(p.area for _r, p in arm), 1)},
           "trim": counts, "shrunk": len(shrink), "rows": shrink, "notes": notes}
    print(f"[{icao}] pads {rec['base']['pads']} / {rec['base']['m2']:.0f} m2 -> "
          f"{rec['arm']['pads']} / {rec['arm']['m2']:.0f} m2; shrunk {len(shrink)}; "
          f"trim {counts}; facades refreshed {nfac}")
    for r in shrink[:top]:
        print(f"  {r['ref']:<16} {r['area_m2']:>10.0f} m2  lost {r['lost_m2']:>9.0f}  "
              f"at {r['lat']}, {r['lon']}")
    for n in notes:
        print(f"  {n}")
    if site is not None:
        to_xy = airport.frame.transformers()[0]
        pt = Point(*to_xy(site[1], site[0]))
        for tag, pads in (("base", base), ("arm", arm)):
            for ref, p in pads:
                if p.distance(pt) <= site[2]:
                    print(f"  site {tag}: {ref} {p.area:.0f} m2 "
                          f"(holds the site: {p.contains(pt)})")
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("captures", nargs="+", type=Path)
    ap.add_argument("--site", default=None, help="LAT,LON[,R]")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    site = None
    if a.site:
        v = [float(x) for x in a.site.split(",")]
        site = (v[0], v[1], v[2] if len(v) > 2 else 60.0)
    recs = [survey(p, site, a.top) for p in a.captures]
    if a.json:
        a.json.write_text(json.dumps(recs, indent=1), encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
