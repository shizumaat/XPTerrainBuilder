"""WHAT THE ``.pol`` PAVEMENT GATE REFUSES, WHAT A GATE CHANGE ADMITS, AND
WHAT THE ADMISSION DOES TO THE CLASSIFICATION — dry, off captures.

    venv/bin/python tools/pavement_admission_report.py refused CAP.pkl [...]
    venv/bin/python tools/pavement_admission_report.py diff ICAO=CTL.pkl,ARM.pkl [...]
        [--reclassify {none,arm,both}] [--min-m2 1.0] [--top 12]

Promoted from lane ``conc333`` / ``surface337``'s scratch ``refused.py``,
``admit_diff.py`` and ``trans.py`` on their second use (RULINGS ``7e90032``;
issues #333 / #337, RULINGS 2026-10-04d (2) / 04e (1)).

``refused``  Per capture (``v2_solve_replay --capture``): every ``.pol`` def
    in the pack's DSF dump (the capture's own ``inputs.dsf_dump_path``, read
    only) that ``airport/dsf.is_pavement_def`` refuses BY NAME, clipped to
    the apt.dat boundary (no boundary: the engine-read pavement + 60 m) —
    polygons, m2, m2 outside engine-read pavement, the file's own SURFACE
    and LAYER_GROUP rows, and whether the full gate (``dsf.pavement_gate``,
    file evidence included) ADMITS it on this tree.

``diff``  Control capture vs arm capture of one airport: the pavements the
    arm admitted that the control did not (joined by GEOMETRY — ``dsf:polN``
    ids are dump indices and shift with every admission), by def: n, m2,
    m2 outside the control's pavement, and the role/side the newly
    classified ground was given; the role-area delta; the paved area
    outside the control's cell footprint; and THE TRANSITION TABLE — ground
    whose (role, source family) changed between the two classifications —
    in full and RESTRICTED TO GROUND APT.DAT PAVEMENT COVERS (role changes,
    and ref-only changes of one role, apart).  ``--reclassify arm|both``
    re-runs the CLASSIFY stage alone on the captured ``Airport`` under THIS
    tree (seconds; ``v2_solve_replay.reclassify``'s own trick) instead of
    reading the classification the capture holds.

IT PRICES NO LAW AND COUNTS NO DEFECTS (``harness/census.py`` does), reads
captures and the dump only, and writes nothing but ``--json``.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pickle
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shapely.geometry import Polygon                      # noqa: E402
from shapely.ops import unary_union                       # noqa: E402
from shapely.strtree import STRtree                       # noqa: E402


def _poly(outer, holes=()):
    p = Polygon(list(outer), [list(h) for h in holes if len(h) >= 3])
    return p if p.is_valid else p.buffer(0)


def _load(path):
    with open(path, "rb") as fh:
        return pickle.load(fh)


def _family(ref) -> str:
    """The source family of a cell ref: apt / dsf / the ref's own prefix."""
    r = str(ref)
    if r.startswith("dsf:"):
        return "dsf"
    if r.startswith("pav"):
        return "apt"
    return r.split(":")[0].rstrip("0123456789#") or r


def refused(caps: list[str]) -> dict:
    from auto_patch_v2.airport import dsf as D, obj8 as O
    out = {}
    for pkl in caps:
        c = _load(pkl)
        a, inp, icao = c["airport"], c["inputs"], c["icao"]
        to_xy, _ = a.frame.transformers()
        root = os.path.dirname(os.path.dirname(a.pack.apt_dat_path))
        index = O.read_library_index(
            O.library_index_path(inp.mod_cache_root, inp.xplane_root))
        resolve = lambda p: O.resolve_resource(p, root, index)      # noqa: E731
        gate = D.pavement_gate(resolve)
        bnd = [_poly(b.outer) for b in a.boundaries]
        pav = unary_union([_poly(p.outer, p.holes) for p in a.pavements])
        clip = unary_union(bnd) if bnd else pav.buffer(60.0)
        rows = collections.defaultdict(lambda: [0, 0.0, 0.0])
        dump = D.read_dump(inp.dsf_dump_path, lambda p: p.lower().endswith(".pol"))
        for pg in dump.polygons:
            if D.is_pavement_def(pg.def_path):
                continue
            rings = [[to_xy(lon, lat) for lon, lat in w] for w in pg.windings]
            s = _poly(rings[0], rings[1:]).intersection(clip)
            if s.is_empty or s.area < 1.0:
                continue
            r = rows[pg.def_path]
            r[0] += 1
            r[1] += s.area
            r[2] += s.difference(pav).area
        print(f"\n== {icao} pack={a.pack.name!r} "
              f"clip={'apt.dat boundary' if bnd else 'pavement + 60 m'}")
        print(f"  {'def':66s} {'n':>5s} {'m2':>10s} {'m2 off pav':>10s}  "
              f"SURFACE / LAYER_GROUP")
        res = []
        for d, (n, m2, mo) in sorted(rows.items(), key=lambda kv: -kv[1][1]):
            decl = D.pol_declaration(resolve(d))
            admit = gate(d)[0]
            print(f"  {d[-66:]:66s} {n:5d} {m2:10.0f} {mo:10.0f}  "
                  f"{decl.surface} / {decl.layer}{'  ADMIT' if admit else ''}")
            res.append(dict(d=d, n=n, m2=m2, m2_off_pavement=mo,
                            surface=decl.surface, layer=decl.layer, admit=admit))
        out[icao] = res
    return out


def _cells(cap, reclassify: bool):
    if not reclassify:
        return cap["cl"]
    from auto_patch_v2.classify import classify, load_rules
    from auto_patch_v2.law import Law
    return classify(cap["airport"], Law.for_airport(cap["icao"]), load_rules())


def diff(spec: str, reclassify: str, min_m2: float, top: int) -> dict:
    icao, paths = spec.split("=", 1)
    fa, fb = paths.split(",")
    A, B = _load(fa), _load(fb)
    a, b = A["airport"], B["airport"]
    cla = _cells(A, reclassify == "both")
    clb = _cells(B, reclassify in ("arm", "both"))
    key = lambda p: (len(p.outer), round(p.outer[0][0], 3), round(p.outer[0][1], 3))  # noqa: E731
    ka = {key(p) for p in a.pavements}
    new = [p for p in b.pavements if key(p) not in ka]
    pav_a = unary_union([_poly(p.outer, p.holes) for p in a.pavements])
    apt = unary_union([_poly(p.outer, p.holes) for p in b.pavements
                       if not p.id.startswith("dsf:")])
    ca = [(c, _poly(c.ring, c.holes)) for c in cla.cells]
    cb = [(c, _poly(c.ring, c.holes)) for c in clb.cells]
    paved_a = unary_union([g for c, g in ca if c.role != "building"])
    foot_a = unary_union([g for _c, g in ca])
    print(f"\n== {icao}: pavements {len(a.pavements)} -> {len(b.pavements)} "
          f"(new {len(new)})  cells {len(ca)} -> {len(cb)}  "
          f"classification: control {'RE-RUN' if reclassify == 'both' else 'captured'}, "
          f"arm {'RE-RUN' if reclassify != 'none' else 'captured'}")
    out: dict = {"new": [], "transitions": [], "apt_ground": []}
    bydef = collections.defaultdict(list)
    for p in new:
        bydef[p.description].append(_poly(p.outer, p.holes))
    paved_b = [(c, g) for c, g in cb if c.role != "building"]
    for d, ps in sorted(bydef.items(), key=lambda kv: -sum(x.area for x in kv[1])):
        fresh = unary_union(ps).difference(pav_a)
        newc = fresh.difference(paved_a)
        by = collections.Counter()
        for c, g in paved_b:
            if g.intersects(newc):
                ar = g.intersection(newc).area
                if ar > 0.5:
                    by[f"{c.role}/{c.side}"] += ar
        m2 = sum(x.area for x in ps)
        print(f"  ADMITTED {d[-58:]:58s} n={len(ps):4d} m2={m2:10.0f} "
              f"off control pavement={fresh.area:9.0f}  newly classified: "
              + (", ".join(f"{k} {v:.0f}" for k, v in by.most_common()) or "none"))
        out["new"].append(dict(d=d, n=len(ps), m2=m2, off_control_pavement=fresh.area,
                               newly_classified=dict(by)))
    ra, rb = collections.Counter(), collections.Counter()
    for cs, r in ((ca, ra), (cb, rb)):
        for c, g in cs:
            r[f"{c.role}/{c.side}"] += g.area
    delta = {k: round(rb[k] - ra[k]) for k in set(ra) | set(rb)
             if abs(rb[k] - ra[k]) > 0.5}
    print("  role area delta m2:", dict(sorted(delta.items(), key=lambda kv: -abs(kv[1]))) or "none")
    armp = unary_union([g for _c, g in paved_b])
    out["outside_control_footprint_m2"] = armp.difference(foot_a).area
    print(f"  paved cells outside the control cell footprint: "
          f"{out['outside_control_footprint_m2']:.0f} m2")
    # ── the transition table ────────────────────────────────────────
    tree = STRtree([g for _c, g in cb])
    T, TA, RA = collections.Counter(), collections.Counter(), collections.Counter()
    ex = collections.defaultdict(list)
    for c, g in ca:
        for j in tree.query(g):
            d, h = cb[int(j)]
            same_role = c.role == d.role
            if same_role and str(c.ref) == str(d.ref):
                continue
            x = g.intersection(h)
            if x.area <= min_m2:
                continue
            k = (f"{c.role}[{_family(c.ref)}]", f"{d.role}[{_family(d.ref)}]")
            on_apt = x.intersection(apt).area
            if not same_role or _family(c.ref) != _family(d.ref):
                T[k] += x.area
                ex[k].append((str(c.ref), str(d.ref), round(x.area)))
            if on_apt > min_m2 and "building" not in (c.role, d.role):
                (RA if same_role else TA)[k] += on_apt
                ex[("apt",) + k].append((str(c.ref), str(d.ref), round(on_apt)))
    def show(title, tab, pre=()):                                  # noqa: E306
        print(f"  {title}: {sum(tab.values()):.0f} m2 in {len(tab)} kind(s)")
        for k, v in tab.most_common(top):
            e = sorted(ex[pre + k], key=lambda t: -t[2])[:2]
            print(f"    {v:9.0f} m2  {k[0]:30s} -> {k[1]:30s} e.g. {e}")
    show("TRANSITIONS, all ground (role or source family changed)", T)
    show("ON APT.DAT PAVEMENT — ROLE CHANGES (the bar: zero)", TA, ("apt",))
    show("ON APT.DAT PAVEMENT — ref-only changes, same role", RA, ("apt",))
    out["transitions"] = [dict(a=k[0], b=k[1], m2=v) for k, v in T.most_common()]
    out["apt_ground"] = [dict(a=k[0], b=k[1], m2=v) for k, v in TA.most_common()]
    out["apt_ground_ref_only_m2"] = sum(RA.values())
    return out


def main() -> int:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refused")
    r.add_argument("captures", nargs="+")
    d = sub.add_parser("diff")
    d.add_argument("pairs", nargs="+", metavar="ICAO=CTL.pkl,ARM.pkl")
    d.add_argument("--reclassify", choices=("none", "arm", "both"), default="none")
    d.add_argument("--min-m2", type=float, default=1.0)
    d.add_argument("--top", type=int, default=12)
    for p in (r, d):
        p.add_argument("--json", type=Path)
    args = ap.parse_args()
    if args.cmd == "refused":
        res = refused(args.captures)
    else:
        res = {s.split("=")[0]: diff(s, args.reclassify, args.min_m2, args.top)
               for s in args.pairs}
    if args.json:
        args.json.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8",
                             newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
