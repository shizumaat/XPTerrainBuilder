"""THE CONSTANT-DEM ORACLE RUNNER — the pair build with no terrain confound.

    venv/bin/python tools/harness/oracle.py ICAO [--worlds -500 10000]
        [--out DIR] [--allow-degraded-dem]

Run it from ``Ortho4XP/``.  Wraps ``auto_patch.constant_dem`` and drives the
assertions the owner's oracle law makes — 1-3 from RULINGS 2026-08-05 ("DEM
is a SEED"), 4 from RULINGS 2026-08-06 ("Instrument truth is law", binding
point 4):

1. **COMPLIANCE** — zero ADJUDICATED law-true rows in BOTH worlds.  Necessary,
   weakest.  A surface can be lawful and still be authored by something other
   than the law.  ADJUDICATED excludes the VERSION-DEFERRED classes per owner
   ruling RULINGS ``d48bc0a`` ("flat-world zero is … zero adjudicated rows
   EXCLUDING the version-deferred classes, which appear in every report under
   their own heading") — those rows are still measured, still printed, and
   carried in the verdict under ``version_deferred_by_world``.  The register
   is ``check_grade.VERSION_DEFERRED_FAMILIES``.
2. **EXTREME-SEATING SATURATION** — the plateau world (−500 m, RULINGS
   2026-08-06 "The low extreme is −500 m") seats every free value at its band
   FLOOR, the canyon world (10 000 m) at its CEILING.  A node that moves
   between two builds on the SAME side of every band is held by something
   that is not the seed: a HIDDEN AUTHORITY.  This is the defect class plain
   compliance cannot see.
3. **THE BAND-WIDTH FIELD** — ``canyon(node) - plateau(node)`` IS the width
   of the band the law grants at that node, written out as the artifact
   (``<ICAO>_band_width.json``).  Width 0 ⇒ PINNED; a NEGATIVE width is a
   defect on its face.
4. **BAND-WIDTH AGREEMENT** — the width above, compared per node against the
   ANALYTIC band (``reach_band_unified``: ``ceiling − floor``).  Two
   independent suppliers of one quantity, agreement reported within a stated
   materiality (RULINGS 2026-08-06 binding point 4).  A REPORT, never a gate:
   each disagreement is an ADDRESS (author + coordinate + both widths), and
   the nodes with no analytic band or a half-open one are counted separately
   rather than swept into it.

WHY A RUNNER AND NOT JUST THE PYTEST.  ``tests/test_constant_dem_oracle.py``
builds each world per test; this builds each world ONCE and runs every
assertion off the same layouts (single-pass principle).  The pytest stays
the gate; this is the instrument you drive an investigation with, and it
emits the artifacts a report is written from.

Consolidated from ``scratchpad/testphase/oracle.py``, with the harness's
census (every law family, sidecar-true) replacing that script's private
``run_checks`` call.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "harness"))

import build_airport as HB            # noqa: E402  (the one build entry)
import census as HC                   # noqa: E402  (the one census)

#: The owner ruling that fixes the LOW synthetic world.  Quoted into every
#: verdict that depends on the worlds being the ruled ones, so the claim
#: carries its own frame instead of assuming it.
LOW_WORLD_RULING = ('RULINGS 2026-08-06, "The low extreme is -500 m" '
                    "(supersedes the DEM=0 letter of the 2026-08-05 "
                    "constant-DEM invariant and retires the DEM=1 m interim; "
                    "the 10 000 m high world stands)")


#: ``_analytic_band``'s status codes.  Each names ONE path out of the
#: reader, and ``defect`` says whether that path is a legitimate answer
#: about the layout or a failure of the reader itself.  The old code
#: returned a bare ``None`` for all of them and printed one parenthetical
#: naming three causes at once ("no anchors, no pavement, or the grid
#: refused") — a catch-all bucket labelled with a cause, and one that did
#: not even list the fourth member, a raised exception.
BAND_STATUS = {
    "ok": (False, "the analytic reach band was built"),
    "no_nodes": (False,
                 "the layout has no pavement-role nodes, so there is no "
                 "node list to build a graph over"),
    "no_band": (False,
                "reach_band_unified returned no band factory at all"),
    "band_reader_raised": (True,
                           "the band reader RAISED — this is a defect in "
                           "the instrument or its inputs, not an answer "
                           "about the layout"),
    "zero_coverage": (False,
                      "a band factory was built but answered None at "
                      "every node, so no node was evaluated"),
}


def _analytic_band(layout):
    """The ANALYTIC reach band for ``layout``, as ``(band_of, status)``.

    ``building_feasibility.reach_band_unified`` — the cap-Dijkstra from the
    runway anchors over the unified grade graph.  This is the band the
    SOLVER bound nodes with and the band ``grade_graph_validate.
    route_band_violations`` confirms against, so assertion 2 reads one law
    rather than minting a second opinion about it.

    Why it is the right supplier and the pair is not: the band-width field
    is the two worlds differenced, so testing "is the node at the pair's
    edge" is circular — it is true by construction.  This band is derived
    from anchors, caps and geometry ALONE, none of which the DEM touches,
    so it is identical in both worlds and genuinely independent of the seed.

    Returns ``(band_of, status)``.  ``band_of((x, y)) -> (floor, ceiling) |
    None`` is the adapted supplier, or ``None`` when no band could be
    produced; ``status`` is ``{"code", "defect", "why", "detail"}`` naming
    WHICH of the reader's several exits was taken.  ``band_of is None`` is
    reported as NOT EVALUATED — never as a pass, which is the failure mode
    this whole item is repairing.

    THE REASON IS CARRIED OUT, NOT THROWN AWAY (cycle-7.5 sweep, Task 3a).
    This function has four distinct exits — an empty node list, a band
    factory that was never built, a raised exception, and success — and it
    used to collapse all of them into a bare ``None``.  The caller then
    printed ONE sentence naming three causes ("no anchors, no pavement, or
    the grid refused") for whichever had actually happened, and that
    sentence did not even include the fourth.  A catch-all bucket labelled
    with a cause is a claim the code does not verify.

    A RAISE IS NOT AN ANSWER (Task 3b).  The bare ``except Exception``
    below used to print and return the same ``None`` as a genuinely
    band-less layout, so a CODE failure in the instrument was
    indistinguishable from a legitimate result — the identical shape to the
    key-shape bug that made assertion 2 read as a clean pass for a whole
    campaign (``constant_dem.saturation_report``'s own docstring records
    it).  The exception is still caught, because an instrument that dies
    mid-run reports nothing at all; but it is caught into
    ``code="band_reader_raised"``, ``defect=True``, with the traceback in
    ``detail``, and the caller is required to surface it.

    READONLY NODE LIST.  ``_build_node_list``'s registry interning is
    ``get_or_add`` by default, and its own docstring records a probe-only
    rebuild moving SPJC's emitted surface (+1 node, 86 altitudes, |dz| <=
    0.21 m) — ``readonly=True`` "exists for MEASUREMENT INSTRUMENTS", which
    is what this is.  (The oracle reads the layout only after
    ``build_patch`` has already written the patch and its sidecar, so the
    emitted bytes were never at risk here; taking the mutating path from an
    instrument was still the wrong contract.)  The two node-space indices
    that function publishes on the layout are snapshotted and restored, as
    its docstring instructs a probe caller to do.

    THE ADAPTER IS DELIBERATE.  The engine's contract is ``band(x, y)``
    (two positional arguments); the reader's is ``band_of(xy)`` (one point,
    because ``_node_values`` hands it a coordinate).  Adapting HERE, at the
    single place the two meet, is the whole of the impedance mismatch — the
    alternative, teaching the reader to try both call shapes, is a
    dual-contract that would hide the next supplier's signature error the
    same way the key-shape bug hid this assertion for the whole campaign.
    """
    def _status(code: str, detail=None) -> dict:
        defect, why = BAND_STATUS[code]
        return {"code": code, "defect": defect, "why": why, "detail": detail}

    _PROBE_ATTRS = ("_terrain_host_yield_first_index",
                    "_adjacent_ground_first_zone_index")
    saved = {a: getattr(layout, a, None) for a in _PROBE_ATTRS}
    try:
        from auto_patch import grade_graph as GG
        from auto_patch.elevation_per_surface.solver_primitives import (
            _build_node_list)
        from auto_patch.elevation_per_surface.building_feasibility import (
            reach_band_unified)
        nodes, b2i = _build_node_list(layout, readonly=True)
        if not nodes:
            return None, _status("no_nodes")
        band = reach_band_unified(layout, GG.build_unified_graph(layout, b2i))
        if band is None:
            return None, _status("no_band")
        return (lambda xy: band(xy[0], xy[1])), _status("ok")
    except Exception as exc:
        import traceback
        detail = traceback.format_exc().strip().splitlines()[-6:]
        print(f"  [harness] DEFECT: the analytic band reader RAISED: "
              f"{exc!r}")
        return None, _status("band_reader_raised",
                             {"exception": repr(exc), "traceback": detail})
    finally:
        for a, v in saved.items():
            if v is None:
                if hasattr(layout, a):
                    try:
                        delattr(layout, a)
                    except Exception:                     # pragma: no cover
                        pass
            else:
                setattr(layout, a, v)


def _analytic_band_world_diff(field, band_lo, band_hi,
                              materiality_m: float, top: int = 10) -> dict:
    """Is the ANALYTIC band really the same in both worlds?

    ``_analytic_band``'s docstring justifies using ``reach_band_unified`` as
    assertion 2's independent supplier with: *"this band is derived from
    anchors, caps and geometry ALONE, none of which the DEM touches, so it
    is identical in both worlds and genuinely independent of the seed."*
    That is the load-bearing premise of assertions 2 and 4 and nothing
    checked it.  This does, over the same node set the band-width field
    covers: per node, the floor, the ceiling and the width from each
    world's band.

    Counts only — plus the worst ``top`` addresses.  A non-zero
    ``width_disagreements`` (or a coverage mismatch) FALSIFIES the premise;
    it does not say what the DEM is doing to the band, and this reports no
    guess about that.
    """
    n = both = 0
    coverage_mismatch = []
    width_rows = []
    for (author, x, y) in field:
        n += 1
        a, b = band_lo((x, y)), band_hi((x, y))
        if (a is None) != (b is None):
            coverage_mismatch.append({"author": author, "x": x, "y": y,
                                      "plateau_band": a, "canyon_band": b})
            continue
        if a is None:
            continue
        if any(v is None for v in (*a, *b)):
            continue
        both += 1
        wa, wb = float(a[1]) - float(a[0]), float(b[1]) - float(b[0])
        if abs(wa - wb) > materiality_m:
            width_rows.append({"author": author, "x": x, "y": y,
                               "plateau_width_m": round(wa, 4),
                               "canyon_width_m": round(wb, 4),
                               "delta_m": round(wb - wa, 4)})
    width_rows.sort(key=lambda r: -abs(r["delta_m"]))
    return {
        "premise": "_analytic_band's docstring claims reach_band_unified is "
                   "identical in both worlds because the DEM touches none of "
                   "its inputs; these numbers test that claim",
        "materiality_m": float(materiality_m),
        "nodes": n,
        "compared": both,
        "coverage_mismatches": len(coverage_mismatch),
        "width_disagreements": len(width_rows),
        "max_abs_delta_m": (round(abs(width_rows[0]["delta_m"]), 4)
                            if width_rows else 0.0),
        "worst": width_rows[:top],
        "worst_coverage_mismatches": coverage_mismatch[:top],
    }


def _frame_stamp(root, args, worlds) -> dict:
    """THE ORACLE'S FRAME — every guard ``build_airport.main`` computes,
    REPORTED (RULINGS 2026-08-06 binding point 3).

    The oracle calls ``HB.build_patch`` directly, so before this it wrote no
    ``env.json`` and no ``frame.json`` at all: an oracle number could not be
    joined to a git HEAD, a code-tree hash, an ``O4_*`` env, a cfg frame or
    a data corpus.  Two oracle runs from two trees were indistinguishable in
    their own artifacts.

    REPORTED, NOT ENFORCED, and that split is deliberate.  Each ``require_*``
    in ``build_airport`` RAISES; wiring them here would change WHETHER the
    oracle runs, which is not this sweep's business.  So this calls the PURE
    half of each pair (``cfg_frame_diff`` under ``require_cfg_frame``,
    ``data_mounts`` under ``require_shared_data``, ``dem_cache_state`` under
    ``require_dem_frame``, ``missing_shared_artifacts`` under
    ``require_no_implicit_refresh``) and records what it found, plus a
    ``frame_warnings`` list and an explicit ``guards_reported_not_enforced``
    note so no reader mistakes a recorded divergence for a cleared one.

    The DEM-frame guards are the ones an oracle run genuinely does not need
    — every world here is a CONSTANT substituted at ``tile_dem``, so real
    inset warmth cannot reach the numbers.  They are recorded anyway,
    because "which corpus was mounted" is a question asked of numbers
    already in a report.
    """
    from auto_patch.constant_dem import (                 # noqa: E402
        CANYON_ELEVATION_M, PLATEAU_ELEVATION_M)
    cfg_diff = HB.cfg_frame_diff(root)
    env = HB.env_snapshot(root, cfg_diff)
    mounts = HB.data_mounts(root)
    private = [n for n, m in mounts.items() if m["present"] and not m["shared"]]
    shared_n = sum(1 for m in mounts.values() if m["shared"])

    tile = HB.resolve_tile_for(args.icao, root)
    dem_state = missing = None
    if tile:
        dem_state = HB.dem_cache_state(root, tile[0], tile[1])
        missing = [{"scope": s, "artifact": a, "why": w}
                   for s, a, w in HB.missing_shared_artifacts(root, *tile)]

    warnings = []
    if cfg_diff:
        warnings.append(
            f"{len(cfg_diff)} DEM-frame cfg key(s) diverge from the owner's "
            f"production config: {sorted(cfg_diff)} (recorded; the oracle "
            f"substitutes the DEM, so this cannot reach an oracle number)")
    if private:
        warnings.append(
            f"PRIVATE data corpus: {private} do not resolve under "
            f"{HB.DATA_REPO} — these numbers are not comparable with another "
            f"lane's (owner ruling e9daef5)")
    if missing:
        warnings.append(
            f"{len(missing)} shared artifact(s) absent: "
            f"{[m['artifact'] for m in missing]} — a REAL-DEM build would "
            f"fetch them as a side effect; scope(s) "
            f"{sorted({m['scope'] for m in missing})}")
    if tile is None:
        warnings.append(
            f"could not resolve {args.icao}'s anchor tile from apt.dat, so "
            f"the DEM cache state and the missing-artifact list are UNKNOWN "
            f"for this run")

    return {
        "icao": args.icao,
        "worlds_m": list(worlds),
        "ruled_worlds_m": {"plateau": PLATEAU_ELEVATION_M,
                           "canyon": CANYON_ELEVATION_M,
                           "ruling": LOW_WORLD_RULING},
        "env": env,
        "dem_frame_effective": HB.frame_surface_keys(root),
        "dem_frame_cfg_divergence": {k: {"ours": o, "production": t}
                                     for k, (o, t) in cfg_diff.items()},
        "data_repo": str(HB.DATA_REPO),
        "data_mounts": mounts,
        "data_corpus": {"shared": shared_n, "total": len(mounts),
                        "private": private},
        "anchor_tile": list(tile) if tile else None,
        "dem_cache_state": dem_state,
        "missing_shared_artifacts": missing,
        "allow_degraded_dem": bool(args.allow_degraded_dem),
        "allow_degraded_dem_effect": (
            "recorded only.  Every build in this run substitutes tile_dem "
            f"with a ConstantDEM at one of {list(worlds)} m, so no real-DEM "
            "cache state can reach a reported number; the flag authorises "
            "nothing and in particular does NOT authorise a shared-repo "
            "write."),
        "guards_reported_not_enforced": [
            "require_cfg_frame", "require_dem_frame", "require_shared_data",
            "require_no_implicit_refresh",
        ],
        "guards_armed": [
            "build_airport.build_patch's SharedRepoWriteGuard (armed inside "
            "build_patch for direct callers such as this one — an "
            "unauthorised shared-repo write is REFUSED at the call)",
            "build_airport.build_patch's axes-sidecar refusal (a patch with "
            "no sidecar raises rather than degrading to the context-free "
            "census frame)",
            "build_airport.require_build_cwd",
        ],
        "frame_warnings": warnings,
        "join": ("every number in <ICAO>_oracle.json was produced by the "
                 "code at env.code_tree_hash / env.git_head (dirty="
                 f"{env.get('git_dirty')}), from builds whose only DEM is a "
                 f"ConstantDEM at {list(worlds)} m, on the data corpus in "
                 "data_mounts; band widths join to saturation rows by "
                 "author (role/ref) + millimetre metre-frame coordinate"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("icao")
    ap.add_argument("--worlds", nargs="+", type=float, default=None,
                    help="constant elevations to build (default: the "
                         "plateau/canyon pair from auto_patch.constant_dem)")
    ap.add_argument("--out", type=Path, default=Path("/tmp/harness/oracle"))
    ap.add_argument("--allow-degraded-dem", action="store_true",
                    help="accepted and RECORDED into <ICAO>_oracle.frame.json "
                         "('allow_degraded_dem'); it changes nothing about "
                         "this run, because every oracle build SUBSTITUTES "
                         "the DEM with a constant (the substituted values are "
                         "recorded beside the flag), so real-DEM cache warmth "
                         "cannot confound it.  It does NOT authorise a write "
                         "to the shared data repo.")
    args = ap.parse_args(argv)

    root = HB.require_build_cwd(Path.cwd())
    for p in (root / "src", root, root / "tests"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from auto_patch.constant_dem import (                 # noqa: E402
        BAND_AGREEMENT_MATERIALITY_M, CANYON_ELEVATION_M, PLATEAU_ELEVATION_M,
        band_agreement_report, band_width_field, band_width_summary,
        saturation_report, saturation_summary, write_band_width_artifact)

    worlds = args.worlds or [PLATEAU_ELEVATION_M, CANYON_ELEVATION_M]
    out = Path(args.out)
    prog = HB.Progress(out / f"{args.icao}_oracle.progress")
    prog.note(f"START oracle {args.icao} worlds={worlds}")

    # ── FRAME STAMP (RULINGS 2026-08-06 binding point 3: "every reported
    # number carries its frame").  The oracle calls ``HB.build_patch``
    # directly, so it skipped every snapshot ``build_airport.main`` writes:
    # an oracle number could not be joined to a tree, a HEAD, an O4_* env or
    # a data corpus at all.  These are REPORTED, not ENFORCED — deliberately.
    # ``require_cfg_frame`` / ``require_dem_frame`` / ``require_shared_data``
    # / ``require_no_implicit_refresh`` all REFUSE, and wiring a refusal in
    # would change whether the oracle runs; that half is left to the build
    # CLI and named in the frame under ``guards_reported_not_enforced``.  The
    # one guard that IS armed was already armed before this change:
    # ``HB.build_patch`` constructs its own ``SharedRepoWriteGuard`` (see its
    # docstring — it arms there precisely because the oracle is a direct
    # caller), so an unauthorised shared-repo write is refused at the call.
    frame = _frame_stamp(root, args, worlds)
    (out / f"{args.icao}_oracle.env.json").write_text(
        json.dumps(frame["env"], indent=1, default=str))
    (out / f"{args.icao}_oracle.frame.json").write_text(
        json.dumps(frame, indent=1, default=str))
    env = frame["env"]
    prog.note(f"frame: HEAD={str(env.get('git_head'))[:9]} "
              f"dirty={env.get('git_dirty')} "
              f"tree={str(env.get('code_tree_hash'))[:12]} "
              f"O4_*={sorted(env.get('o4_env') or {}) or 'NONE'} "
              f"corpus={frame['data_corpus']['shared']}/"
              f"{frame['data_corpus']['total']} shared "
              f"worlds={worlds}")
    for line in frame["frame_warnings"]:
        prog.note(f"FRAME WARNING: {line}")

    cg = HC.load_check_grade()
    layouts, censuses = {}, {}
    for w in worlds:
        tag = f"{args.icao}_dem{w:g}"
        t0 = time.time()
        # The build entry, not a private build: the same sidecar refusal
        # and the same armed shared-repo write guard.  (The env/frame
        # snapshots live in ``build_airport.main``, which this path does not
        # go through — ``_frame_stamp`` above writes them for this run.)
        result = HB.build_patch(args.icao, root, out, tag, prog, const_dem=w)
        osm = Path(result["patch"])
        rep = HC.census_one(osm, cg, top=10)
        censuses[w] = rep
        prog.note(f"  world {w:g}: LAW-TRUE {rep['lawtrue']['total']} rows "
                  f"(airside {rep['lawtrue']['airside']}, mixed "
                  f"{rep['lawtrue']['mixed']}) in {time.time() - t0:.1f}s")
        # Re-open the layout's node values from the build we just did.
        layouts[w] = result
        (out / f"{tag}.census.json").write_text(json.dumps(rep, indent=1))

    # ── ASSERTION 1: COMPLIANCE ──────────────────────────────────────
    # ADJUDICATED, not instrument-zero (owner rulings: 2026-08-02 "the goal
    # is LAW COMPLIANCE, not instrument-zero", and RULINGS d48bc0a, which
    # states flat-world zero IS "zero adjudicated rows EXCLUDING the
    # version-deferred classes, which appear in every report under their
    # own heading").  This verdict used to read ``lawtrue.total``, i.e. it
    # tested instrument-zero and could never pass while a deferred class
    # existed; the deferred rows are still REPORTED here, under their own
    # key, and the census carries the same split from the same register
    # (``check_grade.VERSION_DEFERRED_FAMILIES`` /
    # ``check_grade.adjudication`` — one implementation, no hand
    # subtraction).
    verdicts = {}
    adjs = {w: censuses[w]["adjudication"] for w in worlds}
    non_compliant = {w: adjs[w]["adjudicated_total"] for w in worlds
                     if adjs[w]["adjudicated_total"]}
    verdicts["compliance"] = {
        "pass": not non_compliant,
        "ruling": cg.DEFERRED_ADJUDICATION_RULING,
        # FRAME (binding point 3).  The note below is world-invariant only
        # because these worlds carry NO terrain signal; that is a property
        # of the constants, so the constants travel with the claim.
        "worlds_m": list(worlds),
        "worlds_are_the_ruled_pair": (
            sorted(worlds) == sorted([PLATEAU_ELEVATION_M,
                                      CANYON_ELEVATION_M])),
        "ruled_worlds_m": {"plateau": PLATEAU_ELEVATION_M,
                           "canyon": CANYON_ELEVATION_M},
        "worlds_ruling": LOW_WORLD_RULING,
        "adjudicated_by_world": {f"{w:g}": adjs[w]["adjudicated_total"]
                                 for w in worlds},
        "rows_by_world": {f"{w:g}": censuses[w]["lawtrue"]["total"]
                          for w in worlds},
        "version_deferred_by_world": {
            f"{w:g}": {"total": adjs[w]["deferred_total"],
                       "families": {k: d["n"] for k, d
                                    in adjs[w]["deferred_families"].items()}}
            for w in worlds},
        "version_deferred_why": {
            k: d["why"] for k, d
            in adjs[worlds[0]]["deferred_families"].items()},
        "note": ("zero ADJUDICATED law-true rows in every constant world "
                 "(version-deferred classes excluded per RULINGS "
                 f"{cg.DEFERRED_ADJUDICATION_RULING} and reported under "
                 "'version_deferred_by_world')" if not non_compliant else
                 f"a constant-DEM build (worlds {[f'{w:g}' for w in worlds]} "
                 f"m; the ruled pair is plateau {PLATEAU_ELEVATION_M:g} m / "
                 f"canyon {CANYON_ELEVATION_M:g} m, {LOW_WORLD_RULING}) "
                 "emitted ADJUDICATED rows: with no terrain signal these "
                 "are law, solver or instrument defects — there is nothing "
                 "to blame them on.  The version-deferred classes are "
                 "excluded from this verdict per RULINGS "
                 f"{cg.DEFERRED_ADJUDICATION_RULING} and listed separately"),
    }
    for w in worlds:
        a = adjs[w]
        prog.note(f"  world {w:g}: ADJUDICATED {a['adjudicated_total']} "
                  f"(airside {a['adjudicated_by_side']['airside']}) + "
                  f"VERSION-DEFERRED {a['deferred_total']} "
                  f"[RULINGS {a['ruling']}] = law-true "
                  f"{censuses[w]['lawtrue']['total']}")
        fams = [f for f in censuses[w]["families"] if f["n"]]
        if fams:
            prog.note(f"  world {w:g} families: "
                      + ", ".join(f"{f['family']}={f['n']}" for f in fams))

    # ── ASSERTIONS 2 and 3 read the LAYOUTS the builds just produced,
    # through ``constant_dem.band_width_field`` — the module's OWN reader,
    # the same one the shipped oracle test uses.  Re-parsing the emitted
    # patches here would be a SECOND reader of the same values and a
    # second chance to be wrong.
    lo, hi = min(worlds), max(worlds)
    if lo != hi:
        field = band_width_field(layouts[lo]["_layout"],
                                 layouts[hi]["_layout"])
        keys = field
        summary = band_width_summary(field)
        write_band_width_artifact(
            field, out / f"{args.icao}_band_width.json",
            extra={"icao": args.icao, "plateau_m": lo, "canyon_m": hi,
                   "join": "author (role/ref) + millimetre metre-frame "
                           "coordinate — same author on both sides, so a "
                           "shared coordinate yields one row per surface"})
        verdicts["band_width"] = {
            "pass": summary.get("negative", 0) == 0,
            "summary": summary,
            "artifact": str(out / f"{args.icao}_band_width.json"),
            "note": "a NEGATIVE band width is a defect on its face "
                    "(the ceiling world seated BELOW the floor world)",
        }
        pinned = sum(1 for v in field.values() if abs(v) <= 1e-6)
        prog.note(f"  band width: {json.dumps(summary)}  "
                  f"pinned={pinned}/{len(keys)}")

        # ── ASSERTION 2: EXTREME-SEATING SATURATION ──────────────────
        # NOW ACTUALLY EVALUATED (fix cycle 2 item 3).  This block used to
        # report pinned/free COUNTS off the band-width field and call that
        # saturation.  It is not: the band-width field IS the pair, so
        # "seated at the pair's own edge" is true by construction and says
        # nothing.  The assertion needs an INDEPENDENT band, and the engine
        # already publishes one — ``reach_band_unified``, the cap-Dijkstra
        # from the runway anchors, whose contract is coordinate-keyed
        # (``band(x, y) -> (floor, ceiling) | None``) and joins the reader
        # without any index or proximity hazard.  It is the SAME band the
        # solver bound the nodes with and the validator confirms against,
        # so a node off its edge is a disagreement inside one law, not
        # between two instruments.
        sat: dict = {"shared_nodes": len(keys), "pinned_nodes": pinned,
                     "free_nodes": len(keys) - pinned,
                     "pinned_pct": round(100.0 * pinned / max(1, len(keys)),
                                         1)}
        bands: dict = {}
        for world_name, w in (("plateau", lo), ("canyon", hi)):
            layout = layouts[w]["_layout"]
            band, status = _analytic_band(layout)
            bands[world_name] = band
            if band is None:
                # THE ACTUAL REASON, carried out of the reader (Task 3a) —
                # not a parenthetical listing three causes for whichever one
                # happened.  ``defect`` separates "this layout genuinely has
                # no band" from "the band reader RAISED" (Task 3b): the
                # second is a failure of the instrument, and an instrument
                # that cannot say which of the two it hit is the shape of
                # the bug that made this very assertion read as a clean
                # pass for a whole campaign.
                sat[world_name] = {
                    "evaluated": False,
                    "reason_code": status["code"],
                    "defect": status["defect"],
                    "why": status["why"],
                    "detail": status["detail"],
                    "verdict": "assertion 2 is NOT EVALUATED, which is not "
                               "a pass",
                }
                prog.note(f"  saturation {world_name}: NOT EVALUATED "
                          f"[{status['code']}"
                          + (" DEFECT" if status["defect"] else "")
                          + f"] {status['why']}")
                continue
            coverage: dict = {}
            rows = saturation_report(layout, world_name, band,
                                     coverage_out=coverage)
            rep = saturation_summary(rows)
            rep["coverage"] = coverage
            if coverage.get("with_band", 0) == 0:
                # A band factory EXISTS and answered None at every node.
                # ``reach_band_unified`` never returns None — when no field
                # can be built it returns ``lambda x, y: None`` — so this,
                # not ``band is None``, is the path a band-less airport
                # actually takes, and an empty unsaturated list here is the
                # SAME false pass as the key-shape bug one supplier further
                # out.  Denominator, then verdict.
                code = "zero_coverage"
                defect, why = BAND_STATUS[code]
                rep["evaluated"] = False
                rep["reason_code"] = code
                rep["defect"] = defect
                rep["why"] = (f"{why} (0 of {coverage.get('nodes', 0)} "
                              f"nodes had a band)")
                rep["verdict"] = ("assertion 2 is NOT EVALUATED, which is "
                                  "not a pass")
            else:
                rep["evaluated"] = True
                rep["reason_code"] = status["code"]
                rep["defect"] = status["defect"]
            sat[world_name] = rep
            (out / f"{args.icao}_{world_name}_saturation.json").write_text(
                json.dumps({"world": world_name, "coverage": coverage,
                            "rows": [r.as_dict() for r in rows]}, indent=1))
            top = ", ".join(f"{a['author']}={a['n']}"
                            f"(worst {a['worst_off_edge_m']:+.2f} m)"
                            for a in rep["by_author"][:5]) or "none"
            prog.note(f"  saturation {world_name}: "
                      + ("NOT EVALUATED [zero_coverage] " if not
                         rep["evaluated"] else "")
                      + f"{rep['unsaturated']} unsaturated node(s) across "
                      f"{rep['authors']} author(s) of "
                      f"{coverage.get('with_band', 0)}/"
                      f"{coverage.get('nodes', 0)} node(s) with a band "
                      f"— {top}")
        evaluated = [v for k, v in sat.items()
                     if k in ("plateau", "canyon") and isinstance(v, dict)]
        sat["defect"] = any(v.get("defect") for v in evaluated)
        sat["pass"] = bool(evaluated) and all(
            v.get("evaluated") and v.get("unsaturated", 1) == 0
            for v in evaluated)
        sat["note"] = ("every free node must sit at the band edge nearest "
                       "its seed; an unsaturated node is held by something "
                       "that is not the seed, and its AUTHOR is named in "
                       "<ICAO>_<world>_saturation.json.  'evaluated' false "
                       "means NOT EVALUATED, never a pass; 'defect' true "
                       "means the band READER failed, which is a defect in "
                       "this instrument rather than an answer about the "
                       "layout")
        verdicts["saturation"] = sat

        # ── ASSERTION 4: BAND-WIDTH AGREEMENT ────────────────────────
        # BINDING POINT 4 (RULINGS 2026-08-06): two independent instruments
        # per load-bearing quantity, agreement asserted within materiality.
        # The band width has exactly two suppliers — the MEASURED pair
        # difference above and the ANALYTIC ``reach_band_unified`` ceiling
        # minus floor — and ``constant_dem``'s module docstring has named
        # the comparison as the design since the module was written ("one
        # whose width disagrees with the analytic band is a law/solver
        # disagreement with an exact address") while nothing implemented
        # it.  Assertion 3 checked only ``negative == 0``.
        #
        # IT IS A REPORT, NOT A GATE, and its ``pass`` is therefore the
        # question the code can actually answer: was the comparison made at
        # all?  Whether a disagreement is the law's fault or the solver's is
        # an ADDRESS to go read, not something this code verifies.
        #
        # THE SUPPLIER IS THE PLATEAU WORLD'S BAND, stamped as such.  The
        # analytic band is claimed (in ``_analytic_band``'s docstring) to be
        # identical in both worlds because it is derived from anchors, caps
        # and geometry alone.  That claim was never checked, so the canyon
        # world's band is compared against it here and any difference is
        # reported as ``analytic_band_world_disagreement`` — a DEM-shaped
        # band would be the loudest possible violation of the oracle's own
        # premise.
        agree: dict = {
            "materiality_m": BAND_AGREEMENT_MATERIALITY_M,
            "suppliers": {
                "measured": "constant_dem.band_width_field — canyon(node) "
                            f"− plateau(node) over the {hi:g} m and {lo:g} m "
                            "builds",
                "analytic": "building_feasibility.reach_band_unified — "
                            "ceiling − floor from the cap-Dijkstra over the "
                            "unified grade graph",
            },
            "analytic_band_from_world": "plateau",
        }
        if bands.get("plateau") is None:
            agree["evaluated"] = False
            agree["reason_code"] = (sat.get("plateau", {})
                                    .get("reason_code", "no_band"))
            agree["why"] = ("no analytic band for the plateau world, so the "
                            "second supplier does not exist for this run — "
                            "NOT EVALUATED, which is not a pass")
            agree["pass"] = False
        else:
            rep = band_agreement_report(field, bands["plateau"],
                                        BAND_AGREEMENT_MATERIALITY_M)
            agree.update(rep)
            agree["evaluated"] = rep["compared"] > 0
            agree["pass"] = agree["evaluated"]
            if not agree["evaluated"]:
                agree["why"] = (
                    f"the analytic band answered None (or half-open) at "
                    f"every one of {rep['nodes']} shared node(s), so the two "
                    f"suppliers were never compared — NOT EVALUATED, which "
                    f"is not a pass")
            # the cross-world check of the analytic band's own DEM-invariance
            if bands.get("canyon") is not None:
                agree["analytic_band_world_disagreement"] = (
                    _analytic_band_world_diff(
                        field, bands["plateau"], bands["canyon"],
                        BAND_AGREEMENT_MATERIALITY_M))
            prog.note(
                f"  band agreement: {rep['disagreements']} node(s) differ by "
                f"> {BAND_AGREEMENT_MATERIALITY_M} m of {rep['compared']} "
                f"compared ({rep['no_analytic_band']} no band, "
                f"{rep['analytic_band_half_open']} half-open, of "
                f"{rep['nodes']} shared); worst "
                f"{rep['max_abs_delta_m']:+.4f} m")
        agree["note"] = (
            "the two independent suppliers of the band width, differenced "
            "per node.  'disagreements' is a count of ADDRESSES to read "
            "(author + coordinate + both widths in 'worst'), not a verdict "
            "about which supplier is wrong; 'pass' says only that the "
            "comparison was made")
        agree["artifact"] = str(out / f"{args.icao}_band_agreement.json")
        (out / f"{args.icao}_band_agreement.json").write_text(
            json.dumps(agree, indent=1, default=str))
        verdicts["band_agreement"] = agree

    doc = {"icao": args.icao, "worlds": worlds, "frame": frame,
           "verdicts": verdicts,
           "builds": {f"{w:g}": {k: v for k, v in layouts[w].items()
                                 if not k.startswith("_")}
                      for w in worlds}}
    (out / f"{args.icao}_oracle.json").write_text(
        json.dumps(doc, indent=1, default=str))

    def _state(v: dict) -> str:
        # DEFECT outranks SEE-REPORT: a failure of the instrument and a
        # finding about the airport must not read the same in the exit line.
        if v.get("defect"):
            return "DEFECT"
        if v.get("pass"):
            return "PASS"
        return "SEE-REPORT"

    defects = sorted(k for k, v in verdicts.items() if v.get("defect"))
    prog.note(f"EXIT oracle {args.icao}: "
              + "  ".join(f"{k}={_state(v)}"
                          for k, v in verdicts.items() if "pass" in v))
    if defects:
        prog.note(f"EXIT oracle {args.icao}: INSTRUMENT DEFECT in "
                  f"{defects} — a reader failed, so the affected "
                  f"assertion(s) reported nothing about this airport")
    print(f"\n  [harness] oracle artifacts in {out}")
    return 0 if all(v.get("pass", True) for v in verdicts.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
