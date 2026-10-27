"""Typed events — the engine protocol's vocabulary (spec:
docs/specs/engine-protocol-multi-gui.md §5).

Every event is a frozen dataclass; views receive event OBJECTS in-process
and their ``dataclasses.asdict`` form over the JSON-lines transport, so
this module IS the protocol schema.  Compatibility rule: additive only —
new fields and new event types are minor protocol bumps; removing or
renaming anything is a new major version (negotiated via
:class:`EngineHello`).  Views must ignore unknown event types and fields.

``seq`` (monotonic per session) and ``ts`` (epoch seconds) are stamped by
the session at emission time, never by producers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# 1.1 (2026-07-16, additive): AutoPatchBegin/AutoPatchProgress carry
# lat/lon so parallel builds (docs/specs/parallel-tile-builds.md) stay
# attributable when several tiles stream at once.
# 1.2 (2026-07-23, additive): SecretRequest — the engine asks its front
# end to service one platform-secret-store operation (credential broker;
# answered with the ``secret_response`` command, o4_engine.secret_broker).
# 1.3 (2026-07-27, additive): TileClocks — per-tile elapsed/remaining
# rows beside RunEta, so activity views can show each tile's own clock.
# 1.4 (2026-07-30, additive): ImageryDownloadsDone — the imagery step's
# download queue drained and only its local DDS tail remains, so the
# parallel orchestrator can release that tile's imagery fetch token
# (docs/specs/apron-string-and-scheduling-spec.md §A.2).
# 1.5 (2026-08-11, additive): SignInResult, beside the auth_providers /
# provider_sign_in / provider_sign_out commands — a front end with no
# Python of its own (the macOS application) drives provider account
# sign-in engine-side (docs/specs/swift-provider-signin-spec.md).
# 1.6 (2026-08-15, additive): AirportIndexReady, beside the
# airport_index command — the engine's O4_Airport_Index is the SINGLE
# apt.dat parser for every front end, so a front end asks for the
# Global Airports index instead of parsing its own
# (docs/specs/airport-index-engine-command-spec.md).
# 1.7 (2026-09-01, additive): AutoPatchFailed — the per-airport
# auto-patch failure DIAGNOSIS (airport, stage, cause).  A tile build
# that loses an airport's patch is fatal and says which airport and why;
# before it the death was console-only and the tile exited 0 with the
# previous build's scenery still installed (H1,
# docs/POSTMORTEM-20260831.md Task C).
# 1.8 (2026-09-18, additive): BoundaryAirportsReady + the
# ``boundary_airports`` command + the ``boundary_policy`` keyword on
# build/enqueue_build — an airport whose AIRSIDE claim crosses a 1 degree
# tile line needs the user's answer before the build starts (owner
# RULINGS 2026-09-18b (2), 18i; spec insets-follow-patch-set-spec.md §C).
# 1.9 (2026-10-06, additive): PackMissingArt + the ``omit_missing_art``
# command + the ``missing_art`` keyword on build/enqueue_build — a scenery
# pack whose DSF declares a definition that is not installed is one
# X-Plane will not load; the engine names it and offers a DSF without the
# missing definitions (owner RULINGS 2026-10-06c, issue #433).
# 1.10 (2026-10-12, additive): BuildDone.failures, BuildDone.warnings and
# AutoPatchFailed.code — a tile that was not built says, in the user's
# words, what failed, why and what to do (``O4_Tile_Failures``, issue
# #562); a tile BUILT without one of its airport patches names that
# airport the same way in ``warnings`` (owner RULINGS 2026-10-12a, #564).
# ``BuildDone.error`` stays, and is now that same plain sentence, so a
# front end that reads only it shows no exception text either.  The SAME
# bump covers the ``failure_report`` command (``o4_engine.failure_report``,
# issue #565): a front end offers "Report this problem" / "Save report
# file" only to an engine at 1.10 or later.  Also within 1.10 (additive,
# #598): ``TileState.detail`` — the second line of a stopped tile's row.
# 1.11 (2026-10-14, additive): the ``remove_scenery_link`` command and
# the ``link`` key of a ``BuildDone.failures`` entry — a tile whose
# Custom Scenery folder is a link to a drive that is not mounted
# (``output_link_unmounted``) names the link, and a front end may offer
# to remove it and build on the computer's own drive (issue #668).
# 1.12 (2026-10-15, additive): the patch editor's commands ``patch_list``,
# ``patch_load``, ``patch_save``, ``patch_revert`` (``o4_engine.
# patch_commands``; spec patch-editor-20261015 §2, #46) — commands and
# replies only.  Within 1.12 (2026-10-15, additive): ``terrain_sample``,
# ``pack_objects`` and its completion event PackObjectsReady (spec §5,
# ruled after the massing measurement).
# 1.13 (2026-10-18, additive, #853): the ``severity`` key of every
# ``BuildDone.failures`` / ``warnings`` / ``notes`` entry — ``blocking``
# (not built), ``degraded`` (built, not as asked) or ``info`` — and
# ``warnings`` now also carries a built tile's DEGRADED outputs
# (white-squared textures, an airport inset not fetched, a mask built
# without its extent).  A peer that ignores the key loses nothing.
# Within 1.13 (2026-10-19, additive, #797): ``pack_objects`` takes
# ``footprints_only``; its models then carry ``plan_hull_f32_b64`` (the
# plan outline, ``(x, z)`` pairs) instead of vertices and triangles.
# 1.14 (2026-10-24, additive, #1308): ``cursor_elevation`` answers the
# built mesh's elevation at a point (``source`` "mesh"), else the DEM's
# ("dem"); ``pending`` while a source loads off the read loop.
# Within 1.14 (2026-10-26, additive, #1229): ``custom_patches`` and
# ``use_auto_patch`` — commands and replies only; an older engine refuses
# them and the app draws no band.
# Within 1.14 (2026-10-26, additive, #1326): ``TileState`` and
# ``StepProgress`` carry ``attempt``, the tile's admission number in this
# session, so a front end tells a stopped attempt's late news from the
# attempt that re-queued the tile.  0 from an older engine.
# 1.15 (2026-10-26, additive, #820): the ``plan_estimate`` command and its
# completion event PlanEstimateReady — download, disk and time ranges per
# tile before a build, set against the tile folder's free space.
# 1.16 (2026-10-26, additive, #1320): ``terrain_relief`` answers a
# hillshade-and-contours PNG over a box from the same sources, with its
# legend; ``pending`` while it is drawn off the read loop.
PROTOCOL_VERSION = "1.16"


@dataclass(frozen=True)
class EngineEvent:
    """Base fields shared by every event (stamped by the session)."""

    seq: int = field(default=0, kw_only=True)
    ts: float = field(default=0.0, kw_only=True)

    @property
    def event(self) -> str:
        """Wire name of the event type (the class name)."""
        return type(self).__name__


@dataclass(frozen=True)
class EngineHello(EngineEvent):
    """First event of every session: version + capability handshake."""

    ortho4xp_version: str = ""
    protocol: str = PROTOCOL_VERSION
    capabilities: tuple = ()


@dataclass(frozen=True)
class Log(EngineEvent):
    """A build log line.  ``level``: "info" | "warning" | "error"."""

    level: str = "info"
    text: str = ""


@dataclass(frozen=True)
class ScanProgress(EngineEvent):
    """Progress through a working-directory / Custom Scenery scan."""

    phase: str = ""          # human label, e.g. "Reading installed scenery…"
    done: int = 0
    total: int = 0


@dataclass(frozen=True)
class ScanBatch(EngineEvent):
    """Tiles discovered since the previous batch (streamed ~10 Hz).

    ``built``: {(lat, lon): TileInfo-shaped dict}; ``installed``: list of
    (lat, lon).  Keys are tuples in-process and become 2-item lists over
    JSON — consumers index positionally.
    """

    built: dict = field(default_factory=dict)
    installed: tuple = ()


@dataclass(frozen=True)
class ScanDone(EngineEvent):
    """A scan finished (superseded scans never emit this)."""

    built_count: int = 0
    installed_count: int = 0


@dataclass(frozen=True)
class TileState(EngineEvent):
    """A tile's lifecycle state changed.

    ``state``: "queued" | "active" | "indeterminate" | "done" | "error".
    ``label`` is the short human status ("failed", "stopped", "").
    ``detail`` (additive within 1.10, #598) is one or more whole sentences
    for a second line under the tile's row — for a stopped tile, what it
    is left with (``O4_Stopped_Build``); empty otherwise.  A front end
    shows it verbatim; an older one ignores it.
    ``attempt`` (additive within 1.14, #1326): which admission of the tile
    this event belongs to — 1 the first time a tile joins a run in this
    session, one more on every re-queue (``EngineSession.tile_attempt``).
    A front end drops a stopped attempt's late events by it; 0 = unknown.
    """

    lat: int = 0
    lon: int = 0
    state: str = "queued"
    label: str = ""
    percent: float = 0.0
    detail: str = ""
    attempt: int = 0


@dataclass(frozen=True)
class StepProgress(EngineEvent):
    """Whole-tile progress while a build step runs.

    The session owns ALL percent/label math (step weighting, legacy-bar
    mapping, auto-patch folding) — views only render.  ``indeterminate``
    marks steps that report no usable percentage (mesh triangulation,
    overlay extraction): show a busy indicator while HOLDING ``percent``.
    ``attempt``: as on ``TileState`` (#1326).
    """

    lat: int = 0
    lon: int = 0
    step_key: str = ""
    label: str = ""
    percent: float = 0.0
    indeterminate: bool = False
    attempt: int = 0


@dataclass(frozen=True)
class AutoPatchBegin(EngineEvent):
    """Airport pavement construction started for this tile's airports."""

    airports: tuple = ()
    lat: int = 0
    lon: int = 0


@dataclass(frozen=True)
class AutoPatchProgress(EngineEvent):
    """One airport's auto-patch progress (status: "run"|"done"|"fail").

    ``eta_total_seconds`` is the auto-patch time model's current
    total-duration estimate for this airport — the session folds it into
    the whole-run ETA (see session._EtaTracker).
    """

    airport: str = ""
    done: float = 0.0
    total: float = 0.0
    label: str = ""
    status: str = "run"
    eta_total_seconds: Optional[float] = None
    lat: int = 0
    lon: int = 0


@dataclass(frozen=True)
class AutoPatchFailed(EngineEvent):
    """One airport's auto-patch build FAILED — the tile build is aborting.

    The DIAGNOSIS event, distinct from ``AutoPatchProgress(status="fail")``
    (which is only that airport's row state): it names the airport, the
    ``stage`` it died at (``build`` / ``write`` / ``worker`` / ``missing``
    / ``manifest``) and the cause, so the app can tell the user WHICH
    airport broke WHY instead of showing a red row and a generic
    "the vector data step failed".

    H1 (docs/POSTMORTEM-20260831.md Task C): before this event, a
    per-airport death reached the engine console log and nothing else —
    the tile step finished with exit 0 and the previous build's scenery
    flew.  The tile's own ``BuildDone(ok=False)`` still follows; this is
    the detail that makes it actionable.

    Additive to the protocol — unknown event names are dropped by the
    Python re-assembler (``parallel._rebuild_event``) and reported as
    ``.unknown`` by the Swift client
    (``Sources/SceneryKit/OrthoEngineClient.swift``, which matches this
    class name as a STRING LITERAL: renaming the class breaks the app
    silently).
    """

    airport: str = ""
    stage: str = ""
    error: str = ""
    lat: int = 0
    lon: int = 0
    # 1.10: the ``O4_Tile_Failures`` catalogue code.  Non-empty means the
    # tile's ``BuildDone.failures`` will carry this airport in a message
    # written for the user, and ``error`` is the technical detail only.
    code: str = ""


@dataclass(frozen=True)
class ImageryDownloadsDone(EngineEvent):
    """This tile's imagery DOWNLOAD queue drained; only the local DDS
    conversion tail remains (docs/specs/apron-string-and-scheduling-spec
    §A.2 — the imagery step is hybrid exactly as the vector step is).

    A scheduling signal for the parallel orchestrator: it releases the
    tile's ``imagery`` fetch token here, so a queued tile may start
    downloading while this one converts.  Additive to the protocol —
    unknown event names are dropped by the Python re-assembler
    (``parallel._rebuild_event``) and reported as ``.unknown`` by the
    Swift client (``Sources/SceneryKit/OrthoEngineClient.swift``).
    """

    lat: int = 0
    lon: int = 0
    downloaded: int = 0
    failed: int = 0


@dataclass(frozen=True)
class BuildDone(EngineEvent):
    """One tile finished (ok or not).

    ``failures`` (1.10, issue #562) is why a tile was NOT built, one entry
    per cause: ``{"code", "what", "why", "remedy", "airports", "detail",
    "log_path", "link"}`` (``link``, 1.11: the unreachable link a front
    end may offer to remove, else "") — three short sentences written for the user
    (``O4_Tile_Failures``), the airports the cause covers, and the
    technical ``detail`` (the original exception or console text) for the
    log and a disclosure.  ``error`` is the same message as one plain line.

    ``warnings`` (1.10, owner RULINGS 2026-10-12a, #564) has the same
    entries for AIRPORTS WITHOUT A PATCH: with ``ok`` true and
    ``warnings`` non-empty the tile was BUILT WITH WARNINGS — each named
    airport stands on ungraded terrain — which a front end shows distinct
    from a clean success.  ``unpatched_airports`` is the same set one
    airport per entry — the same dict plus ``stage`` — for a consumer
    that counts rather than displays (the release check, a sweep).

    Since 1.13 (#853) ``warnings`` also names the tile's DEGRADED outputs
    (codes whose ``O4_Tile_Failures`` severity is ``degraded``), and
    every entry of the three lists carries ``severity``
    (``blocking`` / ``degraded`` / ``info``) — optional to a reader.
    """

    lat: int = 0
    lon: int = 0
    ok: bool = True
    error: str = ""
    failures: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    unpatched_airports: list = field(default_factory=list)
    # Info-level entries of the same shape (plus ``cells``) for a tile
    # that WAS built: code ``elevation_substituted`` — a base cell read
    # from a fallback source (owner RULINGS 2026-10-12e).
    notes: list = field(default_factory=list)


@dataclass(frozen=True)
class RunEta(EngineEvent):
    """Whole-run clock estimate, emitted at most ~1 Hz during a build.

    ``remaining_seconds`` is None while no defensible estimate exists
    (views show a dash, never a wild number — the 2026-07-15 owner
    complaint was precisely a wild number).
    """

    elapsed_seconds: float = 0.0
    remaining_seconds: Optional[float] = None
    done_tiles: int = 0
    total_tiles: int = 0


@dataclass(frozen=True)
class TileClocks(EngineEvent):
    """Per-tile clocks for the current run, emitted beside RunEta (~1 Hz).

    ``rows``: one ``[lat, lon, elapsed_seconds, remaining_seconds,
    finished]`` entry per tile in the run (tuples in-process, 5-item
    lists over JSON).  ``elapsed_seconds`` is wall-clock since the
    tile's first step started — 0.0 while it is still queued — and
    freezes at its terminal BuildDone.  ``remaining_seconds`` is the
    tile's OWN remaining work (compute seconds; the run-level RunEta
    stays the slot-aware wall clock, so in a parallel run the per-tile
    figures deliberately sum to more than the wall estimate) or None
    while no defensible basis exists — views show a dash, never a wild
    number, exactly as with RunEta.
    """

    rows: tuple = ()


@dataclass(frozen=True)
class RunDone(EngineEvent):
    """The whole build run ended."""

    done_count: int = 0
    error_count: int = 0
    cancelled: bool = False


@dataclass(frozen=True)
class SecretRequest(EngineEvent):
    """The engine asks the front end to service one secret-store operation.

    Emitted only while a front end brokers the platform secret store for
    the engine (o4_engine.secret_broker; under the packaged app the reply
    comes from the app's own Keychain, so the user-visible prompt and the
    access-control list belong to the signed application, not to an
    ad-hoc-signed engine binary).  The front end answers with a
    ``{"cmd": "secret_response", "request_id": ..., "ok": ...,
    "secret": ...}`` command; the engine blocks (bounded) until it
    arrives.

    ``operation``: "get" | "set" | "delete".  ``secret`` is only
    populated for "set" — the one direction a secret travels engine to
    front end, over the private stdio pipe the transport already owns.
    """

    request_id: int = 0
    operation: str = ""
    session_name: str = ""
    account: str = ""
    secret: str = ""


@dataclass(frozen=True)
class SignInResult(EngineEvent):
    """One provider-account sign-in (or sign-out) attempt finished.

    The completion half of the ``provider_sign_in`` / ``provider_sign_out``
    commands (docs/specs/swift-provider-signin-spec.md): both reply
    ``{"started": true}`` at once and do their work on a worker thread,
    because the work touches the secret store and a store operation made
    on the transport's own read loop can never be answered (see
    o4_engine.secret_broker's threading contract).

    ``ok`` False carries the user-safe failure text in ``error_text``
    (``O4_Authenticated_Sessions.LoginError``'s message verbatim, exactly
    what the Qt sign-in dialog displays).
    """

    session_name: str = ""
    ok: bool = False
    error_text: str = ""


@dataclass(frozen=True)
class AirportIndexReady(EngineEvent):
    """The Global Airports search index finished (re)building.

    The completion half of the ``airport_index`` command
    (docs/specs/airport-index-engine-command-spec.md): a stale index
    replies ``{"status": "building"}`` at once and the parse — hundreds
    of megabytes of ``apt.dat`` — runs on a worker thread, because a
    command handler runs on the transport's read loop and must never
    block it.

    ``path`` is the TSV cache the front end may now read
    (``O4_File_Names.airport_index_cache()``) and ``count`` the number of
    airports written.  On failure ``error`` carries the exception text,
    ``path`` is empty and ``count`` is 0.
    """

    path: str = ""
    count: int = 0
    error: str = ""


@dataclass(frozen=True)
class BoundaryAirportsReady(EngineEvent):
    """The boundary-airport PREFLIGHT finished (spec §C.2).

    The completion half of the ``boundary_airports`` command, which
    replies ``{"status": "started", "request_id": N}`` at once and works
    on a worker thread — a command handler runs on the transport's read
    loop and must never block it (the ``airport_index`` precedent).

    ``airports`` lists ONLY class-S airports — those whose AIRSIDE claim
    (apt.dat row 100 runways + row 110 pavement, buffered by
    ``law.emit.seam.ask_reach_m``) reaches a 1 degree cell this build is
    not building.  An airport whose groundside, inset box or DEM window
    crosses is class M: it is NOT listed, it never prompts, and its far
    side is read context-only (owner RULINGS 2026-09-18h).  Each entry::

        {"icao": str, "name": str, "home": [lat, lon],
         "neighbours": [[lat, lon], ...],   # COLD ones only
         "crossing_m": float}               # how far the claim reaches
                                            # past the line

    ``add_tiles`` is the COMPLETE, DEDUPLICATED set of cold neighbour
    cells needed by EVERY listed airport and not already in ``tiles``,
    sorted — so the dialog's default action ("build all the tiles the
    straddling airports need", owner RULINGS 2026-09-18i (2)) is ONE
    send of ``tiles + add_tiles``.

    ``airports == []`` means proceed straight to ``enqueue_build`` with
    no dialog.  ``remembered`` is the user's saved answer mapped to a
    policy (``""`` | ``"neighbour"`` | ``"skip"``, from the
    ``auto_patch_boundary`` app setting); non-empty means apply it
    without asking.  ``error`` carries the preflight's failure text, in
    which case the front end proceeds with ``boundary_policy=None``.

    ``default_choice`` is the policy the dialog PRESELECTS (its Return-key
    action): ``"neighbour"`` — build all the needed tiles (owner RULINGS
    2026-09-18i (2)).  Engine-owned so the two front ends cannot spell
    the default differently; it is NOT the unattended default, which
    stays skip.
    """

    request_id: int = 0
    airports: list = field(default_factory=list)
    add_tiles: list = field(default_factory=list)
    remembered: str = ""
    error: str = ""
    default_choice: str = "neighbour"


@dataclass(frozen=True)
class PackMissingArt(EngineEvent):
    """A scenery pack X-Plane will NOT load: its DSF declares definitions
    whose files are not installed (owner RULINGS 2026-10-06c, #433).

    Emitted by the object stage (``auto_patch.engine_v2``) before it reads
    or rewrites the pack's DSF, and again as the completion of an
    ``omit_missing_art`` command (which replies ``{"status": "started"}``
    at once and works on a worker thread).  ``state``:

    * ``"found"`` — the pack is named; nothing was changed.  The front end
      shows the owner-fixed warning and, ONLY when ``can_omit`` is true,
      the primary button that sends ``omit_missing_art`` with ``pack_root``,
      ``lat`` and ``lon``.  A missing TERRAIN definition is reported but
      cannot be omitted (its patches are the mesh): no primary button.
    * ``"omitted"`` — the DSF was written without the missing definitions
      and without the placements, polygons and segments that use them;
      the pristine DSF stays as ``<name>.dsf.anchor_bak``.
    * ``"failed"`` — the write was asked for and failed; ``error`` says why.
    * ``"none"`` — (command completion only) nothing is missing any more.

    ``kinds`` is ``{"object"|"polygon"|"network"|"terrain": n}``;
    ``total`` the missing definitions, ``uses`` the DSF rows that use
    them, ``first_paths`` up to five of them in declaration order.

    Additive to the protocol; ``Sources/SceneryKit/OrthoEngineClient.swift``
    matches this class name as a STRING LITERAL (renaming it breaks the
    app silently).
    """

    pack: str = ""
    pack_root: str = ""
    lat: int = 0
    lon: int = 0
    total: int = 0
    kinds: dict = field(default_factory=dict)
    uses: int = 0
    first_paths: list = field(default_factory=list)
    can_omit: bool = False
    state: str = "found"
    error: str = ""


@dataclass(frozen=True)
class PackObjectsReady(EngineEvent):
    """The completion half of the ``pack_objects`` command (protocol 1.12,
    patch-editor spec §2 and §5): the command replies
    ``{"status": "started"}`` and the pack is read on a worker thread,
    because a command handler runs on the transport's read loop.

    ``request`` is the ``id`` of the command it answers; ``result`` is the
    §2 reply (``models``, ``placements``, ``facades``, ``missing``) or
    ``None``, with ``error`` the failure sentence.

    ``Sources/SceneryKit/OrthoEngineClient.swift`` matches this class name
    as a STRING LITERAL (renaming it breaks the app silently).
    """

    request: Any = None
    result: Any = None
    error: str = ""


@dataclass(frozen=True)
class LibraryReady(EngineEvent):
    """The completion half of the Library commands (#824:
    ``library_scan``, ``cache_sizes``, ``free_cache``, ``library_delete``,
    ``o4_engine.library``): each replies ``{"status": "started"}`` and
    walks its folders on a worker thread.

    ``request`` is the ``id`` of the command it answers, ``command`` its
    name; ``result`` is the command's return value or ``None``, with
    ``error`` the failure sentence.

    ``Sources/SceneryKit/OrthoEngineClient.swift`` matches this class name
    as a STRING LITERAL (renaming it breaks the app silently).
    """

    request: Any = None
    command: str = ""
    result: Any = None
    error: str = ""


@dataclass(frozen=True)
class PlanEstimateReady(EngineEvent):
    """The completion half of the ``plan_estimate`` command (protocol
    1.15, #820): the command replies ``{"status": "started"}`` and the
    estimate runs on a worker thread (``o4_engine.plan_estimate``).

    ``request`` is the ``id`` of the command it answers; ``result`` is
    the estimate (``tiles``, ``total``, ``free_gb``, ``cache_free_gb``,
    ``verdict``, ``reason``; every figure a ``[lo, hi]`` range) or
    ``None``, with ``error`` the failure sentence.

    ``Sources/SceneryKit/OrthoEngineClient.swift`` matches this class name
    as a STRING LITERAL (renaming it breaks the app silently).
    """

    request: Any = None
    result: Any = None
    error: str = ""


@dataclass(frozen=True)
class Error(EngineEvent):
    """A non-tile-scoped engine error.  ``fatal`` ends the session."""

    fatal: bool = False
    text: str = ""
