"""JSON-lines standard-input/output transport for the engine session
(docs/specs/engine-protocol-multi-gui.md §5, Phase 2).

This is the subprocess View: a front end in any language launches
``Ortho4XP.py --engine-jsonl`` and speaks a line-oriented protocol over the
child's standard streams.

Wire format
-----------
* **Commands** (caller -> engine): one JSON object per input line,
  ``{"cmd": <name>, "id": <caller id>, ...named arguments}``.  The named
  arguments match the corresponding :class:`o4_engine.session.EngineSession`
  method parameters exactly (for example ``tile_info`` takes ``lat``,
  ``lon``, ``working_dir``); the transport calls the method with them as
  keyword arguments.
* **Events** (engine -> caller): every :class:`o4_engine.events.EngineEvent`
  the session emits is written as one JSON object per output line, its
  ``dataclasses`` fields plus an ``"event"`` key naming the type.
* **Replies** (engine -> caller): every command, whatever events it also
  triggers, produces exactly one ``{"reply": <id>, "ok": true/false, ...}``
  line so callers can await completion without heuristics.  A successful
  reply carries ``"result"`` (the command's return value, serialized); a
  failed one carries ``"error"`` (a human string).

Design notes
------------
* **stdout is the protocol; nothing else may touch it.**  The pipeline is
  full of ``print``/``vprint`` calls that would corrupt the stream, so
  :func:`serve` keeps a private handle to the real stdout for protocol
  writes and repoints ``sys.stdout`` at ``sys.stderr`` for its whole
  lifetime — pipeline prints stay visible on stderr but can never land in
  the middle of a JSON line.  ``stderr`` is reserved for that plus uncaught
  crash text, per the spec.
* **Thread-safe, line-buffered writes.**  Session subscriber callbacks fire
  on worker threads while the read loop blocks on stdin, so every protocol
  write (its ``json.dumps`` line and the flush) is serialized under one
  lock.
* **Tuple / non-JSON handling.**  ``dataclasses.asdict`` cannot serialize
  :class:`o4_engine.events.ScanBatch` because its ``built`` mapping is keyed
  by ``(lat, lon)`` tuples, which are not valid JSON object keys.  The
  schema (that event's docstring) says consumers index positionally, so
  :func:`serialize_event` special-cases ``ScanBatch`` into a list of
  ``[lat, lon, info]`` triples.  All other non-JSON values (dataclasses,
  tuples, enums, Python ``type`` objects in the settings registry) are made
  JSON-safe by :func:`_json_safe`, which stringifies anything it does not
  recognize rather than raise.

The transport itself owns the ``EngineHello`` handshake line: the session
emits its own hello during construction, before any subscriber exists, so
the transport writes the handshake as its deliberate first protocol line.
"""

from __future__ import annotations

import dataclasses
import json
import os
import signal
import sys
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, TextIO

import O4_Console_Encoding
import O4_Edit_Cache as EDITCACHE
import O4_Machine_Slots
import O4_Process_Liveness as PROC
import O4_UI_Utils as UI
import O4_Unmounted_Links as UNMOUNTED

from . import failure_report
from .events import EngineHello, Error, ScanBatch
from .secret_broker import SecretBroker
from .session import EngineSession


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def _json_safe(value: Any) -> Any:
    """Return a JSON-serializable mirror of ``value``.

    The engine hands the transport values that ``json.dumps`` rejects on its
    own: dataclasses (``TileInfo``), tuples, :class:`enum.Enum` members
    (``LinkStatus``), and Python ``type`` objects (the settings registry's
    ``"type"`` fields).  Rather than let one such value crash a reply, every
    unrecognized object is stringified — the protocol is additive and
    forgiving by rule (spec §5), and a stringified value is far better than a
    dropped line.
    """
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _json_safe(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        safe: Dict[Any, Any] = {}
        for key, item in value.items():
            # JSON object keys must be str/number/bool/None; a tuple key
            # (or any other object) is stringified so it never crashes.
            if not (key is None or isinstance(key, (str, int, float, bool))):
                key = str(key)
            safe[key] = _json_safe(item)
        return safe
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if isinstance(value, type):
        return value.__name__
    if callable(value):
        return getattr(value, "__name__", repr(value))
    return str(value)


def serialize_event(event) -> Dict[str, Any]:
    """Serialize one :class:`o4_engine.events.EngineEvent` to a JSON-safe dict.

    The result is the event's dataclass fields plus an ``"event"`` key naming
    the type.  :class:`o4_engine.events.ScanBatch` gets a special case: its
    ``built`` mapping is keyed by ``(lat, lon)`` tuples, so it is emitted as a
    list of ``[lat, lon, info]`` triples (consumers index positionally, per
    that event's schema docstring).

    This is exported so the transport-equivalence test (spec §8.2) can
    serialize directly-subscribed events with the very serializer the pipe
    uses — the two paths cannot drift if they share this function.
    """
    payload: Dict[str, Any] = {"event": event.event}
    for f in dataclasses.fields(event):
        payload[f.name] = getattr(event, f.name)
    if isinstance(event, ScanBatch):
        payload["built"] = [
            [key[0], key[1], _json_safe(info)]
            for key, info in event.built.items()
        ]
    return _json_safe(payload)


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
def _ortho4xp_version() -> str:
    """Best-effort Ortho4XP version string for the handshake (optional)."""
    try:
        import O4_Version
        return O4_Version.version
    except Exception:
        return ""


#: Commands completed by an event that names the command: their handler
#: is given the command's ``id`` as ``request``.
_TAKES_REQUEST_ID = frozenset({"pack_objects", "library_scan", "cache_sizes",
                               "free_cache", "library_delete",
                               "plan_estimate", "build_airports"})


def _build_handlers(session: EngineSession) -> Dict[str, Callable]:
    """Map command names 1:1 onto session methods.

    Kept in one place so an unknown command is a lookup miss (a clean
    ``ok=false`` reply) rather than an attribute error.
    """
    # Imported here, after the hello is written: the patch commands pull in
    # the emitter and the law tables (~0.25 s), which the handshake must
    # not wait for.
    import O4_Imagery_Sources as SOURCES
    from O4_Tile_Customizations import tile_customizations

    from . import patch_commands, patch_insert
    from .build_airports import start_build_airports
    from .elevation_commands import cursor_elevation
    from .imagery_commands import start_imagery_source_status
    from .mesh_commands import mesh_crop
    from .pack_objects import start_pack_objects
    from .pack_outlines import pack_outlines
    from .plan_estimate import start_plan_estimate
    from .relief_commands import terrain_relief
    from .terrain_commands import terrain_sample
    return {
        "scan": session.scan,
        "build": session.build,
        "enqueue_build": session.enqueue_build,
        "cancel": session.cancel,
        "cancel_tile": session.cancel_tile,
        "siblings": session.set_parallel_siblings,
        "tile_info": session.tile_info,
        "config_describe": session.config_describe,
        # Settings write-through to the selected tiles (protocol 1.7,
        # RULINGS 2026-09-18a (2)): set the key when it now differs from
        # the global, REMOVE it when it equals it.  Plain synchronous
        # file writes — no build, no parse, safe on the read loop.
        "tile_settings_write": session.tile_settings_write,
        # The tile's customized settings against the global layer (#1350):
        # the Mac map badge and tile pane.  Synchronous file reads, no
        # session state; the Qt app calls the same function in process.
        "tile_customizations": tile_customizations,
        "links_status": session.links_status,
        "links_install": session.links_install,
        "links_uninstall": session.links_uninstall,
        "reanchor_status": session.reanchor_status,
        "reanchor_restore": session.reanchor_restore,
        # Provider account sign-in (protocol 1.5).  sign-in and sign-out
        # reply {"started": true} and complete through SignInResult: both
        # touch the brokered secret store, which THIS thread may not do
        # (see the secret_broker threading contract, and the hazard note
        # on EngineSession's provider commands).
        "auth_providers": session.auth_providers,
        "provider_sign_in": session.provider_sign_in,
        "provider_sign_out": session.provider_sign_out,
        # Default-airport index (protocol 1.6): replies "none" / "ready"
        # with the cache path / "building", the last completing through
        # AirportIndexReady — the apt.dat parse is hundreds of megabytes
        # and may not run on THIS thread either.
        "airport_index": session.airport_index,
        # Missing art (protocol 1.9, #433): replies {"status": "started"}
        # and completes through PackMissingArt — DSFTool may not run on
        # THIS thread.
        "omit_missing_art": session.omit_missing_art,
        # Failure report (#565, RULINGS 2026-10-12b): the REDACTED report
        # for one tile, its prefilled new-issue URL and, with
        # ``save_path``, the report file.  Synchronous — it reads the end
        # of one log file — and no session state: a module function.
        "failure_report": failure_report.failure_report,
        # Unmounted-drive link (protocol 1.11, #668): remove ONE dangling
        # link directly in a Custom Scenery folder — never its target,
        # never a folder; a refusal is ok=false with the user's sentence.
        "remove_scenery_link": UNMOUNTED.remove_link,
        # Patch editor (protocol 1.12, #46, spec patch-editor-20261015
        # §2): read / write one airport's patch in a tile's Patches
        # folder.  Synchronous file work, no session state.
        "patch_list": patch_commands.patch_list,
        "patch_load": patch_commands.patch_load,
        "patch_save": patch_commands.patch_save,
        "patch_revert": patch_commands.patch_revert,
        # "Insert shape" on the map (protocol 1.17, #1314): the square's
        # corners at the elevation under them and the airport they go to;
        # appending it to a patch the editor does not have open.
        # Synchronous file work, like the commands above.
        "patch_insert_shape": patch_insert.patch_insert_shape,
        "patch_add_shape": patch_insert.patch_add_shape,
        # Custom patches (#1229, RULINGS 2026-10-26c): which tiles carry
        # one (the map band, the tile info) and setting a tile's aside so
        # the auto patch runs again.  Synchronous file work.
        "custom_patches": patch_commands.custom_patches,
        "use_auto_patch": patch_commands.use_auto_patch,
        # Patch editor 3D preview (protocol 1.12, #46): the DEM grid under
        # the patch, from the data repo's caches only.  Synchronous.
        "terrain_sample": terrain_sample,
        # ... and the airport pack's buildings over it, from cached dumps:
        # replies {"status": "started"}; a worker thread completes it with
        # PackObjectsReady carrying this command's id (_TAKES_REQUEST_ID).
        "pack_objects": lambda **kw: start_pack_objects(session._emit, **kw),
        # The Build pane's Airports card (protocol 1.15, #818): replies
        # {"status": "started"} and completes through BuildAirportsReady —
        # CIFP, apt.dat and the Custom Scenery walk stay off THIS thread.
        "build_airports": lambda **kw: start_build_airports(
            session._emit, **kw),
        # ... and the pack's own apt.dat pavement and boundary, as the
        # map's dashed reference outlines.  Synchronous, cache-only.
        "pack_outlines": pack_outlines,
        # ... and the last build's mesh there ("Last build"); synchronous.
        "mesh_crop": mesh_crop,
        # Cursor elevation (protocol 1.14, #1308): the built mesh's
        # elevation at a point, else the DEM's.  Never loads on THIS
        # thread: an uncached source loads on a daemon thread and the
        # reply says pending.
        "cursor_elevation": cursor_elevation,
        # Terrain view (protocol 1.15, #1320): a hillshade-and-contours
        # PNG over a box, from the same sources; drawn off THIS thread,
        # the reply says pending until it is ready.
        "terrain_relief": terrain_relief,
        # Library view (#824): built tiles with sizes, the caches, freeing
        # a cache, deleting tiles.  Each replies {"status": "started"} and
        # completes with LibraryReady carrying this command's id; deleting
        # needs confirm=true and is refused while a build runs.
        **{name: _library_handler(session, name)
           for name in ("library_scan", "cache_sizes", "free_cache",
                        "library_delete")},
        # Build cost (protocol 1.15, #820): download, disk and time ranges
        # for the tiles about to be built.  Replies {"status": "started"};
        # PlanEstimateReady carrying this command's id completes it.
        "plan_estimate": lambda **kw: start_plan_estimate(session._emit, **kw),
        # Imagery sources (protocol 1.17, #1345): the one list every
        # imagery menu reads, one preview tile's URL, and the launch-time
        # liveness check, which replies {"started": true} and completes
        # through one ImagerySourceStatus event per source.
        "imagery_sources": SOURCES.imagery_sources,
        "preview_tile_url": SOURCES.preview_tile_url,
        "imagery_source_status": lambda codes=None: start_imagery_source_status(
            session._emit, codes=codes),
    }


def _library_handler(session: EngineSession, name: str) -> Callable:
    from . import library
    return lambda **kw: library.start(
        session._emit, name, busy=lambda: bool(session._building), **kw)


def command_table(session: EngineSession) -> Dict[str, Callable]:
    """The command name → handler table this transport serves, for an
    in-process client (the Qt app calls the SAME functions, never
    re-spelled; a command this engine lacks is simply absent)."""
    return _build_handlers(session)


def _initialize_pipeline_registries() -> None:
    """Load the imagery provider/extent/filter registries a build needs.

    Both interactive entry points (``Ortho4XP.py``, ``Ortho4XP_Qt.py``)
    run these initializers before any build; the transport must do the
    same for its own process — the 2026-07-16 parallel-build worker
    children failed every imagery step with "not a known provider"
    because the ``--engine-jsonl`` branch exits BEFORE the entry points'
    initialization.  Mirrors those entry points: ``Providers/`` joins
    ``sys.path`` (provider definition files may ship custom code), the
    four registries load, and the live-map imagery cache is shared so a
    worker child reuses tiles the map already fetched.  Called after the
    stdout repoint in :func:`serve`, so any initialization chatter lands
    on standard error, never inside the protocol stream.  Failures warn
    and continue: non-imagery commands must keep working.
    """
    try:
        import O4_File_Names as FNAMES

        if FNAMES.Provider_dir not in sys.path:
            sys.path.append(FNAMES.Provider_dir)
        import O4_Imagery_Utils as IMG

        IMG.initialize_extents_dict()
        IMG.initialize_color_filters_dict()
        IMG.initialize_providers_dict()
        IMG.initialize_combined_providers_dict()
        IMG.shared_tile_cache_dir = os.path.join(
            FNAMES.Preview_dir, "livemap")
    except Exception as error:
        print(
            "WARNING: imagery provider initialization failed in the"
            " engine transport:",
            error,
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Process lifecycle (owns_process mode)
# ---------------------------------------------------------------------------
# How long a dedicated engine process lets an in-flight build acknowledge
# the red flag before the process hard-exits anyway.  The polled
# cancellation contract stops most steps within a second or two; the cap
# exists for steps that never look at the flag.  Must stay SHORTER than
# the front end's SIGTERM→SIGKILL window (BuildModel.hardStopEngine) or
# the wind-down is cut off mid-flight by the harder kill.
SHUTDOWN_GRACE_SECONDS = 10.0
# Cadence of the parent-death watchdog's ``os.getppid()`` poll.
PARENT_WATCH_POLL_SECONDS = 1.0


def _shutdown_grace_seconds() -> float:
    """The bounded wind-down window, overridable through the
    ``O4_ENGINE_SHUTDOWN_GRACE_SECONDS`` environment variable (the
    lifecycle tests shrink it; real runs use the default)."""
    value = os.environ.get("O4_ENGINE_SHUTDOWN_GRACE_SECONDS")
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            pass
    return SHUTDOWN_GRACE_SECONDS


def _stop_session_and_exit_process(session: EngineSession,
                                   reason: str) -> None:
    """Stop any in-flight build and end THIS PROCESS within a bounded time.

    The only exit path for a dedicated engine process: the polled
    cancellation contract (``O4_UI_Utils.red_flag``, set through
    :meth:`EngineSession.cancel`) asks the build worker to stop at its
    next checkpoint; once it acknowledges — or the grace window expires —
    ``os._exit`` ends the process outright.  A plain ``sys.exit`` is NOT
    enough here: pipeline steps spawn non-daemon helper threads
    (``concurrent.futures`` pools in the elevation/bathymetry fetchers),
    and interpreter shutdown joins those while the daemon build-worker
    thread keeps launching new work — the 2026-07-16 orphan was still
    fetching a bathymetry band 1.5 h after its GUI closed, racing the
    replacement session's engine on the shared elevation caches.
    """
    try:
        session.cancel()
    except Exception:
        pass
    deadline = time.time() + _shutdown_grace_seconds()
    # _building is the session's own run flag, cleared by both run modes'
    # end paths once the cancel is acknowledged.
    while time.time() < deadline and session._building:
        time.sleep(0.1)
    if reason in _FRONT_END_GONE:
        # The app quit (or died): its edit caches go with it unless a
        # tile keeps its own (owner RULINGS 2026-10-26h Q148).  A
        # ``shutdown`` command or a terminate signal is an engine restart
        # inside a running app, which keeps them.  A child process never
        # owns the list, so this is a no-op there.
        try:
            EDITCACHE.end_session()
        except Exception:
            pass
    try:
        print("Engine process exiting (%s)." % reason, file=sys.stderr)
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(0)


#: the exit reasons that mean the front end itself is gone
_FRONT_END_GONE = ("standard input closed", "parent process died")


def _front_end_pid() -> int:
    """The front end this engine serves: the declared parent, else ours."""
    declared = os.environ.get("O4_PARENT_PROCESS_ID")
    try:
        return int(declared) if declared else os.getppid()
    except ValueError:
        return os.getppid()


def _install_terminate_signal_handler(session: EngineSession) -> None:
    """Route SIGTERM through the bounded stop instead of dying mid-write.

    The parent orchestrator terminates slow-retiring workers and the Qt
    front end terminates them at application exit; giving the signal the
    same red-flag-then-exit path lets a cooperating step finish its
    current cache write instead of being cut mid-file.
    """
    def handle_terminate_signal(signal_number, frame):
        _stop_session_and_exit_process(session, "terminate signal")

    try:
        signal.signal(signal.SIGTERM, handle_terminate_signal)
    except (ValueError, OSError):
        # Not the main thread, or the platform does not support it: the
        # end-of-file and watchdog paths still bound the process's life.
        pass


def _parent_process_is_dead(declared_parent_id, initial_parent_id):
    """Whether the front end this engine belongs to is gone.

    Preferred signal: the spawner declares its pid in
    ``O4_PARENT_PROCESS_ID`` (the parallel orchestrator does) and we
    probe that pid directly — immune to the startup race where the
    parent dies before this process even captures its ppid.  Fallback
    (manual spawns): on POSIX an orphan is reparented, so a changed —
    or already-1 — ``os.getppid()`` means the parent is dead.
    """
    if declared_parent_id is not None:
        # Never os.kill(pid, 0): on Windows it sends Ctrl-C to a process-
        # group leader and raises for anything else, so the parent was
        # never seen dead there (#83).  Undeterminable reads as alive.
        return PROC.pid_is_alive(declared_parent_id) is False
    current_parent_id = os.getppid()
    return (current_parent_id != initial_parent_id
            or (os.name == "posix" and current_parent_id == 1))


def _start_parent_death_watchdog(session: EngineSession) -> None:
    """Exit when the parent front end dies, even if stdin never closes.

    End-of-file on stdin is the primary death signal, but it only arrives
    once every copy of the pipe's write end is gone; a write end inherited
    by another long-lived process (or a parent that dies without the pipe
    collapsing) leaves this engine orphaned mid-build — exactly the
    observed failure shape (an engine with parent pid 1 still building
    headless long after its GUI closed).
    """
    declared = os.environ.get("O4_PARENT_PROCESS_ID")
    try:
        declared_parent_id = int(declared) if declared else None
    except ValueError:
        declared_parent_id = None
    initial_parent_id = os.getppid()

    def watch():
        while True:
            time.sleep(PARENT_WATCH_POLL_SECONDS)
            if _parent_process_is_dead(declared_parent_id,
                                       initial_parent_id):
                _stop_session_and_exit_process(
                    session, "parent process died")

    threading.Thread(target=watch, daemon=True,
                     name="o4-engine-parent-watchdog").start()


def serve(stdin: TextIO, stdout: TextIO, owns_process: bool = False) -> None:
    """Run the JSON-lines transport until ``stdin`` closes or ``shutdown``.

    Reads one command object per input line and writes events and replies to
    ``stdout``.  Returns when the input stream reaches end-of-file or a
    ``{"cmd": "shutdown"}`` command is received (its reply is written first).

    ``stdout`` is captured privately for protocol writes and ``sys.stdout`` is
    repointed at ``sys.stderr`` for the duration, so stray pipeline prints
    cannot corrupt the stream (restored on return).

    ``owns_process=True`` (the ``--engine-jsonl`` entry points) binds the
    whole process's life to the transport: end-of-file, ``shutdown``,
    SIGTERM, and parent death (a ppid watchdog) each red-flag any
    in-flight build and end the process within a bounded time, so a
    worker can never outlive its front end and keep building headless.
    In-process callers (the tests' transport harness) keep the historic
    return-to-caller behavior.
    """
    # THE STREAMS ARE UTF-8 FIRST (issue #125).  The entry points already
    # called this, and it is idempotent -- but ``serve`` is the transport's
    # own door (the tests' harness and any other host enter here), and it
    # is the stream setup #125 names: the frozen Windows engine's stderr
    # defaulted to the ANSI code page, so ``Adolfo Suárez`` reached the
    # app's console drawer and ``logs/engine-stderr.log`` as undecodable
    # cp1252 bytes.  ``stdout`` below is the PROTOCOL and is ASCII by
    # construction (``json.dumps`` escapes non-ASCII), but the lines the
    # pipeline prints are not: ``sys.stdout`` is repointed at ``sys.stderr``
    # a few lines down, which makes stderr the engine's whole console.
    O4_Console_Encoding.configure_console_streams()
    protocol_stdout = stdout
    write_lock = threading.Lock()

    def write_obj(obj: Dict[str, Any]) -> None:
        line = json.dumps(obj)
        with write_lock:
            protocol_stdout.write(line + "\n")
            protocol_stdout.flush()

    saved_sys_stdout = sys.stdout
    sys.stdout = sys.stderr
    # The front end on the other side of this pipe services the engine's
    # platform-secret-store operations (o4_engine.secret_broker): requests
    # go out as SecretRequest events; secret_response commands come back
    # through the read loop below.  The read loop is therefore named as
    # the thread requests may never block on.
    broker = SecretBroker(
        send_request=lambda event: write_obj(serialize_event(event)),
        service_thread=threading.current_thread())
    UI.secret_broker = broker
    try:
        _initialize_pipeline_registries()
        session = EngineSession(version=_ortho4xp_version())
        session.app_driven = True       # the peer of this pipe is an app
        if owns_process:
            _install_terminate_signal_handler(session)
            _start_parent_death_watchdog(session)
            # The app's edit-cache session (O4_Edit_Cache): keyed by the
            # front end, so an engine restart inside one app keeps it.
            EDITCACHE.begin_session(_front_end_pid())
            # Below the user's applications, inherited by every tile,
            # airport and pool process this engine starts (#1225).
            O4_Machine_Slots.lower_priority()
        session.subscribe(lambda event: write_obj(serialize_event(event)))
        # The session's construction-time hello had no subscriber; the
        # transport owns the handshake framing and writes it first.
        write_obj(serialize_event(EngineHello(
            ortho4xp_version=_ortho4xp_version(),
            capabilities=("scan", "build", "enqueue_build", "cancel",
                          "tile_info", "config", "links", "siblings",
                          "secrets", "tile_settings_write",
                          "missing_art", "library"))))

        handlers = _build_handlers(session)
        handlers["secret_response"] = broker.deliver
        for raw_line in stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except (ValueError, TypeError) as exc:
                # Malformed line: report and keep reading (non-fatal).
                write_obj(serialize_event(
                    Error(fatal=False, text="malformed JSON line: %s" % exc)))
                continue
            if not isinstance(message, dict):
                write_obj(serialize_event(
                    Error(fatal=False,
                          text="command must be a JSON object")))
                continue

            command = message.get("cmd")
            call_id = message.get("id")
            if command == "shutdown":
                write_obj({"reply": call_id, "ok": True})
                if owns_process:
                    _stop_session_and_exit_process(
                        session, "shutdown command")
                return

            handler = handlers.get(command)
            if handler is None:
                write_obj({"reply": call_id, "ok": False,
                           "error": "unknown command: %r" % (command,)})
                continue

            arguments = {
                k: v for k, v in message.items() if k not in ("cmd", "id")
            }
            if command in _TAKES_REQUEST_ID:
                arguments["request"] = call_id
            # build's tiles arrive as JSON arrays; the session keys estimate
            # dicts by tile, so they must be hashable tuples again.
            if (command in ("build", "enqueue_build")
                    and "tiles" in arguments):
                arguments["tiles"] = [
                    tuple(tile) for tile in arguments["tiles"]
                ]
            try:
                result = handler(**arguments)
            except Exception as exc:  # a bad command must not end the session
                write_obj({"reply": call_id, "ok": False,
                           "error": str(exc)})
                continue
            write_obj({"reply": call_id, "ok": True,
                       "result": _json_safe(result)})
        if owns_process:
            # End-of-file: the front end exited, crashed, or retired this
            # worker.  A build command returns immediately (the session
            # runs it on a worker thread), so a build may well be in
            # flight right now — it must not keep building headless.
            _stop_session_and_exit_process(session, "standard input closed")
    finally:
        sys.stdout = saved_sys_stdout
        # The transport owned this session's lifecycle; leave the module
        # routing attributes clean for whatever runs next in-process.
        # Pending secret requests are failed rather than left to time
        # out on their worker threads.
        broker.shutdown()
        UI.secret_broker = None
        UI.engine_session = None
        UI.red_flag = False
