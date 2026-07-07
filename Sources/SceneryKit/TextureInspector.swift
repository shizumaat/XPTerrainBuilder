import Foundation

/// Texture facts read straight from file headers — no image decoding.
public struct TextureInfo: Sendable {
    public enum Format: String, Sendable {
        case png
        case dds
        case other
    }

    public let url: URL
    public let format: Format
    public let width: Int
    public let height: Int
    /// DDS only: number of mipmap levels recorded in the header (0/1 = none).
    public let mipMapCount: Int
    public let fileSizeBytes: Int
    /// DDS only: compression fourCC ("DXT1", "DXT5", "DX10", …), nil otherwise.
    public var ddsFourCC: String? = nil

    public var isPowerOfTwo: Bool {
        func pot(_ n: Int) -> Bool { n > 0 && (n & (n - 1)) == 0 }
        return pot(width) && pot(height)
    }

    /// Rough VRAM estimate in bytes: RGBA for PNG (X-Plane decompresses),
    /// ~1 byte/pixel for block-compressed DDS; +33% for mip chains.
    public var estimatedVRAMBytes: Int {
        let base: Int
        switch format {
        case .png, .other: base = width * height * 4
        case .dds: base = width * height * 1
        }
        return base + base / 3
    }
}

public enum TextureInspector {
    public static func inspect(url: URL) -> TextureInfo? {
        guard let handle = try? FileHandle(forReadingFrom: url),
              let header = try? handle.read(upToCount: 128),
              header.count >= 24
        else { return nil }
        defer { try? handle.close() }

        let size = (try? FileManager.default.attributesOfItem(atPath: url.path))?[.size] as? Int ?? 0

        // PNG: 89 50 4E 47 0D 0A 1A 0A, then IHDR with big-endian width/height at 16/20.
        if header.starts(with: [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) {
            let width = header.bigEndianUInt32(at: 16)
            let height = header.bigEndianUInt32(at: 20)
            return TextureInfo(url: url, format: .png, width: width, height: height,
                               mipMapCount: 0, fileSizeBytes: size)
        }

        // DDS: "DDS " magic; little-endian height at 12, width at 16,
        // mipMapCount at 28, pixel-format fourCC at 84.
        if header.starts(with: [0x44, 0x44, 0x53, 0x20]) {
            let height = header.littleEndianUInt32(at: 12)
            let width = header.littleEndianUInt32(at: 16)
            let mips = header.littleEndianUInt32(at: 28)
            var fourCC: String? = nil
            if header.count >= 88 {
                let cc = header.subdata(in: header.startIndex + 84..<header.startIndex + 88)
                let text = String(decoding: cc, as: UTF8.self)
                if text.allSatisfy({ $0.isLetter || $0.isNumber || $0 == " " }) {
                    fourCC = text
                }
            }
            return TextureInfo(url: url, format: .dds, width: width, height: height,
                               mipMapCount: mips, fileSizeBytes: size, ddsFourCC: fourCC)
        }

        return TextureInfo(url: url, format: .other, width: 0, height: 0,
                           mipMapCount: 0, fileSizeBytes: size)
    }
}

private extension Data {
    func bigEndianUInt32(at offset: Int) -> Int {
        guard count >= offset + 4 else { return 0 }
        return (Int(self[startIndex + offset]) << 24)
             | (Int(self[startIndex + offset + 1]) << 16)
             | (Int(self[startIndex + offset + 2]) << 8)
             | Int(self[startIndex + offset + 3])
    }

    func littleEndianUInt32(at offset: Int) -> Int {
        guard count >= offset + 4 else { return 0 }
        return Int(self[startIndex + offset])
             | (Int(self[startIndex + offset + 1]) << 8)
             | (Int(self[startIndex + offset + 2]) << 16)
             | (Int(self[startIndex + offset + 3]) << 24)
    }
}
