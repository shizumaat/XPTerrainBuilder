import Foundation

/// Airport search by code or name (issue #543, owner RULINGS 2026-10-17c):
/// the Swift half of ONE rule whose Python half (the Qt window's) is
/// `Ortho4XP/src/O4_Airport_Search.py`. Both read
/// `Ortho4XP/tests/fixtures/airport_search_cases.json`.
///
/// Only the airport index's own columns are searched — code, name, city,
/// country — and its size columns break ties; no other dataset. A query
/// matches when every query word starts a word of the airport's text.
/// Tiers, best first: code equals the query; code starts with it (one
/// word); name starts with it; every word starts a name word; every word
/// starts a word of name, city or country. Within a tier the larger
/// airport comes first (`AirportRank`).
public struct AirportSearch: Sendable {
    public static let minQueryLength = 2
    public static let resultLimit = 8

    private struct Row: Sendable {
        let airport: GlobalAirport
        let code: String
        let name: String
        let nameWords: String
        let allWords: String
        let rank: (code: String, sizeClass: Int, runwayMeters: Int)
    }

    private let rows: [Row]

    /// Normalises every airport ONCE; `results` then runs per keystroke.
    public init(_ airports: [GlobalAirport]) {
        rows = airports.map { a in
            let name = Self.normalize(a.name)
            let all = [name, Self.normalize(a.city), Self.normalize(a.country)]
                .filter { !$0.isEmpty }.joined(separator: " ")
            return Row(airport: a, code: Self.normalize(a.icao), name: name,
                       nameWords: " " + name, allWords: " " + all,
                       rank: (a.icao, a.sizeClass ?? AirportRank.unknownSizeClass,
                              a.runwayMeters ?? 0))
        }
    }

    /// Lower case, accents dropped (compatibility decomposition, then every
    /// non-spacing mark removed), anything but a letter or a number a
    /// space, runs of spaces collapsed.
    public static func normalize(_ text: String) -> String {
        var out = String.UnicodeScalarView()
        for scalar in text.lowercased().decomposedStringWithCompatibilityMapping.unicodeScalars {
            switch scalar.properties.generalCategory {
            case .nonspacingMark:
                continue
            case .uppercaseLetter, .lowercaseLetter, .titlecaseLetter, .modifierLetter,
                 .otherLetter, .decimalNumber, .letterNumber, .otherNumber:
                out.append(scalar)
            default:
                out.append(" ")
            }
        }
        return String(out).split(separator: " ").joined(separator: " ")
    }

    /// One result row: `CODE · Name · City, Country` (empty parts left out).
    public static func resultLabel(code: String, name: String, city: String,
                                   country: String) -> String {
        let place = [city, country].map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }.joined(separator: ", ")
        return [code, name.trimmingCharacters(in: .whitespaces), place]
            .filter { !$0.isEmpty }.joined(separator: " · ")
    }

    /// The result list's only row when nothing matches.
    public static func noMatchText(_ query: String) -> String {
        "No airport matches \u{201C}\(query.trimmingCharacters(in: .whitespaces))\u{201D}"
    }

    /// The best `limit` airports for `query`, best first; empty for a query
    /// shorter than `minQueryLength` or one that matches nothing.
    public func results(for query: String, limit: Int = resultLimit) -> [GlobalAirport] {
        let q = Self.normalize(query)
        guard q.unicodeScalars.count >= Self.minQueryLength else { return [] }
        let words = q.split(separator: " ").map(String.init)
        let needles = words.map { " " + $0 }
        var hits: [(tier: Int, row: Row)] = []
        for row in rows {
            if let tier = Self.tier(row, q, words.count, needles) { hits.append((tier, row)) }
        }
        hits.sort { a, b in
            a.tier != b.tier ? a.tier < b.tier : AirportRank.precedes(a.row.rank, b.row.rank)
        }
        return hits.prefix(max(0, limit)).map(\.row.airport)
    }

    private static func tier(_ row: Row, _ q: String, _ wordCount: Int,
                             _ needles: [String]) -> Int? {
        if row.code == q { return 0 }
        if wordCount == 1 && row.code.hasPrefix(q) { return 1 }
        if row.name.hasPrefix(q) { return 2 }
        if needles.allSatisfy({ row.nameWords.contains($0) }) { return 3 }
        if needles.allSatisfy({ row.allWords.contains($0) }) { return 4 }
        return nil
    }
}
