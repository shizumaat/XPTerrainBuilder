"""The Build box under imagery on demand (RULINGS 2026-11-10e (1), (2)).

With ``imagery_on_demand`` on, the app manages the disk (the one budget
of 2026-11-10d), so every built tile goes straight into Custom Scenery and
a Build press never rebuilds a built tile: the Build box hides "When it's
done" with its "Install in X-Plane automatically" and "Skip tiles already
built", and both behave as on, whatever they were left at.  An explicit "Rebuild tile" still
rebuilds (with the switch hidden, its old advice "turn off Skip" could
not be followed).  The Mac app's mirror is ``BuildModel+OnDemandBuild``.
"""

from __future__ import annotations

__all__ = ["HIDDEN", "REBUILD_HINT", "apply", "installs", "skips_built"]

#: What on demand hides in the Build box, as window attributes: "When
#: it's done" and its two switches.
HIDDEN = ("build_done_label", "chk_auto_install", "chk_skip_built")
#: How a built tile is rebuilt while the Skip switch is hidden (the Mac
#: app's ``BuildModel.onDemandRebuildHint``).
REBUILD_HINT = "use Rebuild in the Library to rebuild one"


def apply(window, on: bool) -> None:
    """Show or hide :data:`HIDDEN` for the world switch ``on``."""
    window.on_demand_builds = bool(on)
    for attr in HIDDEN:
        getattr(window, attr).setVisible(not on)


def installs(window) -> bool:
    """Whether a tile that finishes is linked into Custom Scenery."""
    return (getattr(window, "on_demand_builds", False)
            or window.chk_auto_install.isChecked())


def skips_built(window, rebuild: bool = False) -> bool:
    """Whether a Build press leaves built tiles out; ``rebuild`` is the
    explicit "Rebuild tile", which under on demand never does."""
    if getattr(window, "on_demand_builds", False):
        return not rebuild
    return window.chk_skip_built.isChecked()
