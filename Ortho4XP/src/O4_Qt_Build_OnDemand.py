"""The Build box under imagery on demand (RULINGS 2026-11-10e (1), (2);
the Skip half replaced by #2043, owner 2026-11-13T13:09/13:11Z).

With ``imagery_on_demand`` on, the app manages the disk (the one budget
of 2026-11-10d), so every built tile goes straight into Custom Scenery:
the Build box hides "When it's done" with its "Install in X-Plane
automatically" and "Skip tiles already built".  Install behaves as on;
Skip behaves as OFF -- a Build or Queue press builds every tile the user
selected, a built one rebuilt (an airport list typed in the search field
queues all its tiles, a tile picked during a run joins it).  The Mac
app's mirror is ``BuildModel+OnDemandBuild``.
"""

from __future__ import annotations

__all__ = ["HIDDEN", "apply", "installs", "skips_built"]

#: What on demand hides in the Build box, as window attributes: "When
#: it's done" and its two switches.
HIDDEN = ("build_done_label", "chk_auto_install", "chk_skip_built")


def apply(window, on: bool) -> None:
    """Show or hide :data:`HIDDEN` for the world switch ``on``."""
    window.on_demand_builds = bool(on)
    for attr in HIDDEN:
        getattr(window, attr).setVisible(not on)


def installs(window) -> bool:
    """Whether a tile that finishes is linked into Custom Scenery."""
    return (getattr(window, "on_demand_builds", False)
            or window.chk_auto_install.isChecked())


def skips_built(window) -> bool:
    """Whether a Build press leaves built tiles out: only the visible Skip
    switch, so never under on demand (#2043; the Mac app's
    ``BuildModel.skipsBuiltTiles``)."""
    if getattr(window, "on_demand_builds", False):
        return False
    return window.chk_skip_built.isChecked()
