"""AN ITEM MEMO FOR A FUNCTION THAT ASKS THE DEM (#2206; ``geom/item_memo``).

``geom/item_memo`` holds only answers that are pure functions of their key,
and the DEM is never in a key: a cached build's DEM witness
(``pipeline/front_cache``) names every question a stage asked, and a memo
that skipped the questions would hide them.  A function that reads the DEM
is held here instead, WITH its questions:

* computed, it asks a private :class:`~airport.dem_record.DemRecorder` over
  the real DEM, and its record (every sample, call and attribute it read)
  is kept beside the answer -- unless the record is opaque;
* asked again for the same key, the answer is served only when today's DEM
  gives every one of those answers with the same bits
  (``dem_record.holds``), else it is computed afresh;
* either way, the questions are said into the asking run's own recorder
  when its window is open (``DemRecorder.replay``), so the witness names
  what the answer read, as when the function asked it directly (the
  samples come as one block, not interleaved: a witness is a set of
  questions, held or not as a whole).

So the DEM is a checked input of every served answer, whatever the key."""
from __future__ import annotations

import typing as _t

from ..geom.item_memo import ItemMemo
from .dem_record import DemRecorder, holds

__all__ = ["asked"]


def _say_again(dem: _t.Any, record: dict) -> None:
    """``record``'s questions into ``dem``'s window (a recorder listening)."""
    if type(dem) is DemRecorder and dem.listening():
        dem.replay(record)


def asked(memo: ItemMemo, key: _t.Hashable, dem: _t.Any,
          compute: _t.Callable[[_t.Any], _t.Any]) -> _t.Any:
    """``compute(dem_to_ask)``'s answer for ``key``, held in ``memo`` with
    the DEM questions it asked (module docstring).  ``dem`` is the DEM the
    caller would have handed ``compute`` (a cached build's recorder, the
    DEM itself, or ``None``)."""
    if dem is None:
        return memo.get(key, lambda: compute(None))
    target = dem.target() if type(dem) is DemRecorder else dem
    got = memo.peek(key)
    if got is not None:
        answer, record = got[0]
        if holds(target, record) is None:
            _say_again(dem, record)
            return answer
    rec = DemRecorder(target)
    rec.recording(True)
    answer = compute(rec)
    record = rec.record()
    _say_again(dem, record)
    if rec.opaque() is None:
        memo.put(key, (answer, record))
    return answer
