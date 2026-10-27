import Foundation

/// Coordinates typed into the map search field (#1317): the Swift half of
/// `Ortho4XP/src/O4_Coordinate_Query.py`, twinned on
/// `Ortho4XP/tests/fixtures/latlon_search_cases.json`.
///
/// A tile key (`+49+002`, two signed integers run together) wins and
/// selects that tile. Otherwise the text may be a point: decimal degrees
/// with or without a comma, signed; N/S/E/W as prefix or suffix (then lon
/// may come first); degrees-minutes-seconds (`49°00'45.6"N 2°33'29.4"E`,
/// or the same numbers spaced, or typographic marks); degrees and decimal
/// minutes. Out-of-range values, other letters, or a sign together with a
/// hemisphere letter are not a coordinate.
public enum CoordinateQuery: Equatable {
    case tile(lat: Int, lon: Int)
    case point(lat: Double, lon: Double)

    /// The slippy zoom a point search centres at.
    public static let zoomLevel = 19

    public static func parse(_ text: String) -> CoordinateQuery? {
        if let tile = tileKey(text) { return .tile(lat: tile.lat, lon: tile.lon) }
        if let p = point(text) { return .point(lat: p.lat, lon: p.lon) }
        return nil
    }

    /// `(lat, lon)` of a tile key like `+49+002`, or nil.
    public static func tileKey(_ text: String) -> (lat: Int, lon: Int)? {
        let s = Array(text.trimmingCharacters(in: .whitespacesAndNewlines))
        guard let first = s.first, first == "+" || first == "-",
              let split = s.indices.dropFirst().first(where: { s[$0] == "+" || s[$0] == "-" })
        else { return nil }
        let latDigits = s[1..<split], lonDigits = s[(split + 1)...]
        guard (1...2).contains(latDigits.count), (1...3).contains(lonDigits.count),
              (latDigits + lonDigits).allSatisfy(isDigit),
              let lat = Int(String(s[..<split])), let lon = Int(String(s[split...])),
              (-90...89).contains(lat), (-180...179).contains(lon)
        else { return nil }
        return (lat, lon)
    }

    // MARK: - Point grammar (mirrors the Python half step for step)

    private enum Token {
        case num(String, Character?)
        case hemi(Character)
        case comma
    }

    private struct Group {
        var prefix: Character?
        var suffix: Character?
        var nums: [(String, Character?)] = []
    }

    private static let marks: [Character] = ["°", "'", "\""]

    /// Typographic marks folded to the ASCII ones, in the Python order.
    private static let folds: [(String, String)] = [
        ("\u{00BA}", "°"),
        ("\u{2032}", "'"), ("\u{2019}", "'"), ("\u{2018}", "'"), ("\u{00B4}", "'"), ("`", "'"),
        ("\u{2033}", "\""), ("\u{201D}", "\""), ("\u{201C}", "\""), ("''", "\""),
        ("\u{00A0}", " "), ("\u{2009}", " "), ("\u{202F}", " "),
    ]

    private static func isDigit(_ c: Character) -> Bool { c.isASCII && c.isNumber }
    private static func isSpace(_ c: Character) -> Bool { " \t\n\r\u{0B}\u{0C}".contains(c) }

    private static func tokens(_ raw: String) -> [Token]? {
        var text = raw
        for (old, new) in folds { text = text.replacingOccurrences(of: old, with: new) }
        let c = Array(text.uppercased().trimmingCharacters(in: .whitespacesAndNewlines))
        var out: [Token] = []
        var i = 0
        while i < c.count {
            let ch = c[i]
            if isSpace(ch) { i += 1; continue }
            if "NSEW".contains(ch) { out.append(.hemi(ch)); i += 1; continue }
            if ch == "," || ch == ";" { out.append(.comma); i += 1; continue }
            var j = i
            var sign = ""
            if ch == "+" || ch == "-" { sign = String(ch); j += 1 }
            var whole = ""
            while j < c.count, isDigit(c[j]) { whole.append(c[j]); j += 1 }
            var frac: String?
            if j < c.count, c[j] == "." {
                j += 1
                var digits = ""
                while j < c.count, isDigit(c[j]) { digits.append(c[j]); j += 1 }
                frac = digits
            }
            guard !whole.isEmpty || !(frac ?? "").isEmpty else { return nil }
            var number = sign + (whole.isEmpty ? "0" : whole)
            if let frac, !frac.isEmpty { number += "." + frac }
            var k = j
            while k < c.count, isSpace(c[k]) { k += 1 }
            var mark: Character?
            if k < c.count, marks.contains(c[k]) { mark = c[k]; j = k + 1 }
            out.append(.num(number, mark))
            i = j
        }
        return out
    }

    private static func groups(_ tokens: [Token]) -> [Group]? {
        var groups: [Group] = []
        var cur = Group()
        for tok in tokens {
            switch tok {
            case .comma:
                if !cur.nums.isEmpty {
                    groups.append(cur); cur = Group()
                } else if cur.prefix != nil || groups.last?.suffix == nil {
                    return nil  // a comma right after a suffix letter is fine
                }
            case .hemi(let letter):
                if !cur.nums.isEmpty {
                    if cur.prefix != nil {
                        groups.append(cur); cur = Group(prefix: letter)
                    } else {
                        cur.suffix = letter
                        groups.append(cur); cur = Group()
                    }
                } else if cur.prefix != nil {
                    return nil
                } else {
                    cur.prefix = letter
                }
            case .num(let value, let mark):
                if let last = cur.nums.last,
                   value.hasPrefix("+") || value.hasPrefix("-")
                    || mark == marks[0] || last.1 == marks[2] {
                    groups.append(cur); cur = Group()
                }
                cur.nums.append((value, mark))
            }
        }
        if !cur.nums.isEmpty {
            groups.append(cur)
        } else if cur.prefix != nil {
            return nil
        }
        if groups.count == 1 {
            let only = groups[0]
            if [2, 4, 6].contains(only.nums.count), only.nums.allSatisfy({ $0.1 == nil }) {
                let half = only.nums.count / 2
                groups = [Group(prefix: only.prefix, suffix: nil, nums: Array(only.nums[..<half])),
                          Group(prefix: nil, suffix: only.suffix, nums: Array(only.nums[half...]))]
            }
        }
        return groups.count == 2 ? groups : nil
    }

    private enum Axis { case lat, lon }

    private static func value(_ group: Group) -> (degrees: Double, axis: Axis?)? {
        let nums = group.nums
        guard (1...3).contains(nums.count), group.prefix == nil || group.suffix == nil
        else { return nil }
        for (i, num) in nums.enumerated() where num.1 != nil && num.1 != marks[i] {
            return nil
        }
        guard !nums.dropFirst().contains(where: { $0.0.hasPrefix("+") || $0.0.hasPrefix("-") })
        else { return nil }
        let parts = nums.compactMap { Double($0.0) }
        guard parts.count == nums.count else { return nil }
        for i in parts.indices.dropFirst() {
            if parts[i] >= 60 { return nil }
            // Decimal minutes then seconds.
            if i < parts.count - 1, parts[i] != parts[i].rounded(.towardZero) { return nil }
        }
        // Decimal degrees then minutes.
        if parts.count > 1, parts[0] != parts[0].rounded(.towardZero) { return nil }
        var rest = 0.0
        for i in parts.indices.dropFirst() { rest += parts[i] / pow(60, Double(i)) }
        var degrees = abs(parts[0]) + rest
        let hemi = group.prefix ?? group.suffix
        let signed = nums[0].0.hasPrefix("+") || nums[0].0.hasPrefix("-")
        if hemi != nil, signed { return nil }
        if nums[0].0.hasPrefix("-") || hemi == "S" || hemi == "W" { degrees = -degrees }
        let axis: Axis? = switch hemi {
        case "N", "S": .lat
        case "E", "W": .lon
        default: nil
        }
        return (degrees, axis)
    }

    /// `(lat, lon)` in decimal degrees of a typed coordinate, or nil.
    public static func point(_ text: String) -> (lat: Double, lon: Double)? {
        guard let toks = tokens(text), !toks.isEmpty, let halves = groups(toks),
              let first = value(halves[0]), let second = value(halves[1])
        else { return nil }
        var (a, b) = (first.degrees, second.degrees)
        if first.axis == .lon || second.axis == .lat {
            if first.axis == .lat || second.axis == .lon { return nil }
            swap(&a, &b)
        } else if first.axis != nil, first.axis == second.axis {
            return nil
        }
        guard abs(a) <= 90, abs(b) <= 180 else { return nil }
        return (a, b)
    }
}
