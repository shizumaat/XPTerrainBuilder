"""How the map loads the patch of the airport in view (#2061).

The patch's staleness check (spec patch-editor-20261015 §1.4) reads the
airport photos' cover, which finds every nearby airport's apt.dat across
the install: 11-24 s in a fresh engine on the owner's 1,474 packs, the
whole wait before the first patch appeared.  An engine with
``patch_staleness`` loads the patch without it and answers it on its own;
the answer completes the document it was asked for -- the file the
document was opened from -- and nothing else.

One rule in both apps (Mac: ``PatchViewLoad``), twinned on
``tests/fixtures/patch_view_load_cases.json``.
"""
from __future__ import annotations

__all__ = ["load_arguments", "staleness_applies"]


def load_arguments(tile: str, icao: str, fast: bool) -> dict:
    """``patch_load``'s arguments: ``staleness=False`` when the engine
    answers the check on its own (``fast``)."""
    arguments = {"tile": tile, "icao": icao}
    if fast:
        arguments["staleness"] = False
    return arguments


def staleness_applies(opened_path: str, answer_path: str) -> bool:
    """Whether a ``patch_staleness`` answer about ``answer_path``
    completes the document opened from ``opened_path``."""
    return bool(opened_path) and opened_path == answer_path
