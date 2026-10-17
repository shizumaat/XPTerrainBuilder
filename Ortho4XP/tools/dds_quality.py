"""Per-mip quality and speed of the in-process DDS encoder against today's converter.

texture-encode-spec section 5 steps 1-3 (owner RULINGS 2026-10-17a Q5: the in-process
encoder ships off and becomes default only on the owner's sim read; this is the table the
read is asked with).  For every texture (a cached orthophoto JPEG; READ ONLY):

* ``tool``   — today's converter as ``convert_texture`` runs it: DDSTool ``--png2dxt1|5`` on
  macOS, ``nvcompress -bc1|-bc3 -fast`` elsewhere (``O4_Imagery_Utils.dds_convert_cmd``);
  a masked (``--mask``) texture is saved as the temp PNG first, as in production;
* ``inproc`` — ``O4_DDS_Encode.encode_file`` (the pixels, no PNG);

both decoded with ``O4_DDS_Decode`` and scored per mip level (PSNR and block SSIM of RGB,
and alpha PSNR for BC3) against the SOURCE's gamma-2.2 chain, plus seconds per texture
(``--runs`` serial runs, min-max).  ``--mip-filter`` instead says which chain (stored value,
sRGB, gamma 2.2) each converter's decoded mips sit closest to (step 1).

    venv/bin/python tools/dds_quality.py --out /tmp/q T1.jpg T2.jpg ... [--mask M.png]
    venv/bin/python tools/dds_quality.py --out /tmp/q --mip-filter T1.jpg

Outputs (DDS files, ``quality.json``) go to ``--out`` only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import O4_DDS_Decode as DECODE  # noqa: E402
import O4_DDS_Encode as ENCODE  # noqa: E402
import O4_DDS_Mips as MIPS  # noqa: E402


def tool_command(dxt5: bool, src: str, out: str, binary: str | None = None) -> list[str]:
    """The subprocess converter's command line exactly as ``convert_texture`` builds it."""
    if binary is None:
        import O4_Imagery_Utils as IMG
        binary = IMG.dds_convert_cmd
    if "dar" in sys.platform and "nvcompress" not in os.path.basename(binary):
        return [binary, "--png2dxt5" if dxt5 else "--png2dxt1", src, out]
    return [binary, "-bc3" if dxt5 else "-bc1", "-fast", src, out]


def source_pixels(path: str, mask: str | None) -> np.ndarray:
    """RGBA uint8 of the texture; the mask (resized to the texture) is its alpha."""
    rgb = Image.open(path).convert("RGB")
    alpha = (Image.open(mask).convert("L").resize(rgb.size, Image.Resampling.BICUBIC)
             if mask else Image.new("L", rgb.size, 255))
    return np.dstack([np.asarray(rgb), np.asarray(alpha)])


def score(dds_path: str, reference: list[np.ndarray], masked: bool) -> list[dict]:
    """PSNR / SSIM per level of a DDS file against ``reference`` levels."""
    levels = DECODE.decode_dds(open(dds_path, "rb").read())
    rows = []
    for got, ref in zip(levels, reference):
        row = {"psnr": DECODE.psnr(got[..., :3], ref[..., :3]),
               "ssim": DECODE.ssim(got[..., :3], ref[..., :3])}
        if masked:
            row["alpha_psnr"] = DECODE.psnr(got[..., 3], ref[..., 3])
        rows.append(row)
    return rows


def _timed(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def measure(path: str, out: str, mask: str | None, runs: int, levels: int,
            binary: str | None = None) -> dict:
    """Both arms on one texture: seconds per run and the per-level scores."""
    name = os.path.splitext(os.path.basename(path))[0] + ("+mask" if mask else "")
    src = source_pixels(path, mask)
    fmt = "bc3" if mask else "bc1"
    tool_dds, in_dds = (os.path.join(out, f"{arm}_{name}.dds") for arm in ("tool", "inproc"))

    def run_tool() -> None:
        src_file = path
        if mask:
            src_file = os.path.join(out, f"tmp_{name}.png")
            Image.fromarray(src, "RGBA").save(src_file, format="PNG", compress_level=1)
        subprocess.run(tool_command(bool(mask), src_file, tool_dds, binary), check=True,
                       capture_output=True)
        if mask:
            os.remove(src_file)

    def run_inproc() -> None:
        ENCODE.encode_file(src if mask else path, fmt, in_dds)

    seconds = {"tool": [_timed(run_tool) for _ in range(runs)],
               "inproc": [_timed(run_inproc) for _ in range(runs)]}
    reference = MIPS.mip_chain(src, mode="gamma22", levels=levels)
    return {"texture": name, "fmt": fmt, "seconds": seconds,
            "tool": score(tool_dds, reference, bool(mask)),
            "inproc": score(in_dds, reference, bool(mask))}


def table(rows: list[dict], levels: int) -> str:
    """Markdown: per level, mean PSNR/SSIM of each arm and the worst per-texture delta."""
    lines = ["| mip | tool PSNR | inproc PSNR | worst Δ dB | tool SSIM | inproc SSIM |",
             "|---|---|---|---|---|---|"]
    for k in range(levels):
        tp = [r["tool"][k]["psnr"] for r in rows]
        ip = [r["inproc"][k]["psnr"] for r in rows]
        ts = [r["tool"][k]["ssim"] for r in rows]
        iss = [r["inproc"][k]["ssim"] for r in rows]
        worst = min(i - t for i, t in zip(ip, tp))
        lines.append(f"| {k} | {np.mean(tp):.2f} | {np.mean(ip):.2f} | {worst:+.2f} | "
                     f"{np.mean(ts):.4f} | {np.mean(iss):.4f} |")
    for arm in ("tool", "inproc"):
        ts = [t for r in rows for t in r["seconds"][arm]]
        lines.append(f"\n{arm}: {min(ts):.3f}-{max(ts):.3f} s per texture "
                     f"(serial, {len(rows)} textures)")
    return "\n".join(lines)


def mip_filter(path: str, out: str, binary: str | None = None) -> str:
    """Which chain each decoded level of the tool's output sits closest to (PSNR dB)."""
    src = source_pixels(path, None)
    dds_path = os.path.join(out, "filter_tool.dds")
    subprocess.run(tool_command(False, path, dds_path, binary), check=True,
                   capture_output=True)
    got = DECODE.decode_dds(open(dds_path, "rb").read())
    chains = {m: MIPS.mip_chain(src, mode=m, levels=9) for m in MIPS.MIP_MODES}
    return "\n".join(f"L{k}: " + " ".join(
        f"{m}={DECODE.psnr(got[k][..., :3], chains[m][k][..., :3]):.2f}"
        for m in MIPS.MIP_MODES) for k in range(min(9, len(got))))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("textures", nargs="+")
    parser.add_argument("--out", required=True, help="lane-local output folder")
    parser.add_argument("--mask", action="append", default=[],
                        help="a mask PNG; each adds one BC3 case on the next texture")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--levels", type=int, default=7)
    parser.add_argument("--tool", default=None, help="converter binary (default: the "
                        "platform's, as convert_texture runs it)")
    parser.add_argument("--mip-filter", action="store_true")
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    if args.mip_filter:
        for path in args.textures:
            print(os.path.basename(path), "\n" + mip_filter(path, args.out, args.tool))
        return 0
    cases = [(p, None) for p in args.textures]
    cases += [(args.textures[i % len(args.textures)], m) for i, m in enumerate(args.mask)]
    rows = [measure(p, args.out, m, args.runs, args.levels, args.tool) for p, m in cases]
    with open(os.path.join(args.out, "quality.json"), "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=1)
    print(table(rows, args.levels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
