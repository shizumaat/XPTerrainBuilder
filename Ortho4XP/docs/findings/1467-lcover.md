# #1467 — the inset fetch slot and a strategy's download slot nest (lane lcover)

## Attribution (static read + a bounded synthetic repro)

* The per-airport inset loop (`O4_Airport_Elevation_Insets`, the fetch under
  `_held_provider_fetch_slot(code)`) holds one of the provider's in-process
  semaphore slots (default 2) and the machine-wide class
  `net:elevation:<code>` around the WHOLE `fetch_inset`.
* Inside that fetch, `tnm_cog`'s stripped prefetch and `las_tile_index`'s
  tile downloads fan out to WORKER THREADS that take
  `_held_provider_fetch_slot(code, slots)` -- the SAME semaphore.  Two
  airports of one provider hold both slots; their workers wait on
  `slot.acquire(timeout=0.5)` in a loop that ends only on Stop.  A true
  deadlock (re-entrancy per thread cannot help: the waiters are other
  threads).  `cwcb_lidar_api` had already dodged it with a private
  `code + ":tiles"` key.
* Side effect of the shared key: the semaphore is sized the first time a
  key is seen, so the outer default 2 silently capped the inner
  `fetch_slots=` pools (USGSOPR `fetch_slots=8` ran at 2 once an inset
  loop had touched the key).
* Repro: `tests/test_fetch_slot_nesting.py` with the outer slot swapped
  back to `_held_provider_fetch_slot(code)` -- the callers are still alive
  at the 8 s join ("HANG reproduced").

## Rule

One slot key per call path.  The inset fetch holds
`fetch_slots.held_inset_fetch_slot(code)` (key `<code>:insets`, machine class
`net:elevation:<code>:insets`); a ring/band cell holds `cell_fetch_class`
(#1464); a download holds `code` itself.  `cwcb_lidar_api`'s private
`:tiles` key folds back into the download key.

## Acceptance

The synthetic two-airport fan-out finishes within a 30 s join (it hangs
without the fix); the per-airport loop takes no `_held_provider_fetch_slot`
directly.
