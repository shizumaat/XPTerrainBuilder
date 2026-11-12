"""The live flight preview's own words and mark colors (#2001 follow-up,
owner 2026-11-12T19:28Z: the map shows exactly what X-Plane shows).
Mirror of the Mac app's ``Sources/SceneryKit/LivePreviewText.swift``;
``tests/test_live_preview.py`` fails when the two differ.

Keys: ``reload`` -- X-Plane still shows what was there before the file
changed (a square or a tile; drawn hatched); ``own`` -- X-Plane draws its
own scenery (no tile of ours), the map's base imagery shows, marked.
``own`` is the Fly legend's key of the same meaning (``O4_Fly_Text.
LEGEND``); these words are the preview's own, for the map labels and a
legend row.
"""
from __future__ import annotations

import O4_Glossary as GLOSSARY

__all__ = ["LEGEND", "MARK_COLORS", "OWN_LABEL", "RELOAD_LABEL"]

#: Drawn on a stale square or tile large enough to hold it.
RELOAD_LABEL = "Reload scenery to see"
#: Drawn on a tile where X-Plane draws its own scenery.
OWN_LABEL = GLOSSARY.TERMS["xplane_own_scenery"]
#: (key, words) for a legend row.
LEGEND = (("reload", "X-Plane shows the earlier imagery until you reload scenery"),
          ("own", OWN_LABEL))
#: The marks' colors, RGB (Mac: ``LivePreviewText.markColors``).
MARK_COLORS = {"reload": (255, 69, 58), "own": (140, 140, 140)}
