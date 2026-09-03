"""WHO WROTE THIS VALUE — per-vertex authorship for an auto_patch build.

    venv/bin/python tools/harness/who_wrote.py ICAO [--dem M]
        [--roles service_junction,groundside_pavement] [--at X,Y ...]
        [--author final_grade_projection] [--author-tol 0.01]
        [--author-dump moves.jsonl] [--footprint X,Y ...]
        [--out DIR] [--tol 0.05]

Run it from ``Ortho4XP/``.

A census tells you a vertex is wrong.  It cannot tell you WHICH PASS put the
value there, and reading the code to guess has a bad record in this campaign
(nine falsified mechanisms in two days from reading attribution as causal).
This tool answers it by MEASUREMENT: it wraps ``BuiltShape.node_altitudes``
in a recording property, runs the build through the harness build entry, and
reports the call site of every write.

FOUR REPORTS, one build:

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
  The tool REPORTS the three counts and the class definitions; whether a
  move in the ``untouched`` class is the second author the single-solve
  architecture forbids is adjudicated by the law layer (RULINGS
  2026-08-03; the ingestion spec's requirement 2 sets the materiality
  floor at 0.01 m).  This is the reader for
  ``docs/specs/cycle4-projection-ingestion-spec.md``.

* **THE FOOTPRINT HISTORY** (``--footprint X,Y``, metre frame, repeatable).
  The same question asked of the RING instead of the value: *which pass put
  pavement over this spot at all?*  A value history cannot answer it — a
  point outside every shape has no vertex to trace, and the passes that
  MOVE a footprint (the absorb / merge / re-role family) write a polygon,
  never an altitude.  The probe wraps ``BuiltShape.polygon`` the same way,
  and reports per probe point every write at which a shape STARTED or
  STOPPED covering it, with the call site, the role at that moment, and the
  areas either side.  A shape's first sighting is reported as a ``birth``
  row (``dataclasses.replace`` mints a new instance for the same ring all
  over this pipeline, so "a new object covers the point" is NOT by itself a
  pass that grew a footprint — the row says which it is).  It measures no
  law and counts no defects: coverage is ``shapely`` containment on the
  ring as written, and defect counts come from ``harness/census.py`` alone.

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
#: Emitted altitudes are rounded (2 dp on nodes, 2 dp on flat ways), so
#: "exactly on the constant DEM" is decided with a rounding-scale epsilon,
#: not the in-memory 1e-6.
_EMIT_TOL = 5e-3
#: The IN-MEMORY frame's epsilon — full float precision, so "exactly on
#: the constant DEM" really is exact there.  Named so every printed
#: in-memory number can carry it (RULINGS 2026-08-06 point 3).
_MEM_TOL = 1e-6


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


#: The keys a ``dem_authorship``-shaped row may carry the layout.shapes
#: index under.  ``shape`` is what :meth:`AuthorshipProbe.dem_authorship`
#: writes; ``shape_index`` is what the ``--author-dump`` shape records
#: write; ``shapeID`` is the emitted way tag's own name.  Which one was
#: used is REPORTED, never guessed silently.
_SHAPE_KEYS = ("shape", "shape_index", "shapeID")

#: Top-level key of the authorship rows in a ``who_wrote`` report JSON.
_AUTHORSHIP_KEY = "dem_authorship"


def _is_authorship_rows(value) -> bool:
    """A list of mappings carrying a shape key — the shape of the rows."""
    if not isinstance(value, list) or not value:
        return False
    head = value[0]
    return (isinstance(head, dict)
            and any(head.get(k) is not None for k in _SHAPE_KEYS))


def authorship_rows_from_report(obj):
    """``(rows, source, top_keys)`` — the authorship rows in a who-json.

    Returns the rows as a LIST (never ``None``) plus the SOURCE they were
    read from, so a caller can report which key it joined on instead of
    degrading to silence.  ``source`` is ``None`` when nothing of the
    right shape is present — the state that must read differently from
    "attribution was not requested".

    Three accepted layouts, in order:

    * the report dict's top-level ``dem_authorship`` (what
      ``who_wrote.py`` writes) — ``source="dem_authorship"``;
    * a bare list of rows — ``source="<list>"``;
    * rows NESTED one level under some other top-level key (a report
      wrapped by a dossier or a lane's own envelope) — ``source`` names
      that key.  Without this the loader returned ``None`` and every
      downstream count silently vanished.
    """
    if _is_authorship_rows(obj):
        return list(obj), "<list>", []
    if not isinstance(obj, dict):
        return [], None, []
    top = sorted(obj.keys())
    rows = obj.get(_AUTHORSHIP_KEY)
    if _is_authorship_rows(rows):
        return list(rows), _AUTHORSHIP_KEY, top
    for k, v in obj.items():
        if _is_authorship_rows(v):
            return list(v), k, top
        if isinstance(v, dict):
            inner = v.get(_AUTHORSHIP_KEY)
            if _is_authorship_rows(inner):
                return list(inner), f"{k}.{_AUTHORSHIP_KEY}", top
    return [], None, top


def _shape_key_of(row):
    """The layout.shapes index this row carries, as the emitted tag spells
    it (a string), or ``None``."""
    if not isinstance(row, dict):
        return None
    for k in _SHAPE_KEYS:
        v = row.get(k)
        if v is not None:
            return str(v)
    return None


def emitted_on_dem(patch, dem_m, tol=_EMIT_TOL, authorship=None,
                   authorship_source=None):
    """EMITTED vertices sitting exactly on the constant DEM, by way role.

    THE FRAME TRAP THIS CLOSES.  The DEM-authorship census counts the
    IN-MEMORY layout (HECA read 16,019 at ``--dem 1``); the shipped patch
    carried 938 of them, because two decimators sit between the two
    frames.  Quoting one number for the other has already happened once
    (c5auth dossier, "FRAME WARNING"), so both frames now come out of one
    instrument and are labelled.

    Reports, for a patch written by the harness build entry:

    * ``total`` — distinct emitted nodes whose ``alt_abs`` is within
      ``tol`` of the DEM.
    * ``by_role`` — the same nodes attributed to the role of every way
      that references them (a shared vertex is counted once per way, so
      this sums to ≥ ``total``).
    * ``stranded`` — the subset sharing a way with a vertex whose
      ``alt_abs`` is OFF the DEM.  That is the class a within-shape law
      row is minted in: a vertex at the raw DEM beside its own ring's
      neighbour at 90 m.  Whether the off-DEM neighbour's value is a LAW
      value is the law layer's finding, not this instrument's — all this
      code checks is the emitted ``alt_abs``.
    * ``flat_ways`` — ways whose VERTICES all sit on the DEM: every ref
      carrying an ``alt_abs`` is on it and at least one ref does.  Such a
      way has no internal step, so it mints no within-shape row.
    * ``flat_way_tag`` — ways whose way-level ``altitude`` TAG equals the
      DEM, vertices NOT examined.  A different population: a way can
      carry the tag while its nodes carry no ``alt_abs`` at all, and a
      vertex-flat way need carry no tag.  The two were reported as one
      number under the name ``flat_ways`` and that mislabel was read as a
      per-vertex finding (HEAZ task-18 premise, cycle-6 corrections).
    * ``mixed_ways`` — the ways carrying both, i.e. the shapes to fix.

    Roles whose DEM value is lawful authority (a retaining wall's FOOT on
    raw ground, an adjacent-ground band at daylight — RULINGS 2026-08-01
    adjacent-ground zone law) are reported like any other: the instrument
    REPORTS, the law adjudicates.

    ``authorship`` — the ``dem_authorship`` rows of the same build, or
    ``None`` for "attribution not requested".  The emitted way's
    ``shapeID`` tag IS the index into ``layout.shapes``
    (``layout.py:2210``), which is the key those rows carry.  The join is
    MEASURED, never assumed: ``by_writer_join`` reports how many rows
    were supplied, how many ways carried a ``shapeID``, and how many
    joined — so a join that finds nothing says so with numbers instead of
    printing an empty section.  ``None`` (not requested) and ``[]``
    (requested, nothing to join with) are distinct states.
    """
    import xml.etree.ElementTree as ET
    dem_m = float(dem_m)
    tol = float(tol)
    requested = authorship is not None
    intro_of = {}
    n_rows = 0
    for r in (authorship or ()):
        n_rows += 1
        key = _shape_key_of(r)
        if key is not None:
            intro_of[key] = (r.get("introduced_by") if isinstance(r, dict)
                             else None) or "?"
    node_alt = {}
    ways = []
    for _ev, el in ET.iterparse(str(patch), events=("end",)):
        if el.tag == "node":
            alt = None
            for t in el.findall("tag"):
                if t.get("k") == "alt_abs":
                    try:
                        alt = float(t.get("v"))
                    except (TypeError, ValueError):
                        alt = None
            node_alt[el.get("id")] = alt
            el.clear()
        elif el.tag == "way":
            refs = [nd.get("ref") for nd in el.findall("nd")]
            role = ref = sid = None
            walt = None
            for t in el.findall("tag"):
                k = t.get("k")
                if k == "role":
                    role = t.get("v")
                elif k == "ref":
                    ref = t.get("v")
                elif k == "shapeID":
                    sid = t.get("v")
                elif k == "altitude":
                    try:
                        walt = float(t.get("v"))
                    except (TypeError, ValueError):
                        walt = None
            ways.append((role or "?", ref or "", refs, walt, sid))
            el.clear()

    def _on(nid):
        a = node_alt.get(nid)
        return a is not None and abs(a - dem_m) <= tol

    on_dem = {nid for nid in node_alt if _on(nid)}
    by_role, stranded_by_role = Counter(), Counter()
    by_writer, mixed_ways, stranded = Counter(), [], set()
    flat_ways, flat_way_tag = Counter(), Counter()
    n_shapeid = sum(1 for w in ways if w[4] is not None)
    j_ways = j_verts = u_ways = u_verts = 0
    n_on_dem_ways = 0
    for (role, ref, refs, walt, sid) in ways:
        uniq = {r for r in refs if r is not None}
        hits = {r for r in uniq if r in on_dem}
        # TWO POPULATIONS, TWO NAMES.  The way-level ``altitude`` tag and
        # the way's own vertices are different evidence; one number for
        # both read as a per-vertex finding it never was.
        if walt is not None and abs(walt - dem_m) <= tol:
            flat_way_tag[role] += 1
        valued = [r for r in uniq if node_alt.get(r) is not None]
        if valued and len(hits) == len(valued):
            flat_ways[role] += 1
        if not hits:
            continue
        n_on_dem_ways += 1
        by_role[role] += len(hits)
        if requested:
            joined = sid is not None and sid in intro_of
            if joined:
                j_ways += 1
                j_verts += len(hits)
            else:
                u_ways += 1
                u_verts += len(hits)
            by_writer[(role, intro_of.get(sid, "?NOT-IN-AUTHORSHIP?"))] \
                += len(hits)
        off = [r for r in valued if r not in on_dem]
        if off:
            stranded |= hits
            stranded_by_role[role] += len(hits)
            mixed_ways.append({"role": role, "ref": ref, "shape": sid,
                               "on_dem": len(hits), "valued": len(off),
                               "n": len(uniq),
                               "joined": (None if not requested
                                          else (sid is not None
                                                and sid in intro_of)),
                               "introduced_by": (intro_of.get(sid)
                                                 if requested else None)})
    mixed_ways.sort(key=lambda r: -r["on_dem"])
    join = {"requested": requested,
            "source": authorship_source,
            "authorship_rows": n_rows,
            "authorship_keyed": len(intro_of),
            "ways": len(ways), "ways_with_shapeid": n_shapeid,
            "on_dem_ways": n_on_dem_ways,
            "joined_ways": j_ways, "joined_vertices": j_verts,
            "unjoined_ways": u_ways, "unjoined_vertices": u_verts}
    return {"patch": str(patch), "dem_m": dem_m,
            # FRAME STAMP (RULINGS 2026-08-06 point 3): every number below
            # is read from the EMITTED patch, decided at ``tol_m`` against
            # this world — never the in-memory layout's count.
            "frame": "EMITTED", "tol_m": tol,
            "world": f"constant DEM {dem_m:g} m",
            "nodes": len(node_alt), "ways": len(ways),
            "total": len(on_dem), "by_role": dict(by_role.most_common()),
            "stranded": len(stranded),
            "stranded_by_role": dict(stranded_by_role.most_common()),
            "by_writer_join": join,
            "by_writer": [{"role": r, "introduced_by": w, "n": n}
                          for (r, w), n in by_writer.most_common()],
            "flat_ways": dict(flat_ways.most_common()),
            "flat_way_tag": dict(flat_way_tag.most_common()),
            "mixed_ways": mixed_ways[:40],
            "n_mixed_ways": len(mixed_ways)}


def print_emitted_on_dem(rep):
    """The emitted-frame report, labelled so it cannot be misquoted.

    Every line names the population it counts and carries the frame it
    was measured in.  The by-writer block prints in ALL THREE states —
    joined, requested-but-empty, not requested — because an instrument
    that omits a section on failure is indistinguishable from one that
    was never asked (RULINGS 2026-08-06 point 2).
    """
    print(f"\n  === EMITTED nodes whose alt_abs is within "
          f"{rep.get('tol_m', _EMIT_TOL):g} m of the {rep['dem_m']:g} m "
          f"constant DEM: {rep['total']} of {rep['nodes']} node(s)")
    print(f"      [frame: {rep.get('frame', 'EMITTED')} patch"
          f"  |  world: {rep.get('world', '?')}"
          f"  |  NOT the in-memory layout count]")
    for role, n in rep["by_role"].items():
        print(f"      {n:6d}  {role}   (counted once per referencing way)")
    print(f"    STRANDED — on-DEM nodes in a way that also references a "
          f"node whose alt_abs is OFF the DEM: "
          f"{rep['stranded']} in {rep['n_mixed_ways']} way(s)")
    for role, n in rep["stranded_by_role"].items():
        print(f"      {n:6d}  {role}")
    _print_by_writer(rep)
    print("    ways whose VERTICES all sit on the DEM (every ref carrying "
          "an alt_abs is on it, at least one does): "
          + (", ".join(f"{r}={n}" for r, n in rep["flat_ways"].items())
             or "none"))
    print("    ways whose way-level ALTITUDE TAG is on the DEM (tag only; "
          "vertices not examined): "
          + (", ".join(f"{r}={n}"
                       for r, n in rep.get("flat_way_tag", {}).items())
             or "none"))
    for r in rep["mixed_ways"][:10]:
        print(f"      way {r['role']:<22}{r['ref']:<20}"
              f"{r['on_dem']:5d} on DEM / {r['valued']:5d} off DEM")


def _print_by_writer(rep):
    """The by-INTRODUCING-writer block and its join diagnostics."""
    join = rep.get("by_writer_join") or {}
    if not join.get("requested"):
        print("    by INTRODUCING writer: NOT REQUESTED "
              "(no authorship rows passed; the emitted count stands "
              "unattributed)")
        return
    print("    by INTRODUCING writer — joined on the way's shapeID tag "
          "(= the layout.shapes index):")
    print(f"      join: source={join.get('source')!r} "
          f"authorship_rows={join.get('authorship_rows')} "
          f"keyed={join.get('authorship_keyed')} "
          f"ways_with_shapeid={join.get('ways_with_shapeid')}"
          f"/{join.get('ways')}")
    print(f"            on_dem_ways={join.get('on_dem_ways')} "
          f"joined={join.get('joined_ways')} "
          f"({join.get('joined_vertices')} vertex hits) "
          f"unjoined={join.get('unjoined_ways')} "
          f"({join.get('unjoined_vertices')} vertex hits)")
    if not join.get("joined_ways"):
        print(f"      JOIN EMPTY: 0 of {join.get('on_dem_ways')} on-DEM "
              f"way(s) matched an authorship row; every count below is in "
              f"the ?NOT-IN-AUTHORSHIP? bucket")
    for r in rep.get("by_writer") or ():
        print(f"      {r['n']:6d}  {r['role']}")
        print(f"              {r['introduced_by']}")


# ── CERTIFICATE ATTRIBUTION (NO BUILD): the R1.1 table ────────────────
#: Pin-source labels that make an endpoint SENIOR (the projection must not
#: move it under any arm of the solve round): the runway datum, pads /
#: seats, the tile seam, terrain pins.  Everything else hard is a solve-
#: minted hold the S1 filter may stand down.
_SENIOR_PINS = ("runway_node", "pad", "tile_seam", "terrain_pin",
                "building_seat", "rwy_", "seam_")
#: Hard sources S1's ``_solve_law_hold_filter`` / the weld-scan release
#: stand down (fgp-s1-round-ledger.md): a mixed row whose hard endpoint is
#: one of these is the hold-release-only arm's own population.
_RELEASABLE_PINS = ("svc_free_end", "svc_profile", "gs_weld",
                    "service_ring", "feature_weld", "svc_mouth_seat")
#: Certificate families that exist ONLY in the projection's rebuilt graph
#: (never at the solve exit): the S1 law-join replaces them.
_FGP_ONLY_FAMILIES = ("transverse", "junction:transverse_no_step")
_FGP_MARK = "final_grade_projection"
#: The pipeline call line of ``final_grade_projection`` — a write whose
#: chain carries a ``pipeline.py:<line>:solve_and_finalize`` frame with a
#: larger line is POST-projection.  Read from the chain, never assumed:
#: the reader takes it from the first FGP site it sees.
_PIPE_RE = None


def _pipeline_line(site):
    """The ``pipeline.py:<line>:solve_and_finalize`` frame's line in a
    site chain, or ``None`` when the chain does not reach it."""
    global _PIPE_RE
    if _PIPE_RE is None:
        import re
        _PIPE_RE = re.compile(r"pipeline\.py:(\d+):solve_and_finalize")
    m = _PIPE_RE.search(site or "")
    return int(m.group(1)) if m else None


def stage_of_site(site):
    """A short STAGE label for a write site chain (innermost frame first).

    ``fgp`` for any write inside ``final_grade_projection``; ``solve@L``
    for a write inside ``solve_route_profile`` (L = its line: the
    writeback vs the pass-2 sites); otherwise the innermost frame's
    function name, or ``pipeline@L`` when that frame is
    ``solve_and_finalize`` itself (an inline pass; the line names it).
    """
    if not site:
        return "?"
    inner = site.split(" <- ")[0]
    parts = inner.split(":")
    fn = parts[2] if len(parts) >= 3 else inner
    line = parts[1] if len(parts) >= 3 else "?"
    if _FGP_MARK in site:
        return "fgp" if fn == _FGP_MARK else f"fgp/{fn}"
    if _SOLVE_SITE in site:
        return f"solve@{line}" if fn == _SOLVE_SITE else f"solve/{fn}"
    if fn == "solve_and_finalize":
        return f"pipeline@{line}"
    return fn


def load_vertex_dump(path):
    """``(sites, index)`` — ``index`` maps a 2-dp plan coordinate to the
    list of vertex records at it (every role / ref sharing the point)."""
    sites, index = [], {}
    with Path(path).open() as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("kind") == "meta":
                sites = r["sites"]
                continue
            if r.get("kind") != "vertex":
                continue
            index.setdefault((round(r["x"], 2), round(r["y"], 2)),
                             []).append(r)
    return sites, index


def _vertex_at(index, x, y):
    """The vertex records at a plan coordinate, tolerant to 1 cm of
    rounding on either axis (the dumps round to 3 dp, the join to 2)."""
    for dx in (0.0, -0.01, 0.01):
        for dy in (0.0, -0.01, 0.01):
            h = index.get((round(x + dx, 2), round(y + dy, 2)))
            if h:
                return h
    return []


def endpoint_state(recs, sites, fgp_line=None, move_floor=0.1):
    """What the write stream says about ONE certificate endpoint.

    Over every vertex record at the point (several shapes can share it):
    the LAST write that changed the value BEFORE the projection (the
    stage the residual's value was authored by, at the reading), the
    set of roles at the point, whether the projection moved it by
    ``move_floor`` or more (and by how much), and the solve's value.
    Pre-projection = the entries before the first ``fgp`` entry of the
    history; with no ``fgp`` entry, the entries whose pipeline frame
    line is <= the projection's (``fgp_line``) when that is readable.
    """
    roles = sorted({r["role"] for r in recs})
    last_stage, last_site_line = "?", -1
    fgp_moved, fgp_dm, solved = False, 0.0, None
    for r in recs:
        hist = r.get("hist") or []
        pre = []
        seen_fgp = False
        for (si, v) in hist:
            st = sites[si]
            if _FGP_MARK in st:
                seen_fgp = True
                break
            pre.append((si, v))
        if not seen_fgp and fgp_line is not None:
            pre = [(si, v) for (si, v) in hist
                   if (_pipeline_line(sites[si]) or 0) <= fgp_line]
        if pre:
            si, v = pre[-1]
            # Prefer the CHRONOLOGICALLY latest pre-projection writer
            # across the shapes at the point: the pipeline frame line
            # orders inline passes; a deeper chain without one ranks by
            # its position (0) and only wins when nothing else wrote.
            pl = _pipeline_line(sites[si]) or 0
            if pl >= last_site_line:
                last_site_line = pl
                last_stage = stage_of_site(sites[si])
        prev = None
        for (si, v) in hist:
            st = sites[si]
            if _FGP_MARK in st and prev is not None:
                d = abs(v - prev)
                if d >= move_floor:
                    fgp_moved = True
                    fgp_dm = max(fgp_dm, d)
            prev = v
        if r.get("solved") is not None:
            solved = r["solved"]
    return {"roles": roles, "last_stage": last_stage,
            "fgp_moved": fgp_moved, "fgp_dm": round(fgp_dm, 3),
            "solved": solved}


def _family_group(fam):
    f = str(fam)
    if f in _FGP_ONLY_FAMILIES or f in ("rod_interval", "unified_graph"):
        return f
    if f.startswith("unified:"):
        f = f[len("unified:"):]
    return f.split(":", 1)[0] or f


def _pair_key(row):
    pts = tuple(sorted((round(x, 2), round(y, 2)) for x, y in row["xy"]))
    return pts


def disposition(row, ends):
    """The PREDICTED disposition of one residual row under the R1
    arms — a mechanical rule over the row's own evidence (pins, hard
    flags, family, the write stream), stated so the table can be
    checked against the arms when they run.  Never a verdict."""
    pins = [p or "" for p in row.get("pins") or []]
    hard = row.get("hard") or []
    if row.get("both_hard"):
        return "pin-infeasible (both hard)"
    for h, p in zip(hard, pins):
        if h and any(p.startswith(s) for s in _SENIOR_PINS):
            return f"senior-protected ({p})"
    fam = str(row["family"])
    if fam in _FGP_ONLY_FAMILIES:
        return "closes:S1 (FGP-only family)"
    if row.get("mixed"):
        for h, p in zip(hard, pins):
            if h and any(p.startswith(s) for s in _RELEASABLE_PINS):
                return f"closes:S1-hold-release ({p})"
        if any(hard):
            return "needs-solve (R6 pin, non-releasable hard)"
        return "needs-solve (R6 groundside-service, no hard endpoint)"
    if any(e["fgp_moved"] for e in ends):
        if row.get("_in_base"):
            return "needs-solve (inherited from solve exit; FGP moved)"
        return "closes:S2 (FGP re-authored a solve value)"
    if row.get("_in_base"):
        return "needs-solve (inherited from solve exit)"
    return "closes:S1 (minted by the rebuilt graph)"


def attribute_certificate(cert_path, vertex_path, base_paths=(),
                          move_floor=0.1, top_specimens=3):
    """THE R1.1 TABLE: every residual row of one certificate reading,
    grouped by (family group, pair class, last pre-projection writer of
    each endpoint, FGP moved?), with counts, p50 / max excess, the
    predicted disposition split, and specimens.

    ``base_paths`` — ``label=PATH`` readings (e.g. ``solve=…solve_exit…``)
    whose rows are joined on the unordered endpoint pair, so each row
    says which earlier reading already carried it (inherited) or not
    (minted).  Returns ``{"rows": [...], "groups": [...], "summary": …}``.
    """
    cert = json.loads(Path(cert_path).read_text())
    sites, index = load_vertex_dump(vertex_path)
    fgp_line = None
    for st in sites:
        if _FGP_MARK in st:
            fgp_line = _pipeline_line(st)
            if fgp_line is not None:
                break
    bases = {}
    for spec in base_paths or ():
        label, _, pth = spec.partition("=")
        b = json.loads(Path(pth).read_text())
        bases[label] = {_pair_key(r) for r in b["rows"]}
    base_label = next(iter(bases), None)
    rows_out, groups, unjoined = [], {}, 0
    for r in cert["rows"]:
        ends = []
        for (x, y) in r["xy"]:
            recs = _vertex_at(index, x, y)
            if not recs:
                unjoined += 1
            ends.append(endpoint_state(recs, sites, fgp_line, move_floor))
        pk = _pair_key(r)
        member = {lab: (pk in ks) for lab, ks in bases.items()}
        r2 = dict(r)
        r2["_in_base"] = bool(member.get(base_label)) if base_label else False
        disp = disposition(r2, ends)
        fam_role = _family_group(r["family"])
        # Endpoint role: the family's own role when the point carries it,
        # else every role at the point (a weld hub reads as its stack).
        def _erole(e):
            if fam_role in e["roles"]:
                return fam_role
            return "+".join(e["roles"]) or "?"
        eroles = sorted(_erole(e) for e in ends)
        # a hyper row (4 nodes) collapses to its distinct role set
        pair = "|".join(sorted(set(eroles))) if len(eroles) > 2 \
            else "|".join(eroles)
        stages = tuple(e["last_stage"] for e in ends)
        st_key = "|".join(sorted(set(stages)))
        moved = any(e["fgp_moved"] for e in ends)
        key = (fam_role, pair, st_key, moved)
        g = groups.setdefault(key, {
            "family": fam_role, "pair": pair, "last_stage": st_key,
            "fgp_moved": moved, "n": 0, "excess": [], "disp": {},
            "member": {}, "specimens": []})
        g["n"] += 1
        g["excess"].append(float(r["excess_m"]))
        g["disp"][disp] = g["disp"].get(disp, 0) + 1
        for lab, m in member.items():
            g["member"][lab] = g["member"].get(lab, 0) + int(m)
        g["specimens"].append((float(r["excess_m"]), r.get("ll"),
                               r.get("idx"), r["family"], disp))
        rows_out.append({
            "family": r["family"], "family_group": fam_role, "pair": pair,
            "excess_m": r["excess_m"], "both_hard": r.get("both_hard"),
            "mixed": r.get("mixed"), "hard": r.get("hard"),
            "pins": r.get("pins"), "xy": r["xy"], "ll": r.get("ll"),
            "idx": r.get("idx"), "ends": ends, "member": member,
            "disposition": disp})
    out_groups = []
    for g in groups.values():
        ex = sorted(g["excess"])
        g["p50_m"] = round(ex[len(ex) // 2], 3)
        g["max_m"] = round(ex[-1], 3)
        del g["excess"]
        g["specimens"].sort(key=lambda t: -t[0])
        g["specimens"] = [{"excess_m": e, "ll": ll, "idx": idx,
                           "family": f, "disposition": d}
                          for (e, ll, idx, f, d) in
                          g["specimens"][:top_specimens]]
        out_groups.append(g)
    out_groups.sort(key=lambda g: -g["n"])
    disp_tot: dict = {}
    fam_tot: dict = {}
    for r in rows_out:
        disp_tot[r["disposition"]] = disp_tot.get(r["disposition"], 0) + 1
        fam_tot[r["family_group"]] = fam_tot.get(r["family_group"], 0) + 1
    summary = {
        "cert": str(cert_path), "reading": cert.get("tag"),
        "n_rows": len(rows_out), "n_over": cert.get("n_over"),
        "endpoints_unjoined": unjoined, "fgp_pipeline_line": fgp_line,
        "move_floor_m": move_floor,
        "by_disposition": dict(sorted(disp_tot.items(),
                                      key=lambda kv: -kv[1])),
        "by_family": dict(sorted(fam_tot.items(), key=lambda kv: -kv[1])),
        "by_membership": {lab: sum(1 for r in rows_out
                                   if r["member"].get(lab))
                          for lab in bases},
        "rows_with_fgp_moved_endpoint": sum(
            1 for r in rows_out if any(e["fgp_moved"] for e in r["ends"])),
    }
    return {"summary": summary, "groups": out_groups, "rows": rows_out}


def attribute_moves(moves_path, vertex_path, cert_rows=None,
                    author=_FGP_MARK, cls="untouched"):
    """The 827-class by LAST PRE-PROJECTION WRITER: every ``move`` record
    of ``author`` in class ``cls`` from an ``--author-dump``, joined to
    the vertex history at its plan coordinate, grouped by (role, last
    stage), with the count / p50 / max displacement and how many of the
    moved vertices are endpoints of a certificate residual row."""
    sites, index = load_vertex_dump(vertex_path)
    fgp_line = None
    for st in sites:
        if _FGP_MARK in st:
            fgp_line = _pipeline_line(st)
            if fgp_line is not None:
                break
    resid_pts = set()
    for r in (cert_rows or ()):
        for (x, y) in r["xy"]:
            resid_pts.add((round(x, 2), round(y, 2)))
    groups: dict = {}
    n_total = 0
    with Path(moves_path).open() as fh:
        for line in fh:
            m = json.loads(line)
            if m.get("kind") != "move" or m.get("class") != cls:
                continue
            if author not in (m.get("author") or ""):
                continue
            n_total += 1
            x, y = m.get("x"), m.get("y")
            recs = ([rr for rr in _vertex_at(index, x, y)
                     if rr["role"] == m["role"]]
                    if x is not None else [])
            st = endpoint_state(recs, sites, fgp_line)
            on_resid = (x is not None
                        and (round(x, 2), round(y, 2)) in resid_pts)
            key = (m["role"], st["last_stage"])
            g = groups.setdefault(key, {"role": m["role"],
                                        "last_stage": st["last_stage"],
                                        "n": 0, "d": [], "on_residual": 0,
                                        "specimens": []})
            g["n"] += 1
            d = abs(float(m["after"]) - float(m["before"]))
            g["d"].append(d)
            g["on_residual"] += int(on_resid)
            g["specimens"].append((d, m.get("x"), m.get("y"),
                                   m.get("ref"), m.get("before"),
                                   m.get("after")))
    out = []
    for g in groups.values():
        d = sorted(g["d"])
        g["p50_m"] = round(d[len(d) // 2], 3)
        g["max_m"] = round(d[-1], 3)
        del g["d"]
        g["specimens"].sort(key=lambda t: -t[0])
        g["specimens"] = [{"d_m": round(a, 3), "x": x, "y": y, "ref": ref,
                           "before": b, "after": c}
                          for (a, x, y, ref, b, c) in g["specimens"][:3]]
        out.append(g)
    out.sort(key=lambda g: -g["n"])
    return {"n_moves": n_total, "class": cls, "author": author,
            "groups": out}


def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def render_attribution_md(cert_attr, moves_attr=None, top=None):
    """Markdown for the two attribution tables."""
    s = cert_attr["summary"]
    lines = [f"### Certificate residual attribution — {s['reading']}",
             "",
             f"rows {s['n_rows']} (certificate n_over {s['n_over']}); "
             f"endpoints unjoined {s['endpoints_unjoined']}; "
             f"FGP pipeline line {s['fgp_pipeline_line']}; "
             f"rows with an FGP-moved (>= {s['move_floor_m']} m) endpoint "
             f"{s['rows_with_fgp_moved_endpoint']}",
             "",
             "by family: " + ", ".join(f"{k} {v}" for k, v in
                                       s["by_family"].items()),
             "",
             "by membership in earlier readings: " + ", ".join(
                 f"{k} {v}" for k, v in s["by_membership"].items()),
             "",
             "by predicted disposition: " + "; ".join(
                 f"{k} {v}" for k, v in s["by_disposition"].items()),
             ""]
    rows = []
    for g in (cert_attr["groups"] if top is None
              else cert_attr["groups"][:top]):
        disp = "; ".join(f"{k} {v}" for k, v in
                         sorted(g["disp"].items(), key=lambda kv: -kv[1]))
        mem = ", ".join(f"{k} {v}" for k, v in g["member"].items())
        spec = "; ".join(
            f"{sp['excess_m']:.2f} m @ " + (
                ",".join(f"{ll[0]:.6f}/{ll[1]:.6f}" for ll in
                         (sp['ll'] or [])[:2]) or "?")
            for sp in g["specimens"][:2])
        rows.append((g["family"], g["pair"], g["last_stage"],
                     "yes" if g["fgp_moved"] else "no", g["n"],
                     g["p50_m"], g["max_m"], mem, disp, spec))
    lines.append(_md_table(
        ["family", "pair", "last pre-FGP writer (a|b)", "FGP moved",
         "n", "p50 m", "max m", "in earlier reading", "predicted disposition",
         "specimens (excess @ lat/lon)"], rows))
    if moves_attr:
        lines += ["", f"### FGP moves, class '{moves_attr['class']}' "
                      f"({moves_attr['n_moves']} moves) by last "
                      f"pre-FGP writer", ""]
        rows = [(g["role"], g["last_stage"], g["n"], g["p50_m"],
                 g["max_m"], g["on_residual"],
                 "; ".join(f"{sp['d_m']:.2f} m @ ({sp['x']},{sp['y']}) "
                           f"{sp['ref']}" for sp in g["specimens"][:2]))
                for g in moves_attr["groups"]]
        lines.append(_md_table(
            ["role", "last pre-FGP writer", "n", "p50 m", "max m",
             "on a residual row", "specimens"], rows))
    return "\n".join(lines) + "\n"


class AuthorshipProbe:
    """Records every ``node_altitudes`` assignment.  ``install`` swaps the
    dataclass field for a property; ``uninstall`` puts it back."""

    def __init__(self, shape_cls, dem_m=None, roles=None, at=(), tol=0.05,
                 authors=(), author_tol=0.01, solve_site=_SOLVE_SITE,
                 dump_moves=False, track_vertices=False):
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
        #: ``--vertex-dump``: THE VERTEX HISTORY — for EVERY vertex the
        #: build ever wrote, the ordered list of writes that CHANGED its
        #: value (beyond ``author_tol``), keyed by (role, ref, plan
        #: coordinate) so it survives the ``dataclasses.replace`` re-
        #: minting that gives one ring a new instance id.  This is the
        #: "last solver stage that wrote each endpoint" axis the R1
        #: attribution table groups on (zero-airside plan R1.1).
        self.track_vertices = bool(track_vertices)
        self.vhist: dict = {}
        self._vprev: dict = {}
        self._vring: dict = {}
        self._sites: dict = {}
        self.site_list: list = []
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
                          and abs(float(a) - self.dem_m) <= _MEM_TOL)
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
                        and abs(float(v) - self.dem_m) <= _MEM_TOL):
                    dorg[k] = site
        if self.authors:
            self._record_author(shape, role, values, site)
        if self.track_vertices and values is not None and site is not None:
            self._record_vertices(shape, role, values, site)
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

    # ── the vertex history (``--vertex-dump``) ────────────────────────
    def _record_vertices(self, shape, role, values, site):
        """Append this write to the history of every vertex it CHANGED.

        A vertex is keyed by ``(role, ref, x, y)`` with the plan
        coordinate rounded to 1 mm, read from the shape's ring at the
        time of the write (cached per instance and ring length).  A
        write is a change when the value differs from the instance's
        previous value by more than ``author_tol``; the first write of a
        NEW instance (``dataclasses.replace``) that repeats the key's
        last recorded value is a carry, not a change.  In-place list
        mutation (``shape.node_altitudes[k] = v``) never reaches the
        property setter and is invisible here, as it is to every other
        report of this probe.
        """
        sid = id(shape)
        n = len(values)
        ring = self._vring.get(sid)
        if ring is None or len(ring) != n:
            poly = getattr(shape, "polygon", None)
            ring = (list(poly.exterior.coords)
                    if (poly is not None and not poly.is_empty
                        and poly.geom_type == "Polygon") else [])
            self._vring[sid] = ring
        prev = self._vprev.get(sid)
        sidx = self._sites.get(site)
        if sidx is None:
            sidx = len(self.site_list)
            self._sites[site] = sidx
            self.site_list.append(site)
        ref = getattr(shape, "ref", "") or ""
        tol = self.author_tol
        vh = self.vhist
        for k in range(min(n, len(ring))):
            v = values[k]
            if v is None:
                continue
            v = float(v)
            p = prev[k] if (prev is not None and k < len(prev)) else None
            if p is not None and abs(v - p) <= tol:
                continue
            x, y = ring[k]
            key = (role, ref, round(x, 3), round(y, 3))
            h = vh.get(key)
            if h is None:
                h = []
                vh[key] = h
            elif p is None and abs(h[-1][1] - v) <= tol:
                continue
            h.append((sidx, round(v, 4)))
        self._vprev[sid] = [None if v is None else float(v) for v in values]

    def write_vertex_dump(self, path):
        """``--vertex-dump``: one JSONL record per vertex key.

        ``meta`` first (the site table — records carry site INDICES into
        it — the materiality floor and the solve reference site), then
        one ``vertex`` record per key: role, ref, plan coordinate, the
        ordered ``hist`` of ``[site_index, value]`` changes, the
        ``final`` value, the ``solved`` value (the value at the last
        change whose site contains ``solve_site``; ``None`` when the
        solve never wrote it) and ``last_site`` (index).
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        solve_hits = [self.solve_site in st for st in self.site_list]
        n = 0
        with path.open("w") as fh:
            fh.write(json.dumps({
                "kind": "meta", "sites": self.site_list,
                "tol_m": self.author_tol, "solve_site": self.solve_site,
                "n_vertices": len(self.vhist)}) + "\n")
            for (role, ref, x, y), hist in self.vhist.items():
                solved = None
                for (si, v) in hist:
                    if solve_hits[si]:
                        solved = v
                fh.write(json.dumps({
                    "kind": "vertex", "role": role, "ref": ref,
                    "x": x, "y": y, "hist": [[si, v] for si, v in hist],
                    "final": hist[-1][1] if hist else None,
                    "solved": solved,
                    "last_site": hist[-1][0] if hist else None}) + "\n")
                n += 1
        return {"vertices": n, "sites": len(self.site_list),
                "path": str(path)}

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
                      if a is not None and abs(float(a) - self.dem_m) <= _MEM_TOL)
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
                                 and abs(float(a) - self.dem_m) <= _MEM_TOL),
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


class FootprintProbe:
    """Records every ``BuiltShape.polygon`` assignment that CHANGES whether
    a probe point is covered — the FOOTPRINT counterpart of
    :class:`AuthorshipProbe`.

    ``install`` swaps the dataclass field for a property; ``uninstall``
    puts it back.  Instances are tracked by ``id()`` GUARDED BY A WEAK
    REFERENCE, and both halves are load-bearing: ``BuiltShape`` is a
    plain ``@dataclass``, so Python sets ``__hash__ = None`` and a
    ``WeakKeyDictionary`` raises ``TypeError`` on every write — inside
    the "instrumentation never breaks a build" guard, which turns it
    into an instrument that silently records NOTHING (measured: an
    entire HECA build, zero rows).  A bare ``id()`` is the opposite
    failure: ids are reused within one build, which silently joins two
    unrelated shapes' histories.  So each entry keeps a ``weakref`` and
    an entry whose referent is gone (or is a different object) is
    treated as a fresh instance.

    The probe DERIVES NOTHING.  Coverage is ``polygon.covers(Point)`` on
    the ring exactly as the pass wrote it; the report is the ordered list
    of transitions, and naming which of them is the defect is the reader's
    job.
    """

    def __init__(self, shape_cls, at=()):
        from shapely.geometry import Point            # noqa: PLC0415
        self.cls = shape_cls
        self.at = [(float(x), float(y)) for x, y in at]
        self._pts = [Point(p) for p in self.at]
        #: "x,y" → [row, …], in write order
        self.rows: dict = {f"{p[0]},{p[1]}": [] for p in self.at}
        #: id(shape) → [weakref(shape), ordinal, {probe index: covered?}]
        #: as of that instance's last recorded write.  See the class
        #: docstring for why it is neither a WeakKeyDictionary nor a bare
        #: id map.
        self._state: dict = {}
        self._n_inst = 0
        self._step = 0
        self._saved = None

    # ── the hook ─────────────────────────────────────────────────────
    def _record(self, shape, poly):
        if not self._pts:
            return
        self._step += 1
        try:
            empty = poly is None or poly.is_empty
            bounds = None if empty else poly.bounds
        except Exception:
            return
        import weakref                                # noqa: PLC0415
        key = id(shape)
        entry = self._state.get(key)
        if entry is not None and entry[0]() is not shape:
            entry = None                  # the id was reused by a new object
        first = entry is None
        if first:
            self._n_inst += 1
            try:
                ref = weakref.ref(shape)
            except TypeError:             # not weakref-able: id alone
                ref = lambda: shape       # noqa: E731
            entry = [ref, self._n_inst, {}]
            self._state[key] = entry
        prev = entry[2]
        state = {}
        changed = []
        for i, pt in enumerate(self._pts):
            hit = False
            if not empty:
                x, y = self.at[i]
                if (bounds[0] <= x <= bounds[2]
                        and bounds[1] <= y <= bounds[3]):
                    try:
                        hit = bool(poly.covers(pt))
                    except Exception:
                        hit = False
            state[i] = hit
            if prev.get(i, False) != hit or (first and hit):
                changed.append((i, prev.get(i, False), hit))
        entry[2] = state
        if not changed:
            return
        site = call_site(skip=3)
        for i, was, now in changed:
            self.rows[f"{self.at[i][0]},{self.at[i][1]}"].append({
                "step": self._step,
                "instance": entry[1],
                "event": "birth" if first else ("grew" if now else "shrank"),
                "covered": now,
                "was_covered": was,
                "role": getattr(shape, "role", "") or "",
                "ref": getattr(shape, "ref", "") or "",
                "area_m2": None if empty else round(poly.area, 1),
                "site": site,
            })

    def install(self):
        probe = self
        self._saved = self.cls.__dict__.get("polygon", _MISSING)

        # WRITE THROUGH TO THE INSTANCE DICT (the AuthorshipProbe note
        # applies verbatim): the ring must survive ``uninstall`` so the
        # layout a report is taken from is the layout the build produced.
        def _get(self):
            return self.__dict__.get("polygon")

        def _set(self, value):
            self.__dict__["polygon"] = value
            try:
                probe._record(self, value)
            except Exception:          # instrumentation never breaks a build
                pass

        self.cls.polygon = property(_get, _set)
        return self

    def uninstall(self):
        if self._saved is _MISSING:
            try:
                delattr(self.cls, "polygon")
            except AttributeError:
                pass
        else:
            setattr(self.cls, "polygon", self._saved)
        self._saved = None

    # ── the report ───────────────────────────────────────────────────
    def footprint_history(self, layout=None):
        """``{"x,y": {"final": …, "changes": [row, …]}}``.

        ``final`` names the shape covering the point in the FINISHED
        layout — the emitted answer the change list has to end at.  It is
        read off ``layout.shapes`` by index, which IS the ``shapeID`` tag
        ``layout.to_osm`` writes, so a row here joins a patch read.
        """
        out = {}
        for i, key in enumerate(self.rows):
            final = []
            if layout is not None:
                for idx, s in enumerate(getattr(layout, "shapes", ()) or ()):
                    p = getattr(s, "polygon", None)
                    try:
                        if p is not None and not p.is_empty \
                                and p.covers(self._pts[i]):
                            final.append({"shapeID": idx, "role": s.role,
                                          "ref": getattr(s, "ref", ""),
                                          "area_m2": round(p.area, 1)})
                    except Exception:
                        continue
            out[key] = {"final": final, "changes": self.rows[key]}
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("icao", nargs="?", default=None)
    ap.add_argument("--emitted-patch", action="append", default=[],
                    metavar="PATCH.osm",
                    help="NO BUILD: report the EMITTED-frame count of "
                         "vertices sitting exactly on the constant DEM in "
                         "an already-built patch (needs --dem), by way "
                         "role, with the STRANDED subset — the on-DEM "
                         "vertices sharing a way with a law-valued one, "
                         "which is the class a within-shape law row is "
                         "minted in.  Repeatable.  The in-memory census "
                         "and this one are two FRAMES of one question "
                         "(HECA: 16,019 in memory, 938 emitted); both "
                         "come out of this tool so neither can be quoted "
                         "for the other.")
    ap.add_argument("--who-json", default=None, metavar="PATH",
                    help="with --emitted-patch: an earlier run's "
                         "``ICAO_who_wrote.json``, so the emitted count "
                         "comes out ATTRIBUTED to the writer that "
                         "introduced each vertex (joined on the way's "
                         "shapeID tag, which IS the layout.shapes index).  "
                         "The rows are found at the top-level "
                         "``dem_authorship`` key, as a bare list, or "
                         "nested one level under another key; the key "
                         "actually read and the join counts are printed, "
                         "so a join that matches nothing says so")
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
    ap.add_argument("--cert-attrib", default=None, metavar="CERT.json",
                    help="NO BUILD: THE R1.1 TABLE — attribute every "
                         "residual row of an airside-certificate dump "
                         "(``O4_AIRSIDE_CERT_DUMP``) by family, endpoint "
                         "role pair, the LAST PRE-PROJECTION WRITER of "
                         "each endpoint (from --vertex-json) and whether "
                         "the projection moved an endpoint; needs "
                         "--vertex-json.  Optional --cert-base "
                         "LABEL=PATH (repeatable) marks rows an earlier "
                         "reading already carried; --moves-json adds the "
                         "author-dump's untouched-class moves by last "
                         "writer.  Writes --attrib-json / --attrib-md.")
    ap.add_argument("--vertex-json", default=None, metavar="PATH",
                    help="with --cert-attrib: a --vertex-dump JSONL")
    ap.add_argument("--cert-base", action="append", default=[],
                    metavar="LABEL=PATH",
                    help="with --cert-attrib: an earlier reading's dump, "
                         "joined on the endpoint pair (first one given "
                         "is the 'inherited' reference for dispositions)")
    ap.add_argument("--moves-json", default=None, metavar="PATH",
                    help="with --cert-attrib: an --author-dump JSONL; its "
                         "untouched-class projection moves are attributed "
                         "by last pre-projection writer")
    ap.add_argument("--attrib-json", type=Path, default=None)
    ap.add_argument("--attrib-md", type=Path, default=None)
    ap.add_argument("--move-floor", type=float, default=0.1,
                    help="with --cert-attrib: an endpoint counts as "
                         "'FGP moved' at this displacement (default 0.1 m)")
    ap.add_argument("--vertex-dump", type=Path, default=None,
                    metavar="PATH",
                    help="THE VERTEX HISTORY: write, for EVERY vertex the "
                         "build wrote, the ordered list of writes that "
                         "CHANGED its value (site + value), keyed by "
                         "(role, ref, plan coordinate), as JSONL.  The "
                         "axis the R1 attribution joins the airside "
                         "certificate's residual endpoints on (which "
                         "solver stage last wrote each endpoint).  Uses "
                         "--author-tol as its change floor.")
    ap.add_argument("--footprint", action="append", default=[],
                    metavar="X,Y",
                    help="FOOTPRINT history: metre-frame coordinate whose "
                         "COVERAGE is traced instead of its value — every "
                         "write at which a shape started or stopped "
                         "covering it, with the call site.  Repeatable.  "
                         "The report a 'which pass put pavement here at "
                         "all' question needs; a point outside every shape "
                         "has no vertex for --at to trace.")
    ap.add_argument("--out", type=Path, default=Path("/tmp/harness/who"))
    ap.add_argument("--allow-degraded-dem", action="store_true",
                    help="relaxes the ONE gate that lives in build_patch "
                         "itself — the swallowed-degradation refusal (a "
                         "write the shared-repo guard blocked, or a layout "
                         "with no DEM provenance at all), which this entry "
                         "does reach.  The cfg-frame and cold-cache gates "
                         "are armed in build_airport's own main(), which "
                         "who_wrote never enters, so for those the flag is "
                         "still RECORDED ONLY "
                         "(allow_degraded_dem_requested).  It authorises no "
                         "write to the shared data repo.")
    args = ap.parse_args(argv)
    if args.cert_attrib:
        if not args.vertex_json:
            ap.error("--cert-attrib needs --vertex-json (a --vertex-dump)")
        attr = attribute_certificate(args.cert_attrib, args.vertex_json,
                                     base_paths=args.cert_base,
                                     move_floor=args.move_floor)
        mv = None
        if args.moves_json:
            mv = attribute_moves(args.moves_json, args.vertex_json,
                                 cert_rows=attr["rows"])
        md = render_attribution_md(attr, mv)
        print(md)
        if args.attrib_md:
            Path(args.attrib_md).parent.mkdir(parents=True, exist_ok=True)
            Path(args.attrib_md).write_text(md)
        if args.attrib_json:
            Path(args.attrib_json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.attrib_json).write_text(json.dumps(
                {"certificate": attr, "moves": mv}, indent=1))
        return 0
    if args.emitted_patch:
        # A pure FILE read: no build, no layout, so no build cwd and no
        # ICAO.  It answers the emitted half of the frame question on a
        # patch some earlier build already wrote.
        if args.dem is None:
            ap.error("--emitted-patch needs --dem (the predicate is "
                     "'sits exactly on the constant DEM')")
        rows, src = None, None
        if args.who_json:
            # LOUD, not silent: a who-json that carries no authorship rows
            # is a DIFFERENT state from "attribution not requested", and
            # the loader names the key it read them from.  The old form
            # (`.get("dem_authorship")` → None) collapsed both to the same
            # empty section.
            obj = json.loads(Path(args.who_json).read_text())
            rows, src, top = authorship_rows_from_report(obj)
            if src is None:
                print(f"  [harness] --who-json {args.who_json}: no "
                      f"{_AUTHORSHIP_KEY!r}-shaped rows found "
                      f"(top-level keys: {top}); attribution will report "
                      f"an EMPTY join, not silence")
            else:
                print(f"  [harness] --who-json {args.who_json}: "
                      f"{len(rows)} authorship row(s) from {src!r}")
        for p in args.emitted_patch:
            rep = emitted_on_dem(p, args.dem, authorship=rows,
                                 authorship_source=src)
            print(f"\n  [harness] {p}")
            print_emitted_on_dem(rep)
        return 0
    if args.icao is None:
        ap.error("give an ICAO (to build) or --emitted-patch (to read a "
                 "patch an earlier build wrote)")
    if (args.dem is None and not args.at and not args.author
            and not args.footprint and not args.vertex_dump):
        ap.error("give --dem (authorship census), --at X,Y (node history), "
                 "--author SITE (displacement census), --footprint X,Y "
                 "(footprint history), --vertex-dump PATH (vertex "
                 "history), or any combination")

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

    fp_at = [tuple(float(v) for v in a.split(",")) for a in args.footprint]
    probe = AuthorshipProbe(BuiltShape, args.dem, roles, at, args.tol,
                            authors=args.author,
                            author_tol=args.author_tol,
                            dump_moves=bool(args.author_dump),
                            track_vertices=bool(args.vertex_dump)).install()
    fprobe = FootprintProbe(BuiltShape, fp_at).install() if fp_at else None
    try:
        tag = f"{args.icao}_who{'' if args.dem is None else f'_dem{args.dem:g}'}"
        result = HB.build_patch(args.icao, root, out, tag, prog,
                                const_dem=args.dem,
                                allow_degraded=args.allow_degraded_dem)
        layout = result["_layout"]
    finally:
        if fprobe is not None:
            fprobe.uninstall()
        probe.uninstall()

    report: dict = {"icao": args.icao, "dem_m": args.dem,
                    "patch": result["patch"],
                    # FRAME STAMP for the whole run (RULINGS 2026-08-06
                    # point 3).  ``--allow-degraded-dem`` is PASSED to
                    # ``HB.build_patch`` (it relaxes the swallowed-
                    # degradation refusal, which lives there and which this
                    # path does reach) and recorded as REQUESTED for the
                    # rest: the cfg/DEM-frame gates it also relaxes live in
                    # build_airport's own ``main``, which this path never
                    # enters.
                    "roles_filter": roles or None,
                    "at_tol_m": args.tol,
                    "allow_degraded_dem_requested": bool(
                        args.allow_degraded_dem)}
    if args.dem is not None:
        rows, by_author = probe.dem_authorship(layout)
        report["dem_authorship"] = rows
        report["dem_authorship_frame"] = {
            "frame": "IN-MEMORY layout",
            "tol_m": _MEM_TOL,
            "world": f"constant DEM {args.dem:g} m",
            "shapes": len(getattr(layout, "shapes", ()) or ()),
            "roles_filter": roles or None}
        total = sum(by_author.values())
        print(f"\n  === IN-MEMORY layout values within {_MEM_TOL:g} m of "
              f"the {args.dem:g} m constant DEM: {total}, "
              f"by INTRODUCING writer")
        print(f"      [frame: IN-MEMORY layout.shapes"
              f"  |  world: constant DEM {args.dem:g} m"
              f"  |  NOT the emitted-patch count]\n")
        for (role, site), n in by_author.most_common():
            print(f"    {n:6d}  {role}")
            print(f"            {site}")
        print(f"\n  === per shape (top 15, IN-MEMORY frame)")
        for r in rows[:15]:
            print(f"    #{r['shape']:<5}{r['role']:<22}"
                  f"{r['on_dem']:5d}/{r['n']:<5d} writes={r['writes']}")
            print(f"          introduced by: {r['introduced_by']}")
        # The EMITTED frame of the same question, from this build's own
        # patch — so the two counts are never separated.
        try:
            emitted = emitted_on_dem(result["patch"], args.dem,
                                     authorship=rows,
                                     authorship_source="probe.dem_authorship")
            report["emitted_on_dem"] = emitted
            print_emitted_on_dem(emitted)
        except Exception as exc:                        # pragma: no cover
            print(f"  [harness] EMITTED-frame count unavailable "
                  f"({type(exc).__name__}: {exc}); the IN-MEMORY count "
                  f"above stands alone")
    if args.author:
        rows, totals = probe.author_report()
        report["author_displacement"] = rows
        report["author_worst"] = [
            {"delta_m": round(d, 3), "author": a, "class": c, "role": r,
             "ref": ref, "before": before, "after": after, "x": x, "y": y}
            for (d, a, c, r, ref, before, after, x, y) in probe.author_worst]
        report["author_frame"] = {
            "frame": "IN-MEMORY write stream",
            "materiality_m": args.author_tol,
            "solve_site": probe.solve_site,
            "authors": list(args.author),
            "classes": {
                "new_geometry": "the shape's ring length differs from the "
                                "solve's, or the solve wrote None there",
                "moved_post_solve": "the overwritten value was already "
                                    "further than materiality from the "
                                    "solve's",
                "untouched": "the overwritten value was within materiality "
                             "of this shape's last solve write"}}
        print("\n  === VALUES MOVED AWAY FROM THE SOLVE, by author")
        print(f"      [frame: IN-MEMORY write stream  |  materiality "
              f"{args.author_tol:g} m  |  solve reference: writes whose "
              f"site contains {probe.solve_site!r}]\n")
        print(f"    {'author':<26}{'class':<18}{'role':<22}"
              f"{'n_moved':>9}{'max|d| m':>11}{'p50|d| m':>10}")
        for r in rows:
            print(f"    {r['author']:<26}{r['class']:<18}{r['role']:<22}"
                  f"{r['n_moved']:>9}{r['max_m']:>11.3f}{r['p50_m']:>10.3f}")
        print()
        for (author, cls), t in sorted(totals.items()):
            print(f"    TOTAL  {author:<26}{cls:<18}"
                  f"{t['n_moved']:>9}{t['max_m']:>11.3f}")
        # The class DEFINITIONS, not a finding about them: whether a move
        # in the ``untouched`` class is a second author is the law layer's
        # call (docs/specs/cycle4-projection-ingestion-spec.md §req 2),
        # and this tool's own docstring records that the ring-index join
        # behind the classes is exact only while the ring is unchanged.
        print(f"\n    class 'untouched'      = the overwritten value was "
              f"within {args.author_tol:g} m of this shape's last "
              f"{probe.solve_site!r} write")
        print("    class 'moved_post_solve' = it was further than that")
        print(f"    class 'new_geometry'   = ring length differs from the "
              f"solve's, or the solve wrote None at that index")
        print(f"\n  === worst {len(probe.author_worst)} displaced vertices "
              f"(|d| > 0.05 m; IN-MEMORY write stream)")
        for (d, a, c, r, ref, before, after, x, y) in probe.author_worst[:20]:
            print(f"    {d:9.3f} m  {c:<16}{r:<20}{ref:<16}"
                  f"{before} -> {after}   at ({x},{y})")
    if args.vertex_dump:
        vinfo = probe.write_vertex_dump(args.vertex_dump)
        report["vertex_dump"] = vinfo
        print(f"\n  [harness] per-vertex history dump -> {vinfo['path']} "
              f"({vinfo['vertices']} vertices, {vinfo['sites']} distinct "
              f"write sites)")
    if args.author_dump:
        info = probe.write_move_dump(layout, args.author_dump)
        report["author_dump"] = info
        print(f"\n  [harness] per-vertex move dump -> {info['path']} "
              f"({info['moves']} move row(s), {info['shapes']} shape row(s))")
    if at:
        history = probe.node_history()
        report["node_history"] = history
        report["node_history_frame"] = {
            "frame": "IN-MEMORY write stream",
            "coordinate_space": "layout METRE frame (shape exterior ring)",
            "match_tol_m": args.tol,
            "value_dp": 3,
            "compressed": "consecutive equal values per (role, ref) dropped"}
        print(f"\n  === NODE HISTORY  [frame: IN-MEMORY write stream  |  "
              f"coordinates: layout METRE frame  |  matched within "
              f"{args.tol:g} m  |  values rounded to 3 dp  |  consecutive "
              f"equal values per (role, ref) dropped]")
        for point, changes in history.items():
            print(f"\n  === ({point})  {len(changes)} change(s)")
            for c in changes:
                print(f"    {c['step']:7d} {c['role']:<18}{c['ref']:<20}"
                      f"{c['value']}   {c['site']}")
    if fprobe is not None:
        hist = fprobe.footprint_history(layout)
        report["footprint_history"] = hist
        report["footprint_history_frame"] = {
            "frame": "IN-MEMORY write stream",
            "coordinate_space": "layout METRE frame",
            "predicate": "shapely polygon.covers(Point)",
            "rows": "transitions only; a shape's first write is a 'birth' "
                    "row (dataclasses.replace mints a new instance for an "
                    "unchanged ring, so birth != a pass that grew anything)",
            "final": "shapes covering the point in the finished layout, "
                     "indexed by layout.shapes index == the emitted "
                     "shapeID tag"}
        print(f"\n  === FOOTPRINT HISTORY  [frame: IN-MEMORY write stream  "
              f"|  coordinates: layout METRE frame  |  predicate: "
              f"polygon.covers(point)  |  transitions only]")
        for point, rec in hist.items():
            print(f"\n  === ({point})  {len(rec['changes'])} transition(s)")
            for c in rec["changes"]:
                print(f"    {c['step']:7d} inst{c['instance']:<6} "
                      f"{c['event']:<7}{'IN ' if c['covered'] else 'OUT'} "
                      f"{c['role']:<22}{str(c['area_m2']):>10}  {c['site']}")
            print(f"    FINAL: {rec['final'] or '(covered by nothing)'}")
    path = out / f"{args.icao}_who_wrote.json"
    path.write_text(json.dumps(report, indent=1, default=str))
    print(f"\n  [harness] authorship report -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
