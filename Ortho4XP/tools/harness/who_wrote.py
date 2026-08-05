"""WHO WROTE THIS VALUE — per-vertex authorship for an auto_patch build.

    venv/bin/python tools/harness/who_wrote.py ICAO [--dem M]
        [--roles service_junction,groundside_pavement] [--at X,Y ...]
        [--out DIR] [--tol 0.05]

Run it from ``Ortho4XP/``.

A census tells you a vertex is wrong.  It cannot tell you WHICH PASS put the
value there, and reading the code to guess has a bad record in this campaign
(nine falsified mechanisms in two days from reading attribution as causal).
This tool answers it by MEASUREMENT: it wraps ``BuiltShape.node_altitudes``
in a recording property, runs the build through the harness build entry, and
reports the call site of every write.

TWO REPORTS, one build:

* **THE DEM-AUTHORSHIP CENSUS** (default, needs ``--dem``).  For every shape
  that finishes with vertices sitting EXACTLY on the constant DEM, the write
  that INTRODUCED them — defined as the first write after the last write at
  which the shape's DEM-vertex count was zero.  That definition matters: the
  LAST writer is almost always the final projection's writeback, which merely
  carries a value some earlier pass authored.  Under a constant DEM "sits
  exactly on the DEM" is a decidable predicate, which is what makes the
  question answerable at all (RULINGS 5578b6a: DEM is a SEED, never an
  authority — this names the passes that break that).

* **THE NODE HISTORY** (``--at X,Y``, metre frame, repeatable).  Every write
  touching that plan coordinate, in order, with the value and the call site,
  compressed to the changes.  Run it in two constant-DEM worlds and diff the
  two histories to find the exact pass where the worlds first disagree — the
  instrument that attributed the negative band widths to the runway flex.

The hooks are READ-ONLY: they record and delegate, so the build is the same
build ``tools/harness/build_airport.py`` would have produced (same refusals,
same frame snapshots, same sidecar guarantee).
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "harness"))

import build_airport as HB                              # noqa: E402

#: "no such class attribute" — distinct from a class attribute holding None.
_MISSING = object()

#: Frames outside the engine package are noise in a call site.
_PKG = "auto_patch"
#: How many engine frames to keep, innermost last.
_SITE_DEPTH = 5


def call_site(skip: int = 2, depth: int = _SITE_DEPTH) -> str:
    """The engine-side call site of the caller, outermost first."""
    frames = [f"{Path(f.filename).name}:{f.lineno}:{f.name}"
              for f in traceback.extract_stack()[:-skip]
              if _PKG in f.filename]
    return " <- ".join(reversed(frames[-depth:]))


def introducing_write(history):
    """The write that INTRODUCED the current non-zero count in ``history``.

    ``history`` is the shape's writes in order, each ``(count, n, site)``
    where ``count`` is how many of its ``n`` values matched the probe at
    that write.  The answer is the first write AFTER the last write whose
    count was zero — the last writer is usually a carrier, not an author.
    Returns ``None`` for an empty history.
    """
    hist = list(history)
    if not hist:
        return None
    for k in range(len(hist) - 1, -1, -1):
        if hist[k][0] == 0:
            return hist[k + 1] if k + 1 < len(hist) else None
    return hist[0]


class AuthorshipProbe:
    """Records every ``node_altitudes`` assignment.  ``install`` swaps the
    dataclass field for a property; ``uninstall`` puts it back."""

    def __init__(self, shape_cls, dem_m=None, roles=None, at=(), tol=0.05):
        self.cls = shape_cls
        self.dem_m = dem_m
        self.roles = set(roles or ())
        self.at = [(float(x), float(y)) for x, y in at]
        self.tol = float(tol)
        self.by_shape: dict = {}
        self.by_point: dict = {p: [] for p in self.at}
        self._step = 0
        self._saved = None

    # ── the hook ─────────────────────────────────────────────────────
    def _record(self, shape, values):
        self._step += 1
        role = getattr(shape, "role", "") or ""
        if values is not None and (not self.roles or role in self.roles):
            hit = 0
            if self.dem_m is not None:
                hit = sum(1 for a in values
                          if a is not None
                          and abs(float(a) - self.dem_m) <= 1e-6)
            self.by_shape.setdefault(id(shape), []).append(
                (hit, len(values), call_site(skip=4)))
        if not self.at or not values:
            return
        poly = getattr(shape, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            return
        ring = list(poly.exterior.coords)
        site = None
        for k in range(min(len(ring), len(values))):
            rx, ry = ring[k]
            for p in self.at:
                if abs(rx - p[0]) <= self.tol and abs(ry - p[1]) <= self.tol:
                    if site is None:
                        site = call_site(skip=4)
                    v = values[k]
                    self.by_point[p].append(
                        (self._step, role, getattr(shape, "ref", "") or "",
                         None if v is None else round(float(v), 3), site))

    def install(self):
        probe = self
        # A SENTINEL, not ``getattr(..., None)``: ``node_altitudes`` is a
        # dataclass field whose class-level default IS ``None``, so a plain
        # getattr cannot tell "the attribute held None" from "there was no
        # attribute" — and uninstall would then leave the property in place.
        self._saved = self.cls.__dict__.get("node_altitudes", _MISSING)

        # WRITE THROUGH TO THE INSTANCE DICT, never to a private alias: a
        # data descriptor wins over the instance dict while it is installed,
        # and the instance dict wins the moment it is removed.  So the values
        # survive ``uninstall`` and a report taken afterwards still sees
        # them.  (An alias silently reported ZERO on-DEM vertices — an
        # instrument that loses its subject is worse than no instrument.)
        def _get(self):
            return self.__dict__.get("node_altitudes")

        def _set(self, value):
            self.__dict__["node_altitudes"] = value
            try:
                probe._record(self, value)
            except Exception:          # instrumentation never breaks a build
                pass

        self.cls.node_altitudes = property(_get, _set)
        return self

    def uninstall(self):
        if self._saved is _MISSING:
            try:
                delattr(self.cls, "node_altitudes")
            except AttributeError:
                pass
        else:
            setattr(self.cls, "node_altitudes", self._saved)
        self._saved = None

    # ── the reports ──────────────────────────────────────────────────
    def dem_authorship(self, layout):
        """``(rows, by_author)`` over shapes ending ON the constant DEM."""
        rows, by_author = [], Counter()
        for i, s in enumerate(getattr(layout, "shapes", ()) or ()):
            values = s.node_altitudes
            if not values or (self.roles and s.role not in self.roles):
                continue
            hit = sum(1 for a in values
                      if a is not None and abs(float(a) - self.dem_m) <= 1e-6)
            if not hit:
                continue
            history = self.by_shape.get(id(s)) or []
            intro = introducing_write(history)
            site = intro[2] if intro else (history[-1][2] if history
                                           else "?NO-TRACE?")
            by_author[(s.role, site)] += hit
            rows.append({"shape": i, "role": s.role, "ref": s.ref or "",
                         "on_dem": hit, "n": len(values),
                         "writes": len(history), "introduced_by": site,
                         "history": [f"{h[0]}/{h[1]} {h[2]}"
                                     for h in history]})
        rows.sort(key=lambda r: -r["on_dem"])
        return rows, by_author

    def node_history(self):
        """``{"x,y": [change, …]}`` — writes compressed to the changes."""
        out = {}
        for p, writes in self.by_point.items():
            compressed, last = [], {}
            for (step, role, ref, value, site) in writes:
                key = (role, ref)
                if last.get(key) != value:
                    compressed.append({"step": step, "role": role,
                                       "ref": ref, "value": value,
                                       "site": site})
                    last[key] = value
            out[f"{p[0]},{p[1]}"] = compressed
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("icao")
    ap.add_argument("--dem", type=float, default=None,
                    help="constant-DEM elevation; required for the "
                         "DEM-authorship census (the predicate needs it)")
    ap.add_argument("--roles", default="",
                    help="comma-separated role filter (default: all)")
    ap.add_argument("--at", action="append", default=[], metavar="X,Y",
                    help="metre-frame coordinate to trace, repeatable")
    ap.add_argument("--tol", type=float, default=0.05)
    ap.add_argument("--out", type=Path, default=Path("/tmp/harness/who"))
    ap.add_argument("--allow-degraded-dem", action="store_true",
                    help="accepted and recorded; a constant-DEM run "
                         "SUBSTITUTES the DEM, so real-DEM cache warmth "
                         "cannot confound it")
    args = ap.parse_args(argv)
    if args.dem is None and not args.at:
        ap.error("give --dem (authorship census), --at X,Y (node history), "
                 "or both")

    root = HB.require_build_cwd(Path.cwd())
    for p in (root / "src", root, root / "tests"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from auto_patch.layout import BuiltShape                  # noqa: E402

    at = [tuple(float(v) for v in a.split(",")) for a in args.at]
    roles = [r for r in args.roles.split(",") if r]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prog = HB.Progress(out / f"{args.icao}_who_wrote.progress")

    probe = AuthorshipProbe(BuiltShape, args.dem, roles, at, args.tol).install()
    try:
        tag = f"{args.icao}_who{'' if args.dem is None else f'_dem{args.dem:g}'}"
        result = HB.build_patch(args.icao, root, out, tag, prog,
                                const_dem=args.dem)
        layout = result["_layout"]
    finally:
        probe.uninstall()

    report: dict = {"icao": args.icao, "dem_m": args.dem,
                    "patch": result["patch"]}
    if args.dem is not None:
        rows, by_author = probe.dem_authorship(layout)
        report["dem_authorship"] = rows
        total = sum(by_author.values())
        print(f"\n  === VERTICES SITTING EXACTLY ON THE {args.dem:g} m "
              f"CONSTANT DEM: {total}, by INTRODUCING writer\n")
        for (role, site), n in by_author.most_common():
            print(f"    {n:6d}  {role}")
            print(f"            {site}")
        print(f"\n  === per shape (top 15)")
        for r in rows[:15]:
            print(f"    #{r['shape']:<5}{r['role']:<22}"
                  f"{r['on_dem']:5d}/{r['n']:<5d} writes={r['writes']}")
            print(f"          introduced by: {r['introduced_by']}")
    if at:
        history = probe.node_history()
        report["node_history"] = history
        for point, changes in history.items():
            print(f"\n  === ({point})  {len(changes)} change(s)")
            for c in changes:
                print(f"    {c['step']:7d} {c['role']:<18}{c['ref']:<20}"
                      f"{c['value']}   {c['site']}")
    path = out / f"{args.icao}_who_wrote.json"
    path.write_text(json.dumps(report, indent=1, default=str))
    print(f"\n  [harness] authorship report -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
