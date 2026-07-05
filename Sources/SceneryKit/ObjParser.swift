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
    /// Parse an OBJ8 text file. Returns nil if unreadable or not OBJ8.
    public static func parse(url: URL, maxBytes: Int = 64 * 1024 * 1024) -> ObjInfo? {
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
              let size = attrs[.size] as? Int, size <= maxBytes,
              let data = try? Data(contentsOf: url),
              let text = String(data: data, encoding: .utf8)
                    ?? String(data: data, encoding: .isoLatin1)
        else { return nil }
        return parse(text: text)
    }

    public static func parse(text: String) -> ObjInfo {
        var info = ObjInfo()
        var lastBlendState: Bool? = nil // true = blending on

        for rawLine in text.split(separator: "\n", omittingEmptySubsequences: true) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            guard !line.isEmpty, !line.hasPrefix("#") else { continue }

            if line.hasPrefix("VT ") || line.hasPrefix("VT\t") {
                info.vertexCount += 1
            } else if line.hasPrefix("ATTR_LOD") {
                info.hasLOD = true
            } else if line.hasPrefix("TEXTURE") {
                // TEXTURE, TEXTURE_LIT, TEXTURE_NORMAL, TEXTURE_DRAPED...
                let parts = line.split(separator: " ", maxSplits: 1, omittingEmptySubsequences: true)
                if parts.count == 2 {
                    info.textures.append(String(parts[1]).trimmingCharacters(in: .whitespaces))
                }
            } else if line.hasPrefix("ATTR_no_blend") {
                info.perMeshNoBlend += 1
                if lastBlendState == true { info.blendStateChanges += 1 }
                lastBlendState = false
            } else if line.hasPrefix("ATTR_blend") {
                if lastBlendState == false { info.blendStateChanges += 1 }
                lastBlendState = true
            } else if line.hasPrefix("GLOBAL_no_blend") {
                info.hasGlobalNoBlend = true
            } else if line.hasPrefix("ANIM_begin") {
                info.animated = true
            }
        }
        return info
    }
}
