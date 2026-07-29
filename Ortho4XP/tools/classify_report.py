"""Per-airport legacy-vs-scorer pavement classification report.

Spec: ``docs/specs/pavement-scoring-classifier-spec.md`` §9 (Phase A —
SHADOW).  Builds an airport, reads the shadow pass's decisions off the
layout, and prints the confusion matrix plus a per-shape drill-down with
centroid lat/lon so a disagreement can be flown to in-sim.

Usage:
    venv/bin/python tools/classify_report.py ICAO [ICAO ...]
                                             [--json PATH]
    venv/bin/python tools/classify_report.py --from-json PATH

    --json PATH       also dump the raw decisions + summary to PATH
    --from-json PATH  render a previous dump instead of building
                      (no X-Plane install, no build, no network)
    --max-rows N      cap the DISAGREEMENTS listing (default 60, 0 = all)
    --xplane PATH     X-Plane root (default: tests/conftest.xplane_root())

A build takes 60-90 s per airport; ``--from-json`` is instant and is how
the rendering is exercised without paying for one.

BUILD-TIME IMPACT: none.  This is a report-only tool — nothing here is
imported by the engine, and every ``auto_patch`` import is deferred into
the function that needs it so ``--from-json`` never loads the pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "src", _ROOT, _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ── the class vocabulary (mirrored so rendering needs no engine import)

CLASSES = ("APRON", "TAXI", "SERVICE", "GROUNDSIDE")
_RELIABILITY_KEYS = ("apt_names", "osm_aeroway", "road_feed", "truck",
                     "spine", "alt_apt")


def _scoring_tables():
    """``(weights, feature -> reliability-source)`` from the engine.

    Imported lazily and through ``auto_patch.pipeline`` first — the
    package's CLAUDE.md documents the ``junction_repair`` ↔ ``elevation``
    import cycle and requires the pipeline as the entry point.
    """
    import auto_patch.pipeline  # noqa: F401  (cycle-safe entry point)
    from auto_patch.config import PAVEMENT_SCORE_WEIGHTS
    from auto_patch.pavement_scoring import _FEATURE_SOURCE
    return PAVEMENT_SCORE_WEIGHTS, _FEATURE_SOURCE


# ═════════════════════════════════════════════════════════════════════
# Building
# ═════════════════════════════════════════════════════════════════════

def build_report(icao: str, xplane_root: str) -> dict:
    """Build ``icao`` and harvest its shadow-pass decisions."""
    import auto_patch.pipeline as pipeline
    layout = pipeline.build_airport_pavement(
        icao, xplane_root, compute_elevations=True)
    summary = dict(getattr(layout, "pavement_score_summary", None) or {})
    decisions = list(getattr(layout, "pavement_score_decisions", None) or [])
    return {"icao": icao, "summary": summary, "decisions": decisions}


# ═════════════════════════════════════════════════════════════════════
# Rendering
# ═════════════════════════════════════════════════════════════════════

def _verdict(record: dict) -> str:
    """The scorer's answer, using the summary's own convention.

    ``shadow_classify`` counts ``winner or legacy`` as the verdict, so a
    shape the scorer declined to call agrees with the chain by default.
    """
    return record.get("winner") or record.get("legacy") or "-"


def _contributions(record: dict, reliability: dict, weights: dict,
                   feature_source: dict, target: str) -> list:
    """``[(feature, value, points)]`` toward ``target``, strongest first.

    ``points = W[feature][target] x r_source(feature) x x_feature`` — the
    same product ``score_shape`` accumulates, recomputed here so the
    report can name WHY a shape flipped.  Ranked by magnitude, so a
    strong negative (``narrow_only`` against APRON) shows up too.
    """
    out = []
    for feature, value in (record.get("features") or {}).items():
        if not value:
            continue
        row = weights.get(feature) or {}
        points = row.get(target)
        if not points:
            continue
        source = feature_source.get(feature)
        r = 1.0 if source is None else float(reliability.get(source, 0.0))
        if r <= 0.0:
            continue
        out.append((feature, float(value), points * r * float(value)))
    out.sort(key=lambda item: abs(item[2]), reverse=True)
    return out


def _confusion_matrix(decisions: list, summary: dict) -> dict:
    """``{legacy: {verdict: count}}`` over every scored shape.

    Built from the decisions when they are present (a FULL matrix,
    agreements on the diagonal); the summary's own ``confusion`` map
    holds disagreements only and is the fallback.
    """
    matrix: dict = {}
    if decisions:
        for record in decisions:
            legacy = record.get("legacy") or "-"
            matrix.setdefault(legacy, {})
            key = _verdict(record)
            matrix[legacy][key] = matrix[legacy].get(key, 0) + 1
        return matrix
    for key, count in (summary.get("confusion") or {}).items():
        legacy, _arrow, verdict = key.partition("->")
        matrix.setdefault(legacy, {})
        matrix[legacy][verdict] = matrix[legacy].get(verdict, 0) + count
    return matrix


def render(report: dict, out=sys.stdout, max_rows: int = 60) -> None:
    """Print one airport's report."""
    icao = report.get("icao", "????")
    summary = report.get("summary") or {}
    decisions = report.get("decisions") or []
    reliability = summary.get("reliability") or {}
    weights, feature_source = _scoring_tables()

    def line(text=""):
        print(text, file=out)

    rule = "=" * 74
    line(rule)
    line(f"{icao} — pavement classification: legacy chain vs scorer v2")
    line(rule)

    if not summary:
        line("  no shadow summary on the layout "
             "(is O4_PAVEMENT_SCORE_V2 off?)")
        line()
        return

    shapes = int(summary.get("shapes", 0) or 0)
    agree = int(summary.get("agree", 0) or 0)
    disagree = int(summary.get("disagree", 0) or 0)
    low = int(summary.get("low", 0) or 0)
    line(f"  mode {summary.get('mode', '?')}   shapes {shapes}   "
         f"{float(summary.get('seconds', 0.0) or 0.0):.2f} s")

    # ── (a) reliability ──────────────────────────────────────────────
    line()
    line("  SOURCE RELIABILITY (r ∈ [0,1]; 0 = source absent here)")
    for key in _RELIABILITY_KEYS:
        if key in reliability:
            line(f"      {key:<14} {float(reliability[key]):.3f}")
    for key in sorted(set(reliability) - set(_RELIABILITY_KEYS)):
        line(f"      {key:<14} {float(reliability[key]):.3f}")
    if summary.get("alt_apt_path"):
        line(f"      cross-reference apt.dat: {summary['alt_apt_path']}")

    # ── (b) agreement + confusion matrix ─────────────────────────────
    total = max(1, shapes)
    line()
    line(f"  AGREEMENT  {agree}/{shapes} = {100.0 * agree / total:.1f}%   "
         f"({disagree} differ, {low} low-margin)")
    matrix = _confusion_matrix(decisions, summary)
    if matrix:
        columns = [c for c in CLASSES
                   if any(c in row for row in matrix.values())]
        columns += sorted({k for row in matrix.values() for k in row}
                          - set(columns))
        line()
        line("  CONFUSION MATRIX (rows = legacy chain, cols = scorer)")
        width = max(11, *(len(c) for c in columns)) if columns else 11
        header = "      " + "legacy".ljust(12)
        header += "".join(c.rjust(width) for c in columns)
        line(header)
        for legacy in [c for c in CLASSES if c in matrix] + sorted(
                set(matrix) - set(CLASSES)):
            row = matrix[legacy]
            text = "      " + legacy.ljust(12)
            for column in columns:
                count = row.get(column, 0)
                cell = "." if not count else str(count)
                if count and column == legacy:
                    cell = f"[{count}]"          # the agreeing diagonal
                text += cell.rjust(width)
            line(text)

    # ── (c) the disagreements ────────────────────────────────────────
    # ``#N`` is the shape's index in ``layout.pavement_score_decisions`` —
    # most emitted shapes carry no ``ref`` at all, so this is the stable
    # handle for talking about one row (and for finding it in --json).
    flips = [(i, d) for i, d in enumerate(decisions)
             if d.get("winner") and d["winner"] != d.get("legacy")]
    line()
    line(f"  DISAGREEMENTS ({len(flips)})")
    if not flips:
        line("      none — the scorer reproduced the chain everywhere.")
    else:
        flips.sort(key=lambda p: -float(p[1].get("area_m2", 0.0) or 0.0))
        shown = flips if max_rows <= 0 else flips[:max_rows]
        for index, record in shown:
            ref = str(record.get("ref") or "-")
            line(f"      #{index:<6} {ref:<16} "
                 f"{str(record.get('role') or '-'):<22}"
                 f"{float(record.get('area_m2', 0.0) or 0.0):>12,.0f} m²")
            gates = ",".join(record.get("gates") or []) or "-"
            line(f"          {record.get('legacy')} -> {record['winner']}"
                 f"   margin {float(record.get('margin', 0.0) or 0.0):.3f}"
                 f" [{record.get('band', '?')}]   gates {gates}")
            top = _contributions(record, reliability, weights,
                                 feature_source, record["winner"])[:3]
            if top:
                parts = [f"{name}={value:.2f} ({points:+.2f})"
                         for name, value, points in top]
                line(f"          why {record['winner']}: " + "  ".join(parts))
            else:
                line(f"          why {record['winner']}: "
                     "(gate-forced — no weighted evidence)")
            latitude, longitude = record.get("lat"), record.get("lon")
            if latitude is not None and longitude is not None:
                line(f"          at {float(latitude):.6f},"
                     f"{float(longitude):.6f}")
        if len(shown) < len(flips):
            line(f"      … {len(flips) - len(shown)} more "
                 "(raise --max-rows or use --json)")

    # ── (d) the low-margin bucket ────────────────────────────────────
    low_records = [d for d in decisions
                   if d.get("band") == "LOW" or d.get("winner") is None]
    no_winner = sum(1 for d in low_records if d.get("winner") is None)
    line()
    line(f"  LOW-MARGIN ({low or len(low_records)}) — these take the "
         f"LEGACY verdict under the development ruling")
    if decisions:
        line(f"      {no_winner} with no winner at all "
             f"(no evidence reached them), "
             f"{len(low_records) - no_winner} below the "
             f"margin band")
        by_role: dict = {}
        for record in low_records:
            key = record.get("legacy") or "-"
            by_role[key] = by_role.get(key, 0) + 1
        if by_role:
            line("      by legacy class: " + "  ".join(
                f"{k} {v}" for k, v in sorted(by_role.items())))
    line()


# ═════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════

def _load_dump(path: str) -> list:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict) and "airports" in payload:
        return list(payload["airports"])
    if isinstance(payload, dict):
        return [payload]             # a single-airport report
    return list(payload)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Legacy-vs-scorer pavement classification report.")
    parser.add_argument("icao", nargs="*", help="airport codes to build")
    parser.add_argument("--json", default=None,
                        help="write the raw decisions + summary here")
    parser.add_argument("--from-json", default=None,
                        help="render this dump instead of building")
    parser.add_argument("--max-rows", type=int, default=60,
                        help="cap the disagreement listing (0 = all)")
    parser.add_argument("--xplane", default=None,
                        help="X-Plane root (default: conftest.xplane_root)")
    args = parser.parse_args(argv)

    # This tool IS the shadow-scoring consumer: force shadow mode on
    # regardless of the config default (which is "off" pending the
    # owner's build-budget approval — HECA 1.39 s / SPJC 0.82 s vs the
    # 0.6 s hard-law line).  Must happen before any auto_patch import;
    # config reads the env at import time.
    os.environ.setdefault("O4_PAVEMENT_SCORE_V2", "shadow")

    if args.from_json:
        reports = _load_dump(args.from_json)
        if args.icao:
            wanted = {i.upper() for i in args.icao}
            reports = [r for r in reports
                       if str(r.get("icao", "")).upper() in wanted]
    else:
        if not args.icao:
            parser.error("give at least one ICAO, or --from-json PATH")
        xplane_root = args.xplane
        if not xplane_root:
            from conftest import xplane_root as _xplane_root
            xplane_root = _xplane_root()
        if not os.path.isdir(xplane_root):
            parser.error(f"no X-Plane root at {xplane_root!r}")
        reports = []
        for icao in args.icao:
            print(f"building {icao.upper()} … (60-90 s)", file=sys.stderr)
            reports.append(build_report(icao.upper(), xplane_root))

    for report in reports:
        render(report, max_rows=args.max_rows)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump({"airports": reports}, handle, indent=1)
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
