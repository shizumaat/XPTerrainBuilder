#!/usr/bin/env python3
"""Cross-platform icon generator: the app icon PNG -> icon.ico + PNG sizes.

RELEASES-PLAN.md §E.  ``scripts/make_icon.swift`` is CoreGraphics, so it
needs a Mac; the Windows exe icon, the Qt window icon and the AppImage's
hicolor icon all have to be produced on their own runners.  This script is
that producer, and it does NOT redraw the design: ``Resources/AppIcon.png``
is the design of record (rendered once from the Swift generator and
committed), and every output here is a resample of it.

Usage::

    python3 scripts/make_icon.py [--source Resources/AppIcon.png]
                                 [--out DIR] [--name xpterrainbuilder]
                                 [--quiet]

Outputs into ``--out`` (default ``build/icons``):

* ``icon.ico``            — 16/24/32/48/64/128/256 (PyInstaller ``icon=``)
* ``<name>-<N>.png``      — one PNG per size in 16…512
* ``<name>.png``          — the largest emitted PNG, the canonical file the
  Qt app hands ``QApplication.setWindowIcon`` and the AppImage installs as
  ``usr/share/icons/hicolor/256x256/apps/<name>.png``

Determinism: same source bytes in, byte-identical files out.  Pillow writes
no timestamp chunk, and the resample filter, mode and size list are all
pinned here — the release artifacts of two runs of the same commit must not
differ by their icons.  Sizes larger than the source are DROPPED rather than
upscaled (an upscaled icon is worse than an absent one, and silently
shipping a blurry 512 is the failure this refuses).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# The ICO is the Windows exe/shortcut icon: Explorer picks the frame that
# matches the current view, so all seven sizes ship inside the one file.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
# The PNG ladder: 16…512.  Linux desktops read hicolor by size; Qt picks the
# closest frame it is given.
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "Resources" / "AppIcon.png"
DEFAULT_OUT = REPO_ROOT / "build" / "icons"
DEFAULT_NAME = "xpterrainbuilder"


def _load(source: Path):
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - environment problem, not logic
        raise SystemExit(
            "ERROR: Pillow is required (it is pinned in "
            "Ortho4XP/requirements.txt: pillow==12.2.0)."
        )
    if not source.is_file():
        raise SystemExit(f"ERROR: no icon source at {source}")
    image = Image.open(source)
    image.load()
    # RGBA throughout: the ICO frames and every PNG must carry the alpha the
    # rounded-square design needs, whatever mode the source was saved in.
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    if image.width != image.height:
        raise SystemExit(
            f"ERROR: {source} is {image.width}x{image.height}; the icon "
            "source must be square."
        )
    return image


def _resize(image, size: int):
    from PIL import Image

    if size == image.width:
        return image.copy()
    return image.resize((size, size), Image.LANCZOS)


def generate(source: Path, out_dir: Path, name: str = DEFAULT_NAME,
             quiet: bool = False) -> dict:
    """Write icon.ico + the PNG ladder; return the manifest that was written."""
    image = _load(source)
    src_px = image.width

    png_sizes = [s for s in PNG_SIZES if s <= src_px]
    ico_sizes = [s for s in ICO_SIZES if s <= src_px]
    dropped = [s for s in PNG_SIZES + ICO_SIZES if s > src_px]
    if not ico_sizes:
        raise SystemExit(
            f"ERROR: {source} is only {src_px}px — too small for even a "
            "16px icon frame."
        )
    if dropped and not quiet:
        print(
            f"NOTICE: {source.name} is {src_px}px, smaller than the 512px "
            "ladder: emitting only "
            f"{', '.join(str(s) for s in png_sizes)} and NOT upscaling past "
            "the source (dropped: "
            f"{', '.join(str(s) for s in sorted(set(dropped)))})."
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for size in png_sizes:
        path = out_dir / f"{name}-{size}.png"
        _resize(image, size).save(path, format="PNG", optimize=False)
        written.append(path)

    # The canonical PNG: the largest frame, copied under the bare name so
    # consumers (Qt's setWindowIcon, the AppDir icon) need no size in their
    # path.  A copy, not a symlink: it is packaged into zips and AppImages.
    canonical = out_dir / f"{name}.png"
    canonical.write_bytes((out_dir / f"{name}-{png_sizes[-1]}.png").read_bytes())
    written.append(canonical)

    ico = out_dir / "icon.ico"
    # Pillow's ICO writer takes the frame list and resamples internally; hand
    # it the full-resolution image so every frame comes off the source.
    image.save(ico, format="ICO", sizes=[(s, s) for s in ico_sizes])
    written.append(ico)

    if not quiet:
        for path in written:
            print(f"  wrote {path.relative_to(out_dir.parent) if out_dir.parent in path.parents else path}"
                  f" ({os.path.getsize(path)} bytes)")
        print(f"icon.ico frames: {', '.join(str(s) for s in ico_sizes)}")

    return {
        "source": str(source),
        "source_px": src_px,
        "out_dir": str(out_dir),
        "name": name,
        "png_sizes": png_sizes,
        "ico_sizes": ico_sizes,
        "canonical_png": str(canonical),
        "ico": str(ico),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE),
                        help="the app icon PNG (design of record)")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="output directory (created)")
    parser.add_argument("--name", default=DEFAULT_NAME,
                        help="basename for the emitted PNGs")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    generate(Path(args.source).resolve(), Path(args.out).resolve(),
             args.name, args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
