import Foundation

/// One imagery source from the engine's `imagery_sources` command
/// (protocol 1.15, #1345; `Ortho4XP/src/O4_Imagery_Sources.py`). The
/// Build box and the map's preview picker both read this list, so the two
/// menus offer the same sources in the same order as the Qt window.
/// Wire keys are STRING LITERALS matched against the engine's row dicts.
public struct O4ImagerySource: Decodable, Equatable, Sendable, Identifiable {
    /// A combined source's layer, top first; `bbox` is
    /// `[minLon, minLat, maxLon, maxLat]`, nil for a global layer.
    public struct Member: Decodable, Equatable, Sendable {
        public let code: String
        public let bbox: [Double]?
        public let preview: O4ImageryPreview?
    }

    public let code: String
    /// Region folder ("Global", "Netherland", …); empty for combined.
    public let region: String
    public let name: String
    public let combined: Bool
    public let members: [Member]
    /// nil: the source declares no ceiling.
    public let maxZL: Int?
    /// False for a map-only source (OpenStreetMap's tile policy forbids
    /// bulk downloads): the Build box leaves it out.
    public let buildable: Bool
    public let previewable: Bool
    /// Why the map cannot preview it (empty when it can).
    public let reason: String
    public let preview: O4ImageryPreview?
    public let attribution: String

    public var id: String { code }

    private enum CodingKeys: String, CodingKey {
        case code, region, name, combined, members, buildable, previewable, reason
        case preview, attribution
        case maxZL = "max_zl"
    }
}

/// How the map fetches one source's tiles: an engine-made URL template
/// (`O4_Imagery_Sources.preview_spec`) with the tile fields left as
/// placeholders. `url(z:x:y:)` follows `expand_preview` exactly; both are
/// pinned to `Fixtures/Imagery/imagery_menu.json`.
public struct O4ImageryPreview: Decodable, Equatable, Sendable {
    public let template: String
    public let referer: String
    public let maxZL: Int?
    /// WMTS matrix id per web-mercator zoom (nil where none matches).
    public let tilematrix: [String?]?

    private enum CodingKeys: String, CodingKey {
        case template, referer, tilematrix
        case maxZL = "max_zl"
    }

    public init(template: String, referer: String = "", maxZL: Int? = nil,
                tilematrix: [String?]? = nil) {
        self.template = template
        self.referer = referer
        self.maxZL = maxZL
        self.tilematrix = tilematrix
    }

    private static let origin = 20037508.342789244

    /// The URL of web-mercator tile z/x/y, or nil where the source has no
    /// tile at that zoom.
    public func url(z: Int, x: Int, y: Int) -> String? {
        var s = template
        if s.contains("{tilematrix}") {
            guard let tilematrix, z < tilematrix.count, let id = tilematrix[z] else { return nil }
            s = s.replacingOccurrences(of: "{tilematrix}", with: id)
        }
        let size = 2 * Self.origin / Double(1 << z)
        let minx = -Self.origin + Double(x) * size
        let maxy = Self.origin - Double(y) * size
        let box = [minx, maxy - size, minx + size, maxy].map { String(format: "%.2f", $0) }
        s = s.replacingOccurrences(of: "{bbox}", with: box.joined(separator: ","))
            .replacingOccurrences(of: "{bbox_yx}", with: [box[1], box[0], box[3], box[2]].joined(separator: ","))
            .replacingOccurrences(of: "{zoom}", with: String(z))
            .replacingOccurrences(of: "{x}", with: String(x))
            .replacingOccurrences(of: "{y}", with: String(y))
            .replacingOccurrences(of: "{-y}", with: String((1 << z) - 1 - y))
        if s.contains("{quadkey}") {
            s = s.replacingOccurrences(of: "{quadkey}", with: Self.quadkey(x: x, y: y, z: z))
        }
        if let start = s.range(of: "{switch:"),
           let end = s.range(of: "}", range: start.upperBound..<s.endIndex) {
            let options = s[start.upperBound..<end.lowerBound].split(separator: ",")
                .map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
            s.replaceSubrange(start.lowerBound..<end.upperBound,
                              with: options.isEmpty ? "" : options[abs(x &+ y) % options.count])
        }
        return s
    }

    /// Google tile coords → Bing quadkey (O4_Geo_Utils.gtile_to_quadkey).
    public static func quadkey(x: Int, y: Int, z: Int) -> String {
        var quadkey = ""
        var tx = x, ty = y
        for step in 1...max(z, 1) {
            let size = 1 << (z - step)
            let a = tx / size, b = ty / size
            tx -= a * size
            ty -= b * size
            quadkey += String(a + 2 * b)
        }
        return quadkey
    }
}

/// One source's launch-time liveness (`ImagerySourceStatus` event):
/// "online", "offline" or "unknown"; unknown stays enabled.
public struct O4ImageryStatus: Equatable, Sendable {
    public let status: String
    public let reason: String

    public init(status: String, reason: String) {
        self.status = status
        self.reason = reason
    }
}

/// The two imagery menus' items, by the rule the Qt window follows
/// (`O4_Qt_Imagery_Menu.menu_entries`; both pinned to one fixture).
public enum ImageryMenu {
    public static let combinedSection = "Combined"

    public struct Entry: Equatable, Sendable, Identifiable {
        public let code: String
        public let label: String
        public let enabled: Bool
        public let tooltip: String
        public let section: String
        public var id: String { code }
    }

    /// The Build box (`forMap` false) lists what a build may download; the
    /// map's picker lists every source. An offline source is disabled and
    /// labelled "<name> (offline)"; in the map picker a source the map
    /// cannot draw is disabled too. The tooltip says why.
    public static func entries(_ sources: [O4ImagerySource],
                               statuses: [String: O4ImageryStatus],
                               forMap: Bool) -> [Entry] {
        sources.compactMap { source in
            if !forMap && !source.buildable { return nil }
            let status = statuses[source.code]
            var label = source.name.isEmpty ? source.code : source.name
            var enabled = true
            var tooltip = ""
            if status?.status == "offline" {
                label += " (offline)"
                enabled = false
                tooltip = status?.reason ?? ""
            } else if forMap && !source.previewable {
                enabled = false
                tooltip = source.reason
            }
            return Entry(code: source.code, label: label, enabled: enabled, tooltip: tooltip,
                         section: source.combined ? combinedSection : source.region)
        }
    }

    /// One menu section: "Combined" or a region, with its entries.
    public struct Section: Equatable, Sendable, Identifiable {
        public let title: String
        public var entries: [Entry]
        public var id: String { title }
    }

    /// Entries grouped into consecutive sections, in order.
    public static func sections(_ entries: [Entry]) -> [Section] {
        var out: [Section] = []
        for entry in entries {
            if let last = out.last, last.title == entry.section {
                out[out.count - 1].entries.append(entry)
            } else {
                out.append(Section(title: entry.section, entries: [entry]))
            }
        }
        return out
    }
}
