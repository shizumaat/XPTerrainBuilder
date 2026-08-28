"""ROAD-PIECE LEDGER — no road-corridor piece is lost silently.

Spec ``docs/specs/tunnel-integrity-round-spec.md`` §T4.1, which charters
the ATTRIBUTION STEP FIRST: *"a per-pass shape-count checkpoint between
``build_service_road_network`` and ``to_osm`` (counts by role+ref per
pipeline pass, logged once per build) — name the pass that drops 40 rects
+ ~78 junction fills at LEMD."*

WHY A LEDGER AND NOT A GREP.  The minter's own line already reports what
it made (``N service_road rect(s) + M service_junction(s)``), and the
emitted patch reports what survived; between them sit ~56 named pipeline
seams and NOTHING reported the difference.  At LEMD the two numbers
disagreed by 40 rects and ~78 fills with no line anywhere naming a
remover — the class this campaign exists to kill (RULINGS: refusals
recorded and thrown away).

THE SEAMS ARE THE SEAMS THAT EXIST.  This module invents no call site.
It hangs off the two seam lists the pipeline already marks:

* ``pipeline._rod_ckpt`` — the 27 post-solve seams ("ONE named post-solve
  pipeline seam, for the probes that need it"), and
* ``geom_guard.coverage_probe`` — the 29 pre-solve/feature seams the
  coverage probe is sprinkled at for exactly this question ("a point that
  LOSES its owner between two tags names the pass that deleted it").

plus the two ENDPOINTS §T4 names: the service-road mint and the end of
the build (the last state before ``to_osm``).

WRITE-ONLY.  It reads ``layout.shapes`` and appends counters; it never
mutates a shape.  Gate ``O4_ROAD_PIECE_LEDGER`` (default ``1`` — ON; the
instrument is law, not behaviour).  ``O4_ROAD_PIECE_LEDGER=all`` widens
the tracked family from the road/tunnel set to EVERY ``(role, ref)`` pair.
"""
from __future__ import annotations

import os
from collections import Counter

import O4_UI_Utils as UI

_ENV = "O4_ROAD_PIECE_LEDGER"
_STATE_ATTR = "_road_piece_ledger"

#: The ROAD-CORRIDOR family §T4 is about, plus the tunnel pavement the
#: same passes remove.  A role here is tracked whatever its ``ref``; a
#: ``ref`` prefix here is tracked whatever its role (a claimed corridor
#: rides ``ref=tunnel_road`` on several roles).
_TRACKED_ROLES = frozenset({
    "service_road", "service_junction", "groundside_pavement",
    "tunnel_ramp", "retaining_wall", "tunnel_trench",
})
_TRACKED_REF_PREFIXES = ("tunnel_",)


def mode() -> str:
    """``"off"`` | ``"road"`` (default) | ``"all"``."""
    raw = (os.environ.get(_ENV) or "1").strip().lower()
    if raw in ("0", "off", "no", "false"):
        return "off"
    if raw == "all":
        return "all"
    return "road"


def _tracked(role: str, ref: str, all_families: bool) -> bool:
    if all_families:
        return True
    if role in _TRACKED_ROLES:
        return True
    return any(ref.startswith(p) for p in _TRACKED_REF_PREFIXES)


def _census(layout, all_families: bool) -> Counter:
    """``{(role, ref): count}`` over the layout's live shapes."""
    out: Counter = Counter()
    for s in (getattr(layout, "shapes", None) or ()):
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        role = getattr(s, "role", "") or ""
        ref = getattr(s, "ref", "") or ""
        if _tracked(role, ref, all_families):
            out[(role, ref)] += 1
    return out


def checkpoint(layout, name: str) -> None:
    """Record the ``(role, ref)`` census at pipeline seam ``name``.

    Never raises: an instrument that can fail a build is a worse
    instrument than none.
    """
    m = mode()
    if m == "off":
        return
    try:
        state = getattr(layout, _STATE_ATTR, None)
        if state is None:
            state = []
            setattr(layout, _STATE_ATTR, state)
        state.append((name, _census(layout, m == "all")))
    except Exception:                                    # pragma: no cover
        return


#: The ROAD FAMILY for the join rule: a piece of any of these roles is
#: the corridor's own pavement, whatever ``ref`` a later pass gave it.
ROAD_FAMILY_ROLES = frozenset({
    "service_road", "service_junction", "junction",
    "groundside_pavement",
})


def log_removal(layout, shape, predicate: str, *, area_m2=None) -> None:
    """ONE LINE PER PIECE REMOVED — portal-corridor-claim §1's form,
    carried to the road-corridor removers (§T4.1).

    ``[road-piece-remove] <predicate>: role=… ref=… @lat,lon area=…``.
    An aggregate count may remain as a summary; THIS is the law, because
    a removal recorded only as a number is a removal nobody can find.
    Never raises.
    """
    if mode() == "off":
        return
    try:
        poly = getattr(shape, "polygon", None)
        role = getattr(shape, "role", "") or "-"
        ref = getattr(shape, "ref", "") or "-"
        where = ""
        if poly is not None and not poly.is_empty:
            if area_m2 is None:
                area_m2 = poly.area
            try:
                pt = poly.representative_point()
                lat, lon = layout.m_to_ll(pt.x, pt.y)
                where = f" @{lat:.7f},{lon:.7f}"
            except Exception:                            # pragma: no cover
                where = ""
        UI.vprint(1,
            f"  [road-piece-remove] {predicate}: role={role} ref={ref}"
            f"{where}"
            + (f" area={area_m2:.1f} m²" if area_m2 is not None else ""))
    except Exception:                                    # pragma: no cover
        return


def joins_a_surviving_neighbour(piece, survivors, tol_m: float = 0.05
                                ) -> bool:
    """True when ``piece`` TOUCHES a surviving road-family polygon.

    §T4.1: *"fix THAT dropper so surviving corridors keep their fills"*.
    The runway clip's sliver rule is calibrated for taxi-intersection
    remainders — a piece nothing survives a 1 m inward buffer of is a
    hairline.  A CORRIDOR JOIN is exactly that shape and is not a
    hairline: it is the connective tissue between two rects, and
    deleting it emits the corridor as disconnected rectangles at
    different levels (RULINGS 2026-08-28 item 8, ways -10376/-10377).
    """
    if piece is None or piece.is_empty:
        return False
    try:
        for other in survivors:
            if other is None or other.is_empty:
                continue
            if piece.distance(other) <= tol_m:
                return True
    except Exception:                                    # pragma: no cover
        return False
    return False


def _fmt_delta(delta: Counter) -> str:
    rows = sorted(delta.items(), key=lambda kv: (-abs(kv[1]), kv[0]))
    return "  ".join(
        f"{role or '-'}/{ref or '-'} {n:+d}" for (role, ref), n in rows)


def report(layout, icao: str = "") -> None:
    """ONE log block per build: every seam that CHANGED a tracked count,
    with the per-``(role, ref)`` delta, and the mint→end summary.

    Printed even when nothing changed — an absent block means the ledger
    did not run, which is a different fact from "nothing was dropped".
    """
    if mode() == "off":
        return
    try:
        state = list(getattr(layout, _STATE_ATTR, None) or ())
    except Exception:                                    # pragma: no cover
        return
    if not state:
        return
    try:
        tag = f"{icao}: " if icao else ""
        first_name, first = state[0]
        last_name, last = state[-1]
        lines = [
            f"  [road-piece-ledger] {tag}{len(state)} seam(s) from "
            f"{first_name!r} to {last_name!r} — per-pass (role, ref) "
            f"deltas; a piece that vanishes here is named by the pass "
            f"that took it (§T4)."]
        prev_name, prev = first_name, first
        n_changed = 0
        for name, cur in state[1:]:
            delta = Counter()
            for key in set(cur) | set(prev):
                d = cur.get(key, 0) - prev.get(key, 0)
                if d:
                    delta[key] = d
            if delta:
                n_changed += 1
                lines.append(
                    f"  [road-piece-ledger]   {name:<34} "
                    f"{_fmt_delta(delta)}")
            prev_name, prev = name, cur
        net = Counter()
        for key in set(last) | set(first):
            d = last.get(key, 0) - first.get(key, 0)
            if d:
                net[key] = d
        net_label = f"NET {first_name} → {last_name}"
        lines.append(
            f"  [road-piece-ledger]   {net_label:<34} "
            + (_fmt_delta(net) if net else "no change")
            + f"   ({n_changed} seam(s) moved a tracked count)")
        for ln in lines:
            UI.vprint(1, ln)
    except Exception as exc:                             # pragma: no cover
        try:
            UI.vprint(1, f"  [road-piece-ledger] report FAILED ({exc!r}) "
                         f"— piece movement NOT measured this build.")
        except Exception:
            pass
