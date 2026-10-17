import Foundation

/// What the map labels, and where (issue #817): the Swift half of ONE rule
/// whose Python half (the Qt map's) is `Ortho4XP/src/O4_Map_Labels.py`.
/// Both read `Ortho4XP/tests/fixtures/map_label_cases.json`.
///
/// Every zoom here is a map SCALE in screen pixels per degree of longitude
/// (`MapCamera.scale`). Airports are marked from their size class's
/// `markMinScale` (a custom-pack airport always), labelled from its
/// `labelMinScale` (a custom airport one class earlier) at `fontSize`,
/// and placed in rank order — class, custom before default, longest
/// runway, code — dropping any label that would overlap one already placed.
public enum MapLabelLayout {
    public static let markMinScale: [Double] = [4, 8, 14, 26, 52]
    public static let labelMinScale: [Double] = [10, 20, 40, 70, 120]
    public static let labelFontMin = 12.0
    public static let labelFontMax = 16.0
    /// Tile coordinate / imagery labels: from this scale on, at this size.
    public static let tileLabelMinScale = 72.0
    public static let tileLabelFont = 10.0
    /// Labels placed per frame at most.
    public static let maxAirportLabels = 300

    // Box estimate without measuring text — the SAME numbers as the Qt
    // map, so both canvases drop the same labels.
    static let glyphAdvance = 0.62
    static let pillPadX = 4.0
    static let pillPadY = 2.0
    static let labelGap = 3.0
    static let cell = 64.0

    public struct Candidate: Sendable, Equatable {
        public let code: String
        public let x: Double
        public let y: Double
        public let sizeClass: Int
        public let runwayMeters: Int
        public let custom: Bool

        public init(code: String, x: Double, y: Double, sizeClass: Int,
                    runwayMeters: Int, custom: Bool) {
            self.code = code
            self.x = x
            self.y = y
            self.sizeClass = sizeClass
            self.runwayMeters = runwayMeters
            self.custom = custom
        }
    }

    /// A label's screen box (top-left origin) and point size.
    public struct Box: Sendable, Equatable {
        public let x: Double, y: Double, width: Double, height: Double
        public let fontSize: Double

        func overlaps(_ other: Box) -> Bool {
            x < other.x + other.width && other.x < x + width
                && y < other.y + other.height && other.y < y + height
        }
    }

    private static func gate(_ table: [Double], _ sizeClass: Int) -> Double {
        table[min(max(sizeClass, 0), table.count - 1)]
    }

    public static func markVisible(sizeClass: Int, custom: Bool, scale: Double) -> Bool {
        custom || scale >= gate(markMinScale, sizeClass)
    }

    public static func labelAllowed(sizeClass: Int, custom: Bool, scale: Double) -> Bool {
        scale >= gate(labelMinScale, max(custom ? sizeClass - 1 : sizeClass, 0))
    }

    /// 12 pt at the first labelled scale, +1 per doubling, at most 16;
    /// rounded to a half point.
    public static func fontSize(scale: Double) -> Double {
        let base = labelMinScale[0]
        let size = min(max(labelFontMin + log2(max(scale, base) / base), labelFontMin),
                       labelFontMax)
        return floor(size * 2 + 0.5) / 2
    }

    /// An airport mark's radius (px) at `scale`: the sectional sizes.
    public static func markRadius(scale: Double) -> Double {
        scale > 26 ? 5 : (scale > 8 ? 3.5 : 2.2)
    }

    /// The box of `code`'s label, centred over the mark at (x, y).
    public static func box(x: Double, y: Double, code: String,
                           fontSize: Double, markRadius: Double) -> Box {
        let width = Double(code.count) * glyphAdvance * fontSize + 2 * pillPadX
        let height = fontSize + 2 * pillPadY
        return Box(x: x - width / 2, y: y - markRadius - labelGap - height,
                   width: width, height: height, fontSize: fontSize)
    }

    private static func precedes(_ a: Candidate, _ b: Candidate) -> Bool {
        if a.sizeClass != b.sizeClass { return a.sizeClass < b.sizeClass }
        if a.custom != b.custom { return a.custom }
        if a.runwayMeters != b.runwayMeters { return a.runwayMeters > b.runwayMeters }
        return a.code < b.code
    }

    /// `marks`: indexes of every marked candidate, in input order;
    /// `labels`: (index, box) in rank order, no two boxes overlapping.
    public static func place(_ candidates: [Candidate], scale: Double, markRadius: Double,
                             limit: Int = maxAirportLabels)
        -> (marks: [Int], labels: [(index: Int, box: Box)]) {
        let marks = candidates.indices.filter {
            markVisible(sizeClass: candidates[$0].sizeClass,
                        custom: candidates[$0].custom, scale: scale)
        }
        let font = fontSize(scale: scale)
        let order = marks
            .filter { labelAllowed(sizeClass: candidates[$0].sizeClass,
                                   custom: candidates[$0].custom, scale: scale) }
            .sorted { precedes(candidates[$0], candidates[$1]) }
        var grid: [Int64: [Box]] = [:]
        var labels: [(index: Int, box: Box)] = []
        for index in order {
            if labels.count >= limit { break }
            let c = candidates[index]
            let b = box(x: c.x, y: c.y, code: c.code, fontSize: font, markRadius: markRadius)
            let keys = cells(b)
            if keys.contains(where: { key in grid[key]?.contains(where: b.overlaps) ?? false }) {
                continue
            }
            for key in keys { grid[key, default: []].append(b) }
            labels.append((index, b))
        }
        return (marks, labels)
    }

    private static func cells(_ b: Box) -> [Int64] {
        let x0 = Int64(floor(b.x / cell)), x1 = Int64(floor((b.x + b.width) / cell))
        let y0 = Int64(floor(b.y / cell)), y1 = Int64(floor((b.y + b.height) / cell))
        var keys: [Int64] = []
        for cx in x0...x1 {
            for cy in y0...y1 { keys.append(cx &* 1_000_003 &+ cy) }
        }
        return keys
    }

    /// A tile's bottom-left imagery label: `BI ZL16`, `BI ZL16 +zones`;
    /// an unknown part reads `?` and an unknown whole `imagery ?`.
    public static func imageryLabel(provider: String?, zl: Int?, hasZones: Bool) -> String {
        let name = (provider ?? "").trimmingCharacters(in: .whitespaces)
        let zoom = zl.flatMap { $0 == 0 ? nil : $0 }
        var text: String
        if name.isEmpty && zoom == nil {
            text = "imagery ?"
        } else {
            text = "\(name.isEmpty ? "?" : String(name.prefix(4))) ZL\(zoom.map(String.init) ?? "?")"
        }
        if hasZones { text += " +zones" }
        return text
    }
}
