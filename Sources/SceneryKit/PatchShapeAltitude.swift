import Foundation

// A patch shape's own elevation tags (issue #2137), the Swift twin of
// `Ortho4XP/src/o4_engine/patch_shape_alt.py`; both run
// `Ortho4XP/tests/fixtures/patch_shape_alt.json`.
//
// Ortho4XP's patch reader (`O4_Vector_Map`) takes a way's elevation from its
// tags first, in this order (the first key present wins): `cst_alt_abs` (one
// elevation), `cst_alt_rel` (mean ground + offset), `var_alt_rel` (ground +
// offset at each node), the legacy `altitude`, `node_altitudes` (not a
// whole-shape value), then `altitude_high` / `altitude_low` — the sloping
// rectangle: a closed four-corner way whose HIGH side is refs[3]–refs[0] and
// LOW side refs[1]–refs[2]. An edit keeps the key the shape already uses.

/// What a way's tags say about its elevation.
public enum PatchShapeAltitude: Equatable, Sendable {
    public enum Form: String, Sendable {
        case absolute
        case meanOffset = "mean_offset"
        case groundOffset = "ground_offset"
    }

    /// One value for the whole shape under `key`; `value` nil when the tag
    /// is not a number.
    case level(form: Form, key: String, value: Double?)
    /// A sloping rectangle; `valid` false when the way is not a closed
    /// four-corner ring (the build skips it).
    case slope(high: Double?, low: Double?, valid: Bool)

    public static let highKey = "altitude_high"
    public static let lowKey = "altitude_low"

    /// The reader's order; nil = a form the editor does not edit, which
    /// still hides every key after it.
    static let precedence: [(key: String, form: Form?, slope: Bool)] = [
        ("cst_alt_abs", .absolute, false),
        ("cst_alt_rel", .meanOffset, false),
        ("var_alt_rel", .groundOffset, false),
        ("altitude", .absolute, false),
        ("node_altitudes", nil, false),
        (highKey, nil, true),
    ]

    /// Read `tags` (with the way's `refs` for the slope's ring check).
    public init?(tags: [String: String], refs: [Int64] = []) {
        for entry in Self.precedence where tags[entry.key] != nil {
            if entry.slope {
                let valid = refs.count == 5 && refs.first == refs.last
                self = .slope(high: Self.number(tags[Self.highKey]), low: Self.number(tags[Self.lowKey]),
                              valid: valid)
                return
            }
            guard let form = entry.form else { return nil }
            self = .level(form: form, key: entry.key, value: Self.number(tags[entry.key]))
            return
        }
        return nil
    }

    public init?(way: PatchWay) { self.init(tags: way.tags, refs: way.refs) }

    /// Python's `float()` on a tag: surrounding blanks allowed, finite only.
    static func number(_ text: String?) -> Double? {
        guard let t = text?.trimmingCharacters(in: .whitespaces), let v = Double(t), v.isFinite else { return nil }
        return v
    }

    /// A value as the tags carry it: metres, two decimals.
    public static func format(_ value: Double) -> String { String(format: "%.2f", value) }

    /// `tags` with the whole-shape value set under the key the shape uses
    /// (`cst_alt_abs` when it has none).
    public static func levelTags(_ tags: [String: String], value: Double) -> [String: String] {
        var key = "cst_alt_abs"
        if case .level(_, let k, _)? = PatchShapeAltitude(tags: tags) { key = k }
        var out = tags
        out[key] = format(value)
        return out
    }

    /// `tags` with the slope's high and/or low value set; every other tag kept.
    public static func slopeTags(_ tags: [String: String], high: Double?, low: Double?) -> [String: String] {
        var out = tags
        if let high { out[highKey] = format(high) }
        if let low { out[lowKey] = format(low) }
        return out
    }

    public enum Side: String, Sendable { case high, low }

    /// The map label at one end of the arrow: "High 172.4 m" / "Low: mesh".
    public static func label(_ side: Side, _ value: Double?) -> String {
        let word = side == .high ? "High" : "Low"
        return value.map { word + String(format: " %.1f m", $0) } ?? "\(word): mesh"
    }
}

/// The map drawing of a sloping rectangle (owner 2026-11-17 15:58Z): an
/// outlined arrow from the high side to the low side, a label at each end,
/// the high edge drawn thicker. Points are (lat, lon) degrees.
public struct PatchSlopeMarks: Equatable, Sendable {
    public struct LatLon: Equatable, Sendable {
        public let lat: Double
        public let lon: Double
    }

    public let highEdge: [LatLon]
    public let lowEdge: [LatLon]
    /// Seven points, tail to tip and back.
    public let arrow: [LatLon]
    public let highLabel: LatLon
    public let lowLabel: LatLon

    static let arrowFrom = 0.25, arrowTo = 0.75
    static let labelHighAt = 0.10, labelLowAt = 0.90
    static let shaftHalf = 0.12, headHalf = 0.30
    static let headOfArrow = 0.40, headOfWidth = 0.60

    /// From the four corners in ring order (refs[0]…refs[3]); nil when the
    /// two sides coincide. A plane scaled by cos(mean latitude).
    public init?(corners: [LatLon]) {
        guard corners.count == 4 else { return nil }
        let meanLat = corners.reduce(0) { $0 + $1.lat } / 4
        let k = max(cos(meanLat * .pi / 180), 1.0e-6)
        let p = corners.map { (x: $0.lon * k, y: $0.lat) }
        func mid(_ a: (x: Double, y: Double), _ b: (x: Double, y: Double)) -> (x: Double, y: Double) {
            ((a.x + b.x) / 2, (a.y + b.y) / 2)
        }
        func dist(_ a: (x: Double, y: Double), _ b: (x: Double, y: Double)) -> Double { hypot(a.x - b.x, a.y - b.y) }
        let hi = mid(p[3], p[0]), lo = mid(p[1], p[2])
        let length = hypot(lo.x - hi.x, lo.y - hi.y)
        guard length > 0 else { return nil }
        let ux = (lo.x - hi.x) / length, uy = (lo.y - hi.y) / length
        let vx = -uy, vy = ux
        let width = (dist(p[3], p[0]) + dist(p[1], p[2])) / 2
        func ll(_ t: Double, _ s: Double = 0) -> LatLon {
            LatLon(lat: hi.y + uy * t + vy * s, lon: (hi.x + ux * t + vx * s) / k)
        }
        let t0 = Self.arrowFrom * length, t1 = Self.arrowTo * length
        let head = min(Self.headOfArrow * (t1 - t0), Self.headOfWidth * width)
        let base = t1 - head
        let shaft = Self.shaftHalf * width, wing = Self.headHalf * width
        highEdge = [corners[3], corners[0]]
        lowEdge = [corners[1], corners[2]]
        arrow = [ll(t0, shaft), ll(base, shaft), ll(base, wing), ll(t1), ll(base, -wing), ll(base, -shaft),
                 ll(t0, -shaft)]
        highLabel = ll(Self.labelHighAt * length)
        lowLabel = ll(Self.labelLowAt * length)
    }

    /// A sloping rectangle's marks in `doc` (nil unless the way reads as a
    /// valid slope and its corners are all present).
    public init?(way: PatchWay, in doc: PatchDocument) {
        guard case .slope(_, _, true)? = PatchShapeAltitude(way: way) else { return nil }
        let corners = way.refs.prefix(4).compactMap { doc.nodes[$0] }.map { LatLon(lat: $0.lat, lon: $0.lon) }
        self.init(corners: corners)
    }
}

extension PatchDocument {
    /// Change one way's tags (#2137): `put` adds or replaces keys, `remove`
    /// drops them; refs and nodes untouched (`patch_edit.set_way_tags`).
    public mutating func setWayTags(_ wayID: Int64, put: [String: String], remove: [String] = []) throws {
        guard let w = ways.firstIndex(where: { $0.id == wayID }) else { throw PatchEditError.unknownWay(wayID) }
        var tags = ways[w].tags
        for key in remove { tags[key] = nil }
        tags.merge(put) { _, new in new }
        ways[w] = PatchWay(id: wayID, refs: ways[w].refs, tags: tags)
    }
}
