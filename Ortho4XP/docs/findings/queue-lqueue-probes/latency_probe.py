"""Read-loop command latency while preview threads (Airports card,
boundary preflight) run in the same process -- attribution probe.

argv: TILE ICAO MODE   MODE = before (CIFP memo off) | after
env:  PROBE_CARDS=N  concurrent card threads; PROBE_SPIN=N GIL spinners
"""
import os
import sys
import threading
import time

sys.path.insert(0, "src")
import O4_Config_Utils  # noqa: F401
from auto_patch_v2.airport import cifp as C
try:
    from o4_engine import build_airports as BA
except ImportError:          # 1.0.432 had no Airports card
    BA = None
from o4_engine import patch_commands as PC
from o4_engine import session as S

tile, icao, mode = sys.argv[1], sys.argv[2], sys.argv[3]
if mode == "before":
    def _uncached(path):
        runways = C.read_cifp_runways(path)
        return {"RW" + k: {"lat": r.lat, "lon": r.lon,
                           "elevation_m": r.elevation_m,
                           "displaced_m": r.displaced_m}
                for k, r in runways.items()}
    C.read_threshold_dicts = _uncached


def lat_of(fn, *a):
    t = time.perf_counter()
    fn(*a)
    return time.perf_counter() - t


def spin():
    x = 0
    while True:
        for i in range(10000):
            x += i * i


print("warm-up (one card + one patch_load, idle)")
if BA:
    print("  card  [61,-151]  %.2f s" % lat_of(BA.build_airports, [(61, -151)]))
print("  preflight idle   %.2f s" % lat_of(
    S.EngineSession._boundary_preflight,
    S.EngineSession.__new__(S.EngineSession), 0, [(61, -151), (61, -150)]))
print("  patch_list idle  %.3f s" % lat_of(PC.patch_list, tile))
print("  patch_load idle  %.3f s" % lat_of(PC.patch_load, tile, icao))
if BA:
    print("  card again       %.2f s" % lat_of(BA.build_airports, [(61, -151)]))
print("  preflight again  %.2f s" % lat_of(
    S.EngineSession._boundary_preflight,
    S.EngineSession.__new__(S.EngineSession), 0, [(61, -151), (61, -150)]))

for _ in range(int(os.environ.get("PROBE_SPIN", "0"))):
    threading.Thread(target=spin, daemon=True).start()
sess = S.EngineSession.__new__(S.EngineSession)
jobs = []
t0 = time.perf_counter()
for k in range(int(os.environ.get("PROBE_CARDS", "2")) if BA else 0):
    cells = [(61, -151), (61, -150)][: 1 + k % 2]
    th = threading.Thread(target=BA.build_airports, args=(cells,), daemon=True)
    th.start()
    jobs.append(th)
def _press():
    S.EngineSession._boundary_preflight(sess, 1, [(61, -151), (61, -150)])
    pf_done.append(time.perf_counter() - t0)


pf_done = []
pf = threading.Thread(target=_press, daemon=True)
pf.start()
jobs.append(pf)
worst_list = worst_load = 0.0

while any(j.is_alive() for j in jobs):
    worst_list = max(worst_list, lat_of(PC.patch_list, tile))
    worst_load = max(worst_load, lat_of(PC.patch_load, tile, icao))
    time.sleep(0.05)
print("%s: Queue preflight answered in %.2f s; preview threads done in %.2f s; worst patch_list %.3f s, "
      "worst patch_load %.3f s" % (mode, pf_done[0], time.perf_counter() - t0,
                                   worst_list, worst_load))
