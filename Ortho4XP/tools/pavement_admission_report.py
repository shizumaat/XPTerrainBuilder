"""WHAT THE ``.pol`` PAVEMENT GATE REFUSES, WHAT A GATE CHANGE ADMITS, AND
WHAT THE ADMISSION DOES TO THE CLASSIFICATION — dry, off captures.

    venv/bin/python tools/pavement_admission_report.py refused CAP.pkl [...]
    venv/bin/python tools/pavement_admission_report.py diff ICAO=CTL.pkl,ARM.pkl [...]
        [--reclassify {none,arm,both}] [--min-m2 1.0] [--top 12]
    venv/bin/python tools/pavement_admission_report.py sheets CAP.pkl [...]
        [--pieces-out OUT.json] [--strip-out CONTROL.pkl]

Promoted from lane ``conc333`` / ``surface337``'s scratch ``refused.py``,
``admit_diff.py`` and ``trans.py`` on their second use (RULINGS ``7e90032``;
issues #333 / #337, RULINGS 2026-10-04d (2) / 04e (1)).

``refused``  Per capture (``v2_solve_replay --capture``): every ``.pol`` def
    in the pack's DSF dump (the capture's own ``inputs.dsf_dump_path``, read
    only) that ``airport/dsf.is_pavement_def`` refuses BY NAME, clipped to
    the apt.dat boundary (no boundary: the engine-read pavement + 60 m) —
    polygons, m2, m2 outside engine-read pavement, the file's own SURFACE
    and LAYER_GROUP rows, and the full gate's VERDICT on this tree
    (``dsf.pavement_gate``, file evidence included: ``source`` / ``sheet``).

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

``sheets``  THE GAP-SHEET ADMISSION (spec §60; promoted from the spec
    lane's ``docs/briefs/surfspec/admit_probe.py``).  Per capture: the
    dump's ``.pol`` polygons by this tree's verdict (source / sheet /
    refused), each SHEET def (n, m2 inside the classify gate, m2 on
    standing runway / taxi-family / apron cells, on pads, free of both),
    every refused def that DECLARES a hard surface with the reason it
    stays out, and — off the capture's own classification — the gap
    pieces standing (late road pieces ``gap:<k>`` and stage-1 apron
    pieces ``gapapron:<j>``) with THE BAR: m2 of any piece on a standing
    runway / taxi / apron cell (must be 0).  ``--pieces-out`` writes the
    pieces as lat/lon rings; ``--strip-out`` writes the capture WITHOUT
    its page sheets — the control arm of a ``v2_solve_replay --from
    classify`` pair (one capture only).

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
                  f"{decl.surface} / {decl.layer}"
                  f"{'  ADMIT as ' + admit if admit else ''}")
            res.append(dict(d=d, n=n, m2=m2, m2_off_pavement=mo,
                            surface=decl.surface, layer=decl.layer, admit=admit))
        out[icao] = res
    return out


def _mod_root(inp) -> str:
    """The capture's mod cache while it exists, else this tree's mount."""
    root = inp.mod_cache_root
    return root if root and os.path.isdir(root) else str(ROOT / "Airport_mod_cache")


def _dump_of(a, inp) -> str | None:
    """The capture's own dump when it still exists, else the dump of the
    pack's tile DSF in the capture's mod cache or this tree's mount (a
    capture outlives the lane tree it was taken in)."""
    from auto_patch_v2.airport import dsf as D
    if inp.dsf_dump_path and os.path.isfile(inp.dsf_dump_path):
        return inp.dsf_dump_path
    for p in a.pack.dsf_paths:
        base = os.path.basename(p)                         # +60-136.dsf
        got = D.find_text_dump(_mod_root(inp), a.pack.name, int(base[:3]),
                               int(base[3:7]), dsf_path=p if os.path.isfile(p) else None)
        if got:
            return got
    return None


def why_refused(path: str, layer: str | None) -> str:
    """Why a ``.pol`` that DECLARES a hard surface is still no pavement."""
    from auto_patch_v2.airport import dsf as D
    p = path.lower()
    if any(s in p for s in D.PAVEMENT_SKIP):
        return "decorative namespace"
    if any(s in p for s in D.SOFT_NAME_TOKENS):
        return "terrain word in the name"
    if layer == D.PAINT:
        return "paint layer group"
    if any(s in p for s in D.DECORATIVE_TOKENS):
        return "paint/sign word, file names no layer"
    return "?"


def piece_overlap(pieces, standing) -> dict:
    """m2 of gap piece on standing cells, by family — THE §60 BAR (0)."""
    out = {}
    pu = unary_union(pieces) if pieces else Polygon()
    for fam, polys in standing.items():
        out[fam] = float(pu.intersection(unary_union(polys)).area) if polys else 0.0
    return out


def sheets(caps: list[str], pieces_out: Path | None, strip_out: Path | None) -> dict:
    import dataclasses
    from auto_patch_v2.airport import dsf as D, obj8 as O
    from auto_patch_v2.classify import load_rules
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.planar import is_gap_apron_ref, is_gap_ref
    out = {}
    rules = load_rules()
    for pkl in caps:
        c = _load(pkl)
        a, inp, icao, cl = c["airport"], c["inputs"], c["icao"], c["cl"]
        prec = Law.for_airport(icao).tables.precedence
        fam_of = {r: "runway" for r in prec.runway_family.members}
        fam_of.update({r: "taxi" for r in prec.taxi_family.members})
        fam_of.update(apron="apron", building="pads")
        to_xy, to_ll = a.frame.transformers()
        root = os.path.dirname(os.path.dirname(a.pack.apt_dat_path))
        index = O.read_library_index(
            O.library_index_path(_mod_root(inp), inp.xplane_root))
        resolve = lambda p: O.resolve_resource(p, root, index)      # noqa: E731
        gate = D.pavement_gate(resolve)
        bnd = [_poly(b.outer) for b in a.boundaries]
        pav = unary_union([_poly(p.outer, p.holes) for p in a.pavements])
        clip = unary_union(bnd).buffer(float(rules.dsf_pavement.boundary_buffer_m)) \
            if bnd else pav.buffer(60.0)
        standing = collections.defaultdict(list)
        pieces = []
        for cell in cl.cells:
            g = _poly(cell.ring, cell.holes)
            if is_gap_ref(cell.ref) or is_gap_apron_ref(cell.ref):
                pieces.append((cell, g))
            elif not g.is_empty:
                standing[fam_of.get(cell.role, "other")].append(g)
        su = {k: unary_union(v) for k, v in standing.items()}
        hard = unary_union([su[k] for k in su if k != "pads"]) if su else Polygon()
        pads = su.get("pads", Polygon())
        page = [g for g in (getattr(a, "gap_sheets", ()) or ())
                if g.description.lower().endswith(".pol")]
        n_sheets = len(getattr(a, "gap_sheets", ()) or ())
        print(f"\n== {icao} pack={a.pack.name!r}  capture gap sheets: "
              f"{n_sheets - len(page)} object bodies + {len(page)} .pol pages")
        res: dict = {"capture": str(pkl), "capture_page_sheets": len(page),
                     "capture_object_sheets": n_sheets - len(page)}
        dump_path = _dump_of(a, inp)
        counts, rows, refd = collections.Counter(), {}, collections.Counter()
        decls: dict = {}
        if dump_path is None:
            print("  NO DUMP found for the pack — the gate reading is skipped")
        else:
            dump = D.read_dump(dump_path, lambda p: p.lower().endswith(".pol"))
            for pg in dump.polygons:
                d = pg.def_path
                verdict = gate(d)[0]
                counts[verdict or "refused"] += 1
                if verdict == D.SOURCE:
                    continue
                if d not in decls:
                    decls[d] = D.pol_declaration(resolve(d))
                if verdict is None:
                    if decls[d].surface in D.HARD_SURFACES:
                        refd[d] += 1
                    continue
                rings = [[to_xy(lon, lat) for lon, lat in w] for w in pg.windings]
                s = _poly(rings[0], rings[1:]).intersection(clip)
                r = rows.setdefault(d, collections.Counter())
                r["n"] += 1
                r["m2"] += s.area
                for k, u in su.items():
                    if k in ("runway", "taxi", "apron", "pads"):
                        r[k] += s.intersection(u).area
                r["standing"] += s.intersection(hard).area
                r["free"] += s.difference(hard).difference(pads).area
        print(f"  dump .pol polygons by verdict: source {counts[D.SOURCE]} / "
              f"sheet {counts[D.SHEET]} / refused {counts['refused']}")
        cols = ("n", "m2", "runway", "taxi", "apron", "standing", "pads", "free")
        if rows:
            print(f"  {'SHEET def (m2 inside the classify gate)':58s} "
                  + " ".join(f"{k:>9s}" for k in cols) + "  SURFACE / LAYER_GROUP")
        tot = collections.Counter()
        for d, r in sorted(rows.items(), key=lambda kv: -kv[1]["m2"]):
            tot.update(r)
            print(f"  {d[-58:]:58s} " + " ".join(f"{r[k]:9.0f}" for k in cols)
                  + f"  {decls[d].surface} / {decls[d].layer}")
        if len(rows) > 1:
            print(f"  {'TOTAL':58s} " + " ".join(f"{tot[k]:9.0f}" for k in cols))
        if not rows and dump_path is not None:
            print("  NOTHING is admitted by SURFACE alone at this airport")
        for d, n in refd.most_common():
            print(f"  refused though {decls[d].surface}: {d[-58:]:58s} n={n:5d}  "
                  f"{why_refused(d, decls[d].layer)}")
        res.update(dump=dump_path, verdicts={str(k): v for k, v in counts.items()},
                   sheet_defs={d: dict(r, surface=decls[d].surface, layer=decls[d].layer)
                               for d, r in rows.items()},
                   refused_hard={d: dict(n=n, surface=decls[d].surface, layer=decls[d].layer,
                                         why=why_refused(d, decls[d].layer))
                                 for d, n in refd.items()})
        # ── the pieces the capture's classification stands ──────────
        late = [(cc, g) for cc, g in pieces if is_gap_ref(cc.ref)]
        apron = [(cc, g) for cc, g in pieces if not is_gap_ref(cc.ref)]
        over = piece_overlap([g for _c, g in pieces],
                             {k: v for k, v in standing.items()
                              if k in ("runway", "taxi", "apron")})
        print(f"  gap pieces standing: {len(late)} late road cells "
              f"{sum(g.area for _c, g in late):,.0f} m2 + {len(apron)} apron cells "
              f"{sum(g.area for _c, g in apron):,.0f} m2;  ON STANDING CELLS (bar 0): "
              + ", ".join(f"{k} {over.get(k, 0.0):.1f} m2" for k in ("runway", "taxi", "apron")))
        res.update(pieces_late=len(late), pieces_late_m2=sum(g.area for _c, g in late),
                   pieces_apron=len(apron), pieces_apron_m2=sum(g.area for _c, g in apron),
                   piece_on_standing_m2=over)
        if pieces_out:
            pieces_out.write_text(json.dumps([
                {"ref": str(cc.ref), "role": cc.role, "m2": round(g.area),
                 "ring_ll": [list(to_ll(x, y)) for x, y in cc.ring]}
                for cc, g in pieces]), encoding="utf-8", newline="\n")
        if strip_out:
            kept = tuple(g for g in a.gap_sheets
                         if not g.description.lower().endswith(".pol"))
            with open(strip_out, "wb") as fh:
                pickle.dump(dict(c, airport=dataclasses.replace(a, gap_sheets=kept)), fh,
                            protocol=pickle.HIGHEST_PROTOCOL)
            print(f"  control capture without the {len(page)} page sheet(s) -> {strip_out}")
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
    # The console is UTF-8 before the parser can print (#171, #125); a
    # library with a CLI pins in its entry.  Twin: test_console_encoding.
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
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
    s = sub.add_parser("sheets")
    s.add_argument("captures", nargs="+")
    s.add_argument("--pieces-out", type=Path,
                   help="the standing gap pieces as lat/lon rings (one capture)")
    s.add_argument("--strip-out", type=Path,
                   help="write the capture without its page sheets (one capture)")
    for p in (r, d, s):
        p.add_argument("--json", type=Path)
    args = ap.parse_args()
    if args.cmd == "refused":
        res = refused(args.captures)
    elif args.cmd == "sheets":
        if (args.pieces_out or args.strip_out) and len(args.captures) != 1:
            ap.error("--pieces-out / --strip-out take exactly one capture")
        res = sheets(args.captures, args.pieces_out, args.strip_out)
    else:
        res = {s.split("=")[0]: diff(s, args.reclassify, args.min_m2, args.top)
               for s in args.pairs}
    if args.json:
        args.json.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8",
                             newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
