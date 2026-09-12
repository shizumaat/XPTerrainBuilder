"""The auto-patch-v2 engine INSIDE the v1 tile build (RULINGS 2026-09-03d:
v2 ships beside v1; 2026-09-04g OWED: "the app's engine selection").

``auto_patch.driver`` owns the tile: CIFP discovery, the manual-patch and
apt.dat gates, the freshness gate, the per-airport worker pool, the
results loop, the manifest verification and the JSONL failure events.
None of that is v2's to re-implement.  What v2 replaces is ONE step —
the per-airport "build + write + verify" — and this module is that step
for ``auto_patch_engine = v2``: it runs ``auto_patch_v2.pipeline.build``
on the tile build's OWN production DEM (``tile.dem``, handed to the
worker exactly as v1's worker receives it — reused, never re-composed),
places the current tile's patch and sidecar where ``include_patches``
reads them (``Patches/<block>/<tile>/<ICAO>_auto.patch.osm``), writes the
v2 verify census into the same per-airport log part the driver
concatenates into ``auto_patch_verify_debug.log``, and returns the SAME
result record ``_build_write_verify_one`` returns — so the driver's
results loop, manifest check and ``AutoPatchFailed`` events are one
path for both engines.

A v2 solve that is not optimal/feasible, or a v2 refusal (a cold DEM
frame, a law-table error, a loader refusal), is a per-airport build
FAILURE with the IIS / refusal text in the verify debug log — never a
silent skip and never a stale patch left for the mesh to drape.

No environment is read here or in anything under ``auto_patch_v2``: the
engine choice arrives on the task record, resolved once per tile from
the cfg key by :func:`resolved_auto_patch_engine`.
"""
from __future__ import annotations

import json
import os
import re
import time
import traceback
import typing as _t
import urllib.parse

ENGINE_V1 = "v1"
ENGINE_V2 = "v2"
ENGINES = (ENGINE_V1, ENGINE_V2)

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
    """``tile.auto_patch_engine`` normalised to ``"v1"`` / ``"v2"``.

    The cfg key is registered in ``O4_Cfg_Vars.cfg_tile_vars`` (global +
    per-tile scope; ``Tile.read_from_config`` puts the per-tile value on
    the instance).  An unregistered value REFUSES rather than falling back
    to v1: a tile the owner set to ``v2`` with a typo must not quietly
    build with the engine they were trying to compare against.
    """
    raw = getattr(tile, "auto_patch_engine", ENGINE_V1)
    value = str(raw if raw is not None else ENGINE_V1).strip().lower() or ENGINE_V1
    if value not in ENGINES:
        raise ValueError(
            f"auto_patch_engine={raw!r} is not one of {ENGINES} — set the "
            f"tile's (or the global) Ortho4XP config to 'v1' or 'v2'.")
    # THE ENGINE IS A GLOBAL FACT (owner sim read 2026-09-10, RULINGS
    # 2026-09-10c): the owner's −13-077 / −13-078 tile cfgs carried a
    # stale ``auto_patch_engine=v1`` line (stamped when the key's default
    # was v1) and out-ranked the global ``v2`` — SPJC and SPLP shipped on
    # the retired engine in app 1.0.300 while every other tile ran v2, and
    # nothing said so but one ``[provenance]`` line.  A per-tile value that
    # disagrees with the global config file is IGNORED, loudly.
    global_value = _global_cfg_engine()
    if global_value is not None and global_value != value:
        from O4_UI_Utils import lvprint as _lvprint
        _lvprint(0, f"   Auto-patch: engine {value!r} in the tile's own cfg is "
                    f"IGNORED — the global Ortho4XP.cfg says {global_value!r} "
                    f"and the engine is a global setting (RULINGS 2026-09-10c). "
                    f"Delete the tile cfg's auto_patch_engine line to silence this.")
        return global_value
    return value


def _global_cfg_engine() -> str | None:
    """``auto_patch_engine`` as the GLOBAL ``Ortho4XP.cfg`` file spells it
    (``O4_Config_Utils.global_cfg_file``), or ``None`` when the file or the
    key is absent / unregistered.  Read from the file, not the module
    globals: the globals already carry the tile layer once a tile has been
    read."""
    try:
        import O4_Config_Utils as _CFG
        path = _CFG.global_cfg_file
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("auto_patch_engine="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                    return v if v in ENGINES else None
    except (OSError, AttributeError, ImportError):
        return None
    return None


def _fresh_pack_dump(xplane_root: str, icao: str, lat: int, lon: int) -> str | None:
    """The engine's DSFTool text dump of the serving pack's tile DSF,
    regenerated by the v1 cache when the DSF is newer (``dsf_reader.
    ensure_dsf_text_path`` — mtime-keyed, ``<tile>.dsf.<tag>.text``).
    v2 never runs DSFTool itself (its ``find_text_dump`` REFUSES a stale
    dump); the app's driver is where a changed pack is re-dumped.  OTHH
    gained tunnel wall objects on 2026-09-04 and every build until this
    read the 07-30 dump."""
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
    (``_pick_best_apt_dat_against_osm``, on the task as ``apt_dat_path``)
    — that is the datum the comparison is made against; which apt.dat v2
    itself read is in its report and the provenance line."""
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
            dsf_dump_path=_fresh_pack_dump(task["xp_root"], icao, lat, lon),
            dem_frame="production", production_dem_tiles=seeds,
            core_hosted=True,
            road_grade_limit=task.get("road_grade_limit"),
            lane_width_m=task.get("lane_width"))
        law = Law.for_airport(icao)
        scratch = _scratch_dir(task)
        os.makedirs(scratch, exist_ok=True)
        cfg = Config(header_extra=_stamp_header(task))
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
    # A VERIFY DEFECT never ships (lane v2padflat 2026-09-05): a building
    # pad that is not one flat value (RULINGS 03h) and that no 04t(1)
    # relaxation names is a solver/emit invariant broken, not a residual
    # — the airport fails by name, like a non-optimal solve.
    defects = (res.report.get("verify") or {}).get("defects") or {}
    if defects:
        rows = (res.report.get("verify") or {}).get("rows") or {}
        text = "\n".join(f"[v2:{k}] {json.dumps(r, default=str)}"
                          for k in defects for r in rows.get(k, []))
        return {"icao": icao, "ok": False, "stage": "verify", "engine": ENGINE_V2,
                "error": (f"[v2] verify found a structural DEFECT in {icao}: "
                          + ", ".join(f"{k} {n}" for k, n in defects.items())
                          + " — a building pad is not one flat value (RULINGS "
                          "2026-09-03h) and no 04t(1) relaxation names it; the "
                          f"rows are in {os.path.join(scratch, icao + '.report.json')}"),
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
        with open(task["verify_log_path"], "w") as lf:
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
# THE RE-BAKE AFTER THE MESH (RULINGS 2026-09-04i 04f-1)
# ══════════════════════════════════════════════════════════════════════════
# v1's Phase 2 (``post_mesh.rebake_dsf_objects``) runs at the END of
# ``O4_Mesh_Utils.build_mesh`` / ``sort_mesh``; under ``auto_patch_engine =
# v2`` the same hook routes HERE instead (one baker per pack per build —
# two would fight through the reversion pass).  The v2 law half is pure
# (``auto_patch_v2.emit.rebake.seat`` over the tile build's own
# ``o4_v2_rebake_<ICAO>.json`` plans and a sampler of the built mesh);
# this function is the I/O half: it reuses v1's mesh sampler, v1's
# ordering / protected-root guards and — the ONE writer both engines
# share — ``object_rebake.apply`` with its ``.anchor_bak`` discipline,
# provenance sidecar and reversion pass.  ``modify_custom_airports`` is
# honoured exactly as v1 honours it: OFF = measure-only, nothing is baked,
# and an earlier bake is put back to the authored bytes.

REBAKE_RESULT_FILENAME = "o4_v2_rebake_result_{icao}.json"

#: RULINGS 2026-09-09w (3): the pipeline's own plan file names —
#: ``o4_v2_rebake_<ICAO>.json`` (``model.rebake.PLAN_FILENAME``) and
#: nothing else in the patch directory.  ``o4_v2_rebake_result_<ICAO>.json``
#: (this module's own output) and a tool's ``o4_v2_rebake_<ICAO>.seat.json``
#: are NOT plans.
_PLAN_NAME_RE = re.compile(r"^o4_v2_rebake_(?!result_)[A-Za-z0-9]{2,8}\.json$")


def _place_rebake_plan(task: dict, src_plan, icao: str) -> str | None:
    """Copy the pipeline's plan beside the patch (``Patches/<tile>/``)."""
    import shutil
    if src_plan is None or not os.path.isfile(str(src_plan)):
        return None
    from auto_patch_v2.emit.rebake import PLAN_FILENAME
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


def _line_drape(geom, comps, line_stations, anchor, heading_deg) -> dict:
    """The per-vertex deltas of a LINE OBJECT's draped components (RULINGS
    2026-09-10bb): each vertex takes the delta of the station NEAREST it
    in plan.  The vertex world position is the anchor plus the OBJ8 offset
    rotated by the heading (``obj8`` module doc: x east, z SOUTH,
    ``east = x·cos h − z·sin h``, ``north = −(x·sin h + z·cos h)``),
    converted with the local metres per degree — a nearest-station test
    over a few kilometres, where the frame's own projection and a local
    ENU agree to well under the station spacing."""
    import math as _m

    import numpy as _np

    from auto_patch_v2.airport.line_object import station_deltas_at
    by_comp: dict[int, list[tuple[float, float, float]]] = {}
    for comp, la, lo, d in line_stations:
        by_comp.setdefault(int(comp), []).append((float(la), float(lo), float(d)))
    lat0, lon0 = float(anchor[0]), float(anchor[1])
    m_lat = 111_132.954 - 559.822 * _m.cos(2 * _m.radians(lat0)) \
        + 1.175 * _m.cos(4 * _m.radians(lat0))
    m_lon = 111_412.84 * _m.cos(_m.radians(lat0)) - 93.5 * _m.cos(3 * _m.radians(lat0))
    h = _m.radians(float(heading_deg))
    sn, cs = _m.sin(h), _m.cos(h)
    out: dict[int, float] = {}
    for ci, st in by_comp.items():
        if not (0 <= ci < len(comps)) or not st:
            continue
        ids = _np.unique(_np.asarray(comps[ci].tris).reshape(-1))
        v = _np.asarray(geom.vertices)[ids]
        east = v[:, 0] * cs - v[:, 2] * sn
        north = -(v[:, 0] * sn + v[:, 2] * cs)
        lats = lat0 + north / m_lat
        lons = lon0 + east / m_lon
        for i, d in zip(ids.tolist(), station_deltas_at(st, lats, lons).tolist()):
            out[int(i)] = float(d)
    return out


def _decision_from_seats(plan_, result, measure_only: bool,
                         contact_tol_m: float = 0.0,
                         plate_gap_max_m: float = 0.0,
                         rigid_stats: dict | None = None):
    """A v1 ``RebakeDecision`` carrying v2's seat PER VERTEX (RULINGS
    2026-09-06g): a structure-seated member's every solid vertex takes
    the unit's one delta; a cluster-seated member's vertices take their
    PART's cluster delta (``MemberSeat.part_deltas``: ``(component,
    cluster, delta | None)`` — ``None`` keeps the authored y, so one file
    may carry several deltas and unmoved parts).  The components are
    v2's own deterministic partition of the AUTHORED file
    (``auto_patch_v2.airport.obj8.solid_components``), the same the plan
    was built from.  A resource with no bake (below threshold, held,
    facility, off the mesh, measure-only) is listed in ``skipped`` and
    still registered by anchor, so v1's reversion pass puts an earlier
    bake back."""
    from auto_patch_v2.airport import obj8 as _obj8
    from auto_patch_v2.airport import rigid as _rigid
    from .object_anchor import RebakeDecision, Structure
    structures = []
    deltas: dict[str, dict[int, float]] = {}
    ground: dict[str, float] = {}
    anchors: dict[str, tuple[float, float, float]] = {}
    kinds: dict[str, str] = {}
    datums: dict[str, float] = {}
    notes: dict[str, str] = {}
    skipped: list[tuple[str, str]] = []
    for u, us in zip(plan_.units, result.units):
        if us.held:
            # HELD: unknown to the decision, so v1's reversion pass leaves
            # the live bytes exactly as they are (reported, never reverted)
            continue
        by_res = {s.resource: s for s in us.members}
        for m in u.members:
            r = m.resource
            ms = by_res[r]
            anchors[r] = (u.anchor[0], u.anchor[1], m.heading_deg)
            if us.anchor_ground_m is not None:
                ground[r] = float(us.anchor_ground_m)
            if measure_only:
                skipped.append((r, "measure-only: modify_custom_airports is off"))
                continue
            if ms.facility:
                # RULINGS 2026-09-05p (at cluster level 06g): a facility
                # member keeps its authored y — the excluded path, so v1's
                # reversion pass restores an earlier bake and the
                # provenance records the exclusion
                skipped.append((r, f"facility member (05p): stands more than the contact band "
                                   f"below the mesh — keeps its authored y; the cutout is the "
                                   f"basin pass's affair ({us.unit_id})"))
                continue
            if not (us.bakes and ms.bakes):
                skipped.append((r, us.skip_reason or ms.note or "no seat"))
                continue
            try:
                geom = _obj8.parse_obj8(m.authored_path)
            except (OSError, ValueError) as exc:
                skipped.append((r, f"authored file unreadable: {exc}"))
                continue
            comps = _obj8.solid_components(geom)
            if not comps:
                skipped.append((r, "no solid triangle: nothing to seat"))
                continue
            if ms.delta_m is not None and not ms.part_deltas:
                by_comp = {i: float(ms.delta_m) for i in range(len(comps))}
            else:
                by_comp = {comp: float(d) for comp, _k, d in ms.part_deltas
                           if d is not None and 0 <= comp < len(comps)}
            if not by_comp:
                skipped.append((r, ms.note or "no part seated"))
                continue
            # RULINGS 2026-09-09b (5): an object's CONNECTED geometry moves
            # as one rigid body, and a horizontal plane is never split from
            # the walls that carry it.  The seat mints deltas only for the
            # THICKNESS-GATED components (the witness gate, 08-26 §2.1), so
            # every floor/ceiling plane came out with none and stayed at its
            # authored y while its walls moved (HECA 15,716 planes, to 45 m;
            # OTHH the 44 planes of the interchange drainage basins).  Each
            # free component follows the carrier it TOUCHES (09z (4):
            # a plane always follows its walls, held or not — the
            # identity spacing is the contact test), nearest only when
            # nothing touches.
            # a component the seat RULED to stay (a facility cluster 05p, a
            # cluster under min_delta_m, an A3 refusal) keeps its authored y:
            # the completion covers only what the seat never considered
            held = {comp for comp, _k, d in ms.part_deltas if d is None}
            n_free = len(comps) - len(by_comp) - len(held - set(by_comp))
            by_comp = _rigid.complete_component_deltas(geom, comps, by_comp, held,
                                                      contact_tol_m, plate_gap_max_m,
                                                      rigid_stats)
            per_vertex: dict[int, float] = {}
            for ci, d in by_comp.items():
                for i in set(comps[ci].tris.reshape(-1).tolist()):
                    per_vertex[i] = d
            # THE LINE OBJECT DRAPES (owner RULINGS 2026-09-10bb, spec §16.1
            # rule 3): a fence / kerb / jet-blast line follows the ground it
            # stands on — its component's vertices take the delta of the
            # SEGMENT STATION nearest them in plan, not the body's one
            # median.  The stations travel in the seat RESULT, so the write
            # half stays offline (no mesh here, and none in the censuses).
            if ms.line_stations:
                per_vertex.update(_line_drape(geom, comps, ms.line_stations,
                                              u.anchor, m.heading_deg))
            if not per_vertex:
                skipped.append((r, ms.note or "no part seated"))
                continue
            deltas[r] = per_vertex
            ys = [float(geom.vertices[i][1]) for i in per_vertex]
            tris = [tuple(int(x) for x in t) for c in comps for t in c.tris]
            structures.append(Structure(
                triangles_by_resource={r: tris}, surface_area_square_metres=0.0,
                centroid_latitude=u.anchor[0], centroid_longitude=u.anchor[1],
                minimum_base_y_by_resource={r: min(ys)}, is_ground_touching=True,
                ground_span_metres=None, needs_pad=False, skip_reason=None,
                inherited_from_structure_index=None))
            kinds[r] = "v2_" + ms.datum
            note = ms.note or ""
            if n_free:
                note = (note + "; " if note else "") + (
                    f"{n_free} free component(s) follow the carrier they touch "
                    "(09b (5)/09z (4): a plane is never split from its walls)")
            if note:
                notes[r] = note
            if us.datum != "cluster" and us.seat_datum_m is not None:
                datums[r] = float(us.seat_datum_m)
            elif ms.delta_m is not None and us.anchor_ground_m is not None:
                datums[r] = float(us.anchor_ground_m) + u.agl_m + float(ms.delta_m)
            elif us.anchor_ground_m is not None:
                # several deltas in one file: the datum is the base, the
                # provenance records the spread (delta_range_m)
                datums[r] = float(us.anchor_ground_m) + u.agl_m
    return RebakeDecision(structures=structures, delta_by_resource_and_vertex=deltas,
                          anchor_ground_by_resource=ground, skipped=skipped,
                          anchor_by_resource=anchors, decision_kind_by_resource=kinds,
                          seat_datum_by_resource=datums, seat_note_by_resource=notes)


# ── THE PLACEMENT PATH (owner RULINGS 2026-09-11b / 11e (3)) ─────────────
# ``[rebake] placement = "agl"``: X-Plane places every object on the
# terrain under its own anchor.  NO SEAT IS COMPUTED — the plan is built
# (conversions for every MSL/AGL row, splits with coarsened bodies and
# placed anchors), the cut files are written into the pack's ``objects/``
# under new names, the DSF is edited, encoded, verified and backed up, the
# READ path's text-dump cache is refreshed and the placement plan lands
# beside the patch.  ``"seat"`` runs the pre-11b path below, unchanged:
# the ONE permitted gate, a mechanism awaiting the owner's sim read (29e).

def object_stage_is_placement(law) -> bool:
    """THE ONE GATE (owner RULINGS 2026-09-11e (3)): ``[rebake] placement``
    — ``"agl"`` routes the object stage through the PLACEMENT path below
    (no seat is computed); anything else runs the pre-11b seat unchanged."""
    return str(law.tables.structures.rebake.placement) == "agl"


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

    _surface.many = _surface_many
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
    pads, rims = (), ()
    graded = graded_surface_path(patch_dir, plan_.icao)
    if os.path.isfile(graded):
        try:
            pads, rims = _pp.pads_rims_from_graded(graded)
            UI.vprint(1, f"  [v2 placement] {plan_.icao}: design surface "
                         f"{len(pads)} object pad(s), {len(rims)} structure rim(s)")
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
        carrier_fill_min=law.tables.structures.placement.carrier_fill_min,
        coarsen_reach_m=law.tables.structures.placement.coarsen_reach_m,
        pads=pads, rims=rims,
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
    res = _pw.apply_plan(
        plan, files, _DSFR._dsftool_path() or "DSFTool", patch_dir=patch_dir,
        allow_live_install=True,
        refresh_dump=lambda p, _c=cache: _DSFR.ensure_dsf_text_path(p, _c),
        engine_version=_engine_version(), law_digest=digest)
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
    """Re-seat every object of the airports v2 patched on ``tile``
    against the mesh just built (see the section comment).  Never raises
    (the mesh hook wraps it too); returns the counts for the summary."""
    import glob
    import math
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from auto_patch_v2.emit import rebake as _rb
    from auto_patch_v2.law import Law
    from . import object_rebake
    from .mesh_sampler import MeshElevationSampler, OutsideMeshError
    from .post_mesh import (_is_protected_scenery_root, _mesh_is_newer_than_alt,
                            object_anchor_worklist_path)

    counts = {"airports": 0, "units": 0, "units_baked": 0, "units_below_threshold": 0,
              "units_skipped": 0, "units_held": 0, "objects_written": 0,
              "objects_reverted": 0, "clusters": 0, "clusters_baked": 0, "pad_requests": 0,
              "vertices_offset": 0, "findings": 0, "airports_failed": 0,
              "packs_written": 0}
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
            UI.vprint(1, f"  [v2 rebake] mesh not found at {mesh_path}; re-seat skipped")
            return counts
        if not _mesh_is_newer_than_alt(tile, mesh_path):
            UI.vprint(0, "  [v2 rebake] STALE MESH: the mesh predates the tile's .alt — "
                         "re-seat SKIPPED; rebuild the mesh after the elevation step")
            return counts
        measure_only = not getattr(tile, "modify_custom_airports", True)
        if measure_only:
            UI.vprint(1, "  [v2 rebake] modify_custom_airports is off — measure-only: "
                         "no object is reseated and any earlier bake is put back")
        # v1's engine-wide kill switch (``O4_DSF_OBJECT_REANCHOR=0`` "leaves
        # every pack byte-identical"; function-local import so tests drive
        # it): the seat still runs and its result sidecar is written — the
        # measurement is the product — but nothing is applied and nothing
        # is reverted.
        from .config import DSF_OBJECT_REANCHOR
        write_enabled = bool(DSF_OBJECT_REANCHOR)
        if not write_enabled:
            UI.vprint(1, "  [v2 rebake] DSF_OBJECT_REANCHOR is off — seats are measured "
                         "and recorded, no pack file is written or reverted")
        written_packs: set[str] = set()
        for plan_path in plans:
            icao = "?"
            try:
                with open(plan_path) as fh:
                    plan_ = _rb.RebakePlan.from_json(fh.read())
                icao = plan_.icao
                law = Law.for_airport(icao)
                if not plan_.units:
                    UI.vprint(1, f"  [v2 rebake] {icao}: no unit to seat "
                                 f"({len(plan_.skipped)} resource(s) skipped at plan time)")
                    counts["airports"] += 1
                    continue
                if not os.path.isdir(plan_.pack_root) or \
                        _is_protected_scenery_root(plan_.pack_root):
                    UI.vprint(1, f"  [v2 rebake] {icao}: pack {plan_.pack_root} is not a "
                                 "writable Custom Scenery pack — re-seat skipped")
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

                if object_stage_is_placement(law):
                    # 11e (3): the PLACEMENT path — no seat is computed
                    pc = _place_objects(plan_, law, _sample, tile, patch_dir,
                                        write_enabled, measure_only)
                    counts["airports"] += 1
                    for k, v in pc.items():
                        if k in ("packs_written",):
                            continue
                        counts["placement_" + k] = counts.get("placement_" + k, 0) + int(v)
                    if pc.get("packs_written"):
                        written_packs.add(plan_.pack_root)
                    continue

                res = _rb.seat(plan_, _sample, law)
                if write_enabled:
                    rigid_stats: dict = {}
                    decision = _decision_from_seats(
                        plan_, res, measure_only,
                        law.tables.emit.identity.min_distinct_spacing_m,
                        law.tables.structures.rebake.plate_gap_max_m, rigid_stats)
                    if rigid_stats:
                        # RULINGS 2026-09-10u (2): how the free components
                        # found their carrier — touched / eave gap / nearest
                        print(f"    [v2] rigid carriers: {rigid_stats}")
                    report = object_rebake.apply(decision, plan_.pack_root, mesh_path)
                else:
                    report = object_rebake.RebakeReport()
                rc = res.counts()
                counts["airports"] += 1
                counts["units"] += rc["units"]
                counts["units_baked"] += rc["baked"]
                counts["units_below_threshold"] += rc["below_threshold"]
                counts["units_skipped"] += rc["skipped"]
                counts["units_held"] += rc["held"]
                counts["clusters"] += rc["clusters"]
                counts["clusters_baked"] += rc["clusters_baked"]
                counts["pad_requests"] += rc["pad_requests"]
                counts["findings"] += rc["findings"]
                counts["objects_written"] += len(report.objects_written)
                counts["objects_reverted"] += len(report.objects_reverted)
                counts["vertices_offset"] += report.vertices_offset_total
                if report.objects_written or report.objects_reverted:
                    written_packs.add(plan_.pack_root)
                out = {"icao": icao, "plan": plan_path, "mesh": mesh_path,
                       "measure_only": measure_only, "write_enabled": write_enabled,
                       "seat": res.to_dict(),
                       "apply": {"objects_written": list(report.objects_written),
                                 "objects_reverted": list(report.objects_reverted),
                                 "vertices_offset": report.vertices_offset_total,
                                 "skipped": [list(s) for s in report.skipped],
                                 "reversions_missing_backup":
                                     list(report.reversions_missing_backup),
                                 "partially_baked": [list(s) for s in report.partially_baked],
                                 "provenance_path": report.provenance_path}}
                rp = os.path.join(patch_dir, REBAKE_RESULT_FILENAME.format(icao=icao))
                with open(rp + ".tmp", "w") as fh:
                    json.dump(out, fh, indent=1, default=str)
                os.replace(rp + ".tmp", rp)
                UI.vprint(1, f"  [v2 rebake] {icao}: {rc['structures']} structure(s), "
                             f"{rc['clusters']} cluster(s) ({rc['cut_edges']} edge(s) cut): "
                             f"{rc['clusters_baked']} seated, {rc['clusters_below_threshold']} "
                             f"below the {law.tables.structures.rebake.min_delta_m} m threshold, "
                             f"{rc['clusters_refused']} refused, {rc['clusters_facility']} facility, "
                             f"{rc['clusters_held']} held, {rc['pad_requests']} pad request(s); "
                             f"{rc['units']} unit(s) ({rc['deck_units']} deck-founded, "
                             f"{rc['plate_units']} plate): {rc['baked']} bake, {rc['held']} held; "
                             f"{len(report.objects_written)} object(s) written "
                             f"({report.vertices_offset_total} vertices, "
                             f"{rc['members_multi_delta']} with several deltas), "
                             f"{len(report.objects_reverted)} reverted, "
                             f"{rc['findings']} finding(s) -> {os.path.basename(rp)}")
                for u in res.units:
                    for f in u.findings:
                        UI.vprint(2, f"  [v2 rebake] {icao}: {u.unit_id} "
                                     f"{u.resources[0]}{'…' if len(u.resources) > 1 else ''}: {f}")
                for r in report.reversions_missing_backup:
                    UI.vprint(0, f"  [v2 rebake] {icao}: {r} carries a stale bake but its "
                                 ".anchor_bak is missing — left untouched, NOT reverted")
            except Exception as exc:
                counts["airports_failed"] += 1
                UI.vprint(1, f"  [v2 rebake] {icao}: re-seat failed ({exc}); continuing")
                UI.vprint(2, traceback.format_exc())
        counts["packs_written"] = len(written_packs)
        for pr in sorted(written_packs):
            UI.vprint(1, f"  [v2 rebake] pack {os.path.basename(pr)} was modified "
                         "(originals kept as .anchor_bak) — restart X-Plane, objects are cached")
    except Exception as exc:
        UI.vprint(1, f"  [v2 rebake] failed: {exc}")
        UI.vprint(2, traceback.format_exc())
    return counts
