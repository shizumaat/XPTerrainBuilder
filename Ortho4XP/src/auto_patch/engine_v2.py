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
import time
import traceback
import urllib.parse

import O4_Tile_Failures as _FAIL

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
    "sentinel_elevation": "an emitted vertex stands outside the ground "
                          "envelope of its airport — a sentinel, not "
                          "geometry (issue #623)",
}

#: The v2 pipeline's stages as the progress window's phases (the driver's
#: ``BuildProgress`` banner + bar).  Issue #136 (RULINGS 2026-09-30ai): the
#: old five-step table put pack partition + structures + planar under ONE
#: ``[40/100]`` banner that ran ~26 min silent at OTHH (75 % of its build)
#: on weights from 2026-09-04 ("planar ~20 %").  RE-MEASURED 2026-09-30 from
#: the recorded v2 stage clocks (``<ICAO>.report.json`` ``wall_s`` + the
#: planar reads' own ``read_s`` / ``grade_geometry_s``; the build-time
#: ledger ``~/.ortho4xp/auto_patch_build_times`` holds v1 labels only, last
#: written 2026-09-16): per airport the median seconds of its last five
#: harness builds, then the MEDIAN SHARE across OTHH / HECA / KCLT / SPJC /
#: CYXY — load 6.4, partition 13.5, classify+structures 17.0, planar 9.9,
#: constraints 19.6, solve 13.0, emit+verify 17.1 (%, sum 96.6), scaled
#: to 100.  A per-airport time model would do better (OTHH is 54 %
#: structures, CYXY 28 % solve); the heartbeat covers what a static split
#: cannot.
V2_PHASE_LABELS = [
    "Loading airport, pack & production DEM",
    "Partitioning the pack",
    "Classifying & reading structures (door wells, wall corridors, at-grade)",
    "Building the planar map",
    "Generating the law constraints",
    "Solving the surface (HiGHS LP)",
    "Emitting the patch & verifying",
]
V2_PHASE_WEIGHTS = [7, 14, 18, 10, 20, 13, 18]

#: The ``[ICAO] <stage> …`` line that marks a stage FINISHED -> the 1-based
#: phase that begins (``pack`` is ``[ICAO] pack partition``); ``structures``
#: is the ``auto_patch_v2.model.pulse.mark`` inside ``planar.build`` where
#: the structure reads end and the arrangement begins.  ADVANCE-TO, never
#: step-once: a missed boundary skips a phase, it cannot shift every label.
_STAGE_DONE_TO_PHASE = {"load": 2, "pack": 3, "structures": 4, "planar": 5,
                        "constraints": 6, "solve": 7}


class V2Progress:
    """The v2 build's progress wiring (issue #136) — ONE implementation for
    the app's driver (:func:`build_write_verify_one_v2`) and the harness
    (``tools/harness/build_airport.py``): the step banners from the stage
    lines and the pulse marks, and the :class:`progress.Heartbeat` reading
    the pulse.  Use as a context manager; :meth:`line` is the ``out`` hook."""

    def __init__(self, icao: str, *, period_s: float | None = None):
        from auto_patch_v2.model import pulse as _pulse
        from . import progress as _progress
        self._pulse = _pulse
        self.bp = _progress.BuildProgress(icao, V2_PHASE_LABELS, V2_PHASE_WEIGHTS)
        _progress._current = self.bp
        self.hb = _progress.Heartbeat(
            self.bp.heartbeat, self.bp.running_step, _pulse.describe,
            period_s=_progress.HEARTBEAT_S if period_s is None else period_s)
        self._unlisten = None

    def advance(self, stage: str) -> None:
        k = _STAGE_DONE_TO_PHASE.get(stage)
        while k is not None and self.bp._done < min(k, self.bp.total):
            self.bp.step()

    def line(self, line: str) -> None:
        head = line.split("] ", 1)[1] if line.startswith("[") else ""
        self.advance(head.split(" ", 1)[0])

    def __enter__(self):
        self._pulse.clear()
        self.bp.step()
        self._unlisten = self._pulse.listen(self.advance)
        self.hb.start()
        return self

    def __exit__(self, *exc):
        self.hb.stop()
        if self._unlisten:
            self._unlisten()
        self._pulse.clear()
        return False


def v2_line_verbosity(line: str) -> int:
    """The verbosity a v2 build-log line prints at in the TILE build's log.

    0 — always — for the work pool's account (``[pool] workers …``, a
    ``[pool] FELL BACK`` and its reason, a reader held on one core); 1 for
    the rest.  The auto-patch log knob runs the airport builds at
    verbosity 0, so the per-stage lines stay quiet there — but whether an
    airport's stages ran on every core or fell back to one must be in the
    tile's own log, as the ``[v2 rebake]`` lines are, and not only in the
    airport's ``report.json`` (issue #395)."""
    return 0 if line.lstrip().startswith("[pool]") else 1


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
        from auto_patch_v2.airport.dsf_write import DsfToolError
    except Exception as exc:                # the load stage will refuse loudly
        import logging
        logging.getLogger(__name__).warning(
            "pack dump refresh skipped for %s: %s", icao, exc)
        return None
    # THE REFRESH NAMES ITS OWN FAILURE (#560).  A pack DSF that EXISTS and
    # cannot be dumped used to answer ``None`` here, and the load stage then
    # refused with "the pack DSF is newer than every cached text dump" —
    # the wrong cause, and one no retry could clear (2026-10-11: DSFTool
    # crashed on a stock Global Airports tile, six airports refused twice).
    try:
        return _DSFR.ensure_dsf_text_path(
            dsf_path,
            _dsf2.mod_cache_dir(FNAMES.airport_mod_cache_root(), sel.name),
            raise_on_failure=True)
    except DsfToolError as exc:
        raise DsfToolError(
            f"{icao}: the scenery pack {sel.name!r} cannot be read — {exc}. "
            "Nothing was left in the cache; the next build tries again."
        ) from exc
    except Exception as exc:                # the load stage will refuse loudly
        import logging
        logging.getLogger(__name__).warning(
            "pack dump refresh skipped for %s: %s", icao, exc)
        return None


def _pack_dump_naming_its_pack(xplane_root: str, icao: str, lat: int,
                               lon: int) -> str | None:
    """:func:`fresh_pack_dump`, with the serving PACK'S NAME attached to
    whatever exception leaves it (``failure_params``, issue #562): the
    user's message then names the pack whatever class arrives."""
    try:
        return fresh_pack_dump(xplane_root, icao, lat, lon)
    except Exception as exc:
        if not getattr(exc, "failure_params", None):
            try:
                from auto_patch_v2.airport.pack import select_pack
                sel = select_pack(xplane_root, icao)
                if sel is not None:
                    exc.failure_params = {"pack": sel.name}
            except Exception:
                pass
        raise


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
    prog = None
    try:
        import O4_File_Names as FNAMES
        from auto_patch_v2.airport.load import Inputs
        from auto_patch_v2.law import Law, law_tables_digest
        from auto_patch_v2.pipeline.build import Config, build
        from . import provenance as _prov

        lat, lon = int(task["tile_lat"]), int(task["tile_lon"])
        digest = law_tables_digest()
        if not digest["sha256"]:
            raise RuntimeError(
                f"v2 law tables are MISSING under {digest['dir']} — this "
                f"engine build carries no *.toml law files (a frozen engine "
                f"whose datas omitted them); v2 never falls back to v1.")
        prog = V2Progress(icao).__enter__()     # closed in ``finally``

        def _out(line: str) -> None:
            log_lines.append(line)
            prog.line(line)

        seeds = {(lat, lon): tile_dem} if tile_dem is not None else None
        inputs = Inputs(
            xplane_root=task["xp_root"], cifp_dir=task.get("cifp_path") or "",
            osm_root=FNAMES.OSM_dir, elevation_root=FNAMES.Elevation_dir,
            mod_cache_root=FNAMES.airport_mod_cache_root(),
            dsf_dump_path=_pack_dump_naming_its_pack(
                task["xp_root"], icao, lat, lon),
            dem_frame="production", production_dem_tiles=seeds,
            core_hosted=True,
            road_grade_limit=task.get("road_grade_limit"),
            lane_width_m=task.get("lane_width"),
            # spec §B.4 (#27): the pack walk the parent took once per tile
            pack_pristine=task.get("pack_pristine"))
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
                "error": f"[v2] {exc}", **_FAIL.record_fields(exc),
                "traceback": traceback.format_exc() + "\n--- v2 build log ---\n"
                + "\n".join(log_lines)}
    finally:
        if prog is not None:        # the heartbeat thread never outlives the build
            prog.__exit__(None, None, None)

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
    # A SOLVED VERTEX OFF THE GROUND IS A NAMED FAILURE (issue #623): the
    # solve met every row and still put a vertex outside every level the
    # airport's ground holds (``auto_patch_v2/solve/ground_band.py``) — a
    # datum that is not geometry reached it.  CZNL shipped 15 strip
    # vertices at 1,798 m beside a 535 m runway under ``status optimal``.
    off = (solve_rep.get("off_ground") or {}).get("vertices") or []
    if off:
        env = solve_rep["off_ground"].get("envelope_m")
        worst = off[0]
        return {"icao": icao, "ok": False, "stage": "solve", "engine": ENGINE_V2,
                "code": "airport_surface_off_ground",
                "error": (f"[v2] the solve for {icao} put {len(off)} vertex(es) "
                          f"outside the airport's ground envelope {env} m — "
                          f"worst {worst.get('z_m'):.2f} m over a DEM of "
                          f"{worst.get('dem_m')} m at ({worst.get('lat')}, "
                          f"{worst.get('lon')}); the report is in "
                          f"{os.path.join(scratch, icao + '.report.json')}"),
                "traceback": json.dumps(solve_rep["off_ground"], default=str)
                + "\n--- v2 build log ---\n" + "\n".join(log_lines)}
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
        rebake_plan_path = None
        _screen = getattr(res, "rebake_screen", None)
        if res.rebake_plan is not None or _screen is not None:
            from auto_patch_v2.airport import object_plan as _oplan
            rebake_plan_path = _oplan.place(os.path.dirname(dest), res.rebake_plan,
                                            icao, _screen)
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
                **_FAIL.record_fields(exc),
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
            # spec §56 (3): the fixed lines the user is WARNED with (a
            # building pad whose frontage the apron cannot be welded to
            # within the caps) — said by the parent, ``driver``
            "warnings": list(res.report.get("warnings") or ()),
            "v2": {"status": status, "law_tables": digest,
                   "ruleset": law.ruleset_key, "wall": res.wall,
                   "report": os.path.join(scratch, icao + ".report.json"),
                   "rebake_plan": rebake_plan_path,
                   "tiles": sorted(f"{a:+03d}{b:+04d}" for a, b in pieces)}}


def _place_graded_surface(task: dict, paths, icao: str) -> str | None:
    """Copy the pipeline's whole-airport graded surface beside the patch."""
    import shutil
    from auto_patch_v2.model.rebake import graded_surface_path
    src = getattr(paths, "graded", None) if paths is not None else None
    if src is None or not os.path.isfile(str(src)):
        return None
    dest = graded_surface_path(os.path.dirname(task["auto_patch_file"]), icao)
    shutil.copyfile(str(src), dest + ".tmp")
    os.replace(dest + ".tmp", dest)
    return dest
