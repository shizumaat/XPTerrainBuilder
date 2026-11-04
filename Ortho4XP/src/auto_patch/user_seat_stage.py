"""HAND-SET OBJECT SEATS IN THE OBJECT STAGE (issue #1703).

The seats a user gave pack objects in the patch editor
(``auto_patch_v2.airport.user_seats``, beside the patch) are a layer of
the pack DSF's write, recorded in its provenance like the 3D forest
upgrade: ``dsf_write.write_pack(seats=)``.

ONE WRITER: the placement write (``object_stage``) carries
:func:`file_seats`, whether the mesh was built from the airport's auto
patch or from its EDITED patch (owner RULINGS 2026-11-03e, #1637: the
pack is re-placed against the new mesh and the hand-set seats win over
the re-seat; this superseded 2026-10-15d (5), under which an edited patch
wrote the hand-set seats alone and left every other object baked against
an older mesh).

Nothing here raises into the build: a failed write is one log line.
"""
from __future__ import annotations

import typing as _t

__all__ = ["file_seats", "say_seated"]


def file_seats(patch_dir: str, icao: str, plan_key: str = ""
               ) -> dict[str, dict] | None:
    """``{ICAO: {row: UserSeat}}`` from the seats file for
    ``write_pack(seats=)`` (``{ICAO: {}}`` with none: an Automatic clears
    the DSF's); ``None`` — keep what the DSF records — for a companion
    pack's plan (``ICAO~k``: the editor seats the airport's own pack) or
    an unreadable file."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import user_seats as _us
    icao = str(icao).upper()
    if plan_key and plan_key.upper() != icao:
        return None
    try:
        return {icao: _us.read(patch_dir, icao)}
    except (OSError, ValueError) as exc:
        UI.vprint(0, f"  [v2 placement] {icao}: hand-set object elevations "
                     f"unreadable ({exc}); the pack keeps the ones it has")
        return None


def say_seated(icao: str, result: _t.Any) -> None:
    """The log line of a write that placed hand-set seats."""
    import O4_UI_Utils as UI
    n = len(getattr(result, "hand_seated", ()) or ())
    if n:
        UI.vprint(1, f"  [v2 placement] {icao}: {n} object(s) at the elevation "
                     f"set by hand")

