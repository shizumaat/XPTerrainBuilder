"""Which ``O4_`` environment variables are patch settings, and which only
identify the run (issue #607).

WHY.  ``provenance.config_digest`` folds the live ``O4_`` environment into
the patch stamp ``o4_cfg`` — it has to: a FROZEN engine ships no ``.py`` for
the gate introspection to read, so a variable that is SET is the only
evidence of a gate flip there.  It took every set ``O4_`` name bar a short
exclusion list, and the names that say WHO is running the build were not on
that list: the app's process id (``O4_PARENT_PROCESS_ID``) and the number of
tiles building at once (``O4_PARALLEL_BUILD_SIBLINGS``).  Every airport
therefore rebuilt after each app launch.

THE TABLE.  Every ``O4_`` variable the engine, the app, the harness or the
release scripts read or set is in exactly one class:

* a GATE DECLARED IN ``config.py`` — enumerated from the source by
  ``provenance.introspect_config_gates``, never listed here;
* :data:`SETTINGS_OUTSIDE_CONFIG` — a setting read somewhere else, or by
  ``config.py`` in a form that introspection does not see.  DIGESTED;
* :data:`RUN_ENVIRONMENT` — who runs the build, how it is scheduled, where
  it logs, where it keeps scratch and ledgers, how it reacts to a failure.
  NEVER digested: none of them can change an emitted patch, and each entry
  says why.

A name in NO class is still digested — fail-safe: an unverifiable setting
is a rebuild — and it is NAMED: :func:`unclassified` lists it and the tile
driver prints it once per tile build.  ``tests/test_patch_env_
classification.py`` walks every ``O4_`` name the source spells as a string
and fails on one that is in no class, so a new variable is classified in
the commit that adds it.
"""
from __future__ import annotations

import os
from typing import Mapping

__all__ = [
    "RUN_ENVIRONMENT",
    "SETTINGS_OUTSIDE_CONFIG",
    "digested_environment",
    "unclassified",
]

#: Never digested.  ``name -> why it cannot change an emitted patch``.
RUN_ENVIRONMENT: dict[str, str] = {
    # ── who is running the build ────────────────────────────────────────
    "O4_PARENT_PROCESS_ID":
        "the pid the parent-death watchdog probes (the app's, or the "
        "parallel orchestrator's) — new on every launch",
    "O4_PARALLEL_BUILD_SIBLINGS":
        "how many tiles build at once; read by network fetchers to share "
        "the machine",
    # ── scheduling ──────────────────────────────────────────────────────
    "O4_PARALLEL_AIRPORTS":
        "scheduling only; the parallel path is byte-identical to serial",
    "O4_PARALLEL_AIRPORTS_N": "the airport worker cap",
    "O4_STEP_REUSE":
        "whether a tile build may skip a step whose output is current "
        "(O4_Step_Reuse, #615); a step that runs builds the same patch",
    "O4_V2_STAGE_CACHE":
        "whether the v2 airport build may serve a stage from its content-"
        "keyed record (#843); a hit is byte-identical to the build that "
        "wrote it (RULINGS 2026-10-18d)",
    "O4_TRIANGLE_IO":
        "text or binary (default) Triangle4XP exchange files (RULINGS "
        "2026-10-17c); "
        "the .mesh is byte-identical either way",
    "O4_CACHE_AWARE_ADMISSION": "tile admission order in a parallel run",
    "O4_OSM_CLASS_LIMIT": "concurrent Overpass fetches",
    "O4_IMAGERY_CLASS_LIMIT": "concurrent imagery fetches",
    "O4_IMAGERY_FETCHER":
        "which imagery downloader fetches the tiles (RULINGS 2026-10-17e); "
        "same bytes either way, never the airport patch",
    "O4_DISABLE_OSM_WARMER": "whether a parallel run warms the OSM cache",
    "O4_ENGINE_SHUTDOWN_GRACE_SECONDS": "how long a stopping engine waits",
    "O4_SECRET_BROKER_TIMEOUT_SECONDS": "how long a key request waits",
    # ── what is printed ─────────────────────────────────────────────────
    "O4_LOG_VERBOSITY": "chatter volume",
    "O4_BUILD_PROGRESS": "progress banners",
    "O4_DDS_ENCODER":
        "which DDS texture encoder converts the imagery (RULINGS 2026-10-17d); "
        "textures only, never the airport patch",
    "O4_REPORT_GRADE_AUDIT": "a warn-only audit that nothing acts on",
    # ── the stamp and its gate ──────────────────────────────────────────
    "O4_AUTO_PATCH_REBUILD":
        "the gate's own force flag, which the gate reads directly",
    "O4_PATCH_PROVENANCE": "the header block's switch, not geometry",
    "O4_PATCH_FRESHNESS_WHOLE_TREE":
        "which code digest the gate stamps as ``o4_code`` (the patch "
        "build's closure, or the whole tree, #880); the build is the same",
    # ── what happens around the patch, never in it ──────────────────────
    "O4_AUTO_PATCH_STRICT":
        "whether an airport that FAILED fails its tile; a patch that was "
        "written is the same patch",
    "O4_PACK_WRITES":
        "whether the object stage writes the scenery pack after the mesh; "
        "the patch is on disk before it runs",
    # ── where scratch, masks and ledgers are kept ───────────────────────
    "O4_INSET_SCRATCH_DIR":
        "where an elevation download is staged before it reaches the "
        "cache; the cached raster is stamped by ``o4_dem``",
    "O4_MASKS_DIR":
        "where the masks are kept; the masks step runs after the patch "
        "and the airport build reads nothing there (#346)",
    "O4_HARNESS_IN_LEDGER": "the harness's own re-entry marker",
    "O4_HARNESS_PYTHON": "which interpreter the lane ritual uses",
    "O4_RUN_LEDGER_PATH": "where the run ledger is kept",
    "O4_ARTIFACT_LEDGER_DIR": "where the artifact ledger is kept",
    "O4_ARTIFACT_LEDGER_MAX_MB": "the artifact ledger's size cap",
    "O4_CENSUS_CACHE_DIR": "where census results are cached",
    "O4_LANE_CACHE_ROOT": "where a lane's private caches are kept",
    "O4_MAIN_REPO": "where the main checkout is, for the lane ritual",
    "O4_DATA_REPO":
        "where the data repo is; every file read from it is stamped by "
        "path, size and mtime",
    "O4_CORPUS_SNAPSHOT":
        "where a corpus snapshot is; the files read are stamped as above",
    # ── the test suite's own switches (``tests/conftest.py``) ───────────
    "O4_ALLOW_QT_XDIST": "suite: lets Qt tests run under xdist",
    "O4_ALLOW_SHARED_REPO_WRITES": "suite: lifts the shared-repo guard",
    "O4_SHIP_MODE": "suite: selects the ship-gate test set",
    "O4_SUITE_ALLOW_NETWORK": "suite: lifts the network guard",
    "O4_SUITE_WRITE_AUDIT": "suite: records what the tests write",
    "O4_SUITE_WRITE_AUDIT_OUT": "suite: where that record goes",
    "O4_TEST_AIRPORTS": "suite: which airports the fixtures use",
    "O4_TEST_TILE": "suite: which tile the fixtures use",
    "O4_TIMING_RUNS": "suite: how many runs a timing test takes",
    "O4_TRIANGLE4XP_TEST_BINARY": "suite: which Triangle4XP the binary twin runs",
}

#: Digested, like a gate ``config.py`` declares.  Read outside ``config.py``
#: (the DEM and inset bake, the object stage, the mesh,
#: the census law) or by ``config.py`` without a string default.  Being
#: here claims only "a change to it rebuilds", which is the safe side; the
#: mesh-stage and cache entries are development knobs kept on that side.
SETTINGS_OUTSIDE_CONFIG: frozenset[str] = frozenset({
    # config.py reads without a string default, and the apt.dat override
    "O4_FABRIC_W2_ICAO_STRIP_AUTHORITY", "O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY",
    "O4_HOLE_ROUTER", "O4_PADS_BAND_VARIABLES", "O4_PAVEMENT_SCORE_WEIGHTS",
    "O4_RULESET", "O4_SERVICE_LOT_ABSORPTION", "O4_FORCE_APT_DAT",
    # the DEM the solve reads, and the inset bake
    "O4_DEM_QUERY_BAKED", "O4_INSET_BAKE_INTERP", "O4_INSET_FILL_METHOD",
    "O4_INSET_MIN_VALID_FRAC", "O4_INSET_SEAM_HARMONIZE",
    # the two cache roots that hold what the build READS (#346)
    "O4_DSF_CACHE_DIR", "O4_AIRPORT_MOD_CACHE_DIR",
    # the v2 build
    "O4_V2_XPLAT_QUANTISE_M", "O4_V2_XPLAT_DIGEST", "O4_FRAME_ENTRY_DUMP",
    # the object stage and its readers
    "O4_BASIN_OPEN_PIT_DECK_KEY", "O4_BRIDGE_FALLBACK_MAX_DECK_AREA_M2",
    "O4_BRIDGE_FALLBACK_MAX_DECK_LENGTH_M",
    "O4_BRIDGE_FALLBACK_MAX_DECK_WIDTH_M",
    "O4_TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2", "O4_OBJECT_TUNNEL_TERRAIN",
    "O4_OBJECT_REBAKE_REVERT_EXCLUDED", "O4_REANCHOR_SHORT_CIRCUIT",
    "O4_DSF_OBJECT_POSITIONS_CACHE", "O4_OBJECT_FOOTPRINT_CACHE",
    "O4_OBJECT_PAD_FRAME_CACHE", "O4_OBJECT_PARTITION_CACHE",
    "O4_LIBRARY_INDEX_CACHE",
    # the mesh and vector steps
    "O4_BANK_ANNULUS_BAR", "O4_BANK_BLEND_DUMP", "O4_HAIRLINE_PREFLIGHT",
    "O4_INTERP_ALT_LEAK", "O4_INTERP_ALT_SEAL", "O4_SEAWALL_OFFSET_M",
    "O4_VECTOR_SPLIT_M", "O4_VECTOR_WELD_M",
    # the census law (``tools/harness/law_support``)
    "O4_APRON_BODY_CHORD_MAX_M", "O4_APRON_CHORD_ANCHOR_TARGET",
    "O4_APRON_INTERIOR_RAMP_CAP", "O4_APRON_ROUTE_CONTACT",
    "O4_PAIR_BUDGET_PRUNE_M", "O4_PAIR_CHORD_LOCAL_M",
    "O4_ROUTE_LEG_EXACT", "O4_ROUTE_METRIC_PAIRS", "O4_SPINE_FRAME_PAIRS",
})


def digested_environment(environ: Mapping[str, str] | None = None
                         ) -> dict[str, str]:
    """The ``O4_`` variables that are SET and belong in the patch stamp:
    every one that is not in :data:`RUN_ENVIRONMENT`, at its value."""
    environ = os.environ if environ is None else environ
    return {name: environ[name] for name in environ
            if name.startswith("O4_") and name not in RUN_ENVIRONMENT}


def unclassified(config_gates, environ: Mapping[str, str] | None = None
                 ) -> list[str]:
    """Set ``O4_`` variables that are in no class, sorted.

    ``config_gates`` is the gate inventory of ``provenance.introspect_
    config_gates``; a frozen engine hands in an empty one, and there a gate
    ``config.py`` declares reads as unclassified — it is digested either
    way, and naming it tells the reader which variable the stamp carries.
    """
    return sorted(
        name for name in digested_environment(environ)
        if name not in SETTINGS_OUTSIDE_CONFIG and name not in config_gates)
