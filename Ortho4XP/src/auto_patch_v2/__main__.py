"""``python -m auto_patch_v2 build ICAO --out DIR`` (see ``pipeline``)."""
import sys

from .pipeline.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
