"""WHAT THIS PATCH'S VERTICES SIT ON, AND WHO OWES EACH CERTIFICATE ROW.

    venv/bin/python tools/harness/who_wrote.py --emitted-patch PATCH.osm
        --dem M [--who-json ICAO_who_wrote.json]
    venv/bin/python tools/harness/who_wrote.py --cert-attrib CERT.json
        --vertex-json V.jsonl [--cert-base LABEL=PATH ...]
        [--moves-json MOVES.jsonl] [--attrib-md OUT.md] [--attrib-json OUT.json]

Run it from ``Ortho4XP/``.

THE BUILD-AND-INTERCEPT MODE IS GONE (2026-09-17, lane ``v1retire`` round 2; landed by lane ``v1cut``, 2026-10-04).
Per-vertex authorship here WAS property interception on v1's
``layout.BuiltShape`` during a ``build_airport.build_patch`` build: the four
reports (the DEM-authorship census, the node history, the displacement census,
the footprint history) all read a sequence of per-shape writes.  v2 solves the
whole airport as ONE linear program — there is no such sequence — so the
machinery and its CLI options are DELETED rather than left inert, and ``main``
REFUSES BY NAME with the pointer.  For v2, authorship is read out of the solve:
``tools/v2_solve_replay.py --why-hard / --why-hard-stage N / --probe-site
LAT,LON``.

TWO REPORTS SURVIVE, both ENGINE-NEUTRAL FILE READS (no build, no ICAO):

* **THE EMITTED FRAME** (``--emitted-patch PATCH --dem M``, repeatable).  How
  many vertices sit exactly on the constant DEM **in the shipped patch**, by
  way role, and split into the STRANDED subset — on-DEM vertices sharing a way
  with a law-valued one, the class a within-shape law row is minted in — versus
  whole ways lying flat on the DEM, which mint none.  ``--who-json`` joins an
  earlier authorship report onto it by ``shapeID`` and says so when the join
  matches nothing.  The in-memory and emitted frames differ by the decimators
  (HECA read 16,019 in memory and shipped 938), which is why both halves came
  out of one tool.

* **THE R1.1 ATTRIBUTION TABLE** (``--cert-attrib CERT.json --vertex-json
  V.jsonl``).  Every residual row of an airside-certificate dump
  (``O4_AIRSIDE_CERT_DUMP``) joined to the vertex history at each endpoint and
  grouped by (family, endpoint role pair, the LAST PRE-PROJECTION WRITER of
  each endpoint, whether the projection moved an endpoint), with count / p50 /
  max excess, membership in earlier readings (``--cert-base``) and a MECHANICAL
  predicted disposition stated so an arm can check it — never a verdict.
  ``--moves-json`` adds the untouched-class moves by last pre-projection
  writer.  Twin: ``tests/test_who_wrote_attrib.py``.

Everything either report needs is a JSON/OSM file some earlier run wrote, so
this tool builds nothing and touches no corpus.
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Self-contained and ahead of every
# other import because a tool's own ``--help`` carries the house spelling
# (``Δ``, ``ε``, ``≥``, ``→``) and a Windows console RAISES on those
# rather than mangling them.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__)))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

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
        _PIPE_RE = re.compile(r"pipeline\.py:(\d+):(\w+)")
    best = None
    for m in _PIPE_RE.finditer(site or ""):
        line, fn = int(m.group(1)), m.group(2)
        if fn == "solve_and_finalize":
            return line
        # A nested helper (``_post_projection_conformance_passes``) is
        # defined beside its call site, so the OUTERMOST pipeline frame
        # in a chain the depth cut short still orders the write.
        best = line if best is None else max(best, line)
    return best


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


# ``AuthorshipProbe`` and ``FootprintProbe`` — THE BUILD-AND-INTERCEPT
# MACHINERY — were DELETED on 2026-09-17 (lane v1retire round 2,
# session ruling: DELETE-class code inside a keep tool).  They wrapped
# ``auto_patch.layout.BuiltShape``'s ``node_altitudes`` / ``polygon``
# in recording properties while ``build_airport.build_patch`` ran the
# v1 pipeline; the class, the builder and the pipeline are all gone
# with the engine.  v2 solves the whole airport as ONE linear program,
# so there is no per-shape write sequence to record — the equivalent
# question is answered from the solve itself
# (``tools/v2_solve_replay.py --why-hard / --why-hard-stage /
# --probe-site``).  THE READING MODES BELOW ARE ENGINE-NEUTRAL AND
# STAY: ``--emitted-patch`` (with ``--dem`` / ``--who-json``) and
# ``--cert-attrib`` (the R1.1 attribution table).


# ``AuthorshipProbe`` and ``FootprintProbe`` — THE BUILD-AND-INTERCEPT
# MACHINERY — were DELETED on 2026-09-17 (lane v1retire round 2,
# session ruling: DELETE-class code inside a keep tool).  They wrapped
# ``auto_patch.layout.BuiltShape``'s ``node_altitudes`` / ``polygon``
# in recording properties while ``build_airport.build_patch`` ran the
# v1 pipeline; the class, the builder and the pipeline are all gone
# with the engine.  v2 solves the whole airport as ONE linear program,
# so there is no per-shape write sequence to record — the equivalent
# question is answered from the solve itself
# (``tools/v2_solve_replay.py --why-hard / --why-hard-stage /
# --probe-site``).  THE READING MODES BELOW ARE ENGINE-NEUTRAL AND
# STAY: ``--emitted-patch`` (with ``--dem`` / ``--who-json``) and
# ``--cert-attrib`` (the R1.1 attribution table).


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
    # ── THE BUILD-AND-INTERCEPT MODE HAS NO SUBJECT (lane v1retire,
    # 2026-09-17; ruling (f) of the stage-B brief, the 13az pattern) ─────
    # Per-vertex authorship here IS property interception on v1's
    # ``layout.BuiltShape`` (``node_altitudes`` / ``polygon``), driven by a
    # ``build_airport.build_patch`` build.  Both are gone with the v1 engine
    # (RULINGS 2026-09-13au/13aw; ``build_patch`` deleted in this round):
    # v2 computes its surface as one LP over the whole airport, so there is
    # no sequence of per-shape writes to record and no class to wrap.
    #
    # The READING modes survive and are what this tool still does:
    # ``--emitted-patch`` (with ``--dem``, and ``--who-json`` to join an
    # authorship report) answers "which vertices of this patch sit exactly
    # on the DEM" off the patch bytes, engine-neutrally, and returns above.
    # For v2 the equivalent of "which pass authored this value" is read from
    # the solve itself: ``tools/v2_solve_replay.py --why-hard /
    # --why-hard-stage / --probe-site`` (the hard set and its provenance),
    # (``tools/solve_cut.py`` went with the v1 solver in this same round).
    raise SystemExit(
        "REFUSED: who_wrote's BUILD mode is a v1 instrument and v1 is "
        "retired (RULINGS 2026-09-13au/13aw; lane v1retire 2026-09-17).\n"
        "  It recorded writes to auto_patch.layout.BuiltShape (a DELETE "
        "module) during a build_airport.build_patch build (DELETED).  v2 "
        "solves the whole airport as one LP: there is no per-shape write "
        "sequence to intercept.\n"
        "  STILL AVAILABLE HERE: --emitted-patch PATCH --dem M "
        "[--who-json REPORT] reads a patch an earlier build wrote and is "
        "engine-neutral.\n"
        "  For v2 authorship use tools/v2_solve_replay.py --why-hard / "
        "--why-hard-stage N / --probe-site LAT,LON.")


if __name__ == "__main__":
    sys.exit(main())
