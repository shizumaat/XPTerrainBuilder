"""One build-slot budget and one owner per tile for the two build-ahead
jobs that run at once: a flight's job (``flight_job_run``) and track
mode around the aircraft (``world_job_run``), which always runs while
imagery on demand and the World pack are on, whatever the flight plan
(owner 2026-11-12, #2019; World spec 2026-11-10 §8.5).

* **Priority.** :data:`_PRIORITY` ranks the owners, the flight first.
  The flight publishes its slot count and how many of its jobs wait
  for a slot (:meth:`BuildShare.publish`); track mode dispatches only
  into what is left (:meth:`BuildShare.free_for`), so a corridor
  deadline wins a contended slot.  Each job counts the other's running
  builds against the one budget (:meth:`BuildShare.others_running`).
* **One build per tile.** A job takes a tile before it builds it
  (:meth:`BuildShare.take`).  A tile another job is building or has
  built this session (staged or swapped) is never built again: a
  higher-ranked job of the same kind adopts it (the result goes to the
  adopter, at once when it is built; the old owner is told ``(tile,
  None)``: handed over), a lower-ranked job is refused.  A different kind (a flight's ``full`` departure over track
  mode's drape) waits for the drape, then replaces it.  The flight's
  tiles are its own (:meth:`BuildShare.claimed`): track mode leaves them.
* Results reach the owner through :meth:`BuildShare.poll`; a job that
  stops lets go of everything (:meth:`BuildShare.leave`).
"""
from __future__ import annotations

import threading
from typing import Dict, Iterable, List, Optional, Tuple

__all__ = ["BuildShare", "SHARE"]

#: Owners, highest priority first.
_PRIORITY = ("flight", "track")

Tile = Tuple[int, int]


def _rank(owner: str) -> int:
    return _PRIORITY.index(owner) if owner in _PRIORITY else len(_PRIORITY)


class BuildShare:
    """See the module.  Thread-safe: each job runs on its own thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._held: Dict[Tile, list] = {}     # tile -> [owner, kind, state]
        self._done: Dict[str, list] = {}      # owner -> [(tile, ok|None)]
        self._budget: Dict[str, Tuple[int, int]] = {}  # owner -> (slots, waiting)
        self._claims: Dict[str, frozenset] = {}

    # ------------------------------------------------------------- tiles

    def take(self, owner: str, tile, kind: str) -> str:
        """``"start"`` (build it), ``"adopted"`` (another job's build of
        the same kind is now ``owner``'s) or ``"busy"`` (leave it)."""
        tile = (int(tile[0]), int(tile[1]))
        with self._lock:
            held = self._held.get(tile)
            if held is None or held[0] == owner:
                self._held[tile] = [owner, kind, "building"]
                return "start"
            other, other_kind, state = held
            if _rank(owner) >= _rank(other):
                return "busy"
            if other_kind == kind:
                held[0] = owner
                self._done.setdefault(other, []).append((tile, None))
                if state == "built":
                    self._done.setdefault(owner, []).append((tile, True))
                return "adopted"
            if state == "building":
                return "busy"               # the drape first, then ours
            self._done.setdefault(other, []).append((tile, None))
            self._held[tile] = [owner, kind, "building"]
            return "start"

    def finish(self, tile, ok: bool) -> None:
        """A build ended: the result goes to the tile's owner now."""
        tile = (int(tile[0]), int(tile[1]))
        with self._lock:
            held = self._held.get(tile)
            if held is None:
                return
            self._done.setdefault(held[0], []).append((tile, bool(ok)))
            if ok:
                held[2] = "built"
            else:
                del self._held[tile]

    def drop(self, owner: str, tile) -> None:
        """``owner`` did not start the tile after all."""
        tile = (int(tile[0]), int(tile[1]))
        with self._lock:
            if (self._held.get(tile) or [None])[0] == owner:
                del self._held[tile]

    def poll(self, owner: str) -> List[tuple]:
        """``[(tile, ok)]`` for ``owner`` since the last call; ``ok`` None:
        the tile was handed to a higher-ranked job."""
        with self._lock:
            return self._done.pop(owner, [])

    def owner_of(self, tile) -> Optional[str]:
        with self._lock:
            held = self._held.get((int(tile[0]), int(tile[1])))
            return held[0] if held else None

    # ---------------------------------------------------- claims, slots

    def claim(self, owner: str, tiles: Iterable) -> None:
        """``owner``'s whole set of tiles (a flight's corridor, departure
        and destination): lower-ranked jobs leave them."""
        with self._lock:
            self._claims[owner] = frozenset(
                (int(t[0]), int(t[1])) for t in tiles)

    def claimed(self, owner: str, tile) -> bool:
        """Does a higher-ranked job claim ``tile``?"""
        tile = (int(tile[0]), int(tile[1]))
        with self._lock:
            return any(tile in tiles for other, tiles in self._claims.items()
                       if _rank(other) < _rank(owner))

    def publish(self, owner: str, slots: int, waiting: int) -> None:
        """``owner``'s slot count now and how many of its jobs wait for
        one."""
        with self._lock:
            self._budget[owner] = (max(0, int(slots)), max(0, int(waiting)))

    def leave(self, owner: str) -> None:
        """``owner`` stopped: its claims, budget and tiles go."""
        with self._lock:
            self._claims.pop(owner, None)
            self._budget.pop(owner, None)
            self._done.pop(owner, None)
            for tile, held in list(self._held.items()):
                if held[0] == owner:
                    del self._held[tile]

    def others_running(self, owner: str) -> int:
        """Builds other jobs run now (they count against one budget)."""
        with self._lock:
            return sum(1 for held in self._held.values()
                       if held[0] != owner and held[2] == "building")

    def free_for(self, owner: str, own_slots: int, own_running: int) -> int:
        """Slots ``owner`` may start now: the smallest budget of the jobs
        running, less every running build, less what higher-ranked jobs
        wait to start."""
        with self._lock:
            budget, waiting = int(own_slots), 0
            for other, (slots, wants) in self._budget.items():
                if other == owner:
                    continue
                budget = min(budget, slots)
                if _rank(other) < _rank(owner):
                    waiting += wants
            others = sum(1 for held in self._held.values()
                         if held[0] != owner and held[2] == "building")
        return max(0, budget - own_running - others - waiting)


#: The engine's one share (both runners use it).
SHARE = BuildShare()
