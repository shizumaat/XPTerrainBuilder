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
    return value


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
                           ruleset: str, dem_prov: dict, status: str) -> str:
    """The v2 twin of ``provenance.format_log_line`` — one line per airport
    at patch completion, ``engine=v2`` and the law-table digest instead of
    v1's gate census (v2 has no gates: RULINGS 2026-09-03e, no numeric law
    value lives in Python)."""
    law = (law_sha256 or "absent")[:12]
    return (f"  [provenance] {icao} patch: engine=v2 sha={sha} law={law} "
            f"ruleset={ruleset} solve={status} dem={_dem_label(dem_prov)}")


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
            dem_frame="production", production_dem_tiles=seeds,
            core_hosted=True)
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
    git = _prov.git_provenance() or {}
    sha = (git.get("sha") or "absent") + ("*" if git.get("dirty") else "")
    line = format_provenance_line(icao, sha=sha, law_sha256=digest["sha256"],
                                  ruleset=law.ruleset_key, dem_prov=dem_prov,
                                  status=status)
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


def _decision_from_seats(plan_, result, measure_only: bool):
    """A v1 ``RebakeDecision`` carrying v2's ONE delta per unit: one
    structure per resource over all its solid triangles, every vertex the
    same delta; a resource whose unit has no bake (below threshold, off
    the mesh, measure-only) is listed in ``skipped`` and still registered
    by anchor, so v1's reversion pass puts an earlier bake back."""
    from . import obj8_reader
    from .object_anchor import RebakeDecision, Structure
    structures = []
    deltas: dict[str, dict[int, float]] = {}
    ground: dict[str, float] = {}
    anchors: dict[str, tuple[float, float, float]] = {}
    kinds: dict[str, str] = {}
    datums: dict[str, float] = {}
    skipped: list[tuple[str, str]] = []
    for u, us in zip(plan_.units, result.units):
        if us.held:
            # HELD: unknown to the decision, so v1's reversion pass leaves
            # the live bytes exactly as they are (reported, never reverted)
            continue
        for m in u.members:
            r = m.resource
            anchors[r] = (u.anchor[0], u.anchor[1], m.heading_deg)
            if us.anchor_ground_m is not None:
                ground[r] = float(us.anchor_ground_m)
            if measure_only:
                skipped.append((r, "measure-only: modify_custom_airports is off"))
                continue
            if not us.bakes:
                skipped.append((r, us.skip_reason or "no seat"))
                continue
            try:
                geom = obj8_reader.load_object_file(m.authored_path)
            except (OSError, ValueError) as exc:
                skipped.append((r, f"authored file unreadable: {exc}"))
                continue
            tris = list(geom.solid_triangles)
            if not tris:
                skipped.append((r, "no solid triangle: nothing to seat"))
                continue
            vids = sorted({i for t in tris for i in t})
            deltas[r] = {i: float(us.delta_m) for i in vids}
            ys = [geom.vertices[i][1] for i in vids]
            structures.append(Structure(
                triangles_by_resource={r: tris}, surface_area_square_metres=0.0,
                centroid_latitude=u.anchor[0], centroid_longitude=u.anchor[1],
                minimum_base_y_by_resource={r: min(ys)}, is_ground_touching=True,
                ground_span_metres=None, needs_pad=False, skip_reason=None,
                inherited_from_structure_index=None))
            kinds[r] = "v2_" + us.datum
            if us.seat_datum_m is not None:
                datums[r] = float(us.seat_datum_m)
    return RebakeDecision(structures=structures, delta_by_resource_and_vertex=deltas,
                          anchor_ground_by_resource=ground, skipped=skipped,
                          anchor_by_resource=anchors, decision_kind_by_resource=kinds,
                          seat_datum_by_resource=datums)


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
              "objects_reverted": 0,
              "vertices_offset": 0, "findings": 0, "airports_failed": 0,
              "packs_written": 0}
    try:
        patch_dir = os.path.dirname(object_anchor_worklist_path(tile))
        plans = sorted(glob.glob(os.path.join(patch_dir, "o4_v2_rebake_*.json")))
        plans = [p for p in plans if "_result_" not in os.path.basename(p)]
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

                res = _rb.seat(plan_, _sample, law)
                if write_enabled:
                    decision = _decision_from_seats(plan_, res, measure_only)
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
                UI.vprint(1, f"  [v2 rebake] {icao}: {rc['units']} unit(s) "
                             f"({rc['deck_units']} deck-founded): {rc['baked']} seated "
                             f"({len(report.objects_written)} object(s) written, "
                             f"{report.vertices_offset_total} vertices), "
                             f"{rc['below_threshold']} below the {law.tables.structures.rebake.min_delta_m} m "
                             f"threshold, {rc['held']} held (no land witness: current "
                             f"bytes kept), {rc['skipped']} unseatable, "
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
