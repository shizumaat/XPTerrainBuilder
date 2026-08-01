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
from typing import Optional

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
PROTOCOL_VERSION = "1.4"


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
    """

    lat: int = 0
    lon: int = 0
    state: str = "queued"
    label: str = ""
    percent: float = 0.0


@dataclass(frozen=True)
class StepProgress(EngineEvent):
    """Whole-tile progress while a build step runs.

    The session owns ALL percent/label math (step weighting, legacy-bar
    mapping, auto-patch folding) — views only render.  ``indeterminate``
    marks steps that report no usable percentage (mesh triangulation,
    overlay extraction): show a busy indicator while HOLDING ``percent``.
    """

    lat: int = 0
    lon: int = 0
    step_key: str = ""
    label: str = ""
    percent: float = 0.0
    indeterminate: bool = False


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
    """One tile finished (ok or not)."""

    lat: int = 0
    lon: int = 0
    ok: bool = True
    error: str = ""


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
class Error(EngineEvent):
    """A non-tile-scoped engine error.  ``fatal`` ends the session."""

    fatal: bool = False
    text: str = ""
