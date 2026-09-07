"""THE RUNWAY-EDGE TIE read GEOMETRICALLY on an emitted patch (RULINGS
2026-09-06p (1)/(3); the scout's ``geo_count.py`` promoted on its second
use, 2026-09-06, lane v2ridge).

    venv/bin/python tools/harness/runway_edge_tie.py PATCH.osm [--icao HECA]
        [--rwy 05C/23C] [--worst N] [--all] [--json OUT.json]

Every vertex of every way — ANY role but the runway family's own and a
``retaining_wall`` crest — lying abeam a runway-family ring edge inside
that runway's zone-2 half width, against the edge foot (the elevation
interpolated along the edge): the rise ``z_v − z_foot`` judged at
``strip_transverse_bound(d)`` (the strip corridor's transverse cap
accumulated over ``d``) plus the census's coarse quantum, EITHER way for
every vertex (RULINGS 2026-09-06q (2)).  Generator-independent by construction — it never
reads a published pair list (owner 2026-09-06o: both instruments passed
HECA's 05C/23C ridges because no pair had been minted to the runway edge
7 m away).  Prints, per ROLE SET of the vertex's ways, the vertices in
reach, those OVER the bound and the worst (rise, d, node id, runway ref);
``--worst N`` lists the N worst with lat/lon, z, edge z, d and the bound;
``--rwy REF`` restricts the reading to one runway; ``--json`` dumps every
hit.  Exit 1 when any vertex is over.

ONE core: ``check_grade.runway_edge_tie_frame`` (the population, the
edges, the abeam axes — the oracle's ``strip_transverse`` family reads
the same frame) and ``auto_patch_v2.verify.strips.runway_edge_tie`` (the
geometry and the bound — the v2 verify reader's own).  Twin:
``tests/auto_patch_v2/test_v2ridge.py``.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses as _dc
import json
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
from auto_patch_v2.verify.strips import runway_edge_tie  # noqa: E402

__all__ = ["TieReading", "read_ties", "main"]


@_dc.dataclass(frozen=True)
class TieReading:
    """One vertex in reach of a runway edge."""

    nid: str
    roles: str               # the role set of the vertex's ways, "+"-joined
    ref: str                 # the runway
    lat: float
    lon: float
    z: float
    z_foot: float
    d: float
    rise: float              # z − z_foot (signed)
    bound: float
    over: bool
    both_ways: bool          # a graded-strip-only vertex (the 06b label; every vertex reads either way since 06q)


def read_ties(patch: str | Path, icao: str | None = None, *, rwy: str | None = None,
              out: _t.Callable[[str], None] | None = None) -> list[TieReading]:
    """Every vertex in reach with its reading (module docstring)."""
    patch = Path(patch)
    icao = icao or patch.name.split("_")[0][:4].upper()
    law = Law.for_airport(icao)
    q = law.tables.emit.instrument.coarse_noise_m
    edge_tol = law.tables.emit.identity.min_distinct_spacing_m
    nodes, ways = cg._parse_osm(patch)
    ll_to_m = cg._ll_to_m_factory(nodes)
    points, edges, axes, _rw = cg.runway_edge_tie_frame(ways, nodes, ll_to_m, law)
    if rwy is not None:
        edges = [e for e in edges if e[2] == rwy]
    roles_at: dict[str, set[str]] = {}
    for w in ways:
        r = cg.effective_role(w)
        if r:
            for nid in w.nids:
                roles_at.setdefault(nid, set()).add(r)
    say = out or (lambda s: None)
    say(f"{len(points)} vertices, {len(edges)} runway-family ring edges, law {law.ruleset_key}"
        + (f", runway {rwy}" if rwy else ""))
    hits = runway_edge_tie(points, edges, axes, law, q, edge_tol, all_hits=True)
    readings: list[TieReading] = []
    for h in hits:
        lat, lon = nodes[h.vid]
        rs = "+".join(sorted(roles_at.get(h.vid, {"?"})))
        both = roles_at.get(h.vid) == {"graded_strip"}
        # two-way for every vertex (RULINGS 2026-09-06q (2)); ``both`` is
        # the strip-only label the 06b reading named
        over = abs(h.dz) > h.bound + q
        readings.append(TieReading(h.vid, rs, h.ref, lat, lon, h.z, h.z_foot, h.d, h.dz,
                                   h.bound, over, both))
    return readings


def table(readings: _t.Sequence[TieReading]) -> list[str]:
    cnt: collections.Counter = collections.Counter()
    over: collections.Counter = collections.Counter()
    worst: dict[str, TieReading] = {}
    for r in readings:
        cnt[r.roles] += 1
        if r.over:
            over[r.roles] += 1
            if r.roles not in worst or abs(r.rise) > abs(worst[r.roles].rise):
                worst[r.roles] = r
    lines = ["vertices in reach of a runway-family edge, by role set:"]
    for k, n in cnt.most_common():
        w = worst.get(k)
        lines.append(f"  {k:45s} n {n:5d}  over {over[k]:4d}"
                     + (f"  worst +{w.rise:.2f} m at {w.d:.1f} m node {w.nid} {w.ref}" if w else ""))
    lines.append(f"TOTAL {sum(cnt.values())} over {sum(over.values())}")
    return lines


def main(argv: _t.Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("patch")
    ap.add_argument("--icao", default=None, help="the law's airport (default: the patch's prefix)")
    ap.add_argument("--rwy", default=None, help="restrict to one runway ref")
    ap.add_argument("--worst", type=int, default=0, help="list the N worst vertices")
    ap.add_argument("--json", default=None, help="write every reading here")
    a = ap.parse_args(argv)
    readings = read_ties(a.patch, a.icao, rwy=a.rwy, out=print)
    for ln in table(readings):
        print(ln)
    if a.worst:
        for r in sorted((r for r in readings if r.over), key=lambda r: -abs(r.rise))[:a.worst]:
            print(f"  +{r.rise:.2f} m at d {r.d:.1f} (bound {r.bound:.2f}) node {r.nid} "
                  f"{r.roles} {r.ref} z {r.z:.2f} edge {r.z_foot:.2f} @ {r.lat:.6f},{r.lon:.6f}")
    if a.json:
        Path(a.json).write_text(json.dumps([_dc.asdict(r) for r in readings], indent=1))
    return 1 if any(r.over for r in readings) else 0


if __name__ == "__main__":
    sys.exit(main())
