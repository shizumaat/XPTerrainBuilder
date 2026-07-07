import Foundation

/// Dead-alpha analysis and stripping for DXT5/BC3 DDS files.
///
/// A BC3 block is an 8-byte alpha block followed by an 8-byte color block
/// whose layout is EXACTLY a BC1 block — so a fully-opaque BC3 texture can
/// be rewritten as BC1 by dropping the alpha blocks, without re-encoding
/// (no quality loss) and at half the file size and VRAM. The only trap:
/// BC3 color blocks always decode in 4-color mode, while BC1 switches to
/// 3-color + transparent mode when color0 <= color1 — those blocks get
/// their endpoints swapped and indices remapped (0↔1, 2↔3), which decodes
/// to identical colors.
public enum DDSAlpha {

    public enum Verdict: Sendable {
        /// Every alpha value in every mip decodes ≥ the opacity threshold —
        /// the alpha channel is dead weight.
        case opaqueBC3
        /// At least one pixel is genuinely translucent.
        case hasRealAlpha
        /// Not a plain BC3 2-D texture (different fourCC, cubemap, volume,
        /// truncated data) — leave it alone.
        case notApplicable
    }

    /// Alpha values below this count as real transparency (matches
    /// DDSEncoder.levelHasAlpha — 250..255 is visually opaque).
    static let opaqueThreshold = 250

    static let headerSize = 128

    struct Layout {
        var width: Int
        var height: Int
        var mipCount: Int
        /// (offset, blockCount) per mip level, BC3 blocks (16 bytes).
        var mips: [(offset: Int, blocks: Int)]
    }

    /// Validate the header and compute the BC3 block layout. nil = not a
    /// plain BC3 2-D texture.
    static func bc3Layout(_ data: Data) -> Layout? {
        guard data.count > headerSize,
              data.starts(with: [0x44, 0x44, 0x53, 0x20]) else { return nil }
        func le32(_ offset: Int) -> Int {
            Int(data[data.startIndex + offset])
                | Int(data[data.startIndex + offset + 1]) << 8
                | Int(data[data.startIndex + offset + 2]) << 16
                | Int(data[data.startIndex + offset + 3]) << 24
        }
        let height = le32(12), width = le32(16)
        let mipCount = max(1, le32(28))
        let fourCC = String(decoding: data[data.startIndex + 84..<data.startIndex + 88], as: UTF8.self)
        let caps2 = le32(112)
        guard fourCC == "DXT5", caps2 == 0, width > 0, height > 0,
              width <= 32_768, height <= 32_768, mipCount <= 20 else { return nil }

        var mips: [(offset: Int, blocks: Int)] = []
        var offset = headerSize
        var (w, h) = (width, height)
        for _ in 0..<mipCount {
            let blocks = max(1, (w + 3) / 4) * max(1, (h + 3) / 4)
            guard offset + blocks * 16 <= data.count else { return nil } // truncated: don't guess
            mips.append((offset, blocks))
            offset += blocks * 16
            w = max(1, w / 2); h = max(1, h / 2)
        }
        return Layout(width: width, height: height, mipCount: mipCount, mips: mips)
    }

    /// One BC3 alpha palette entry, computed on demand — analyze runs this
    /// per pixel over millions of blocks, so no per-block array allocation.
    /// Same interpolation DDSEncoder.encodeBC3 writes.
    static func alphaValue(index: Int, a0: Int, a1: Int) -> Int {
        switch index {
        case 0: return a0
        case 1: return a1
        default:
            if a0 > a1 {
                return ((7 - (index - 1)) * a0 + (index - 1) * a1) / 7
            }
            if index == 6 { return 0 }
            if index == 7 { return 255 }
            return ((5 - (index - 1)) * a0 + (index - 1) * a1) / 5
        }
    }

    public static func analyze(url: URL, maxBytes: Int = 256 << 20) -> Verdict {
        guard let size = (try? FileManager.default.attributesOfItem(atPath: url.path))?[.size] as? Int,
              size <= maxBytes,
              let data = try? Data(contentsOf: url, options: .mappedIfSafe) else { return .notApplicable }
        return analyze(data: data)
    }

    public static func analyze(data: Data) -> Verdict {
        guard let layout = bc3Layout(data) else { return .notApplicable }
        var verdict = Verdict.opaqueBC3
        data.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            guard let base = raw.baseAddress?.assumingMemoryBound(to: UInt8.self) else {
                verdict = .notApplicable
                return
            }
            for mip in layout.mips {
                for block in 0..<mip.blocks {
                    let p = mip.offset + block * 16
                    let a0 = Int(base[p]), a1 = Int(base[p + 1])
                    // Fast path: both endpoints opaque in a0>a1 mode means
                    // every interpolated value is opaque too. (a0<=a1 mode
                    // has hardcoded 0/255 palette slots, so its indices
                    // must be checked even with opaque endpoints.)
                    if a0 > a1, a1 >= opaqueThreshold { continue }
                    // 48-bit little-endian index stream, 3 bits per pixel.
                    var bits: UInt64 = 0
                    for i in 0..<6 { bits |= UInt64(base[p + 2 + i]) << (8 * i) }
                    for pixel in 0..<16 {
                        let index = Int((bits >> (3 * pixel)) & 0x7)
                        if alphaValue(index: index, a0: a0, a1: a1) < opaqueThreshold {
                            verdict = .hasRealAlpha
                            return
                        }
                    }
                }
            }
        }
        return verdict
    }

    /// Rewrite an all-opaque BC3 DDS as BC1: same dimensions and mip chain,
    /// alpha blocks dropped, color blocks copied byte-for-byte (with the
    /// endpoint-order fixup where needed). nil if the file is not a fully
    /// opaque BC3 texture.
    public static func stripToBC1(_ data: Data) -> Data? {
        guard case .opaqueBC3 = analyze(data: data),
              let layout = bc3Layout(data) else { return nil }

        var out = Data(capacity: headerSize + layout.mips.reduce(0) { $0 + $1.blocks * 8 })
        // Header: copy, then patch linear size (offset 20) and fourCC (84).
        out.append(data.prefix(headerSize))
        let linearSize = layout.mips[0].blocks * 8
        out.withUnsafeMutableBytes { (raw: UnsafeMutableRawBufferPointer) in
            let base = raw.baseAddress!.assumingMemoryBound(to: UInt8.self)
            for i in 0..<4 { base[20 + i] = UInt8((linearSize >> (8 * i)) & 0xFF) }
            let cc = Array("DXT1".utf8)
            for i in 0..<4 { base[84 + i] = cc[i] }
        }

        data.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            let base = raw.baseAddress!.assumingMemoryBound(to: UInt8.self)
            for mip in layout.mips {
                for block in 0..<mip.blocks {
                    let p = mip.offset + block * 16 + 8 // color half
                    let c0 = UInt16(base[p]) | UInt16(base[p + 1]) << 8
                    let c1 = UInt16(base[p + 2]) | UInt16(base[p + 3]) << 8
                    if c0 > c1 {
                        // Already decodes identically in BC1's 4-color mode.
                        out.append(UnsafeBufferPointer(start: base + p, count: 8))
                    } else if c0 == c1 {
                        // BC1 would flip to 3-color mode where index 3 means
                        // TRANSPARENT; both endpoints are the same color, so
                        // point every pixel at index 0.
                        out.append(contentsOf: [base[p], base[p + 1], base[p + 2], base[p + 3],
                                                0, 0, 0, 0])
                    } else {
                        // Swap endpoints into 4-color order and remap the
                        // 2-bit indices (0↔1, 2↔3 — i.e. index ^ 1).
                        var swapped: [UInt8] = [base[p + 2], base[p + 3], base[p], base[p + 1],
                                                0, 0, 0, 0]
                        for i in 0..<4 {
                            // Flipping the low bit of every 2-bit field:
                            // XOR with 0b01010101.
                            swapped[4 + i] = base[p + 4 + i] ^ 0x55
                        }
                        out.append(contentsOf: swapped)
                    }
                }
            }
        }
        return out
    }
}
