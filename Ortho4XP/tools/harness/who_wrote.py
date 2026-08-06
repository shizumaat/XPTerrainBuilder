"""WHO WROTE THIS VALUE — per-vertex authorship for an auto_patch build.

    venv/bin/python tools/harness/who_wrote.py ICAO [--dem M]
        [--roles service_junction,groundside_pavement] [--at X,Y ...]
        [--author final_grade_projection] [--author-tol 0.01]
        [--author-dump moves.jsonl] [--out DIR] [--tol 0.05]

Run it from ``Ortho4XP/``.

A census tells you a vertex is wrong.  It cannot tell you WHICH PASS put the
value there, and reading the code to guess has a bad record in this campaign
(nine falsified mechanisms in two days from reading attribution as causal).
This tool answers it by MEASUREMENT: it wraps ``BuiltShape.node_altitudes``
in a recording property, runs the build through the harness build entry, and
reports the call site of every write.

THREE REPORTS, one build:

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

* **THE DISPLACEMENT CENSUS** (``--author SITE``, repeatable).  How far a
  named pass moves values AWAY FROM THE SOLVE'S, per vertex, split three
  ways: ``new_geometry`` (the shape's ring changed after the solve — law
  pairs the solve never saw, which is a post-solve projection's legitimate
  job), ``moved_post_solve`` (some other pass had already moved the value,
  so the author is not the one disagreeing with the solve), and
  ``untouched`` — a vertex the solve produced that nothing else touched.
  A move in the ``untouched`` class is a SECOND AUTHOR, which the
  single-solve architecture forbids (RULINGS 2026-08-03; the ingestion
  spec's requirement 2 sets the materiality floor at 0.01 m).  This is the
  reader for ``docs/specs/cycle4-projection-ingestion-spec.md``.

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
#: The write that defines "the solved value" for the displacement census —
#: the one elevation solve's own writeback (RULINGS 2026-08-03,
#: single-solve architecture).  Every later author is measured AGAINST it.
_SOLVE_SITE = "solve_route_profile"
#: How many worst rows the displacement census keeps.
_WORST_KEEP = 40


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

    def __init__(self, shape_cls, dem_m=None, roles=None, at=(), tol=0.05,
                 authors=(), author_tol=0.01, solve_site=_SOLVE_SITE,
                 dump_moves=False):
        self.cls = shape_cls
        self.dem_m = dem_m
        self.roles = set(roles or ())
        self.at = [(float(x), float(y)) for x, y in at]
        self.tol = float(tol)
        self.authors = tuple(authors or ())
        self.author_tol = float(author_tol)
        self.solve_site = solve_site
        self.by_shape: dict = {}
        self.by_point: dict = {p: [] for p in self.at}
        #: shape id → the values the SOLVE last wrote (the reference state
        #: requirement (2) of the ingestion spec measures idempotence against)
        self._solved: dict = {}
        #: shape id → the values as they stood before the write in progress
        self._prev: dict = {}
        #: (author, class, role) → [|Δ| …] over every moved vertex
        self.author_moves: dict = {}
        #: the worst rows, kept small: (|Δ|, author, cls, role, ref, before,
        #: after, x, y)
        self.author_worst: list = []
        #: ``--author-dump``: EVERY moved vertex, not just the worst 40.
        #: The aggregate report answers "how much"; only a per-vertex dump
        #: answers "are these the SAME vertices some other writer seeded",
        #: which needs a join key (shape + ring index + plan coordinate).
        self.dump_moves = bool(dump_moves)
        self.move_rows: list = []
        #: shape id → {ring index: site of the FIRST write that gave that
        #: index a value} — the vertex's ORIGIN writer.  One entry per
        #: vertex, so it is bounded by the layout, not by the write count.
        self.origin_site: dict = {}
        #: shape id → {ring index: site of the FIRST write at which that
        #: index sat EXACTLY on the constant DEM} — the vertex-granular
        #: version of the DEM-authorship census, which is per SHAPE.
        self.dem_origin_site: dict = {}
        self._step = 0
        self._saved = None

    # ── the hook ─────────────────────────────────────────────────────
    def _record(self, shape, values):
        self._step += 1
        role = getattr(shape, "role", "") or ""
        # ONE stack walk per write, shared by both censuses: ``extract_stack``
        # dominates the probe's cost and a second walk would double the
        # instrumented build's overhead for the same string.
        site = call_site(skip=4) if values is not None else None
        if values is not None and (not self.roles or role in self.roles):
            hit = 0
            if self.dem_m is not None:
                hit = sum(1 for a in values
                          if a is not None
                          and abs(float(a) - self.dem_m) <= 1e-6)
            self.by_shape.setdefault(id(shape), []).append(
                (hit, len(values), site))
        if self.dump_moves and values is not None and site is not None:
            org = self.origin_site.setdefault(id(shape), {})
            dorg = (self.dem_origin_site.setdefault(id(shape), {})
                    if self.dem_m is not None else None)
            for k, v in enumerate(values):
                if v is None:
                    continue
                if k not in org:
                    org[k] = site
                if (dorg is not None and k not in dorg
                        and abs(float(v) - self.dem_m) <= 1e-6):
                    dorg[k] = site
        if self.authors:
            self._record_author(shape, role, values, site)
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

    # ── the displacement census (ingestion spec requirement (2)) ─────
    def _record_author(self, shape, role, values, site):
        """Attribute this write's per-vertex displacement, and classify it.

        The classification is the ingestion spec's own partition of the
        post-solve world (``docs/specs/cycle4-projection-ingestion-spec.md``
        §requirement 2):

        * ``new_geometry`` — the shape's ring vertex COUNT differs from what
          the solve wrote (a planarize insert, a T-weld adoption, a merge, a
          clip rebuild).  These law pairs the solve never saw, so projecting
          them is this pass's legitimate residual job.
        * ``moved_post_solve`` — the value the author overwrote is already
          off the solved value: some other post-solve pass authored it, so
          the author is not the one disagreeing with the solve.
        * ``untouched`` — neither.  A vertex whose geometry and value the
          solve produced and no later pass changed.  **A move here is the
          second-author class**: the spec's materiality floor is 0.01 m.
        """
        sid = id(shape)
        prev = self._prev.get(sid)
        if values is not None:
            vals = [None if v is None else float(v) for v in values]
        else:
            vals = None
        # The reference state: whatever the SOLVE last wrote on this shape.
        if vals is not None and self.solve_site in site:
            self._solved[sid] = list(vals)
        if vals is None or prev is None or site is None:
            self._prev[sid] = list(vals) if vals is not None else None
            return
        author = next((a for a in self.authors if a in site), None)
        if author is None:
            self._prev[sid] = list(vals)
            return
        solved = self._solved.get(sid)
        ring = None
        for k in range(min(len(prev), len(vals))):
            a, b = prev[k], vals[k]
            if a is None or b is None:
                continue
            delta = abs(b - a)
            if delta <= self.author_tol:
                continue
            if solved is None or len(solved) != len(vals):
                cls = "new_geometry"
            elif solved[k] is None:
                cls = "new_geometry"
            elif abs(a - solved[k]) > self.author_tol:
                cls = "moved_post_solve"
            else:
                cls = "untouched"
            self.author_moves.setdefault((author, cls, role),
                                         []).append(delta)
            if delta > 0.05 or self.dump_moves:
                if ring is None:
                    poly = getattr(shape, "polygon", None)
                    ring = (list(poly.exterior.coords)
                            if (poly is not None and not poly.is_empty
                                and poly.geom_type == "Polygon") else ())
                x, y = (ring[k] if k < len(ring) else (None, None))
            if delta > 0.05:
                self.author_worst.append(
                    (delta, author, cls, role, getattr(shape, "ref", "") or "",
                     round(a, 3), round(b, 3), x, y))
            if self.dump_moves:
                sv = (None if (solved is None or len(solved) != len(vals)
                               or solved[k] is None) else round(solved[k], 4))
                self.move_rows.append(
                    (author, cls, role, getattr(shape, "ref", "") or "",
                     site, sid, k, round(a, 4), round(b, 4), sv, x, y))
        if len(self.author_worst) > 8 * _WORST_KEEP:
            self.author_worst.sort(key=lambda r: -r[0])
            del self.author_worst[_WORST_KEEP:]
        self._prev[sid] = list(vals)

    def author_report(self):
        """``(table_rows, totals)`` for the displacement census."""
        rows = []
        for (author, cls, role), deltas in self.author_moves.items():
            deltas.sort()
            rows.append({
                "author": author, "class": cls, "role": role,
                "n_moved": len(deltas),
                "max_m": round(deltas[-1], 3),
                "p50_m": round(deltas[len(deltas) // 2], 3),
            })
        rows.sort(key=lambda r: (r["author"], r["class"], -r["n_moved"]))
        totals: dict = {}
        for r in rows:
            t = totals.setdefault((r["author"], r["class"]),
                                  {"n_moved": 0, "max_m": 0.0})
            t["n_moved"] += r["n_moved"]
            t["max_m"] = max(t["max_m"], r["max_m"])
        self.author_worst.sort(key=lambda r: -r[0])
        del self.author_worst[_WORST_KEEP:]
        return rows, totals

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

    def write_move_dump(self, layout, path):
        """``--author-dump``: every moved vertex + its shape's write history.

        JSONL, three record kinds:

        * ``shape`` — one per shape the probe saw: its final index in
          ``layout.shapes``, role, ref, ring size, how many of its values
          end EXACTLY on the constant DEM, and the ORDERED list of write
          sites (consecutive duplicates collapsed).
        * ``move``  — one per vertex displacement above the materiality
          floor: author, class, role, the FULL call site of the moving
          write (the writing-pass axis the aggregate report collapses),
          before / after / the solve's value, the plan coordinate, and
          the vertex's ``origin`` writer + ``dem_origin`` writer.
        * ``meta``  — the header.

        ``origin``/``dem_origin`` are keyed by RING INDEX, which is stable
        only while the ring is: for a vertex whose ring was rebuilt after
        the solve (the ``new_geometry`` class) the index may name a
        different point than it did before the rebuild.  For the
        ``untouched`` class the ring is unchanged since the solve wrote
        it, so the join is exact there — which is the class the
        second-author question is about.
        """
        index_of = {}
        for i, s in enumerate(getattr(layout, "shapes", ()) or ()):
            index_of[id(s)] = i
        dem_of = {}
        for i, s in enumerate(getattr(layout, "shapes", ()) or ()):
            vals = s.node_altitudes or ()
            dem_of[id(s)] = (sum(1 for a in vals
                                 if a is not None and self.dem_m is not None
                                 and abs(float(a) - self.dem_m) <= 1e-6),
                             len(vals), s.role, getattr(s, "ref", "") or "")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        n_shape = 0
        with path.open("w") as fh:
            fh.write(json.dumps({
                "kind": "meta", "dem_m": self.dem_m,
                "authors": list(self.authors),
                "author_tol": self.author_tol,
                "solve_site": self.solve_site,
                "n_moves": len(self.move_rows)}) + "\n")
            for sid, hist in self.by_shape.items():
                sites, last = [], None
                for (_hit, _n, st) in hist:
                    if st != last:
                        sites.append(st)
                        last = st
                on_dem, n_v, role, ref = dem_of.get(sid, (0, 0, "", ""))
                fh.write(json.dumps({
                    "kind": "shape", "sid": sid,
                    "shape_index": index_of.get(sid),
                    "role": role, "ref": ref, "n": n_v,
                    "on_dem": on_dem, "writes": len(hist),
                    "sites": sites}) + "\n")
                n_shape += 1
            for (author, cls, role, ref, site, sid, k, a, b, sv,
                 x, y) in self.move_rows:
                fh.write(json.dumps({
                    "kind": "move", "author": author, "class": cls,
                    "role": role, "ref": ref, "site": site,
                    "sid": sid, "shape_index": index_of.get(sid), "k": k,
                    "before": a, "after": b, "solved": sv, "x": x, "y": y,
                    "origin": self.origin_site.get(sid, {}).get(k),
                    "dem_origin": self.dem_origin_site.get(sid, {}).get(k),
                }) + "\n")
        return {"shapes": n_shape, "moves": len(self.move_rows),
                "path": str(path)}

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
    ap.add_argument("--author", action="append", default=[], metavar="SITE",
                    help="displacement census: how far this call site (a "
                         "substring of the reported site, e.g. "
                         "final_grade_projection) moves values AWAY from the "
                         "solve's, split by whether the vertex was touched "
                         "post-solve.  Repeatable.")
    ap.add_argument("--author-tol", type=float, default=0.01,
                    metavar="M",
                    help="materiality floor for the displacement census "
                         "(default 0.01 m, the campaign floor)")
    ap.add_argument("--author-dump", type=Path, default=None, metavar="PATH",
                    help="displacement census: write EVERY moved vertex to "
                         "PATH as JSONL (author, class, role, the full call "
                         "site of the moving write, before/after/solved, the "
                         "plan coordinate, and the vertex's origin and "
                         "DEM-origin writers), plus one record per shape "
                         "with its ordered write-site history.  The printed "
                         "report keeps only the worst 40 rows, which cannot "
                         "answer whether a moved vertex is one some other "
                         "writer seeded.")
    ap.add_argument("--out", type=Path, default=Path("/tmp/harness/who"))
    ap.add_argument("--allow-degraded-dem", action="store_true",
                    help="accepted and recorded; a constant-DEM run "
                         "SUBSTITUTES the DEM, so real-DEM cache warmth "
                         "cannot confound it")
    args = ap.parse_args(argv)
    if args.dem is None and not args.at and not args.author:
        ap.error("give --dem (authorship census), --at X,Y (node history), "
                 "--author SITE (displacement census), or any combination")

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

    probe = AuthorshipProbe(BuiltShape, args.dem, roles, at, args.tol,
                            authors=args.author,
                            author_tol=args.author_tol,
                            dump_moves=bool(args.author_dump)).install()
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
    if args.author:
        rows, totals = probe.author_report()
        report["author_displacement"] = rows
        report["author_worst"] = [
            {"delta_m": round(d, 3), "author": a, "class": c, "role": r,
             "ref": ref, "before": before, "after": after, "x": x, "y": y}
            for (d, a, c, r, ref, before, after, x, y) in probe.author_worst]
        print(f"\n  === VALUES MOVED AWAY FROM THE SOLVE, by author "
              f"(materiality {args.author_tol:g} m)\n")
        print(f"    {'author':<26}{'class':<18}{'role':<22}"
              f"{'n_moved':>9}{'max|d| m':>11}{'p50|d| m':>10}")
        for r in rows:
            print(f"    {r['author']:<26}{r['class']:<18}{r['role']:<22}"
                  f"{r['n_moved']:>9}{r['max_m']:>11.3f}{r['p50_m']:>10.3f}")
        print()
        for (author, cls), t in sorted(totals.items()):
            flag = ("   <-- SECOND AUTHOR (spec requirement 2)"
                    if cls == "untouched" and t["n_moved"] else "")
            print(f"    TOTAL  {author:<26}{cls:<18}"
                  f"{t['n_moved']:>9}{t['max_m']:>11.3f}{flag}")
        print(f"\n  === worst {len(probe.author_worst)} displaced vertices")
        for (d, a, c, r, ref, before, after, x, y) in probe.author_worst[:20]:
            print(f"    {d:9.3f} m  {c:<16}{r:<20}{ref:<16}"
                  f"{before} -> {after}   at ({x},{y})")
    if args.author_dump:
        info = probe.write_move_dump(layout, args.author_dump)
        report["author_dump"] = info
        print(f"\n  [harness] per-vertex move dump -> {info['path']} "
              f"({info['moves']} move row(s), {info['shapes']} shape row(s))")
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
