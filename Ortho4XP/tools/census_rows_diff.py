"""Row-level A/B between two ``census.py --rows-json`` dumps.

`harness/census.py --rows-json` itemises a patch's law-true rows; nothing
read them back.  A CLASS delta says a family moved by N.  It cannot say
WHICH N, and it hides equal churn by construction — 200 new rows and 182
gone read as "+18".  The zero-new-adjudicated-airside bar is a claim
about ROWS, so it needs a row-level reader.

**This tool derives no law and measures nothing.**  Every row is read
verbatim out of a census dump; the census remains the only instrument
that produces defect counts (the census-wrapper precedent, RULINGS
`7e90032`).  What it adds is the JOIN, and the join is the part that can
lie, so it is explicit in three tiers:

  EXACT      same family, same role pair, same side, and both endpoint
             coordinates identical to the millimetre in the patch's own
             layout-local metre frame.  The row did not move.
  MOVED      the same class, matched to the nearest surviving partner
             within ``--tol`` metres (default 0.50 m) of BOTH endpoints,
             each partner used once.  The row is the same defect at a
             moved vertex — the class a geometry repair produces — and
             its magnitude delta is reported.
  NEW/GONE   no partner within tolerance.  These are the rows an
             attribution owes a mechanism for.

A MOVED match is an inference and is labelled one everywhere it appears;
raising ``--tol`` moves rows out of NEW/GONE and into MOVED, so the
tolerance is printed with every table and the counts at two tolerances
are the honest way to show the join is not doing the work.

The two dumps must share a law frame: identical ``law_true_knobs`` and
``axis_frame``, or the tool REFUSES — two dumps read under different law
knobs are the two-instruments trap with a join bolted on.  Their patch
provenance is expected to differ (that is the A/B) and is printed.

Usage::

    venv/bin/python tools/census_rows_diff.py A.rows.json B.rows.json \\
        [--tol 0.5] [--side airside] [--family F] [--top 20] \\
        [--json OUT.json]

``--side`` / ``--family`` filter the REPORT, never the join (a row is
matched against the whole population, then reported or not).
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

DEFAULT_TOL_M = 0.50


def load_dump(path: Path) -> dict:
    """One ``--rows-json`` dump, with the fields this tool needs checked."""
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"REFUSING: cannot read {path}: {exc}")
    for key in ("rows", "law_true_knobs", "n_rows"):
        if key not in d:
            raise SystemExit(
                f"REFUSING: {path} is not a census --rows-json dump "
                f"(no '{key}' key).  A class-level census JSON has no rows; "
                f"re-run the census with --rows-json.")
    if len(d["rows"]) != d["n_rows"]:
        raise SystemExit(
            f"REFUSING: {path} claims {d['n_rows']} rows and carries "
            f"{len(d['rows'])} — a truncated dump.")
    return d


def assert_same_frame(a: dict, b: dict, a_name: str, b_name: str) -> None:
    """Refuse a join across law frames (the two-instruments trap)."""
    if a["law_true_knobs"] != b["law_true_knobs"]:
        raise SystemExit(
            f"REFUSING: the two dumps were read under different law knobs, "
            f"so their rows are not the same population.\n"
            f"  {a_name}: {a['law_true_knobs']}\n"
            f"  {b_name}: {b['law_true_knobs']}")
    fa = (a.get("axis_frame") or {}).get("frame")
    fb = (b.get("axis_frame") or {}).get("frame")
    if fa != fb:
        raise SystemExit(
            f"REFUSING: different AXIS FRAMES ({fa!r} vs {fb!r}).  A "
            f"base-frame number is a frame claim, never a defect count; "
            f"joining one to an own-frame dump compares two populations.")


def row_class(r: dict) -> tuple:
    """The class a row is matched WITHIN — never across."""
    return (r.get("family"), r.get("roles"), r.get("side"))


def _pts(r: dict) -> tuple:
    """Both endpoints in the patch's layout-local metre frame, ordered so
    an A-B/B-A spelling of one edge is one key."""
    site = r.get("site_m") or []
    pts = tuple(tuple(round(float(c), 3) for c in p) for p in site)
    return tuple(sorted(pts))


def exact_key(r: dict) -> tuple:
    return row_class(r) + _pts(r)


def _sep(pa: tuple, pb: tuple) -> float:
    """Worst endpoint separation between two 2-point sites (metres).

    Both are already sorted, so this is the pairing the sort implies; a
    row whose two endpoints swapped order under the sort is still the
    same edge.  Returns ``inf`` when the sites are not comparable
    (different endpoint counts) — never a silent 0.
    """
    if len(pa) != len(pb) or not pa:
        return math.inf
    return max(math.dist(x, y) for x, y in zip(pa, pb))


def diff_rows(rows_a: list[dict], rows_b: list[dict],
              tol_m: float = DEFAULT_TOL_M) -> dict:
    """The three-tier join.  Returns exact / moved / gone / new lists.

    Each A row partners at most one B row and vice versa.  EXACT pairs
    are consumed first (a coordinate-identical partner always beats a
    near one), then MOVED greedily by nearest separation within class.
    """
    used_b: set[int] = set()
    exact: list[tuple[dict, dict]] = []
    by_key: dict[tuple, list[int]] = {}
    for j, rb in enumerate(rows_b):
        by_key.setdefault(exact_key(rb), []).append(j)
    unmatched_a: list[int] = []
    for i, ra in enumerate(rows_a):
        pool = by_key.get(exact_key(ra))
        j = None
        while pool:
            cand = pool.pop()
            if cand not in used_b:
                j = cand
                break
        if j is None:
            unmatched_a.append(i)
        else:
            used_b.add(j)
            exact.append((ra, rows_b[j]))

    # MOVED — within class only, nearest first, each partner once.
    free_b_by_class: dict[tuple, list[int]] = {}
    for j, rb in enumerate(rows_b):
        if j not in used_b:
            free_b_by_class.setdefault(row_class(rb), []).append(j)
    cands: list[tuple[float, int, int]] = []
    for i in unmatched_a:
        ra = rows_a[i]
        pa = _pts(ra)
        for j in free_b_by_class.get(row_class(ra), ()):
            s = _sep(pa, _pts(rows_b[j]))
            if s <= tol_m:
                cands.append((s, i, j))
    cands.sort()
    taken_a: set[int] = set()
    moved: list[tuple[dict, dict, float]] = []
    for s, i, j in cands:
        if i in taken_a or j in used_b:
            continue
        taken_a.add(i)
        used_b.add(j)
        moved.append((rows_a[i], rows_b[j], s))

    gone = [rows_a[i] for i in unmatched_a if i not in taken_a]
    new = [rows_b[j] for j in range(len(rows_b)) if j not in used_b]
    return {"exact": exact, "moved": moved, "gone": gone, "new": new,
            "tol_m": tol_m}


def _keep(r: dict, side: str | None, family: str | None) -> bool:
    if side and r.get("side") != side:
        return False
    if family and r.get("family") != family:
        return False
    return True


def _class_tally(rows: Iterable[dict]) -> Counter:
    return Counter(f"{r.get('family')}::{r.get('roles')}"
                   f"[{r.get('side')}]" for r in rows)


def _fmt_row(r: dict) -> str:
    mag = r.get("magnitude_m")
    grade = r.get("grade_pct")
    cap = r.get("cap_pct")
    return (f"{r.get('family','?'):<22} {str(r.get('roles','?')):<44} "
            f"{str(r.get('side','?')):<11} "
            f"|de|={0.0 if mag is None else mag:>10.3f} m  "
            f"grade={('-' if grade is None else f'{grade:.3f}%'):>12}"
            f"/{('none' if cap is None else f'{cap:.3f}%'):<9} "
            f"@({r.get('lat'):.6f},{r.get('lon'):.6f}) "
            f"ways={r.get('way_a')}|{r.get('way_b')}"
            f"{'  [out-of-scope: ' + str(r.get('out_of_scope')) + ']' if r.get('out_of_scope') else ''}")


def report(res: dict, a: dict, b: dict, *, side=None, family=None,
           top: int = 20) -> list[str]:
    out: list[str] = []
    p = out.append
    tol = res["tol_m"]
    p(f"=== ROW-LEVEL A/B  (join tolerance {tol:.3f} m) ===")
    p(f"  A  {a.get('patch')}")
    p(f"     provenance sha={(a.get('provenance') or {}).get('sha')} "
      f"dirty={(a.get('provenance') or {}).get('dirty')}  rows={a['n_rows']}")
    p(f"  B  {b.get('patch')}")
    p(f"     provenance sha={(b.get('provenance') or {}).get('sha')} "
      f"dirty={(b.get('provenance') or {}).get('dirty')}  rows={b['n_rows']}")
    p(f"  law knobs (identical, asserted): {a['law_true_knobs']}")
    p(f"  axis frame: {(a.get('axis_frame') or {}).get('frame')}")
    p("")
    filt = (side or family)
    def keep(rs):
        return [r for r in rs if _keep(r, side, family)]
    ex = keep([x[1] for x in res["exact"]])
    mv = [(x, y, s) for x, y, s in res["moved"] if _keep(y, side, family)]
    gn = keep(res["gone"])
    nw = keep(res["new"])
    if filt:
        p(f"  REPORT FILTER: side={side or 'any'} family={family or 'any'} "
          f"(the join ran on the FULL population; this filters the tables)")
    p(f"  EXACT (same class, coordinates identical to 1 mm) : {len(ex)}")
    p(f"  MOVED (same class, partner within {tol:.2f} m)     : {len(mv)}"
      f"   ← an INFERENCE, not an identity")
    p(f"  GONE  (A only, no partner)                        : {len(gn)}")
    p(f"  NEW   (B only, no partner)                        : {len(nw)}")
    p(f"  NET   (NEW − GONE)                                : "
      f"{len(nw) - len(gn):+d}")
    p("")
    if mv:
        worst = sorted(mv, key=lambda t: -abs((t[1].get('magnitude_m') or 0.0)
                                              - (t[0].get('magnitude_m') or 0.0)))
        p(f"  MOVED rows whose MAGNITUDE changed most (top {top}):")
        for ra, rb, s in worst[:top]:
            da = (rb.get('magnitude_m') or 0.0) - (ra.get('magnitude_m') or 0.0)
            p(f"    Δ|de|={da:+9.3f} m  moved {s:6.3f} m   {_fmt_row(rb)}")
        p("")
    for label, rows in (("NEW", nw), ("GONE", gn)):
        if not rows:
            continue
        p(f"  {label} by class:")
        for cls, n in _class_tally(rows).most_common():
            p(f"    {n:>6}  {cls}")
        p(f"  {label} rows, worst {top} by |de|:")
        for r in sorted(rows,
                        key=lambda r: -(r.get('magnitude_m') or 0.0))[:top]:
            p(f"    {_fmt_row(r)}")
        p("")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path, metavar="A.rows.json",
                    help="the BASELINE dump (the control arm)")
    ap.add_argument("b", type=Path, metavar="B.rows.json",
                    help="the dump under test")
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL_M,
                    help="MOVED-match tolerance in metres on BOTH endpoints "
                         f"(default {DEFAULT_TOL_M}).  Raising it converts "
                         "NEW/GONE into MOVED — quote two tolerances when "
                         "the join is load-bearing")
    ap.add_argument("--side", default=None,
                    choices=("airside", "groundside", "mixed", "unknown"),
                    help="filter the REPORT to one side (never the join)")
    ap.add_argument("--family", default=None,
                    help="filter the REPORT to one law family")
    ap.add_argument("--top", type=int, default=20,
                    help="rows per worst-N table (default 20)")
    ap.add_argument("--json", type=Path, default=None,
                    help="also write the full NEW / GONE / MOVED lists here")
    args = ap.parse_args(argv)

    a = load_dump(args.a)
    b = load_dump(args.b)
    assert_same_frame(a, b, str(args.a), str(args.b))
    res = diff_rows(a["rows"], b["rows"], tol_m=args.tol)
    for line in report(res, a, b, side=args.side, family=args.family,
                       top=args.top):
        print(line)
    if args.json:
        args.json.write_text(json.dumps({
            "a": {"patch": a.get("patch"), "provenance": a.get("provenance"),
                  "n_rows": a["n_rows"]},
            "b": {"patch": b.get("patch"), "provenance": b.get("provenance"),
                  "n_rows": b["n_rows"]},
            "tol_m": res["tol_m"],
            "law_true_knobs": a["law_true_knobs"],
            "counts": {"exact": len(res["exact"]), "moved": len(res["moved"]),
                       "gone": len(res["gone"]), "new": len(res["new"])},
            "new": res["new"],
            "gone": res["gone"],
            "moved": [{"a": x, "b": y, "sep_m": s}
                      for x, y, s in res["moved"]],
        }, indent=1))
        print(f"JSON -> {args.json}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
