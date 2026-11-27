"""THE GATEWAY ANSWER BEFORE THE PATCH (#2212).

Owner 2026-11-21T03:40Z: KPIT's tile "got all the way to completion, then
prompted me to download the gateway airport, and when I said yes the tile
started over the build".  The run-start question
(``gateway_stage.gateway_early``) reads the airport's OSM feeds already on
disk; a tile never built has none, so on a first build the question came
only once the patch was built, and an Install built it again (19 min).

This module asks inside the tile's vector step, once its feeds are on disk
and before any patch is built, and lets the patches wait for the answer:

* :func:`ask_tile` -- the tile's Global Airports airports that flatten or
  whose feeds show a deck / road-bridge candidate, asked now (one
  ``GatewayAirports(state="found")``; the app asks once per tile and
  airport set, so the run-start question is not shown twice); returns the
  ICAOs not yet answered.
* :func:`wait_for_answers` -- the step waits (``O4_Step_Wait``: no slot
  held) until each is answered -- Install done, Never, or Not now (the
  ``"later"`` action) -- or :data:`ANSWER_WAIT_S` passes.  An Install that
  lands in time makes the patch build once, against the Gateway pack (the
  driver selects the apt.dat after this wait).  An Install still
  downloading holds the wait up to :data:`INSTALL_WAIT_S`.
* :func:`before_patches` -- the vector step's hook (``o4_engine.session``
  hands it in as ``tile.gateway_before_patches``): asks, and returns the
  wait to run once the airport photos are fetched.
* :func:`note_answer` -- ``gateway_stage.gateway_choice`` records each
  answer with its time in :data:`ANSWERS` (a file: the step may run in a
  worker process of its own).

A lane or harness build (``O4_PACK_WRITES`` set) or a build with no
engine session asks nothing and never waits.
Build-time impact: one feed read per tile with a Global Airports airport
(seconds); a wait only while a question is open.
"""
from __future__ import annotations

import os
import time
import typing as _t

from auto_patch_v2.airport import pack_choice as _PC

__all__ = ["ANSWERS", "ANSWER_WAIT_S", "ask_tile", "before_patches",
           "note_answer", "wait_for_answers"]

#: how long the patches wait for an open question's answer
ANSWER_WAIT_S = 120.0
#: how long an Install the user chose may take before the patches go on
INSTALL_WAIT_S = 600.0
#: an answer older than this is not an answer to this run's question
ANSWER_STANDS_S = 12 * 3600.0
POLL_S = 0.5


def _answer_value(value: object) -> bool:
    """``"<action>@<epoch>"`` (:func:`note_answer`)."""
    return isinstance(value, str) and value.count("@") == 1


#: the last answer per airport: ``"install@<t>"`` | ``"installing@<t>"``
#: | ``"failed@<t>"`` | ``"never@<t>"`` | ``"later@<t>"``
ANSWERS = _PC.Store("gateway_airport_answers.json", allowed=_answer_value)


def note_answer(xplane_root: str, icao: str, action: str,
                now: float | None = None) -> None:
    """Record the user's ``action`` for ``icao`` (never raises)."""
    from . import gateway_stage as _GW
    try:
        stamp = time.time() if now is None else now
        ANSWERS.remember(_GW._choice_key(xplane_root, icao),
                         f"{action}@{stamp:.3f}")
    except OSError:
        pass


def _answer(xplane_root: str, icao: str, now: float) -> str:
    """The airport's standing answer (``""`` none, or one too old)."""
    from . import gateway_stage as _GW
    raw = ANSWERS.choice(_GW._choice_key(xplane_root, icao))
    action, _, stamp = raw.partition("@")
    try:
        if now - float(stamp) <= ANSWER_STANDS_S:
            return action
    except ValueError:
        pass
    return ""


def _asks() -> bool:
    """An interactive build: an engine session carries the question and it
    is not a lane build."""
    import O4_UI_Utils as UI
    return (UI.engine_session is not None
            and os.environ.get("O4_PACK_WRITES") is None)


def _unanswered(xplane_root: str, icao: str, now: float) -> bool:
    from . import gateway_stage as _GW
    return (_GW.STORE.choice(_GW._choice_key(xplane_root, icao)) != "never"
            and _answer(xplane_root, icao, now) in ("", "installing"))


def ask_tile(lat: int, lon: int, xplane_root: str | None,
             osm_root: str | None = None) -> list[str]:
    """Ask the tile's question now (module doc); the ICAOs left open.
    Never raises."""
    from . import gateway_stage as _GW
    try:
        if not xplane_root or not _asks():
            return []
        if osm_root is None:
            import O4_File_Names as FNAMES
            osm_root = FNAMES.OSM_dir
        now = time.time()
        cache: dict = {}
        rows = []
        for icao in dict.fromkeys(c.upper() for c in
                                  _GW._codes_of_tile(xplane_root, lat, lon)):
            if not _unanswered(xplane_root, icao, now):
                continue
            row = _GW._global_flatten(xplane_root, icao) \
                or _GW._early_bridges(xplane_root, icao, osm_root, cache)
            if row is not None:
                rows.append(row)
        if rows:
            _GW._say_rows(rows, "its taxiways cross roads that need")
            _GW._announce(lat, lon, "found", rows)
        return [r["icao"] for r in rows]
    except Exception as exc:
        _GW._say(1, f"  [gateway] the Gateway question before the patch "
                    f"failed ({exc})")
        return []


def wait_for_answers(xplane_root: str | None, icaos: _t.Iterable[str],
                     *, clock: _t.Callable[[], float] = time.monotonic,
                     sleep: _t.Callable[[float], None] = time.sleep
                     ) -> list[str]:
    """Wait (no slot held) for the answers to the open ``icaos`` (module
    doc); the ICAOs answered Install.  Stop ends the wait.  Never raises."""
    import O4_Step_Wait as STEP_WAIT
    import O4_UI_Utils as UI

    from . import gateway_stage as _GW
    icaos = list(icaos)
    try:
        if not xplane_root or not icaos:
            return []
        wait_s = ANSWER_WAIT_S
        started = clock()
        left = [i for i in icaos if _unanswered(xplane_root, i, time.time())]
        if left:
            _GW._say(0, f"  [gateway] {', '.join(left)}: the patch waits up "
                        f"to {wait_s:.0f} s for the Gateway answer, so it is "
                        "built once, against the pack X-Plane will draw.")
        with STEP_WAIT.waiting():
            while left and not UI.red_flag:
                now = time.time()
                limit = INSTALL_WAIT_S if any(
                    _answer(xplane_root, i, now) == "installing"
                    for i in left) else wait_s
                if clock() - started >= limit:
                    _GW._say(0, f"  [gateway] {', '.join(left)}: no answer "
                                "yet; the patch is built against Global "
                                "Airports (an Install later builds it "
                                "again).")
                    break
                sleep(POLL_S)
                left = [i for i in left
                        if _unanswered(xplane_root, i, time.time())]
        now = time.time()
        return [i for i in icaos if _answer(xplane_root, i, now) == "install"]
    except Exception as exc:
        _GW._say(1, f"  [gateway] the wait for the Gateway answer failed "
                    f"({exc})")
        return []


def before_patches(lat: int, lon: int, cifp_path: str
                   ) -> _t.Callable[[], list[str]] | None:
    """THE VECTOR STEP'S HOOK (module doc): ask the tile's question for
    the install ``cifp_path`` belongs to; the wait for its answers, or
    ``None`` with nothing open.  Never raises."""
    try:
        from auto_patch_v2.airport.cifp import xplane_root_from_cifp_path
        root = xplane_root_from_cifp_path(cifp_path)
    except Exception:
        return None
    icaos = ask_tile(lat, lon, root)
    if not icaos:
        return None
    return lambda: wait_for_answers(root, icaos)
