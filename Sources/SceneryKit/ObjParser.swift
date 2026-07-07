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
    public var spillLightCount = 0      // LIGHT_PARAM / LIGHT_SPILL_CUSTOM lines
    public var hasLightLevel = false    // ATTR_light_level (dataref-driven, blocks instancing)
    /// Spill radii in meters, one per light whose size slot we know for
    /// certain: LIGHT_SPILL_CUSTOM (8th argument) and LIGHT_PARAM
    /// full_custom_halo[_night] (8th argument after the light name).
    /// Other LIGHT_PARAM names have per-name layouts — never guessed.
    public var spillRadii: [Double] = []
    /// LIGHT_SPILL_CUSTOM lights driven by a real dataref (not NULL/none) —
    /// each evaluates per frame; Laminar recommends param lights for
    /// repeated fixtures.
    public var datarefSpillCount = 0

    public var maxSpillRadius: Double? { spillRadii.max() }

    // Bounding box from VT coordinates (OBJ8 units are meters).
    public var minX = Double.infinity, maxX = -Double.infinity
    public var minY = Double.infinity, maxY = -Double.infinity
    public var minZ = Double.infinity, maxZ = -Double.infinity

    /// Width × height × depth in meters, nil if the file has no geometry.
    public var dimensions: (x: Double, y: Double, z: Double)? {
        guard vertexCount > 0, minX.isFinite else { return nil }
        return (maxX - minX, maxY - minY, maxZ - minZ)
    }

    public var largestDimension: Double? {
        dimensions.map { max($0.x, $0.y, $0.z) }
    }

    /// Human-readable size like "42 × 18 × 65 m" (x=width, y=height, z=depth).
    public var dimensionsDescription: String? {
        dimensions.map { d in
            String(format: "%.0f × %.0f × %.0f m", d.x.rounded(), d.y.rounded(), d.z.rounded())
        }
    }
}

public enum ObjParser {
    /// THE table of light forms whose spill-size slot is known for certain —
    /// the detector (below) and FixEngine's clamp both consult this, so they
    /// can never disagree about which token is the radius. tokens[0] is the
    /// keyword. Returns nil for every layout we don't know (never guessed).
    public static func spillSizeTokenIndex(_ tokens: [String]) -> Int? {
        guard let keyword = tokens.first else { return nil }
        if keyword == "LIGHT_SPILL_CUSTOM" {
            // LIGHT_SPILL_CUSTOM x y z r g b a SIZE dx dy dz semi dref
            return tokens.count >= 9 ? 8 : nil
        }
        if keyword == "LIGHT_PARAM", tokens.count >= 10,
           tokens[1].hasPrefix("full_custom_halo") {
            // LIGHT_PARAM full_custom_halo[_night] x y z R G B A SIZE …
            return 9
        }
        return nil
    }
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

            /// Parse the three leading coordinates of a VT line (after "VT").
            /// Hand-rolled instead of strtod: Darwin's strtod takes a
            /// process-wide locale lock, and ten threads parsing millions of
            /// VT lines serialize on it (measured: >80% of CPU in ulock_wait).
            /// Bounding-box math doesn't need strtod's last-ulp precision.
            func accumulateVertex(_ start: Int, _ end: Int) {
                var p = start

                func nextDouble() -> Double? {
                    while p < end, base[p] == 0x20 || base[p] == 0x09 { p += 1 }
                    var negative = false
                    if p < end, base[p] == UInt8(ascii: "-") { negative = true; p += 1 }
                    else if p < end, base[p] == UInt8(ascii: "+") { p += 1 }

                    var sawDigit = false
                    var value = 0.0
                    while p < end, base[p] >= 0x30, base[p] <= 0x39 {
                        value = value * 10 + Double(base[p] - 0x30)
                        sawDigit = true
                        p += 1
                    }
                    if p < end, base[p] == UInt8(ascii: ".") {
                        p += 1
                        var scale = 0.1
                        while p < end, base[p] >= 0x30, base[p] <= 0x39 {
                            value += Double(base[p] - 0x30) * scale
                            scale *= 0.1
                            sawDigit = true
                            p += 1
                        }
                    }
                    guard sawDigit else { return nil }
                    if p < end, base[p] == UInt8(ascii: "e") || base[p] == UInt8(ascii: "E") {
                        p += 1
                        var expNegative = false
                        if p < end, base[p] == UInt8(ascii: "-") { expNegative = true; p += 1 }
                        else if p < end, base[p] == UInt8(ascii: "+") { p += 1 }
                        var exponent = 0
                        while p < end, base[p] >= 0x30, base[p] <= 0x39 {
                            exponent = exponent * 10 + Int(base[p] - 0x30)
                            p += 1
                        }
                        value *= pow(10, expNegative ? -Double(exponent) : Double(exponent))
                    }
                    return negative ? -value : value
                }

                guard let x = nextDouble(), let y = nextDouble(), let z = nextDouble() else { return }
                info.minX = min(info.minX, x); info.maxX = max(info.maxX, x)
                info.minY = min(info.minY, y); info.maxY = max(info.maxY, y)
                info.minZ = min(info.minZ, z); info.maxZ = max(info.maxZ, z)
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
                        accumulateVertex(start + 3, end)
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
                    } else if lineStarts(start, end, "ATTR_light_level") {
                        info.hasLightLevel = true
                    } else if lineStarts(start, end, "ANIM_begin") {
                        info.animated = true
                    }
                case UInt8(ascii: "L"):
                    // LIGHT_PARAM lines number in the thousands in airport
                    // lighting objects, so a byte-level name check gates the
                    // String materialization: only LIGHT_SPILL_CUSTOM (rare)
                    // and full_custom_halo params (the sized forms) pay it.
                    let isSpillCustom = lineStarts(start, end, "LIGHT_SPILL_CUSTOM")
                    var isSizedParam = false
                    if !isSpillCustom, lineStarts(start, end, "LIGHT_PARAM") {
                        info.spillLightCount += 1
                        var p = start + 11 // past "LIGHT_PARAM"
                        while p < end, base[p] == 0x20 || base[p] == 0x09 { p += 1 }
                        isSizedParam = lineStarts(p, end, "full_custom_halo")
                    }
                    if isSpillCustom || isSizedParam {
                        if isSpillCustom { info.spillLightCount += 1 }
                        let bytes = UnsafeBufferPointer(start: base + start, count: end - start)
                        let tokens = String(decoding: bytes, as: UTF8.self)
                            .split(whereSeparator: { $0 == " " || $0 == "\t" })
                            .map(String.init)
                        if let sizeIndex = Self.spillSizeTokenIndex(tokens),
                           let size = Double(tokens[sizeIndex]), size > 0 {
                            info.spillRadii.append(size)
                        }
                        // LIGHT_SPILL_CUSTOM's 13th argument is the dataref;
                        // NULL means "always on" (param-light equivalent).
                        if isSpillCustom, tokens.count >= 14 {
                            let dref = tokens[13].lowercased()
                            if dref != "null", dref != "none", dref != "no_ref" {
                                info.datarefSpillCount += 1
                            }
                        }
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
