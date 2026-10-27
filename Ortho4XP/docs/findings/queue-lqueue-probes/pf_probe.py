"""Profile the boundary preflight for some tiles (attribution, not a timing A/B)."""
import cProfile
import pstats
import sys
import time

sys.path.insert(0, "src")
import O4_Config_Utils  # noqa: F401  (cfg globals)
from o4_engine import session as S

cells = [tuple(map(int, c.split(","))) for c in sys.argv[1:]]
import os, threading
def _spin():
    x = 0
    while True:
        for i in range(10000):
            x += i * i
for _ in range(int(os.environ.get("PF_SPIN", "0"))):
    threading.Thread(target=_spin, daemon=True).start()
if os.environ.get("PF_MEMO"):
    from auto_patch_v2.airport import cifp as _C
    _orig = _C.read_threshold_dicts
    _memo = {}
    def _memo_read(path):
        try:
            st = os.stat(path); key = (st.st_mtime_ns, st.st_size)
        except OSError:
            return _orig(path)
        hit = _memo.get(path)
        if hit is None or hit[0] != key:
            hit = (key, _orig(path)); _memo[path] = hit
        return {k: dict(v) for k, v in hit[1].items()}
    _C.read_threshold_dicts = _memo_read
sess = S.EngineSession.__new__(S.EngineSession)
for _ in range(int(__import__("os").environ.get("PF_WARM", "0"))):
    t0 = time.perf_counter()
    S.EngineSession._boundary_preflight(sess, 0, cells)
    print("warmup pass", round(time.perf_counter() - t0, 2), "s")
t = time.perf_counter()
pr = cProfile.Profile()
pr.enable()
ev = S.EngineSession._boundary_preflight(sess, 1, cells)
pr.disable()
print("preflight", cells, round(time.perf_counter() - t, 2), "s",
      len(ev.airports), "airports", ev.add_tiles)
pstats.Stats(pr).sort_stats("cumtime").print_stats(22)
