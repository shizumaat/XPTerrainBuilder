import Foundation
import CoreGraphics
import ImageIO

public enum DDSEncodeError: Error, CustomStringConvertible {
    case unreadableImage
    case unsupportedSize(Int, Int)

    public var description: String {
        switch self {
        case .unreadableImage: return "Could not decode the PNG."
        case .unsupportedSize(let w, let h): return "Unsupported image size \(w)×\(h)."
        }
    }
}

/// Encodes PNGs as mipmapped, block-compressed DDS (DXT1 for opaque images,
/// DXT5 when there's an alpha channel) — the format X-Plane loads without
/// CPU-side decompression or mip generation. Range-fit compression: fast,
/// and fine for photographic/ortho content, which is where the big PNGs are.
public enum DDSEncoder {

    public static func encodePNG(at url: URL) -> Result<Data, DDSEncodeError> {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
        else { return .failure(.unreadableImage) }

        // Resample non-power-of-two images to the nearest power of two (UVs
        // are normalized, so nothing shifts) — required for clean mip chains
        // and part of the C-04 non-POT fix.
        let width = nearestPowerOfTwo(image.width)
        let height = nearestPowerOfTwo(image.height)
        guard width >= 4, height >= 4, width <= 32_768, height <= 32_768 else {
            return .failure(.unsupportedSize(image.width, image.height))
        }

        guard var level = rgbaPixels(of: image, width: width, height: height) else {
            return .failure(.unreadableImage)
        }

        let hasAlpha = levelHasAlpha(level)

        // Mip chain, halving down to 1×1 (padded to ≥1 per axis).
        var levels: [(pixels: [UInt8], w: Int, h: Int)] = [(level, width, height)]
        var (w, h) = (width, height)
        while w > 1 || h > 1 {
            let nw = max(1, w / 2), nh = max(1, h / 2)
            level = downsample(level, w: w, h: h, nw: nw, nh: nh)
            levels.append((level, nw, nh))
            (w, h) = (nw, nh)
        }

        var payload = Data()
        for (pixels, lw, lh) in levels {
            payload.append(hasAlpha
                ? encodeBC3(pixels, w: lw, h: lh)
                : encodeBC1(pixels, w: lw, h: lh))
        }

        var dds = header(width: width, height: height, mipCount: levels.count, dxt5: hasAlpha)
        dds.append(payload)
        return .success(dds)
    }

    static func nearestPowerOfTwo(_ n: Int) -> Int {
        guard n > 4 else { return 4 }
        let lower = 1 << Int(log2(Double(n)))
        let upper = lower << 1
        return (n - lower) < (upper - n) ? lower : upper
    }

    // MARK: - Pixel access

    static func rgbaPixels(of image: CGImage, width: Int, height: Int) -> [UInt8]? {
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
        guard let context = CGContext(
            data: &pixels, width: width, height: height,
            bitsPerComponent: 8, bytesPerRow: width * 4, space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return nil }
        context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))

        // Un-premultiply so DXT alpha blending in-sim matches the original.
        for i in stride(from: 0, to: pixels.count, by: 4) {
            let a = pixels[i + 3]
            if a != 0 && a != 255 {
                let alpha = Int(a)
                pixels[i] = UInt8(min(255, Int(pixels[i]) * 255 / alpha))
                pixels[i + 1] = UInt8(min(255, Int(pixels[i + 1]) * 255 / alpha))
                pixels[i + 2] = UInt8(min(255, Int(pixels[i + 2]) * 255 / alpha))
            }
        }
        return pixels
    }

    /// Same cutoff DDSAlpha uses to call BC3 alpha "dead" — the encoder's
    /// "needs alpha" and the stripper's "alpha is dead weight" definitions
    /// must stay complementary or the two fixes would fight each other.
    static func levelHasAlpha(_ pixels: [UInt8]) -> Bool {
        for i in stride(from: 3, to: pixels.count, by: 4)
        where Int(pixels[i]) < DDSAlpha.opaqueThreshold {
            return true
        }
        return false
    }

    static func downsample(_ src: [UInt8], w: Int, h: Int, nw: Int, nh: Int) -> [UInt8] {
        var dst = [UInt8](repeating: 0, count: nw * nh * 4)
        for y in 0..<nh {
            for x in 0..<nw {
                let sx = min(x * 2, w - 1), sy = min(y * 2, h - 1)
                let sx1 = min(sx + 1, w - 1), sy1 = min(sy + 1, h - 1)
                for c in 0..<4 {
                    let sum = Int(src[(sy * w + sx) * 4 + c])
                        + Int(src[(sy * w + sx1) * 4 + c])
                        + Int(src[(sy1 * w + sx) * 4 + c])
                        + Int(src[(sy1 * w + sx1) * 4 + c])
                    dst[(y * nw + x) * 4 + c] = UInt8(sum / 4)
                }
            }
        }
        return dst
    }

    // MARK: - Block compression

    /// Extract a 4×4 block (edge-clamped) as 16 RGBA pixels.
    static func block(_ pixels: [UInt8], w: Int, h: Int, bx: Int, by: Int) -> [(r: Int, g: Int, b: Int, a: Int)] {
        var out: [(Int, Int, Int, Int)] = []
        out.reserveCapacity(16)
        for dy in 0..<4 {
            for dx in 0..<4 {
                let x = min(bx * 4 + dx, w - 1)
                let y = min(by * 4 + dy, h - 1)
                let i = (y * w + x) * 4
                out.append((Int(pixels[i]), Int(pixels[i + 1]), Int(pixels[i + 2]), Int(pixels[i + 3])))
            }
        }
        return out
    }

    static func to565(_ r: Int, _ g: Int, _ b: Int) -> UInt16 {
        UInt16((r >> 3) << 11 | (g >> 2) << 5 | (b >> 3))
    }

    static func from565(_ c: UInt16) -> (r: Int, g: Int, b: Int) {
        let r = Int(c >> 11) & 0x1F, g = Int(c >> 5) & 0x3F, b = Int(c) & 0x1F
        return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))
    }

    /// One BC1 color block: endpoints from the block's extremes along each
    /// channel (range fit), 2-bit palette indices per pixel.
    static func colorBlock(_ px: [(r: Int, g: Int, b: Int, a: Int)]) -> Data {
        var minR = 255, minG = 255, minB = 255, maxR = 0, maxG = 0, maxB = 0
        for p in px {
            minR = min(minR, p.r); maxR = max(maxR, p.r)
            minG = min(minG, p.g); maxG = max(maxG, p.g)
            minB = min(minB, p.b); maxB = max(maxB, p.b)
        }
        var c0 = to565(maxR, maxG, maxB)
        var c1 = to565(minR, minG, minB)
        if c0 < c1 { swap(&c0, &c1) }
        // Equal endpoints: all pixels index 0.
        let e0 = from565(c0), e1 = from565(c1)
        let palette: [(Int, Int, Int)] = [
            (e0.r, e0.g, e0.b),
            (e1.r, e1.g, e1.b),
            ((2 * e0.r + e1.r) / 3, (2 * e0.g + e1.g) / 3, (2 * e0.b + e1.b) / 3),
            ((e0.r + 2 * e1.r) / 3, (e0.g + 2 * e1.g) / 3, (e0.b + 2 * e1.b) / 3),
        ]

        var indices: UInt32 = 0
        for (i, p) in px.enumerated() {
            var best = 0, bestDist = Int.max
            if c0 != c1 {
                for (j, pal) in palette.enumerated() {
                    let dr = p.r - pal.0, dg = p.g - pal.1, db = p.b - pal.2
                    let dist = dr * dr + dg * dg + db * db
                    if dist < bestDist { bestDist = dist; best = j }
                }
            }
            indices |= UInt32(best) << (2 * i)
        }

        var data = Data()
        data.appendLE16(c0)
        data.appendLE16(c1)
        data.appendLE32(indices)
        return data
    }

    static func encodeBC1(_ pixels: [UInt8], w: Int, h: Int) -> Data {
        var data = Data()
        let bw = (w + 3) / 4, bh = (h + 3) / 4
        for by in 0..<bh {
            for bx in 0..<bw {
                data.append(colorBlock(block(pixels, w: w, h: h, bx: bx, by: by)))
            }
        }
        return data
    }

    /// BC3 = 8-byte interpolated alpha block + BC1 color block.
    static func encodeBC3(_ pixels: [UInt8], w: Int, h: Int) -> Data {
        var data = Data()
        let bw = (w + 3) / 4, bh = (h + 3) / 4
        for by in 0..<bh {
            for bx in 0..<bw {
                let px = block(pixels, w: w, h: h, bx: bx, by: by)

                let alphas = px.map { $0.a }
                let a0 = alphas.max()!, a1 = alphas.min()!
                var alphaBlock = Data([UInt8(a0), UInt8(a1)])
                // 8-entry interpolated palette (a0 >= a1 mode).
                var palette = [a0, a1]
                for i in 1...6 { palette.append(((7 - i) * a0 + i * a1) / 7) }
                var bits: UInt64 = 0
                for (i, a) in alphas.enumerated() {
                    var best = 0, bestDist = Int.max
                    if a0 != a1 {
                        for (j, pal) in palette.enumerated() {
                            let dist = abs(a - pal)
                            if dist < bestDist { bestDist = dist; best = j }
                        }
                    }
                    bits |= UInt64(best) << (3 * i)
                }
                for shift in stride(from: 0, to: 48, by: 8) {
                    alphaBlock.append(UInt8((bits >> shift) & 0xFF))
                }
                data.append(alphaBlock)
                data.append(colorBlock(px))
            }
        }
        return data
    }

    // MARK: - Header

    static func header(width: Int, height: Int, mipCount: Int, dxt5: Bool) -> Data {
        let blockSize = dxt5 ? 16 : 8
        let linearSize = max(1, (width + 3) / 4) * max(1, (height + 3) / 4) * blockSize

        var data = Data("DDS ".utf8)
        data.appendLE32(124)                       // dwSize
        // CAPS | HEIGHT | WIDTH | PIXELFORMAT | MIPMAPCOUNT | LINEARSIZE
        data.appendLE32(0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000)
        data.appendLE32(UInt32(height))
        data.appendLE32(UInt32(width))
        data.appendLE32(UInt32(linearSize))
        data.appendLE32(0)                         // depth
        data.appendLE32(UInt32(mipCount))
        for _ in 0..<11 { data.appendLE32(0) }     // reserved
        // DDS_PIXELFORMAT
        data.appendLE32(32)                        // size
        data.appendLE32(0x4)                       // DDPF_FOURCC
        data.append(Data((dxt5 ? "DXT5" : "DXT1").utf8))
        for _ in 0..<5 { data.appendLE32(0) }      // RGB masks unused
        // caps: TEXTURE | MIPMAP | COMPLEX
        data.appendLE32(0x1000 | 0x400000 | 0x8)
        data.appendLE32(0)
        data.appendLE32(0)
        data.appendLE32(0)
        data.appendLE32(0)                         // reserved2
        return data
    }
}

private extension Data {
    mutating func appendLE16(_ value: UInt16) {
        append(UInt8(value & 0xFF))
        append(UInt8(value >> 8))
    }
    mutating func appendLE32(_ value: UInt32) {
        append(UInt8(value & 0xFF))
        append(UInt8((value >> 8) & 0xFF))
        append(UInt8((value >> 16) & 0xFF))
        append(UInt8((value >> 24) & 0xFF))
    }
    mutating func appendLE32(_ value: Int) {
        appendLE32(UInt32(truncatingIfNeeded: value))
    }
}
