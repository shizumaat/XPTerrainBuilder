"""Why a pack-row action must wait (#2168).

A pack row's Revert, trees, Optimise and Adjust write the pack's files.
Only a run building a tile that writes THAT pack can be rewriting them; a
background job (World pack drapes, imagery on demand, storage) or a run on
other tiles never blocks the row.  Both front ends ask here — the mac app
through the engine's refusal, the Qt window in process — so the reason a
row waits is the engine's, named the same in both.
"""

from __future__ import annotations

# pack_forests / pack_optimise / pack_adjust actions that write the pack;
# "ask", "adjust" (the report) and "never" (a remembered answer) do not
WRITING_ACTIONS = frozenset({"update", "undo", "change"})


def busy_reason(pack_root: str, building_tiles) -> str:
    """The reason ``pack_root`` must wait, or ``""``.

    ``building_tiles`` are the live run's queued and building tile names
    (``Session.building_tiles``).
    """
    building = set(building_tiles or ())
    if not building or not pack_root:
        return ""
    from auto_patch import object_rebake

    hit = sorted(building & object_rebake.pack_tiles(pack_root))
    if not hit:
        return ""
    return ("the current run is building %s, which writes this pack; "
            "wait for %s to finish" % (", ".join(hit),
                                       "it" if len(hit) == 1 else "them"))
