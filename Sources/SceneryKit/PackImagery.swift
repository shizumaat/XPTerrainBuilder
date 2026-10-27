import Foundation

/// The imagery an installed ortho pack carries — provider code and base
/// zoom level — read from the pack itself, so the map can label ortho
/// tiles the app did not build in its working folder (#1227): packs on
/// another volume linked into Custom Scenery, builds from an older working
/// folder, stock Ortho4XP output.
public struct PackImagery: Codable, Sendable, Equatable {
    public let provider: String
    public let zl: Int?

    public init(provider: String, zl: Int?) {
        self.provider = provider
        self.zl = zl
    }

    /// Dominant provider among Ortho4XP-named texture/terrain file names
    /// (`{y}_{x}_{provider}{zl}[_suffix].dds|.ter`), and that provider's
    /// most common ZL — the tile's base level; airport high-ZL covers are
    /// fewer files. nil when no name parses.
    public static func fromFileNames<S: Sequence>(_ names: S) -> PackImagery?
        where S.Element == String {
        var counts: [String: [Int: Int]] = [:]
        for name in names {
            let lower = name.lowercased()
            guard lower.hasSuffix(".dds") || lower.hasSuffix(".ter") else { continue }
            let stem = String(name.dropLast(4))
            guard let parsed = TileTextureAudit.parseStem(stem) else { continue }
            counts[parsed.provider, default: [:]][parsed.zl, default: 0] += 1
        }
        // Ties break on the name so the label is stable across scans.
        guard let (provider, zls) = counts.max(by: { a, b in
            let ca = a.value.values.reduce(0, +), cb = b.value.values.reduce(0, +)
            return (ca, b.key) < (cb, a.key)
        }) else { return nil }
        let zl = zls.max(by: { ($0.value, $1.key) < ($1.value, $0.key) })?.key
        return PackImagery(provider: provider, zl: zl)
    }

    /// Fallback for packs whose files don't carry Ortho4XP names: this
    /// app's `XPTerrainBuilder_+XX+YYY.cfg` first, else the
    /// `Ortho4XP_+XX+YYY.cfg` (or legacy `Ortho4XP.cfg`) Ortho4XP copies
    /// into the pack root, read for the pack's imagery only —
    /// `default_website` / `default_zl`, read the way the engine's
    /// `O4_Custom_Scenery.pack_imagery` reads them.
    public static func fromConfig(inPack packURL: URL) -> PackImagery? {
        guard let names = try? FileManager.default.contentsOfDirectory(atPath: packURL.path)
        else { return nil }
        let cfgs = names.filter {
            ($0.hasPrefix("XPTerrainBuilder") || $0.hasPrefix("Ortho4XP"))
                && $0.lowercased().hasSuffix(".cfg")
        }
        for name in cfgs.sorted(by: {
            ($0.hasPrefix("Ortho4XP") ? 1 : 0, $0) < ($1.hasPrefix("Ortho4XP") ? 1 : 0, $1)
        }) {
            guard let data = try? Data(contentsOf: packURL.appendingPathComponent(name)),
                  let text = String(data: data, encoding: .utf8)
                      ?? String(data: data, encoding: .isoLatin1)
            else { continue }
            if let imagery = parseConfig(text) { return imagery }
        }
        return nil
    }

    static func parseConfig(_ text: String) -> PackImagery? {
        func unquoted(_ value: String) -> String {
            guard value.count >= 2, let first = value.first,
                  first == value.last, first == "'" || first == "\""
            else { return value }
            return String(value.dropFirst().dropLast())
        }
        var provider = "", zl: Int?
        for line in text.split(whereSeparator: \.isNewline) {
            let parts = line.split(separator: "=", maxSplits: 1)
            guard parts.count == 2 else { continue }
            let key = parts[0].trimmingCharacters(in: .whitespaces)
            let value = unquoted(parts[1].trimmingCharacters(in: .whitespaces))
            if key == "default_website" { provider = value }
            if key == "default_zl" { zl = Int(value) }
        }
        return provider.isEmpty ? nil : PackImagery(provider: provider, zl: zl)
    }
}
