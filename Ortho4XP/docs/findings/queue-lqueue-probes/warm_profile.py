"""Warm-path profile of the card and patch_load (attribution)."""
import cProfile
import pstats
import sys

sys.path.insert(0, "src")
import O4_Config_Utils  # noqa: F401
from o4_engine import build_airports as BA
from o4_engine import patch_commands as PC

tile, icao = sys.argv[1], sys.argv[2]
BA.build_airports([(61, -151)])
PC.patch_load(tile, icao)
for label, fn in (("card", lambda: BA.build_airports([(61, -151)])),
                  ("patch_load", lambda: PC.patch_load(tile, icao))):
    pr = cProfile.Profile()
    pr.enable()
    fn()
    pr.disable()
    print("=====", label)
    pstats.Stats(pr).sort_stats("tottime").print_stats(12)
