"""Per-runway-half BUILT CROSS-FALL on an emitted patch — the harness
reading of the runway transverse maximum (RULINGS 2026-09-05o/s: runways
are FLAT LATERALLY; ``rulesets.runway.transverse_max``).

    venv/bin/python tools/harness/rwy_xfall.py PATCH.osm [--icao HECA]
        [--half N --stations -764 36 536] [--json OUT.json]

Per ``runway`` way (a crown half): the max FALL and max RISE of
``(z_ridge(foot) − z_v) / d`` over its off-ridge ring vertices, the foot
being the nearest point on any ``o4_feature=crown_spine`` way (``d ≥
MIN_FOOT_M``, the identity floor), judged against the law's cap for the
way's code letter plus the census's noise envelope (``verify.frame.
noise_m``, the emit quantum) — the SAME population and allowance the v2
verify reader (``verify/runway.runway_transverse``) flags defects on, so
a half this tool reads OVER is a half the reader flags, and every half
``ok`` is the acceptance "≤ cap + quantum".  ``--half N`` additionally
prints the outer-edge vertex nearest each ``--stations`` value (along the
spine's principal axis, origin its midpoint) with its edge z, ridge z,
fall and grade — the owner-site read (HECA half 14).

Promoted 2026-09-05 (lane v2relaxfull) from lane v2rwytransverse's
scratchpad copy on its second use; ``check_grade``'s parser is the
library, the law is v2's tables.  Twin: ``tests/auto_patch_v2/
test_rwy_xfall.py``.
"""
from __future__ import annotations

import argparse
import dataclasses as _dc
import json
import math
import sys
import typing as _t
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1]
_ROOT = _TOOLS.parent
for _p in (_TOOLS, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import check_grade as cg  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.law.tables import runway_transverse_max  # noqa: E402
from auto_patch_v2.verify.frame import noise_m  # noqa: E402

__all__ = ["HalfReading", "read_cross_falls", "main"]

#: A vertex closer than this to the ridge is ON it (the emit identity floor
#: the verify reader's ``dist <= 0`` test rounds to on an emitted patch).
MIN_FOOT_M = 2.0


@_dc.dataclass(frozen=True)
class HalfReading:
    """One runway half's built cross-fall."""

    shape_id: str
    ref: str
    code_letter: str | None
    n_off_ridge: int
    max_fall: float          # (ridge − edge)/d, the steepest fall below the ridge
    max_rise: float          # (edge − ridge)/d, the steepest rise above it
    cap: float
    allowance: float         # noise / d at the worst vertex (the quantum's grade)
    ok: bool
    worst_nid: str | None

    @property
    def worst(self) -> float:
        return max(self.max_fall, self.max_rise)


def _nearest(px: float, py: float, spines: list[list[tuple[float, float, float]]]
             ) -> tuple[float, float | None, list | None]:
    best: tuple[float, float | None, list | None] = (math.inf, None, None)
    for pts in spines:
        for i in range(len(pts) - 1):
            ax, ay, az = pts[i]
            bx, by, bz = pts[i + 1]
            vx, vy = bx - ax, by - ay
            l2 = vx * vx + vy * vy
            t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
            d = math.hypot(px - (ax + t * vx), py - (ay + t * vy))
            if d < best[0]:
                best = (d, az + t * (bz - az), pts)
    return best


def read_cross_falls(patch: str | Path, icao: str | None = None, *,
                     half: str | None = None, stations: _t.Sequence[float] = (),
                     out: _t.Callable[[str], None] | None = None
                     ) -> list[HalfReading]:
    """Every runway half's reading (module docstring).  ``icao`` names the
    law (default: the patch's ``ICAO_`` prefix); ``half`` + ``stations``
    print the station read through ``out``."""
    patch = Path(patch)
    icao = icao or patch.name.split("_")[0][:4].upper()
    law = Law.for_airport(icao)
    feats: dict = {}
    nodes, ways = cg._parse_osm(patch, feature_out=feats)
    ll_to_m = cg._ll_to_m_factory(nodes)
    spines: list[list[tuple[float, float, float]]] = []
    for w in feats.get("crown_spine", []):
        pts = []
        for nid, z in zip(w.nids, w.elevs):
            if z is None:
                continue
            x, y = ll_to_m(*nodes[nid])
            pts.append((x, y, z))
        if len(pts) >= 2:
            spines.append(pts)
    say = out or (lambda s: None)
    say(f"{len(spines)} crown spines; law {law.ruleset_key}")
    xing: set[str] = set()
    for w in ways:
        if w.role == "runway_crossing":
            xing.update(w.nids)
    readings: list[HalfReading] = []
    for w in ways:
        if w.role != "runway":
            continue
        sid = w.tags.get("shapeID", w.wid)
        letter = w.tags.get("code_letter") or None
        number = w.tags.get("code_number")
        cap = runway_transverse_max(law, letter, int(number) if number else None)
        if cap is None:
            continue
        noise = noise_m(law, "runway")
        per_v = []
        for nid, z in zip(w.nids[:-1], w.elevs[:-1]):
            if z is None or nid in xing:
                continue
            x, y = ll_to_m(*nodes[nid])
            d, rz, sp = _nearest(x, y, spines)
            if rz is None or d < MIN_FOOT_M:
                continue
            per_v.append((nid, x, y, z, rz, d, (rz - z) / d, sp))
        if not per_v:
            continue
        worst = max(per_v, key=lambda v: abs(v[6]))
        max_fall = max(0.0, max(v[6] for v in per_v))
        max_rise = max(0.0, -min(v[6] for v in per_v))
        allowance = noise / worst[5]
        ok = abs(worst[6]) <= cap + allowance
        readings.append(HalfReading(sid, w.ref, letter, len(per_v), max_fall, max_rise,
                                    cap, allowance, ok, worst[0]))
        say(f"shape {sid:>5} {w.ref:<10} off-ridge {len(per_v):4d}  max fall {100*max_fall:6.2f} %"
            f"  max rise {100*max_rise:6.2f} %  cap {100*cap:.2f} % (+{100*allowance:.3f} % quantum)"
            f"  {'ok' if ok else 'OVER'}")
        if half is not None and str(half) == sid and stations:
            sp = max((v[7] for v in per_v), key=lambda s: sum(1 for v in per_v if v[7] is s))
            cx = sum(p[0] for p in sp) / len(sp)
            cy = sum(p[1] for p in sp) / len(sp)
            ux, uy = sp[-1][0] - sp[0][0], sp[-1][1] - sp[0][1]
            L = math.hypot(ux, uy) or 1.0
            ux, uy = ux / L, uy / L
            dmax = max(v[5] for v in per_v)
            outer = [v for v in per_v if v[5] > 0.5 * dmax]
            for s in stations:
                v = min(outer, key=lambda v: abs((v[1] - cx) * ux + (v[2] - cy) * uy - s))
                st = (v[1] - cx) * ux + (v[2] - cy) * uy
                say(f"  half {sid} station {s:+7.0f} (nearest outer vertex at {st:+7.1f} m, "
                    f"d {v[5]:.1f} m): edge z {v[3]:.2f}  ridge z {v[4]:.2f}  "
                    f"fall {v[4]-v[3]:+.2f} m  grade {100*v[6]:.2f} %")
    return readings


def main(argv: _t.Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("patch")
    ap.add_argument("--icao", default=None, help="the law's airport (default: the patch's prefix)")
    ap.add_argument("--half", default=None, help="shapeID of the half to station-read")
    ap.add_argument("--stations", type=float, nargs="*", default=[-764.0, 36.0, 536.0])
    ap.add_argument("--json", default=None, help="write the readings here")
    a = ap.parse_args(argv)
    readings = read_cross_falls(a.patch, a.icao, half=a.half, stations=a.stations, out=print)
    over = [r for r in readings if not r.ok]
    print(f"{len(readings)} runway halves; worst {100*max((r.worst for r in readings), default=0.0):.2f} %; "
          f"{len(over)} OVER the cap + quantum")
    if a.json:
        Path(a.json).write_text(json.dumps([_dc.asdict(r) for r in readings], indent=1))
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
