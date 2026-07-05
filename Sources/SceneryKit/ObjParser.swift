import Foundation

/// Lightweight parse of an X-Plane OBJ8 file (plain text) — just the facts
/// the health checks need, not full geometry.
public struct ObjInfo: Sendable {
    public var vertexCount = 0          // VT lines
    public var hasLOD = false           // any ATTR_LOD
    public var textures: [String] = []  // TEXTURE / TEXTURE_LIT / TEXTURE_NORMAL
    public var perMeshNoBlend = 0       // ATTR_no_blend occurrences
    public var hasGlobalNoBlend = false // GLOBAL_no_blend present
    public var blendStateChanges = 0    // ATTR_blend <-> ATTR_no_blend flips
    public var animated = false         // ANIM_begin present
}

public enum ObjParser {
    /// Parse an OBJ8 text file. Returns nil if unreadable.
    public static func parse(url: URL, maxBytes: Int = 64 * 1024 * 1024) -> ObjInfo? {
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
              let size = attrs[.size] as? Int, size <= maxBytes,
              let data = try? Data(contentsOf: url, options: .mappedIfSafe)
        else { return nil }
        return parse(data: data)
    }

    public static func parse(text: String) -> ObjInfo {
        parse(data: Data(text.utf8))
    }

    /// Byte-level line scan. OBJ files can run to tens of megabytes with
    /// hundreds of thousands of VT lines; splitting them into String lines
    /// is what made whole-install scans take minutes per pack, so this stays
    /// on raw bytes and only materializes the rare TEXTURE line.
    public static func parse(data: Data) -> ObjInfo {
        var info = ObjInfo()
        var lastBlendState: Bool? = nil // true = blending on

        data.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            guard let base = raw.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return }
            let count = raw.count
            var i = 0

            func lineStarts(_ start: Int, _ end: Int, _ keyword: StaticString) -> Bool {
                let len = keyword.utf8CodeUnitCount
                guard end - start >= len else { return false }
                return memcmp(base + start, keyword.utf8Start, len) == 0
            }

            while i < count {
                // Find end of line.
                var j = i
                while j < count && base[j] != 0x0A { j += 1 }
                // Trim leading whitespace and trailing CR.
                var start = i
                var end = j
                while start < end && (base[start] == 0x20 || base[start] == 0x09) { start += 1 }
                if end > start && base[end - 1] == 0x0D { end -= 1 }
                i = j + 1
                guard end > start else { continue }

                switch base[start] {
                case UInt8(ascii: "V"):
                    // "VT " or "VT\t"
                    if end - start >= 3, base[start + 1] == UInt8(ascii: "T"),
                       base[start + 2] == 0x20 || base[start + 2] == 0x09 {
                        info.vertexCount += 1
                    }
                case UInt8(ascii: "A"):
                    if lineStarts(start, end, "ATTR_LOD") {
                        info.hasLOD = true
                    } else if lineStarts(start, end, "ATTR_no_blend") {
                        info.perMeshNoBlend += 1
                        if lastBlendState == true { info.blendStateChanges += 1 }
                        lastBlendState = false
                    } else if lineStarts(start, end, "ATTR_blend") {
                        if lastBlendState == false { info.blendStateChanges += 1 }
                        lastBlendState = true
                    } else if lineStarts(start, end, "ANIM_begin") {
                        info.animated = true
                    }
                case UInt8(ascii: "G"):
                    if lineStarts(start, end, "GLOBAL_no_blend") {
                        info.hasGlobalNoBlend = true
                    }
                case UInt8(ascii: "T"):
                    if lineStarts(start, end, "TEXTURE") {
                        // TEXTURE, TEXTURE_LIT, TEXTURE_NORMAL, TEXTURE_DRAPED...
                        var space = start
                        while space < end && base[space] != 0x20 && base[space] != 0x09 { space += 1 }
                        var value = space
                        while value < end && (base[value] == 0x20 || base[value] == 0x09) { value += 1 }
                        if value < end {
                            let bytes = UnsafeBufferPointer(start: base + value, count: end - value)
                            info.textures.append(String(decoding: bytes, as: UTF8.self))
                        }
                    }
                default:
                    break
                }
            }
        }
        return info
    }
}
