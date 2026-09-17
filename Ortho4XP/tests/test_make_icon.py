"""Twin for ``scripts/make_icon.py`` (RELEASES-PLAN §E).

The Windows exe icon, the Qt window icon and the AppImage's hicolor icon are
all produced on their own runners by this script, from the committed design
of record ``Resources/AppIcon.png``.  Nothing downstream notices a bad icon:
a missing ICO frame degrades to a blurry Explorer entry, a PNG without an
alpha channel ships a black square behind the rounded corners, and an
upscaled 512 is simply blurry.  So the frame list, the per-PNG dimensions,
the alpha channel, the no-upscale rule and byte determinism are pinned here.

Hermetic: the repo's own AppIcon.png plus synthetic sources, into
``tmp_path``.  No network, no freeze, no X-Plane install.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_DIR.parent
MAKE_ICON = REPO_ROOT / "scripts" / "make_icon.py"
APP_ICON = REPO_ROOT / "Resources" / "AppIcon.png"

pytestmark = pytest.mark.skipif(
    not MAKE_ICON.is_file() or not APP_ICON.is_file(),
    reason="engine used standalone: the app-side icon assets are absent",
)

Image = pytest.importorskip("PIL.Image", reason="Pillow is a pinned engine dep")

# Must match scripts/make_icon.py.  Replicated (not imported) on purpose:
# the numbers are the contract, and a silent edit to the script should fail
# here rather than reach a release artifact.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
NAME = "xpterrainbuilder"


def _run(out_dir: Path, source: Path = APP_ICON, name: str = NAME):
    return subprocess.run(
        [sys.executable, str(MAKE_ICON), "--source", str(source),
         "--out", str(out_dir), "--name", name],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )


def test_ico_carries_every_windows_frame(tmp_path):
    out = tmp_path / "icons"
    _run(out)
    ico = out / "icon.ico"
    assert ico.is_file()
    with Image.open(ico) as image:
        sizes = sorted(image.ico.sizes())
    assert sizes == [(s, s) for s in ICO_SIZES]


def test_every_png_has_its_size_and_an_alpha_channel(tmp_path):
    out = tmp_path / "icons"
    _run(out)
    for size in PNG_SIZES:
        path = out / f"{NAME}-{size}.png"
        assert path.is_file(), f"missing {path.name}"
        with Image.open(path) as image:
            assert image.size == (size, size)
            assert image.mode == "RGBA", f"{path.name} lost its alpha channel"
            assert image.getchannel("A").getextrema()[0] < 255, (
                f"{path.name} is fully opaque — the rounded-square design's "
                "transparent corners were flattened"
            )


def test_canonical_png_is_the_largest_frame(tmp_path):
    out = tmp_path / "icons"
    _run(out)
    canonical = out / f"{NAME}.png"
    assert canonical.read_bytes() == (out / f"{NAME}-512.png").read_bytes()


def test_output_is_deterministic(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    _run(first)
    _run(second)
    names = sorted(p.name for p in first.iterdir())
    assert names == sorted(p.name for p in second.iterdir())
    for name in names:
        assert (first / name).read_bytes() == (second / name).read_bytes(), (
            f"{name} differs between two runs of the same source"
        )


def test_small_source_is_not_upscaled(tmp_path):
    """A 128px source emits 16…128 and says so — never a blurry 512."""
    source = tmp_path / "small.png"
    with Image.open(APP_ICON) as image:
        image.convert("RGBA").resize((128, 128), Image.LANCZOS).save(source)
    out = tmp_path / "icons"
    result = _run(out, source=source)
    assert "NOTICE" in result.stdout and "128px" in result.stdout
    assert not (out / f"{NAME}-256.png").exists()
    assert not (out / f"{NAME}-512.png").exists()
    with Image.open(out / "icon.ico") as ico:
        assert sorted(ico.ico.sizes()) == [(s, s) for s in ICO_SIZES
                                           if s <= 128]
    assert (out / f"{NAME}.png").read_bytes() == (
        out / f"{NAME}-128.png").read_bytes()


def test_non_square_source_refused(tmp_path):
    source = tmp_path / "wide.png"
    with Image.open(APP_ICON) as image:
        image.convert("RGBA").resize((256, 128), Image.LANCZOS).save(source)
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        _run(tmp_path / "icons", source=source)
    assert "square" in excinfo.value.stderr
