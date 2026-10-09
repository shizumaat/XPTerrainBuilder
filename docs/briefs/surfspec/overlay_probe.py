"""surfspec probe — THE #333 CLASS: name-admitted ``.pol`` pages that OVERLIE
apt.dat pavement, per airport, off a registered capture (dry, no solve).

    venv/bin/python docs/briefs/surfspec/overlay_probe.py ICAO=CAP.pkl [...]

Per airport, from ``Airport.pavements`` (the loader's output, ``dsf:pol*``
ids) and the capture's classification:
  * every ``dsf:pol`` page: m2, the fraction on apt.dat pavement, whether
    ``classify/evidence._dsf_pavements``' overlay rule (>= 80 % on apt.dat)
    would keep only its remainder; the remainder pieces >= 50 m2;
  * the cells the classification holds on remainder refs (``dsf:pol<N>#<k>``)
    by role and side — what Option B (remainders as GAP SHEETS) would move
    out of the stage-1 problem;
  * the pages that are < 80 % on apt.dat but still overlie some (the pages
    that join ``ev.pavement_union`` whole and can re-cut an apt.dat slice,
    as SPJC's ``conc_3`` ``dsf:pol50`` did to ``pav6``).
"""
from __future__ import annotations

import collections
import pickle
import re
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "Ortho4XP"
sys.path.insert(0, str(ROOT / "src"))

from shapely.geometry import Polygon        # noqa: E402
from shapely.ops import unary_union         # noqa: E402

REM = re.compile(r"^dsf:pol\d+#\d+$")


def _poly(outer, holes=()):
    try:
        p = Polygon(list(outer), [list(h) for h in holes if len(h) >= 3])
    except (ValueError, TypeError):
        return None
    if not p.is_valid:
        p = p.buffer(0)
    return None if p.is_empty else p


def _parts(g):
    if g.is_empty:
        return []
    return [g] if g.geom_type == "Polygon" else [q for q in g.geoms if q.geom_type == "Polygon"]


def main(pairs):
    from auto_patch_v2.classify import load_rules
    rules = load_rules()
    dp = rules.dsf_pavement
    for pair in pairs:
        icao, pkl = pair.split("=", 1)
        with open(pkl, "rb") as fh:
            cap = pickle.load(fh)
        a, cl = cap["airport"], cap["cl"]
        apt = unary_union([q for q in (_poly(p.outer, p.holes) for p in a.pavements
                                       if not p.id.startswith("dsf:")) if q is not None])
        bnd = unary_union([q for q in (_poly(b.outer) for b in a.boundaries) if q is not None])
        gate = bnd.buffer(dp.boundary_buffer_m) if not bnd.is_empty else None
        n_pages = n_over = n_partial = 0
        over_m2 = rem_m2 = rem_n = partial_on_apt = partial_m2 = 0.0
        partial = []
        for p in a.pavements:
            if not p.id.startswith("dsf:pol"):
                continue
            q = _poly(p.outer, p.holes)
            if q is None:
                continue
            if gate is not None:
                parts = _parts(q.intersection(gate))
                if not parts:
                    continue
                q = max(parts, key=lambda g: g.area)
            if q.area < dp.min_area_m2:
                continue
            n_pages += 1
            on = q.intersection(apt).area if not apt.is_empty else 0.0
            frac = on / q.area if q.area else 0.0
            if frac >= dp.overlay_fraction:
                n_over += 1
                over_m2 += q.area
                for g in _parts(q.difference(apt)):
                    if g.area >= dp.remainder_min_m2:
                        rem_n += 1
                        rem_m2 += g.area
            elif on > 1.0:
                n_partial += 1
                partial_on_apt += on
                partial_m2 += q.area
                partial.append((p.id, round(q.area), round(on), round(frac, 2), p.description[-40:]))
        cells = collections.Counter()
        cells_m2 = collections.Counter()
        for c in cl.cells:
            if REM.match(str(c.ref)):
                q = _poly(c.ring, c.holes)
                if q is None:
                    continue
                cells[(c.role, c.side)] += 1
                cells_m2[(c.role, c.side)] += q.area
        print(f"\n== {icao}: dsf:pol pages in the gate {n_pages}; OVERLAYS (>= {dp.overlay_fraction:.0%} on apt.dat) "
              f"{n_over} / {over_m2:,.0f} m2 -> remainder pieces {rem_n} / {rem_m2:,.0f} m2; "
              f"PARTIAL overlap (< {dp.overlay_fraction:.0%}, join the union whole) {n_partial} pages / "
              f"{partial_m2:,.0f} m2, of which {partial_on_apt:,.0f} m2 on apt.dat")
        print("   remainder-ref cells in the classification: "
              + (", ".join(f"{r}/{s} {n} ({cells_m2[(r, s)]:,.0f} m2)" for (r, s), n in cells.most_common()) or "none"))
        for row in sorted(partial, key=lambda t: -t[2])[:8]:
            print("   partial:", row)
    return 0


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    raise SystemExit(main(sys.argv[1:]))
