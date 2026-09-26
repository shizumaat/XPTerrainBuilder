"""The auto-patch-v2 engine INSIDE the tile build (RULINGS 2026-09-03d: v2
beside v1; 2026-09-13au: v1 RETIRED — v2 is the only engine, there is no
``auto_patch_engine`` key and no selector any more).

``auto_patch.driver`` owns the tile: CIFP discovery, the manual-patch and
apt.dat gates, the freshness gate, the per-airport worker pool, the
results loop, the manifest verification and the JSONL failure events.
None of that is v2's to re-implement.  What v2 replaces is ONE step —
the per-airport "build + write + verify" — and this module is that step:
it runs ``auto_patch_v2.pipeline.build``
on the tile build's OWN production DEM (``tile.dem``, handed to the
worker exactly as the driver's own worker receives it — reused, never
re-composed),
places the current tile's patch and sidecar where ``include_patches``
reads them (``Patches/<block>/<tile>/<ICAO>_auto.patch.osm``), writes the
v2 verify census into the same per-airport log part the driver
concatenates into ``auto_patch_verify_debug.log``, and returns the SAME
result record ``_build_write_verify_one`` returns — so the driver's
results loop, manifest check and ``AutoPatchFailed`` events are one path.

A v2 solve that is not optimal/feasible, or a v2 refusal (a cold DEM
frame, a law-table error, a loader refusal), is a per-airport build
FAILURE with the IIS / refusal text in the verify debug log — never a
silent skip and never a stale patch left for the mesh to drape.

No environment is read here or in anything under ``auto_patch_v2``.
"""
from __future__ import annotations

import json
import os
import re
import time
import traceback
import typing as _t
import urllib.parse

#: THE engine name.  v1 is retired (owner RULINGS 2026-09-13au): there is
#: no second value, no cfg key and no selector — this constant is the one
#: spelling the freshness stamp, the provenance line and the harness frame
#: all read.
ENGINE_V2 = "v2"


#: WHAT EACH DEFECT FAMILY'S LAW IS, for the failure the tile build aborts
#: on (owner 2026-09-14, the +40-004 tile: a LERM ``runway_transverse``
#: abort read "a building pad is not one flat value" — the template named
#: ONE family's law for every family).  A family absent here fails with the
#: generic wording rather than a wrong one.
_DEFECT_LAW = {
    "pad_flat": "a building pad is not one flat value, RULINGS 2026-09-03h, "
                "and no 04t(1) relaxation names it",
    "runway_transverse": "a runway-family vertex is off its crown ridge by "
                         "more than its transverse maximum (the runway's "
                         "inside its half width, the shoulder's beyond it, "
                         "spec §40 (2))",
    "runway_crown": "a runway-family vertex does not carry its designed "
                    "crown drop",
    "runway_vertical_curve": "the built runway ridge breaks the vertical-"
                             "curve law",
    "stacked_nodes": "two emitted nodes share one identity at different "
                     "elevations",
    "sentinel_elevation": "an emitted vertex carries a sentinel elevation",
}

#: The v2 pipeline's stages as the progress window's phases (the driver's
#: ``BuildProgress`` banner + bar), with rough time shares (OTHH 2026-09-04:
#: load ~40 %, planar ~20 %, constraints ~5 %, solve ~30 %, emit+verify ~5 %).
V2_PHASE_LABELS = [
    "Loading airport, pack & production DEM",
    "Classifying & building the planar map",
    "Generating the law constraints",
    "Solving the surface (HiGHS LP)",
    "Emitting the patch & verifying",
]
V2_PHASE_WEIGHTS = [8, 4, 1, 6, 1]

#: The ``[ICAO] <stage> …`` line that marks a stage FINISHED → the next
#: phase begins.  ``load`` ends phase 1, ``planar`` phase 2, and so on.
_STAGE_DONE_TO_NEXT_PHASE = ("load", "planar", "constraints", "solve")


def resolved_auto_patch_engine(tile) -> str:
    """``"v2"``.  Always.

    THE V1 ENGINE IS RETIRED (owner RULINGS 2026-09-13au, stage A): v2 is
    the only engine, so there is nothing left to select.  The cfg key
    ``auto_patch_engine`` is gone from ``O4_Cfg_Vars`` and lives on only in
    ``retired_cfg_keys``, where the readers DELETE it from any cfg file
    still carrying it (RULINGS 2026-09-13a (2)) — a stale ``= v1`` line is
    never honoured and never warned about.  The function itself stays as
    the ONE place the engine name is spelled, so the freshness stamp
    (``o4_ap_engine``), the ``[provenance]`` line and the harness frame
    keep reading it from a single source; *tile* is ignored.
    """
    return ENGINE_V2


def select_apt_dat(xplane_root: str, icao: str) -> str | None:
    """THE apt.dat that serves ``icao`` — v2's OWN selector, called once.

    ONE SELECTOR, ONE DATUM (lane ``aptstamp`` 2026-09-17).  Until this
    existed auto_patch carried TWO apt.dat policies: the driver's gate and
    freshness stamp re-derived v1's
    ``osm_load._pick_best_apt_dat_against_osm`` (custom pack carrying a
    1201/1202 taxi network, ELSE fall back to Global Airports), while the
    build read ``auto_patch_v2.airport.apt_dat.find_apt_dat`` (§44 (1):
    the pack is the pack — the first custom pack with row-110 pavement,
    never a Global fallback).  MEASURED on the owner's install 2026-09-17:
    of 1,327 CIFP airports carried by a custom pack the two disagreed at
    **225** (220 of them v1=Global Airports vs v2=the custom pack; 5
    custom-vs-custom, incl. KAUS, YMML, KJAN, MPTO, PAKD).  For each of
    those the patch header stamped — and the gate re-derived — a file the
    build never opened: editing the pack v2 DID read left the patch
    reading "current" and a stale patch was reused.

    The build is the authority, so the gate follows the build: every v1-
    side caller (the freshness gate, the stamp, the "no apt.dat in this
    install" skip line, the DSF object-anchor worklist) resolves through
    HERE, and nothing re-implements the policy.
    """
    from auto_patch_v2.airport.apt_dat import find_apt_dat
    return find_apt_dat(xplane_root, icao)


def fresh_pack_dump(xplane_root: str, icao: str, lat: int, lon: int) -> str | None:
    """The engine's DSFTool text dump of the serving pack's tile DSF,
    regenerated by the v1 cache when the DSF is newer (``dsf_reader.
    ensure_dsf_text_path`` — mtime-keyed, ``<tile>.dsf.<tag>.text``).
    v2 never runs DSFTool itself (its ``find_text_dump`` REFUSES a stale
    dump); the driver is where a changed pack is re-dumped.  OTHH gained
    tunnel wall objects on 2026-09-04 and every build until this read the
    07-30 dump.

    PUBLIC since RULINGS 2026-09-13 (lane ``v2zerocrater``): the HARNESS
    build entry calls THIS function too.  Once the object stage has written
    a pack, the read frame is the ``.dsf.anchor_bak`` beside it, and the
    dump named for that file exists only where something made it — so
    ``tools/harness/build_airport.py --engine v2`` refused every KCLT build
    after 09-12's object stage with "the pack DSF is newer than every
    cached text dump", while the app built the same airport fine.  One
    implementation, both entries.
    """
    try:
        import O4_File_Names as FNAMES
        from auto_patch_v2.airport import dsf as _dsf2
        from auto_patch_v2.airport.pack import select_pack
        from . import dsf_reader as _DSFR
        from auto_patch_v2.airport.dsf_write import pristine_dsf_path
        sel = select_pack(xplane_root, icao)
        if sel is None:
            return None
        # 11m: the READ FRAME is the PRISTINE DSF — once the object stage
        # has written the pack, the live file carries the bodies it minted
        # and a plan derived from it names placements the write half
        # (which dumps the backup) cannot find.
        dsf_path = pristine_dsf_path(_dsf2.dsf_path_in_pack(sel.root, lat, lon))
        if not os.path.isfile(dsf_path):
            return None
        return _DSFR.ensure_dsf_text_path(
            dsf_path, _dsf2.mod_cache_dir(FNAMES.airport_mod_cache_root(), sel.name))
    except Exception as exc:                # the load stage will refuse loudly
        import logging
        logging.getLogger(__name__).warning(
            "pack dump refresh skipped for %s: %s", icao, exc)
        return None


def _stamp_header(task: dict) -> dict[str, str]:
    """The ``<osm>`` root attributes the driver's freshness gate reads back
    (``layout.read_patch_source`` → ``_auto_patch_is_current``), rendered
    EXACTLY as ``PavementLayout.to_osm`` renders them for a v1 patch: the
    percent-encoded apt.dat path + its mtime, and the all-or-nothing
    freshness block.  The apt.dat stamped is the one the GATE re-derives
    — and since lane ``aptstamp`` (2026-09-17) that is :func:`select_apt_dat`,
    v2's OWN selector, on both sides: the file stamped is the file the
    build read.  It overrides the ``o4_apt_dat`` v2's emitter writes only
    to percent-encode it (``pipeline/build.py`` :915, ``Config.
    header_extra``), never to name a different file.

    NOT STAMPED HERE: §44's BORROWED Global Airports block.  When the
    pack's pavement covers < 25 % of Global's, v2 reads a SECOND apt.dat
    — decided inside the load stage, long after this stamp is cut, so
    ``pipeline/build.py`` writes it into the header itself:
    ``o4_apt_dat_borrowed`` (§44 (4)) plus ``o4_apt_dat_borrowed_mtime``
    (:func:`~auto_patch_v2.pipeline.build.borrowed_apt_dat_stamp`, lane
    ``borrowstamp``).  Both ARE now watched: ``_auto_patch_is_current``
    stat()s the borrowed file, so a Global Airports update in place
    invalidates a borrowed patch.

    STILL NOT WATCHED, anywhere: the borrow DECISION.  A Global Airports
    update that would flip an airport from not-borrowing to borrowing (or
    back) is invisible to the gate — re-deciding it costs a Global-block
    parse plus a coverage union per airport per tile build, and the gate
    is stat()s by construction.  Every cache keyed on the pack signature
    (``borrowed_block_sha256``) does see the content change."""
    from . import provenance as _prov
    hdr: dict[str, str] = {}
    apt = task.get("apt_dat_path")
    if apt:
        hdr["o4_apt_dat"] = urllib.parse.quote(str(apt))
        try:
            hdr["o4_apt_dat_mtime"] = f"{os.path.getmtime(apt):.6f}"
        except OSError:
            pass
    fresh = task.get("freshness")
    if fresh is not None:
        from .driver import _dsf_identities_now
        stamps = dict(fresh)
        stamps["o4_fresh_v"] = _prov.FRESHNESS_SCHEMA_VERSION
        tiles_key = f"{int(task['tile_lat'])},{int(task['tile_lon'])}"
        stamps["o4_dsf_tiles"] = tiles_key
        stamps["o4_dsf"] = (_dsf_identities_now(apt, tiles_key)
                            if apt else "unknown")
        for k in _prov.FRESHNESS_KEYS:
            hdr[k] = str(stamps.get(k, "unknown"))
    return hdr


def _scratch_dir(task: dict) -> str:
    """Where the v2 pipeline writes its products (report, graded surface,
    the whole-airport patch, tile pieces) BEFORE the current tile's patch
    is moved into ``Patches/``: the engine's own ``tmp/`` (lane-local by
    the ritual), never inside the Patches tree — ``include_patches`` and
    the driver's manual-patch scan both enumerate that directory."""
    import O4_File_Names as FNAMES
    root = FNAMES.Tmp_dir or FNAMES.data_path("tmp")
    return os.path.join(root, "auto_patch_v2",
                        f"{int(task['tile_lat']):+03d}{int(task['tile_lon']):+04d}",
                        task["icao"])


def _dem_label(dem_prov: dict) -> str:
    """One token for the provenance line from the v2 loader's DEM
    provenance: the tiles it sampled and their baked insets."""
    tiles = [k[5:] for k in dem_prov if k.startswith("tile:")]
    insets = []
    for k in tiles:
        v = dem_prov.get("tile:" + k, "")
        if "insets=" in v:
            ins = v.split("insets=", 1)[1].strip()
            if ins:
                insets.append(ins)
    label = f"production[{','.join(tiles) or '?'}]"
    label += f" insets={';'.join(insets)}" if insets else " insets=NONE"
    if dem_prov.get("degraded"):
        label += " DEGRADED"
    return label


def format_provenance_line(icao: str, *, sha: str, law_sha256: str | None,
                           ruleset: str, dem_prov: dict, status: str,
                           flat_site: dict | None = None) -> str:
    """The v2 twin of ``provenance.format_log_line`` — one line per airport
    at patch completion, ``engine=v2`` and the law-table digest instead of
    v1's gate census (v2 has no gates: RULINGS 2026-09-03e, no numeric law
    value lives in Python).  ``flat=<Z0>`` names the flat-site datum the
    LP priced when the verdict substitutes (RULINGS 2026-09-05k-2; the
    ``law=`` digest already changes when a site is declared)."""
    law = (law_sha256 or "absent")[:12]
    flat = ""
    if flat_site and flat_site.get("substitutes") and flat_site.get("z0_m") is not None:
        flat = f" flat={float(flat_site['z0_m']):.2f}"
    return (f"  [provenance] {icao} patch: engine=v2 sha={sha} law={law} "
            f"ruleset={ruleset} solve={status}{flat} dem={_dem_label(dem_prov)}")


def _iis_text(report: dict, log_lines: list[str]) -> str:
    solve = (report or {}).get("solve") or {}
    rows = solve.get("iis") or []
    out = [f"v2 solve status={solve.get('status')!r}: {solve.get('message')}",
           f"IIS rows: {len(rows)}"]
    for r in rows[:50]:
        out.append(f"  IIS {r.get('generator')} [{r.get('ruling')}] "
                   f"{r.get('inputs')}: {r.get('row')}")
    out.append("--- v2 build log ---")
    out.extend(log_lines)
    return "\n".join(out)


def build_write_verify_one_v2(task: dict, tile_dem) -> dict:
    """Build ONE airport with v2, place its patch, verify it — the v2 body
    of ``driver._build_write_verify_one`` (same ``task`` keys plus
    ``engine``, ``cifp_path``, ``apt_dat_path``; same result record).
    ``tile_dem`` is the worker's ``_WORKER_DEM`` — the tile build's own
    production raster, seeded into the v2 loader for the current tile."""
    icao = task["icao"]
    t0 = time.time()
    log_lines: list[str] = []
    try:
        import O4_File_Names as FNAMES
        from auto_patch_v2.airport.load import Inputs
        from auto_patch_v2.law import Law, law_tables_digest
        from auto_patch_v2.pipeline.build import Config, build
        from . import progress as _progress
        from . import provenance as _prov

        lat, lon = int(task["tile_lat"]), int(task["tile_lon"])
        digest = law_tables_digest()
        if not digest["sha256"]:
            raise RuntimeError(
                f"v2 law tables are MISSING under {digest['dir']} — this "
                f"engine build carries no *.toml law files (a frozen engine "
                f"whose datas omitted them); v2 never falls back to v1.")
        bp = _progress.BuildProgress(icao, V2_PHASE_LABELS, V2_PHASE_WEIGHTS)
        _progress._current = bp
        bp.step()

        def _out(line: str) -> None:
            log_lines.append(line)
            head = line.split("] ", 1)[1] if line.startswith("[") else ""
            if head.split(" ", 1)[0] in _STAGE_DONE_TO_NEXT_PHASE:
                bp.step()

        seeds = {(lat, lon): tile_dem} if tile_dem is not None else None
        inputs = Inputs(
            xplane_root=task["xp_root"], cifp_dir=task.get("cifp_path") or "",
            osm_root=FNAMES.OSM_dir, elevation_root=FNAMES.Elevation_dir,
            mod_cache_root=FNAMES.airport_mod_cache_root(),
            dsf_dump_path=fresh_pack_dump(task["xp_root"], icao, lat, lon),
            dem_frame="production", production_dem_tiles=seeds,
            core_hosted=True,
            road_grade_limit=task.get("road_grade_limit"),
            lane_width_m=task.get("lane_width"))
        law = Law.for_airport(icao)
        scratch = _scratch_dir(task)
        os.makedirs(scratch, exist_ok=True)
        # THE CROSS-PLATFORM STAGE DUMP (lane ``xplatdeterminism``).  The
        # v2 package may not read the environment (its own twin forbids
        # it), so the release check's request is read HERE, in the v1
        # wrapper, and handed on as a schema flag.  Set by
        # ``scripts/check_frozen_tile.py --xplat-dump`` in the frozen
        # bundle's environment; unset in every ordinary build.
        # ``O4_V2_XPLAT_QUANTISE_M`` (lane ``xplatspread``; re-pointed by
        # ``xplatquantum``) OVERRIDES the law's ``emit.identity.
        # input_quantum_m`` for a measurement arm — including with ``0``,
        # the pre-§46 unquantised arm.  UNSET means the law's own value,
        # which is what every shipped build uses; read only when the dump
        # is armed, and a malformed value is ignored rather than failing a
        # release check.
        _xq_raw = os.environ.get("O4_V2_XPLAT_QUANTISE_M")
        try:
            _xq = None if _xq_raw in (None, "") else float(_xq_raw)
        except ValueError:
            _xq = None
        cfg = Config(header_extra=_stamp_header(task),
                     xplat_dump=bool(os.environ.get("O4_V2_XPLAT_DIGEST")),
                     xplat_quantise_m=_xq)
        res = build(icao, inputs, scratch, cfg, law, out=_out)
    except Exception as exc:
        return {"icao": icao, "ok": False, "stage": "build", "engine": ENGINE_V2,
                "error": f"[v2] {exc}",
                "traceback": traceback.format_exc() + "\n--- v2 build log ---\n"
                + "\n".join(log_lines)}

    status = res.solution.status.value
    if status not in ("optimal", "feasible") or res.paths is None:
        return {"icao": icao, "ok": False, "stage": "solve", "engine": ENGINE_V2,
                "error": (f"[v2] the solve for {icao} ended {status!r} — "
                          f"{res.solution.message}; the IIS is in "
                          f"{os.path.join(scratch, icao + '.report.json')}"),
                "traceback": _iis_text(res.report, log_lines)}
    # A GOVERNED FAMILY DEMOTED IS A NAMED FAILURE (RULINGS 2026-09-05u,
    # ``[relaxation] tier_ladder_last``): the tier ladder answered after
    # the whole relaxable scope could not, and made a governed surface
    # yield — not a lawful surface; the airport fails by name like a
    # non-optimal solve (the patch and report stay in the scratch dir).
    solve_rep = res.report.get("solve") or {}
    if solve_rep.get("demoted"):
        names = "; ".join(f"tier {g.get('tier')} ({' '.join(g.get('roles') or [])}) "
                          f"{g.get('rows')} rows, max {g.get('max_m')} m"
                          for g in solve_rep["demoted"])
        return {"icao": icao, "ok": False, "stage": "solve", "engine": ENGINE_V2,
                "error": (f"[v2] the law ladder DEMOTED a governed family at {icao} "
                          f"(scope {solve_rep.get('scope')}): {names} — "
                          f"{solve_rep.get('failure')}; the report is in "
                          f"{os.path.join(scratch, icao + '.report.json')}"),
                "traceback": _iis_text(res.report, log_lines)}
    # A VERIFY DEFECT never ships (lane v2padflat 2026-09-05): a DEFECT
    # family is a solver/emit invariant broken, not a residual — the
    # airport fails by name, like a non-optimal solve.  The pad_flat
    # family (RULINGS 03h) is one member of that set, not the set: the
    # message used to name it for EVERY defect, and a LERM
    # `runway_transverse` abort read "a building pad is not one flat
    # value" (owner, 2026-09-14, the +40-004 tile).  Each family now
    # states its OWN law.
    # THE MATERIALITY FLOOR IS ALREADY APPLIED (owner RULINGS 2026-09-14bx,
    # ``auto_patch_v2/verify/census.py`` ``defect_gate``): ``defects`` holds
    # the MATERIAL rows only — a row under ``emit.verify.defect_min_excess_m``
    # of excess is a census violation named in the build log, never an abort.
    defects = (res.report.get("verify") or {}).get("defects") or {}
    if defects:
        rows = (res.report.get("verify") or {}).get("rows") or {}
        text = "\n".join(f"[v2:{k}] {json.dumps(r, default=str)}"
                          for k in defects for r in rows.get(k, []))
        return {"icao": icao, "ok": False, "stage": "verify", "engine": ENGINE_V2,
                "error": (f"[v2] verify found a structural DEFECT in {icao}: "
                          + ", ".join(f"{k} {n} ({_DEFECT_LAW.get(k, 'a v2 verify invariant')})"
                                      for k, n in defects.items())
                          + "; the rows are in "
                          f"{os.path.join(scratch, icao + '.report.json')}"),
                "traceback": text + "\n--- v2 build log ---\n" + "\n".join(log_lines)}

    # ── PLACE the current tile's patch where the mesh reads it ────────
    try:
        pieces = res.pieces or {}
        src = pieces.get((lat, lon)) if pieces else res.paths
        if src is None:
            raise RuntimeError(
                f"v2 emitted tile pieces for "
                f"{sorted(f'{a:+03d}{b:+04d}' for a, b in pieces)} but none "
                f"for this tile {lat:+03d}{lon:+04d} — the airport has no "
                f"face on it")
        dest = task["auto_patch_file"]
        pd = os.path.dirname(dest)
        if pd and not os.path.exists(pd):
            os.makedirs(pd)
        os.replace(str(src.patch), dest)
        os.replace(str(src.sidecar), dest + ".axes.json")
        # the post-mesh re-seat plan (04f-1) beside the patch, read by
        # ``rebake_after_mesh`` at the end of build_mesh
        rebake_plan_path = _place_rebake_plan(task, res.rebake_plan, icao)
        # and the WHOLE-AIRPORT design surface beside it: §6's class rule
        # reads the emitted object pads and structure rims, and the object
        # stage runs post-mesh, long after ``res`` is gone (lane
        # v2planfix).  ``res.paths`` is the whole surface even when tile
        # pieces were also written — the same file
        # ``tools/obj8_split_report.py`` is pointed at.
        _place_graded_surface(task, res.paths, icao)
    except Exception as exc:
        return {"icao": icao, "ok": False, "stage": "write", "engine": ENGINE_V2,
                "error": f"[v2] {exc}", "auto_patch_file": task["auto_patch_file"],
                "traceback": traceback.format_exc()}
    build_s = time.time() - t0

    # ── VERIFY: the v2 census rows into the per-airport log part ──────
    t_v = time.time()
    verify_err = None
    try:
        rep_v = (res.report.get("verify") or {})
        by_family = rep_v.get("by_family") or {}
        with open(task["verify_log_path"], "w", encoding="utf-8",
                  newline="\n") as lf:
            lf.write(f"=== {icao} v2 verify: {sum(by_family.values())} row(s) ===\n")
            for fam, n in sorted(by_family.items()):
                if n:
                    lf.write(f"  {fam}: {n}\n")
            for fam, rows in sorted((rep_v.get("rows") or {}).items()):
                for row in rows:
                    lf.write(f"[v2:{fam}] {json.dumps(row, default=str)}\n")
            lf.write("--- v2 build log ---\n" + "\n".join(log_lines) + "\n")
    except Exception as exc:
        verify_err = str(exc)

    dem_prov = dict((res.report.get("load") or {}).get("dem_provenance") or {})
    sha = _prov.source_label(_prov.git_provenance())
    line = format_provenance_line(icao, sha=sha, law_sha256=digest["sha256"],
                                  ruleset=law.ruleset_key, dem_prov=dem_prov,
                                  status=status,
                                  flat_site=(res.report.get("load") or {}).get("flat_site"))
    summary = (f"{src.ways} ways, {src.nodes} nodes [v2 {status}, "
               f"verify rows {sum(by_family.values()) if by_family else 'n/a'}]")
    return {"icao": icao, "ok": True, "engine": ENGINE_V2, "summary": summary,
            "build_s": build_s, "worker_pid": os.getpid(),
            "verify_s": time.time() - t_v, "verify_err": verify_err,
            "verify_log_path": task["verify_log_path"],
            "object_pad_records": [], "provenance_log": line,
            "log_lines": log_lines,
            "v2": {"status": status, "law_tables": digest,
                   "ruleset": law.ruleset_key, "wall": res.wall,
                   "report": os.path.join(scratch, icao + ".report.json"),
                   "rebake_plan": rebake_plan_path,
                   "tiles": sorted(f"{a:+03d}{b:+04d}" for a, b in pieces)}}


# ══════════════════════════════════════════════════════════════════════════
# THE OBJECT STAGE AFTER THE MESH (RULINGS 2026-09-04i 04f-1;
# THE SEAT RETIRED 2026-09-12s, spec §8)
# ══════════════════════════════════════════════════════════════════════════
# The retired v1 Phase 2 (``post_mesh.rebake_dsf_objects``) ran at the END
# of ``O4_Mesh_Utils.build_mesh`` / ``sort_mesh``; since v1 went (RULINGS
# 2026-09-13au) that hook routes HERE, unconditionally.  What runs here is the PLACEMENT
# path and nothing else: over the tile build's own ``o4_v2_rebake_<ICAO>.
# json`` plans and a sampler of the built mesh, every object is cut,
# re-anchored and placed ON the terrain (``airport/placement_*.py``).
# NO SEAT IS COMPUTED and no authored vertex is rewritten — v1's vertex
# re-bake (``_decision_from_seats`` -> ``object_rebake.apply``, the
# ``o4_v2_rebake_result_*`` sidecars) is a refuted mechanism, DELETED.
# The pack's ``.obj.anchor_bak`` survives as the RESTORE (spec §10): a
# pack authored under the seat is put back before the placement writes.
# ``modify_custom_airports`` is honoured exactly as v1 honours it: OFF =
# measure-only, nothing is written.

#: RULINGS 2026-09-09w (3): the pipeline's own plan file names —
#: ``o4_v2_rebake_<ICAO>.json`` (``model.rebake.PLAN_FILENAME``) and
#: nothing else in the patch directory.  A tool's
#: ``o4_v2_rebake_<ICAO>.seat.json`` is NOT a plan.
_PLAN_NAME_RE = re.compile(r"^o4_v2_rebake_(?!result_)[A-Za-z0-9]{2,8}\.json$")


def _place_rebake_plan(task: dict, src_plan, icao: str) -> str | None:
    """Copy the pipeline's plan beside the patch (``Patches/<tile>/``)."""
    import shutil
    if src_plan is None or not os.path.isfile(str(src_plan)):
        return None
    from auto_patch_v2.model.rebake import PLAN_FILENAME
    dest = os.path.join(os.path.dirname(task["auto_patch_file"]),
                        PLAN_FILENAME.format(icao=icao))
    shutil.copyfile(str(src_plan), dest + ".tmp")
    os.replace(dest + ".tmp", dest)
    return dest


#: ``<ICAO>.graded.json`` beside the patch — the emitted DESIGN SURFACE the
#: post-mesh object stage reads its §6 classes off (``placement_plan.
#: pads_rims_from_graded``).  The pipeline writes it into the engine's
#: ``tmp/`` scratch; the object stage runs at the end of ``build_mesh``,
#: with no handle on that build's ``res`` — so it is PLACED here exactly
#: as the re-seat plan is.  ``include_patches`` reads ``*.patch.osm`` only,
#: so a JSON beside the patch is inert to every other consumer.
GRADED_SURFACE_FILENAME = "{icao}.graded.json"


def graded_surface_path(patch_dir: str, icao: str) -> str:
    """Where :func:`_place_graded_surface` puts it / the object stage
    looks for it."""
    return os.path.join(patch_dir, GRADED_SURFACE_FILENAME.format(icao=icao))


def _place_graded_surface(task: dict, paths, icao: str) -> str | None:
    """Copy the pipeline's whole-airport graded surface beside the patch."""
    import shutil
    src = getattr(paths, "graded", None) if paths is not None else None
    if src is None or not os.path.isfile(str(src)):
        return None
    dest = graded_surface_path(os.path.dirname(task["auto_patch_file"]), icao)
    shutil.copyfile(str(src), dest + ".tmp")
    os.replace(dest + ".tmp", dest)
    return dest


# ── THE PLACEMENT PATH (owner RULINGS 2026-09-11b / 11e (3)) ─────────────
# THE ONLY OBJECT STAGE (owner RULINGS 2026-09-12s, spec §8: the seat is
# RETIRED — deleted, not gated, and with it the ``[rebake] placement``
# key that used to choose between them).  X-Plane places every object on
# the terrain under its own anchor: NO SEAT IS COMPUTED and no authored
# vertex is rewritten — the plan is built (conversions for every MSL/AGL
# row, splits with coarsened bodies and placed anchors), the cut files
# are written into the pack's ``objects/`` under new names, the DSF is
# edited, encoded, verified and backed up, the READ path's text-dump
# cache is refreshed and the placement plan lands beside the patch.

def _placement_surface(mesh_sample):
    """The placement stage's design surface over a mesh sampler
    (RULINGS 2026-09-12g (2)).

    Two things the bare closure this replaced did not do, both measured
    on the shipped 1.0.320 LEMD frame:

    * ``.many`` — ``placement_geom.surface_many`` batches only when the
      sampler carries it, so 103,479 of the stage's 302,532 queries were
      taking the per-point fallback and the vectorised reading §16b was
      designed on was never taken by the app.  Here it is, backed by
      ``MeshElevationSampler.sample_many`` through ``mesh_sample.many``
      (and by a plain loop when the sampler offers none, so a graded or
      synthetic sampler still satisfies the protocol).
    * a ``(lat, lon)`` MEMO — 165,114 of those 302,532 queries were
      unique; 45 % were exact repeats.  The memo is keyed on the float
      pair as given, so a repeat is a repeat only when it is bit-equal,
      and no answer can differ from the sampler's own.
    """
    memo: dict[tuple[float, float], float | None] = {}
    #: §16e / R12 amendment 1: THE WATER BIT, beside the height.  The mesh
    #: is a datum at 0.00 over water and half of OTHH's Bridge_01 stands
    #: over the canal, so a datum's stations must be able to discard a
    #: sample on water — the SAME discard the retired seat's
    #: ``_plate_reading`` / ``_abutment_grade`` made.  It rides the
    #: surface callable as ``.water``, the way ``.roles`` and ``.many``
    #: do, so no caller between here and ``anchor_rule`` grows an
    #: argument; it is asked only at a datum's stations (OTHH: 1,033
    #: points of the stage's 336,003).
    wmemo: dict[tuple[float, float], bool] = {}
    batch = getattr(mesh_sample, "many", None)

    def _surface(lat: float, lon: float):
        key = (lat, lon)
        if key in memo:
            return memo[key]
        s = mesh_sample(lat, lon)
        z = None if s is None else float(s[0])
        memo[key] = z
        return z

    def _surface_many(lats, lons):
        lats = list(lats)
        lons = list(lons)
        answers: list[float | None] = [None] * len(lats)
        wanted: list[int] = []
        want_lat: list[float] = []
        want_lon: list[float] = []
        for index, (lat, lon) in enumerate(zip(lats, lons)):
            key = (lat, lon)
            if key in memo:
                answers[index] = memo[key]
            else:
                wanted.append(index)
                want_lat.append(lat)
                want_lon.append(lon)
        if wanted:
            if batch is not None:
                sampled = batch(want_lat, want_lon)
            else:
                sampled = [mesh_sample(a, o)
                           for a, o in zip(want_lat, want_lon)]
            for index, lat, lon, s in zip(wanted, want_lat, want_lon,
                                          sampled):
                z = None if s is None else float(s[0])
                memo[(lat, lon)] = z
                answers[index] = z
        return answers

    def _water(lat: float, lon: float) -> bool:
        key = (lat, lon)
        hit = wmemo.get(key)
        if hit is None:
            s = mesh_sample(lat, lon)
            hit = bool(s[1]) if (s is not None and len(s) > 1) else False
            wmemo[key] = hit
        return hit

    _surface.many = _surface_many
    _surface.water = _water
    return _surface


def _place_objects(plan_, law, mesh_sample, tile, patch_dir: str,
                   write_enabled: bool, measure_only: bool) -> dict:
    """One airport's placement write (RULINGS 2026-09-11e (3)).  Returns
    the counts; raises nothing the caller does not already catch."""
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport import placement_write as _pw
    from . import dsf_reader as _DSFR

    pack_name = os.path.basename(os.path.normpath(plan_.pack_root))
    dsf_path = _dsf2.dsf_path_in_pack(plan_.pack_root, tile.lat, tile.lon)
    if not os.path.isfile(dsf_path):
        UI.vprint(1, f"  [v2 placement] {plan_.icao}: no DSF at {dsf_path}; skipped")
        return {}
    cache = _dsf2.mod_cache_dir(FNAMES.airport_mod_cache_root(), pack_name)
    # the PRISTINE dump (§3.4, RULINGS 2026-09-11m): ONE resolver, and
    # the cache entry is keyed on that file's CONTENT
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    dump_path = _DSFR.ensure_dsf_text_path(pristine_dsf_path(dsf_path), cache)
    if not dump_path:
        UI.vprint(1, f"  [v2 placement] {plan_.icao}: no DSF text dump; skipped")
        return {}
    dump = _dsf2.read_dump(dump_path)

    _surface = _placement_surface(mesh_sample)

    # §6's CLASS RULE reads the emitted surface (lane v2planfix): without
    # the pads and rims ``classify_body`` can never answer ``building`` or
    # ``basin``, and the shipped path passed NEITHER — every shipped body
    # fell through to ``other`` while ``tools/obj8_split_report.py``,
    # deriving them from the same file, classified both.  ONE derivation,
    # ``placement_plan.pads_rims_from_graded``, two callers.
    from auto_patch_v2.airport import placement_plan as _pp
    from auto_patch_v2.airport import placement_boxes as _pb
    pads, rims = (), ()
    decks: tuple = ()                                               # §49
    jetway_strips: tuple = ()          # jetway-strip spec §4 (C17), #31
    graded = graded_surface_path(patch_dir, plan_.icao)
    if os.path.isfile(graded):
        try:
            import json as _json
            with open(graded, encoding="utf-8") as _fh:
                _gd = _json.loads(_fh.read())
            pads, rims = _pp.pads_rims_from_graded_doc(_gd)
            decks = _pp.decks_from_graded_doc(_gd)                  # §49
            jetway_strips = tuple((_gd.get("provenance") or {})
                                  .get("jetway_strips") or ())
            # §17 (owner RULINGS 2026-09-12am (2)): the FACE ROLE under a
            # point, off the SAME parsed document — what says whether a
            # foot stands where the aircraft ROLLS.  §9's anchor reads it
            # through the sampler (``surface.roles`` beside
            # ``surface.many``): a body every foot of which stands on
            # rolled-on pavement keeps the MEDIAN of its feet instead of
            # its low-side one.  Without this the shipped path would take
            # the low-side rule everywhere while the dry-run tool took the
            # median — the v2planfix defect over again.
            from auto_patch_v2.law import tables as _T
            _surface.roles = _pb.graded_roles_from_doc(
                _gd, rank=lambda r: _T.authority_rank(law, r))
            _surface.rolled_on = frozenset(_T.rolled_on_roles(law))
            UI.vprint(1, f"  [v2 placement] {plan_.icao}: design surface "
                         f"{len(pads)} object pad(s), {len(rims)} structure "
                         f"rim(s), {len(_surface.roles.faces)} graded face(s) "
                         f"for the §17 motion rule")
        except Exception as exc:                   # a malformed surface
            UI.vprint(1, f"  [v2 placement] {plan_.icao}: {os.path.basename(graded)} "
                         f"unreadable ({exc}) — pads/rims unavailable")
    else:
        UI.vprint(1, f"  [v2 placement] {plan_.icao}: no {os.path.basename(graded)} "
                     "beside the patch — no body can classify as building or basin")

    from auto_patch_v2.law.tables import law_tables_digest
    digest = str(law_tables_digest().get("sha256") or "")
    plan, files, ss = _pw.build_plan(
        plan_, dump, _surface, icao=plan_.icao, pack_name=pack_name,
        pack_root=plan_.pack_root, dsf_path=dsf_path,
        split_tol_m=law.tables.structures.placement.split_tol_m,
        elevated_base_m=law.tables.structures.rebake.elevated_base_m,
        line_segment_m=law.tables.structures.placement.line_segment_m,
        line_stations_max=law.tables.structures.rebake.line_object_stations_max,
        line_ratio=law.tables.structures.rebake.line_object_ratio,
        line_max_h=law.tables.structures.rebake.line_object_max_h,
        foot_band_m=law.tables.structures.basin.contact_band_m,
        coarsen_reach_m=law.tables.structures.placement.coarsen_reach_m,
        contact_eps_m=law.tables.structures.placement.contact_eps_m,
        rigid_reach_m=law.tables.structures.placement.rigid_reach_m,
        # (A), owner RULINGS 2026-09-12ap: the height a cross-member
        # §16c (7) bind may move a body off its OWN ground.
        bind_ground_m=law.tables.emit.cockpit.visual_m,
        # §16f (7) (owner RULINGS 2026-09-13bj item 1): the footprint-union
        # area above which a family is a CLUSTER and seats as one unit.
        cluster_min_m2=law.tables.structures.placement.cluster_pad_min_m2,
        # §16g (owner RULINGS 2026-09-13bo): the FOOTPRINT UNIT and the
        # only cut (the HECA elevated-rail connector class).
        touch_m=law.tables.structures.placement.footprint_touch_m,
        connector_span_m=law.tables.structures.placement.connector_span_m,
        # §16g (10) (4) (owner RULINGS 2026-09-14ah): only a WALLED body
        # links a unit — a floor slab, a plate, a deck or a canopy is a
        # LEAF, seated on its own ground and never a link.
        chain_min_height_m=law.tables.structures.placement.chain_min_height_m,
        # §16g (10) (9) (2) (owner RULINGS 2026-09-14az): the unit seated
        # on a pad takes the pad's LOW side, not its median
        low_side=bool(getattr(law.tables.structures.placement,
                              'pad_between_aprons', False)),
        # §16g (5) (owner RULINGS 2026-09-13cb): "on ground" is only where
        # the terrain at the anchor already IS the unit's datum
        hard_tol_m=law.tables.emit.design.hard_tol_m,
        # §16e (6): the deck end line's LANDWARD WALK to the graded face
        # the deck connects to (RULINGS 2026-09-13v).
        abutment_step_m=law.tables.structures.bridge.abutment_sample_step_m,
        abutment_walk_max_m=law.tables.structures.bridge.abutment_walk_max_m,
        pads=pads, rims=rims,
        # §49: the emitted deck faces are a datum for the bodies on them
        decks=decks,
        deck_on_fraction=law.tables.structures.deck.on_fraction,
        deck_edge_m=law.tables.structures.deck.edge_m,
        deck_under_m=law.tables.structures.deck.under_m,
        # jetway-strip spec §4 (C17): the riders' population and strips
        jetway_strips=jetway_strips,
        engine_version=_engine_version(), law_digest=digest,
        write_cuts=bool(write_enabled and not measure_only))
    c = dict(plan.counts())
    # §6's CLASSES ride out with the counts (lane v2planfix): they are the
    # only reading that says whether the pads and rims above were seen at
    # all — with none, every body reads ``class_other``.
    c.update({k: int(v) for k, v in ss.counts.items() if k.startswith("class_")})
    if not write_enabled or measure_only:
        UI.vprint(1, f"  [v2 placement] {plan_.icao}: MEASURE ONLY — "
                     f"{c['conversions']} conversion(s), {c['splits']} split(s) into "
                     f"{c['bodies']} body file(s), {c['kept']} kept; nothing written")
        return c
    from auto_patch_v2.airport.backup_state import (BackupUnproven,
                                                    SUPERSEDED_INFIX as
                                                    _BS_SUPERSEDED,
                                                    UNRECOGNISED_INFIX as
                                                    _BS_UNRECOGNISED)
    try:
        res = _pw.apply_plan(
            plan, files, _DSFR._dsftool_path() or "DSFTool", patch_dir=patch_dir,
            allow_live_install=True,
            refresh_dump=lambda p, _c=cache: _DSFR.ensure_dsf_text_path(p, _c),
            engine_version=_engine_version(), law_digest=digest)
    except BackupUnproven as exc:
        # §12a (4): ONE line, at verbosity 0.  NOTHING in the pack was
        # touched — not the DSF, not an object, not a cut file: a pack
        # half-written against a DSF we may not touch is torn geometry.
        UI.vprint(0, f'  [v2 placement] PACK NOT TOUCHED: "{pack_name}" — '
                     f'{exc}')
        return {}
    # §12a (4): ONE line per pack per build when the rule had to act;
    # NOTHING on the normal path (D3 / D4, O1 / O2).
    _adopted = list(res.restore.adopted)
    _unproven = list(res.restore.unproven)
    if res.dsf is not None:
        for note in res.dsf.notes:
            UI.vprint(0, f'  [v2 placement] PACK UPDATED: "{pack_name}" — {note}')
        if res.dsf.composed_airports:
            # #25: one pack DSF serving two airports (TNCM + TFFG) — the
            # sibling's recorded edits were re-applied beside this one's
            UI.vprint(1, f"  [v2 placement] {plan_.icao}: "
                         f"{os.path.basename(res.dsf.dsf_path)} also carries "
                         f"{', '.join(res.dsf.composed_airports)} — their "
                         f"recorded placements were re-applied with this "
                         f"airport's"
                         + (f"; {len(res.dsf.orphaned_bodies)} orphaned body "
                            f"file(s) removed" if res.dsf.orphaned_bodies
                            else ""))
    if _adopted or _unproven:
        UI.vprint(0, f'  [v2 placement] PACK UPDATED: "{pack_name}" — '
                     f'{len(_adopted)} file(s) of yours were kept as installed '
                     f'(their old backups are now *{_BS_SUPERSEDED}<date>)'
                     + (f'; {len(_unproven)} object(s) could not be proven and '
                        f'their bytes were kept as *{_BS_UNRECOGNISED}<date>'
                        if _unproven else ''))
    UI.vprint(1, f"  [v2 placement] {plan_.icao}: "
                 f"{len(res.restore.restored)}/{len(res.restore.backups)} object(s) "
                 f"restored from .anchor_bak, {c['conversions']} placement(s) "
                 f"converted to on-ground, {c['splits']} split into "
                 f"{len(res.files_written)} body file(s), {c['kept']} kept whole; "
                 f"DSF rewritten (backup {os.path.basename(res.dsf.backup_path)}, "
                 f"round trip {'ok' if res.dsf.report.ok else 'FAILED'}), dump cache "
                 f"{'refreshed' if res.dump_refreshed else 'not refreshed'} -> "
                 f"{os.path.basename(res.plan_path)}")
    out = dict(res.counts)
    out.update({k: v for k, v in c.items() if k.startswith("class_")})
    out["packs_written"] = 1
    return out


def _engine_version() -> str:
    try:
        from . import provenance as _prov
        return str(_prov.engine_version() or "")
    except Exception:
        return ""


def rebake_after_mesh(tile) -> dict:
    """Run the PLACEMENT stage for every airport v2 patched on ``tile``
    against the mesh just built (see the section comment).  Never raises
    (the mesh hook wraps it too); returns the counts for the summary."""
    import glob
    import math
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from auto_patch_v2.law import Law
    from auto_patch_v2.model import rebake as _rb
    from .mesh_sampler import MeshElevationSampler, OutsideMeshError
    from .post_mesh import (_is_protected_scenery_root, _mesh_is_newer_than_alt,
                            object_anchor_worklist_path)

    counts = {"airports": 0, "airports_failed": 0, "packs_written": 0}
    try:
        patch_dir = os.path.dirname(object_anchor_worklist_path(tile))
        # RULINGS 2026-09-09w (3): the engine loads ITS OWN plan files only.
        # ``o4_v2_rebake_*.json`` also matched a tool's output beside them
        # (``tools/v2_rebake_replay.py`` writes ``o4_v2_rebake_<ICAO>.seat.
        # json``), which the loader then tried to read as a plan.
        plans = sorted(p for p in glob.glob(os.path.join(patch_dir, "o4_v2_rebake_*.json"))
                       if _PLAN_NAME_RE.match(os.path.basename(p)))
        if not plans:
            return counts
        mesh_path = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
        if not os.path.isfile(mesh_path):
            UI.vprint(1, f"  [v2 rebake] mesh not found at {mesh_path}; placement skipped")
            return counts
        if not _mesh_is_newer_than_alt(tile, mesh_path):
            UI.vprint(0, "  [v2 rebake] STALE MESH: the mesh predates the tile's .alt — "
                         "placement SKIPPED; rebuild the mesh after the elevation step")
            return counts
        # THE USER'S SWITCH IS A STAND-DOWN, NOT A MEASURE-ONLY ARM
        # (owner ruling RULINGS 2026-09-18a (3), BETA2 GEN-1).  When the
        # user unchecks "Modify custom airports" the whole placement stage
        # is skipped: no pack DSF dump into the mod cache, no placement
        # plan, no ``[v2 placement]`` output — ONE line naming the switch.
        # The env arms below (``O4_PACK_WRITES=measure_only``, the
        # ``DSF_OBJECT_REANCHOR`` kill switch) exist precisely to KEEP the
        # measurement while standing the writes down, so they do NOT take
        # this return.
        measure_only = not getattr(tile, "modify_custom_airports", True)
        if measure_only:
            UI.vprint(1, "  [v2 rebake] modify_custom_airports is off — "
                         "placement stage skipped entirely (no pack is read, "
                         "dumped or written, no placement plan is computed)")
            return counts
        # v1's engine-wide kill switch (``O4_DSF_OBJECT_REANCHOR=0`` "leaves
        # every pack byte-identical"; function-local import so tests drive
        # it): the placement plan is still built and reported — the
        # measurement is the product — but nothing is written.
        # THE LANE STAND-DOWN (owner ruling e9daef5 + the lane protocol;
        # measured 2026-09-15, RULINGS 2026-09-15av).  The write half
        # below targets the SERVING PACK, which lives in the owner's
        # X-Plane install — outside the shared data repo, so neither the
        # shared-repo write guard nor the harness's cache redirects ever
        # covered it.  Lane v2vmmcshore's harness TILE build of +22+113
        # rewrote the OWNER'S live VHHH pack DSF (6,390 placements) at
        # 11:49 and re-dumped it at 11:52, and the flag surfaced on a
        # DIFFERENT lane's concurrent build.  The harness sets
        # ``O4_PACK_WRITES=measure_only`` on every lane build; the APP
        # sets nothing and writes exactly as before, and an owner-
        # authorised ``--refresh-data pack_rebake`` clears it.  Measure-
        # only keeps the MEASUREMENT whole — the placement plan is still
        # built, classified and reported; only the writes stand down.
        if os.environ.get("O4_PACK_WRITES") == "measure_only":
            measure_only = True
            UI.vprint(0,
                "  [v2 rebake] LANE BUILD (O4_PACK_WRITES=measure_only): the "
                "placement plan is measured and recorded and NO pack file is "
                "written — a lane never mutates the owner's X-Plane install "
                "(RULINGS 2026-09-15av).  --refresh-data pack_rebake is the "
                "owner's act.")
        from .config import DSF_OBJECT_REANCHOR
        write_enabled = bool(DSF_OBJECT_REANCHOR)
        if not write_enabled:
            UI.vprint(1, "  [v2 rebake] DSF_OBJECT_REANCHOR is off — the placement plan "
                         "is measured and recorded, no pack file is written")
        written_packs: set[str] = set()
        for plan_path in plans:
            icao = "?"
            try:
                with open(plan_path) as fh:
                    plan_ = _rb.RebakePlan.from_json(fh.read())
                icao = plan_.icao
                law = Law.for_airport(icao)
                if not plan_.units:
                    UI.vprint(1, f"  [v2 rebake] {icao}: no unit to place "
                                 f"({len(plan_.skipped)} resource(s) skipped at plan time)")
                    counts["airports"] += 1
                    continue
                if not os.path.isdir(plan_.pack_root) or \
                        _is_protected_scenery_root(plan_.pack_root):
                    UI.vprint(1, f"  [v2 rebake] {icao}: pack {plan_.pack_root} is not a "
                                 "writable Custom Scenery pack — placement skipped")
                    counts["airports"] += 1
                    continue
                # A DISABLED PACK IS NEVER REWRITTEN (owner RULINGS
                # 2026-09-18 17b/c: "its files are not rewritten"; §12a
                # (3) row 15).  v1 had this test (``object_rebake.py``
                # :1339) and the v2 write path had none, so a plan JSON
                # left beside the patch from before the user disabled a
                # pack would still have been classified, adopted,
                # restored and written.
                import O4_Scenery_Packs as _SP
                if not _SP.pack_enabled(plan_.pack_root):
                    UI.vprint(1, f"  [v2 rebake] {icao}: pack "
                                 f"{os.path.basename(os.path.normpath(plan_.pack_root))}"
                                 " is DISABLED in scenery_packs.ini — "
                                 "nothing is read, classified or written")
                    counts["airports"] += 1
                    continue
                sampler = MeshElevationSampler(mesh_path, plan_.bounds())

                def _sample(lat: float, lon: float, _s=sampler):
                    try:
                        s = _s.sample_at(lat, lon)
                    except OutsideMeshError:
                        return None
                    z = float(s.elevation_metres)
                    return (z, bool(s.is_water)) if math.isfinite(z) else None

                def _sample_many(lats, lons, _s=sampler):
                    """The same grid index, one call for a whole batch
                    (RULINGS 2026-09-12g).  Point-for-point identical to
                    ``_sample`` — the non-finite guard included."""
                    out = []
                    for s in _s.sample_many(lats, lons):
                        if s is None:
                            out.append(None)
                            continue
                        z = float(s.elevation_metres)
                        out.append((z, bool(s.is_water))
                                   if math.isfinite(z) else None)
                    return out

                _sample.many = _sample_many

                # THE PLACEMENT PATH (11e (3); the ONLY object stage
                # since 2026-09-12s) — no seat is computed
                pc = _place_objects(plan_, law, _sample, tile, patch_dir,
                                    write_enabled, measure_only)
                counts["airports"] += 1
                for k, v in pc.items():
                    if k in ("packs_written",):
                        continue
                    counts["placement_" + k] = counts.get("placement_" + k, 0) + int(v)
                if pc.get("packs_written"):
                    written_packs.add(plan_.pack_root)
            except Exception as exc:
                counts["airports_failed"] += 1
                UI.vprint(1, f"  [v2 rebake] {icao}: placement failed ({exc}); continuing")
                UI.vprint(2, traceback.format_exc())
        counts["packs_written"] = len(written_packs)
        for pr in sorted(written_packs):
            UI.vprint(1, f"  [v2 rebake] pack {os.path.basename(pr)} was modified "
                         "(originals kept as .anchor_bak) — restart X-Plane, objects are cached")
    except Exception as exc:
        UI.vprint(1, f"  [v2 rebake] failed: {exc}")
        UI.vprint(2, traceback.format_exc())
    return counts
