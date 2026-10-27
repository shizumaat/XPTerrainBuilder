"""#1467: the inset fetch slot and a strategy's download slot never nest on
one pool.  Two airports of one provider each hold an inset-fetch slot while
the fetch inside fans its downloads out to worker threads that take the
provider's download slots (``tnm_cog``'s stripped prefetch,
``las_tile_index``'s tiles).  On one pool the two callers hold both slots
and their own workers queue behind them forever; on two pools they finish.
Bounded: a hang fails the join timeout, it never hangs the suite."""
from __future__ import annotations

import inspect
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
from elevation_access import fetch_slots as FS  # noqa: E402

JOIN_TIMEOUT_S = 30.0


def _airport_fetch(code, both_holding, downloads):
    with FS.held_inset_fetch_slot(code):
        both_holding.wait(timeout=JOIN_TIMEOUT_S)

        def _download(_number):
            with FS._held_provider_fetch_slot(code, 2):
                downloads.append(_number)

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(_download, range(2)))


def test_two_airports_fanning_downloads_out_never_deadlock():
    code = "NESTPROV1467"
    both_holding = threading.Barrier(2)
    downloads = []
    callers = [
        threading.Thread(
            target=_airport_fetch, args=(code, both_holding, downloads),
            daemon=True)
        for _ in range(2)
    ]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join(JOIN_TIMEOUT_S)
    assert not any(caller.is_alive() for caller in callers), (
        "the inset fetch slot and the download slot share one pool")
    assert len(downloads) == 4


def test_the_three_call_paths_have_three_keys():
    keys = {FS.inset_fetch_key("X"), FS.cell_fetch_class("X"),
            FS.machine_class("X")}
    assert len(keys) == 3
    assert FS.machine_class(FS.inset_fetch_key("X")) != FS.machine_class("X")


def test_the_per_airport_loop_holds_the_inset_key():
    source = inspect.getsource(INSETS)
    assert "held_inset_fetch_slot(code)" in source
    assert "_held_provider_fetch_slot(" not in source
