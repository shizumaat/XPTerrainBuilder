"""Release a build's DATA-PREP refresh locks before its compute steps.

THE MEASURED COST (llocks, 2026-11-14).  ``build_airport.py`` held every
``--refresh-data`` scope's lock (``dem``, ``osm_layers``, ``rings``,
``parking`` ...) for the WHOLE build: LFLL held them 1 h 45 min, then
KBNA and OTHH back to back (~2.5 h), and every other lane's capture or
refresh was refused "lock held" while those builds were only computing.

THE RULE.  A scope whose refresh is one of the harness's own prep passes
(:data:`PREP_SCOPES`) is written BEFORE the build and never by it, so its
lock is released the moment the prep ends — after the re-judge and, on a
tile build, the bathymetry band admission — unless a pre-flight still
names an artifact of that scope as owed to the build, in which case the
build keeps it (the old behaviour, by name).  Every other scope
(``pack_rebake``, ``airport_mod_cache``, ``osm_roadfeed``, the caches)
is written by the build itself and stays held to the end.

THE CONSISTENCY GUARANTEE IS KEPT, NOT TRADED.  At release the shared
repo is snapshotted (``mid``) and the guard stops authorising the
released scopes, so from then on:

* a write THIS build makes into a released scope is refused at the call
  (``guard.blocked``) and named by the post-build refusal;
* a write ANOTHER lane makes into the build's input set lands in the
  build window ``mid -> after`` and is audited as unauthorised: in scope
  it CONTAMINATES the run, out of scope it is an external candidate —
  either way the artifact ledger refuses to store the result;
* the ledger stamps this run's own refresh from the prep window
  ``before -> mid`` only, so another lane's later refresh is never
  recorded as this run's.
"""
from __future__ import annotations

import time

from shared_repo_guard import scope_of, snapshot_diff

#: The scopes whose refresh is a harness PREP pass that completes before
#: the build: ``las_tiles`` (``--seed-from``), ``osm_layers``, ``shore``,
#: ``parking``, ``runway_refs``, ``dem`` (incl. ``--warm-insets``) and
#: ``rings``.  ``airport_mod_cache`` has a prep pass too, but an
#: authorised one is also left SHARED for the build's own writes
#: (``redirect_engine_caches``), so it is not here.
PREP_SCOPES = frozenset({"las_tiles", "osm_layers", "shore", "parking",
                         "runway_refs", "dem", "rings"})

#: The holder record's expected-release text once the prep has released.
HELD_THROUGH_BUILD = ("at the end of the build: the build itself writes "
                      "this scope")


class PrepRelease:
    """The one release point of a build's prep-scope locks.

    ``snapshot`` is the caller's full shared-repo (+ install) snapshot
    function — the same one that took ``before``.  :meth:`release` is
    idempotent; nothing is released when no lock qualifies, and then the
    audit is the whole-window one, unchanged.
    """

    def __init__(self, locks, guard, snapshot, prog=None):
        self.locks = list(locks)
        self.guard = guard
        self.snapshot = snapshot
        self.prog = prog
        self.done = False
        self.mid = None
        self.released: list = []
        self.kept_owed: list = []
        self.released_at = None

    def release(self, owed=()) -> list:
        """Release every held prep-scope lock not in ``owed`` (the scopes a
        pre-flight still names an artifact of).  Returns the scopes."""
        if self.done:
            return self.released
        self.done = True
        owed = set(owed or ())
        go = [lk for lk in self.locks
              if lk.held and lk.scope in PREP_SCOPES and lk.scope not in owed]
        self.kept_owed = sorted(lk.scope for lk in self.locks
                                if lk.scope in PREP_SCOPES
                                and lk.scope in owed)
        for lk in self.locks:
            if lk not in go:
                lk.set_phase("build", HELD_THROUGH_BUILD)
        if not go:
            return self.released
        # SNAPSHOT FIRST, then release: anything after ``mid`` is not
        # this run's prep.
        self.mid = self.snapshot()
        self.released = sorted(lk.scope for lk in go)
        if self.guard is not None:
            self.guard.requested -= set(self.released)
        for lk in go:
            lk.release()
        self.released_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        if self.prog is not None:
            self.prog.note(
                f"PREP DONE: released shared-repo lock(s) {self.released} "
                f"before the build; the guard no longer authorises them and "
                f"any change to them from here is audited as this build's "
                f"corpus moving under it (held through the build: "
                f"{self.held_scopes()}"
                + (f"; kept, still owed to the build: {self.kept_owed}"
                   if self.kept_owed else "") + ")")
        return self.released

    def held_scopes(self) -> list:
        return sorted(lk.scope for lk in self.locks
                      if lk.scope not in self.released)

    def audit_changes(self, before: dict, after: dict, requested) -> tuple:
        """``(changes, scopes)`` for ``report_unauthorised_writes``.

        Nothing released: the whole window under every requested scope.
        Released: the prep window minus the released scopes' own (locked,
        authorised) writes, plus the WHOLE build window, audited under the
        held scopes only."""
        requested = set(requested or ())
        if self.mid is None:
            return snapshot_diff(before, after), requested
        prep = snapshot_diff(before, self.mid)
        build = snapshot_diff(self.mid, after)
        released = set(self.released)
        changes = {k: sorted({r for r in prep[k]
                              if scope_of(r) not in released}
                             | set(build[k]))
                   for k in ("added", "modified", "removed")}
        return changes, requested - released

    def scope_changes(self, scope: str, before: dict, after: dict) -> dict:
        """The window a scope's ledger record is stamped from: the prep
        window for a released scope, the whole run for a held one."""
        end = self.mid if scope in self.released else after
        diff = snapshot_diff(before, end)
        return {k: [r for r in v if scope_of(r) == scope]
                for k, v in diff.items()}

    def record(self, after: dict = None) -> dict:
        """What rides in ``<tag>.frame.json``."""
        rec = {"released_after_prep": self.released,
               "released_at": self.released_at,
               "held_through_build": self.held_scopes(),
               "kept_owed_to_build": self.kept_owed}
        if self.mid is not None and after is not None:
            rec["build_window_writes"] = snapshot_diff(self.mid, after)
        return rec
